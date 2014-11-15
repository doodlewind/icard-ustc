#coding=utf-8
import util.captcha as captcha
import util.parse as parse
import util.hash
import tornado.web as web
from tornado.httpclient import AsyncHTTPClient
from tornado.httpclient import HTTPRequest
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import StaticFileHandler
from futures import ThreadPoolExecutor
from tornado.log import enable_pretty_logging
import motor
import datetime
import json
import operator
import platform

enable_pretty_logging()

static_path = 'site'

executor = ThreadPoolExecutor(5)
dbclient = motor.MotorClient('localhost', 27017)
# database is icard and main collection is record
db = dbclient.icard
client = AsyncHTTPClient()


class LoginHandler(web.RequestHandler):

    @web.asynchronous
    def get(self):
        self.write('200')
        self.finish()

    @web.asynchronous
    @gen.coroutine
    def post(self):
        input_id = self.get_argument('inputId')
        input_password = self.get_argument('inputPassword')

        # visit index to get cookie
        visit_index = HTTPRequest(
            url="http://ecard.ustc.edu.cn",
            method='GET',
            headers={
                'User-Agent': 'Firefox'
            }
        )
        response = yield gen.Task(client.fetch, visit_index)

        # get captcha code with cookie
        cookie = response.headers['Set-Cookie'].split(';')[0]
        get_captcha = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/login/getimgcode",
            user_agent="Firefox",
            headers={
                'Cookie': cookie
            }
        )
        response = yield gen.Task(client.fetch, get_captcha)

        # generate captcha code and try login
        code = captcha.parse(response.body)
        login = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/login/dologin/",
            method='POST',
            headers={
                'Cookie': cookie
            },
            body='username=' + input_id + '&password=' + input_password
                 + '&usertype=1&schoolcode=001&imgcode=' + code
        )
        yield gen.Task(client.fetch, login)

        # test login status
        state_test = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/person/information",
            method='GET',
            headers={
                'Cookie': cookie
            }
        )
        response = yield gen.Task(client.fetch, state_test)

        # return token if success
        if len(response.body) > 8000:
            name = parse.find_name(response.body)
            token = util.hash.generate_token(input_id)

            usr_tmp = yield db.tmp.find_one({
                'ustc_id': input_id
            })
            # for new user, set flag to mark fetch status
            if usr_tmp is None:
                usr_tmp = {
                    'ustc_id': input_id,
                    'fetching_for_new': True
                }
            # do not save password into temp collection
            usr_tmp['cookie'] = cookie
            usr_tmp['token'] = token
            print "usr_tmp", usr_tmp

            yield db.tmp.save(usr_tmp)
            self.write(parse.to_json(dict(token=token, name=name)))
            self.finish()

        else:
            raise web.HTTPError(500)


class OfflineLoginHandler(web.RequestHandler):

    @web.asynchronous
    @gen.coroutine
    def post(self):
        self.write(json.dumps(dict(token='8184241')))
        self.finish()


class DbHandler(web.RequestHandler):

    @web.asynchronous
    @gen.coroutine
    def get(self):

        map_function = """
        function() {
            var dingingExp = /餐厅|美食|食堂|快餐|豆浆|餐饮/;
            var retailExp = /商店|绿光|百货|超市|商行|书店|小吃部/;
            var busExp = /校车/;
            if (this.type == "消费") {
                if (this.location.search(dingingExp) != -1)
                    emit(
                        {'type': '餐饮', 'location': this.location},
                        {'amount': this.amount, 'count': 1}
                        );

                else if (this.location.search(retailExp) != -1)
                    emit(
                        {'type': '购物', 'location': this.location},
                        {'amount': this.amount, 'count': 1}
                        );

                else if (this.location.search(busExp) != -1)
                    emit(
                        {'type': '校车'},
                        {'amount': this.amount, 'count': 1}
                        );

                else emit(
                        {'type': '其它', 'location': this.location},
                        {'amount': this.amount, 'count': 1}
                        );
            }
        }
        """
        reduce_function = """
        function(key, values) {
            var amount = 0, count = 0;
            values.forEach(function(v) {
                amount += v['amount'];
                count += v['count'];
            });
            return {'amount': amount, 'count': count};
        }
        """
        query = {"time": {"$gt": parse.get_days_before(15)}}
        coll = yield db.record.map_reduce(map_function, reduce_function, "testmr", query=query)
        test = coll.find().sort([('value.amount', -1)])

        resp = {"name": u"15天聚类", "children": [
            {"name": u'餐饮',
             "children": [  # {"name": "somewhere", "size": 999}
             ]},
            {"name": u'购物',
             "children": []},
            {"name": u'其它',
             "children": []}
        ]}
        while (yield test.fetch_next):
            tmp = test.next_object()
            if tmp['_id']['type'] == u'餐饮':
                resp["children"][0]["children"].append({"name": tmp['_id']['location'], "size": int(tmp['value']['amount'])})

            elif tmp['_id']['type'] == u'购物':
                resp["children"][1]["children"].append({"name": tmp['_id']['location'], "size": int(tmp['value']['amount'])})

            elif tmp['_id']['type'] == u'其它':
                resp["children"][2]["children"].append({"name": tmp['_id']['location'], "size": int(tmp['value']['amount'])})

        # print repr(resp).decode("unicode-escape")
        self.write(resp)
        self.finish()


class StatHandler(web.RequestHandler):

    @web.asynchronous
    @gen.coroutine
    def post(self):
        self.ustc_id = self.get_argument('id')
        token = self.get_argument('token')
        days = int(self.get_argument('days'))
        true_token = str(util.hash.generate_token(self.ustc_id))

        if not true_token == token:
            raise web.HTTPError(500)

        print "request id: %s, token: %s, for Stat" % (self.ustc_id, token)

        if days == 10:
            yield gen.Task(self.recent_data)

        elif days == 60:
            yield gen.Task(self.count_daily_sum)

    @gen.coroutine
    def recent_data(self):
        cursor = db.record.find(
            spec={
                'ustc_id': self.ustc_id,
                'type': u'消费',
                'amount': {'$gt': 0},
                'time': {'$gt': parse.get_days_before(10)}
            },
            fields={
                'time': True,
                'amount': True,
            })
        cursor.sort([('time', -1)])
        resp = []
        for document in (yield cursor.to_list(length=int(200))):
            resp.append(document)

        json_data = parse.to_json(resp, escape_time=True)
        self.write(json_data)
        self.finish()
        raise gen.Return()

    @gen.coroutine
    def count_daily_sum(self):
        # get month sum via aggregate

        pipeline = [
            {'$match': {
                '$and': [
                    {'ustc_id': self.ustc_id},
                    {'type': "消费"},
                    {'time': {'$gt': parse.get_days_before(60)}},
                ]}},
            {'$group': {
                '_id': {'$dayOfYear': "$time"},
                'amount': {'$sum': "$amount"},
                'time': {'$last': '$time'},
                'ustc_id': {'$last': '$ustc_id'}
            }}
        ]
        resp = [{'key': u'消费金额', 'color': "#54B59A", 'values':[]}]
        tmp = []
        cursor = yield db.record.aggregate(pipeline, cursor={})
        while (yield cursor.fetch_next):
            item = cursor.next_object()
            tmp.append([int(item['time'].strftime('%s')) * 1000, item['amount']])

        tmp.sort(key=operator.itemgetter(0))
        resp[0]['values'] = tmp
        self.write(parse.to_json(resp))
        self.finish()
        raise gen.Return()


class BriefHandler(web.RequestHandler):
    # this week
    # this month
    # last month
    # index

    @web.asynchronous
    @gen.coroutine
    def post(self):
        ustc_id = self.get_argument('id')
        token = self.get_argument('token')
        true_token = str(util.hash.generate_token(ustc_id))

        if not true_token == token:
            raise web.HTTPError(500)

        print "request id: %s, token: %s, for Brief" % (ustc_id, token)

        # find sum of this week
        cursor = db.record.find(
            spec={
                'ustc_id': ustc_id,
                'type': u'消费',
                'amount': {'$gt': 0},
                'time': {'$gt': parse.start_of_this_week()}
            },
            fields={
                'amount': True,
            }
        )
        cursor.sort([('time', -1)])
        sum_of_week = 0
        while (yield cursor.fetch_next):
            sum_of_week += cursor.next_object()['amount']


        monthly = []
        cursor = db.monthly.find({'ustc_id': ustc_id}).sort([('time', -1)])
        for document in (yield cursor.to_list(length=int(2))):
            monthly.append(document)

        # count rate by sum of last month
        usr = yield db.tmp.find_one({'ustc_id': ustc_id})
        usr['weekly'] = monthly[1]
        yield db.tmp.save(usr)
        base = yield db.tmp.count()
        me = yield db.tmp.find({'weekly': {'$gte': monthly[1]}}).count()
        # the richer, the less rate
        rate = int((float(me) / float(base)) * 100)

        # cursor = yield db.monthly.find({'time': {
        #     '$gt': parse.get_days_before(30),
        #     '$lt': parse.get_last_day()}})
        # print cursor.count()

        # newest record
        cursor = db.record.find({'ustc_id': ustc_id}).sort([('time', -1)])
        for document in (yield cursor.to_list(length=int(1))):
            delta = (datetime.datetime.now() - document['time']).days

        resp = {
            'this_week': sum_of_week,
            'this_month': monthly[0]['total'],
            'last_month': monthly[1]['total'],
            'delta': delta,
            'rate': rate
        }

        self.write(parse.to_json(resp))
        self.finish()


class DetailHandler(web.RequestHandler):

    @gen.coroutine
    def post(self):
        # when this request is received, user id has been saved in login process

        # token validation
        self.ustc_id = self.get_argument('id')
        token = self.get_argument('token')
        time = parse.str_to_datetime(self.get_argument('time'))
        rows = self.get_argument('rows')
        mode = self.get_argument('mode')

        true_token = str(util.hash.generate_token(self.ustc_id))
        if not true_token == token:
            raise web.HTTPError(500)

        print "request id: %s, token: %s, time: %s, rows: %s, mode: %s for Detail" % (self.ustc_id, token, time, rows, mode)

        resp_data = []

        if mode == 'newer':
            operator = '$gt'
        else:
            operator = '$lt'

        cursor = db.record.find({
            'ustc_id': self.ustc_id,
            'time': {operator: time}
        })
        cursor.sort([('time', -1)])
        for document in (yield cursor.to_list(length=int(rows))):
            resp_data.append(document)

        json_data = parse.to_json(resp_data, escape_time=True)
        self.write(json_data)
        self.finish()


class OfflineDetailHandler(web.RequestHandler):
    
    @gen.coroutine
    def post(self):
        ustc_id = self.get_argument('id')
        print 'ustc-id', ustc_id

        # all_data = []
        # cursor = yield db.record.find_one({'ustc_id': ustc_id})
        # for document in (yield cursor.to_list(length=2000)):
        #     all_data.append(document)
        # print len(all_data)
        # print all_data
        # data = parse.to_json(all_data, escape_time=True)

        yield gen.Task(self.foo)
        print "bar"
        self.write('')
        self.finish()

    @gen.coroutine
    def foo(self):
        print "foo"
        raise gen.Return()


class OfflineWaitHandler(web.RequestHandler):

    @gen.coroutine
    def post(self):
        ustc_id = self.get_argument('id')
        print 'ustc-id', ustc_id
        yield gen.Task(self.foo)
        self.write(parse.to_json(dict(time="2014-10-20", end=False)))
        self.finish()

    @gen.coroutine
    def foo(self):
        print "foo"
        raise gen.Return()


class WaitHandler(web.RequestHandler):

    @gen.coroutine
    def post(self):
        self.ustc_id = self.get_argument('id')
        self.token = self.get_argument('token')
        self.time = self.get_argument('time')
        self.usr = yield db.tmp.find_one({'ustc_id': self.ustc_id})

        if self.usr is None:
            raise web.HTTPError(403)

        if str(self.usr['token']) != self.token:
            print 'not done'

        if self.usr['fetching_for_new'] is True:
            yield gen.Task(self.fetch_record, self.time)
            yield gen.Task(self.calculate)


        # for old user, the fetch_for_new flag is false
        else:
            yield gen.Task(self.update)
            self.write(parse.to_json({'end': True}))

    @gen.coroutine
    def update(self):
        cookie = self.usr['cookie']
        per_page = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/index/per_page",
            method='POST',
            headers={
                'User-Agent': 'Firefox',
                'Cookie': cookie
            },
            body='per_page=50'
        )
        yield gen.Task(client.fetch, per_page)

        cursor = db.record.find(
            spec={
                'ustc_id': self.ustc_id,
            },
            fields={
                'time': True,
                'amount': True,
            }
        )
        cursor.sort([('time', -1)])

        start_time = ''
        end_time = parse.datetime_to_str(datetime.datetime.now())
        for document in (yield cursor.to_list(length=int(1))):
            start_time = parse.datetime_to_str(document['time'])
            print start_time

        deal = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/person/deal",
            method='POST',
            headers={
                'User-Agent': 'Firefox',
                'Cookie': cookie
            },
            body='start_date=' + start_time + '&type=&end_date=' + end_time + '&place='
        )
        response_data = yield gen.Task(client.fetch, deal)
        record = parse.Parser(self.ustc_id, response_data.body).read()

        if record is not None:
            for r in record:
                test = yield db.record.find_one({'time': r['time']})

                # if no record in db.record, save a new one
                if test is None:
                    future = db.record.save(r)
                    # print 'saved'
                    result = yield future

                    # if new record saved, update the monthly collection
                    tmp = yield db.monthly.find_one({
                        'ustc_id': self.ustc_id,
                        'time': {'$gt': parse.start_of_this_month()}})

                    if tmp is None:
                        yield db.monthly.insert({'ustc_id': self.ustc_id, 'time': r['time'], 'total': 0})
                        # print 'tmp is None, done insert'
                    else:
                        tmp['total'] += r['amount']
                        yield db.monthly.save(tmp)
                        # print 'tmp is not None, add to monthly record'

                else:
                    pass
                    # print 'not None, skip saving'

            count = parse.get_record_count(response_data.body)
            if count > 50:
                for i in range(50, count, 50):
                    print 'get', i, 'start', start_time, 'end', end_time
                    get = HTTPRequest(
                        url="http://ecard.ustc.edu.cn/sisms/index.php/person/deal/" + str(i),
                        method='GET',
                        headers={
                            'User-Agent': 'Firefox',
                            'Cookie': cookie
                        }
                    )
                    response_data = yield gen.Task(client.fetch, get)
                    record = parse.Parser(self.ustc_id, response_data.body).read()
                    for r in record:
                        test = yield db.record.find_one({'time': r['time']})
                        if test is None:
                            future = db.record.save(r)
                            print 'saved'
                            result = yield future
                        else:
                            print 'not None, skip saving'

        raise gen.Return()

    @gen.coroutine
    def fetch_record(self, time):
        print "fetch_record"
        start_time = time
        end_time = parse.get_last_day(time)
        cookie = self.usr['cookie']

        per_page = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/index/per_page",
            method='POST',
            headers={
                'User-Agent': 'Firefox',
                'Cookie': cookie
            },
            body='per_page=50'
        )
        yield gen.Task(client.fetch, per_page)

        deal = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/person/deal",
            method='POST',
            headers={
                'User-Agent': 'Firefox',
                'Cookie': cookie
            },
            body='start_date=' + start_time + '&type=&end_date=' + end_time + '&place='
        )
        response_data = yield gen.Task(client.fetch, deal)
        record = parse.Parser(self.ustc_id, response_data.body).read()

        if record is not None:
            for r in record:
                future = db.record.save(r)
                result = yield future

            count = parse.get_record_count(response_data.body)
            if count > 50:
                for i in range(50, count, 50):
                    print 'get', i, 'start', start_time, 'end', end_time
                    get = HTTPRequest(
                        url="http://ecard.ustc.edu.cn/sisms/index.php/person/deal/" + str(i),
                        method='GET',
                        headers={
                            'User-Agent': 'Firefox',
                            'Cookie': cookie
                        }
                    )
                    response_data = yield gen.Task(client.fetch, get)
                    record = parse.Parser(self.ustc_id, response_data.body).read()
                    for r in record:
                        future = db.record.insert(r)
                        result = yield future

            # end fetching and saving, write response to client
            cursor = db.record.find({
                'ustc_id': self.ustc_id,
                "type": u"消费",
                "amount": {"$gt": 0}
            })
            cursor.sort([('time', -1)]).limit(1)
            while (yield cursor.fetch_next):
                tmp = cursor.next_object()
            # plus a day for next query
            resp = {
                'end': False,
                'time': tmp['time'].strftime('%Y-%m-%d'),
                'amount': tmp['amount'],
                'location': tmp['location']
            }

            if parse.plus_one_day(tmp['time']) == parse.plus_one_day(datetime.datetime.now()):
                self.usr['fetching_for_new'] = False
                resp['end'] = True
                yield db.tmp.save(self.usr)

            self.write(resp)
            self.finish()
            raise gen.Return()

        # for case that no record in a month, maybe start of month
        # if request date is larger than current date, stop fetching by return a True end flag
        elif parse.str_to_datetime(time + ' 00:00:00').month >= datetime.datetime.now().month:
            resp = {
                'end': True,
                'time': time,
                'amount': 0,
                'location': 'empty'
            }
            self.write(resp)
            self.finish()
            raise gen.Return()

        else:
            resp = {
                'end': False,
                'time': parse.plus_one_day(datetime.datetime.strptime(end_time, '%Y-%m-%d')),
                'amount': 0,
                'location': 'empty'
            }
            self.write(resp)
            self.finish()
            raise gen.Return()

    @gen.coroutine
    def calculate(self):
        # get month sum via aggregate
        pipeline = [
            {'$match': {
                '$and': [
                    {'ustc_id': self.ustc_id},
                    {'type': "消费"},
                ]}},
            {'$group': {
                '_id': {'$month': "$time"},
                'amount': {'$sum': "$amount"},
                'time': {'$last': '$time'},
                'ustc_id': {'$last': '$ustc_id'}
            }}
        ]
        cursor = yield db.record.aggregate(pipeline, cursor={})
        while (yield cursor.fetch_next):
            item = cursor.next_object()
            del(item['_id'])
            db.monthly.update(
                {
                    'ustc_id': self.ustc_id,
                    'time': item['time']
                },
                {
                    '$set': {
                        'ustc_id': item['ustc_id'],
                        'time': item['time'],
                        'total': item['amount']
                    }
                }, upsert=True
            )

        raise gen.Return()


class PieHandler(web.RequestHandler):

    @gen.coroutine
    def post(self):
        ustc_id = self.get_argument('id')
        token = self.get_argument('token')
        true_token = str(util.hash.generate_token(ustc_id))

        if not true_token == token:
            raise web.HTTPError(500)

        print "request id: %s, token: %s for Pie" % (ustc_id, token)


        map_function = """
        function() {
            var dingingExp = /餐厅|美食|食堂|快餐|豆浆|餐饮/;
            var retailExp = /商店|绿光|百货|超市|商行|书店|小吃部/;
            var busExp = /校车/;
            if (this.type == "消费") {
                if (this.location.search(dingingExp) != -1)
                    emit(
                        {'type': '餐饮', 'location': this.location},
                        {'amount': this.amount, 'count': 1}
                        );

                else if (this.location.search(retailExp) != -1)
                    emit(
                        {'type': '购物', 'location': this.location},
                        {'amount': this.amount, 'count': 1}
                        );

                else if (this.location.search(busExp) != -1)
                    emit(
                        {'type': '校车'},
                        {'amount': this.amount, 'count': 1}
                        );

                else emit(
                        {'type': '其它', 'location': this.location},
                        {'amount': this.amount, 'count': 1}
                        );
            }
        }
        """
        reduce_function = """
        function(key, values) {
            var amount = 0, count = 0;
            values.forEach(function(v) {
                amount += v['amount'];
                count += v['count'];
            });
            return {'amount': amount, 'count': count};
        }
        """
        query = {"time": {"$gt": parse.get_days_before(15)}, "ustc_id": ustc_id}
        coll = yield db.record.map_reduce(map_function, reduce_function, "testmr", query=query)
        test = coll.find().sort([('value.amount', -1)])

        resp = {"name": u"15天聚类", 'color': "#2E3E4F", "children": [
            {"name": u'餐饮', 'color': "#54B59A",  # green
             "children": [  # {"name": "somewhere", "size": 999}
             ]},
            {"name": u'购物', 'color': "#489AD8",  # blue
             "children": []},
            {"name": u'其它', 'color': "#EA9F33",  # yellow
             "children": []}
        ]}
        while (yield test.fetch_next):
            tmp = test.next_object()
            if tmp['_id']['type'] == u'餐饮':
                resp["children"][0]["children"].append({
                    "name": tmp['_id']['location'],
                    "size": int(tmp['value']['amount']),
                    "color": "#89BFAF"
                })

            elif tmp['_id']['type'] == u'购物':
                resp["children"][1]["children"].append({
                    "name": tmp['_id']['location'],
                    "size": int(tmp['value']['amount']),
                    "color": "#7BB0DB"
                })

            elif tmp['_id']['type'] == u'其它':
                resp["children"][2]["children"].append({
                    "name": tmp['_id']['location'],
                    "size": int(tmp['value']['amount']),
                    "color": "#E5B36A"
                })

        self.write(resp)
        self.finish()


def make_app():
    return web.Application([
        (r"/stat", StatHandler),
        (r"/wait", WaitHandler),
        (r"/brief", BriefHandler),
        (r"/detail", DetailHandler),
        (r"/login", LoginHandler),
        # (r"/wait", OfflineWaitHandler),
        # (r"/detail", OfflineDetailHandler),
        # (r"/login", OfflineLoginHandler),
        (r"/pie", PieHandler),
        (r"/db", DbHandler),
        (r"/", web.RedirectHandler, {'url': 'index.html'}),
        (r"/(.*)", StaticFileHandler, {'path': static_path}),
    ], db=db)


if __name__ == "__main__":
    # port 8888 for test case on OS X
    if platform.system() == 'Darwin':
        port = 8888
    else:
        port = 80

    app = make_app()
    app.listen(port)
    IOLoop.instance().start()