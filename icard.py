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
import sys

enable_pretty_logging()

executor = ThreadPoolExecutor(5)

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

        yield db.log.insert({
            'ustc_id': input_id,
            'time': datetime.datetime.now()
        })

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
        if response.body is not None and len(response.body) > 8000:
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
            # print "usr_tmp", usr_tmp

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

        # print "%s req Stat" % (self.ustc_id)

        if days == 10:
            yield gen.Task(self.recent_data)

        elif days == 60:
            yield gen.Task(self.count_daily_sum)

        elif days == 360:
            yield gen.Task(self.monthly_sum)

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

    @gen.coroutine
    def monthly_sum(self):
        cursor = db.monthly.find({
            "ustc_id": self.ustc_id
        }).sort([('time', 1)])
        resp = [{'key': u'消费金额', 'color': "#EA9F33", 'values':[]}]
        tmp = []
        while (yield cursor.fetch_next):
            item = cursor.next_object()
            tmp.append({'x': int(item['time'].strftime('%s')) * 1000, 'y': item['total']})

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

        # print "%s req Brief" % (ustc_id)

        # find sum of this week
        weekly_sum = 0
        start_of_this_week = parse.start_of_this_week()
        weekly_cursor = db.record.find(
            spec={
                'ustc_id': ustc_id,
                'type': u'消费',
                'amount': {'$gt': 0},
                'time': {'$gte': start_of_this_week}
            },
            fields={
                'amount': True,
            }
        ).sort([('time', -1)])
        while (yield weekly_cursor.fetch_next):
            weekly_sum += weekly_cursor.next_object()['amount']
        # print "weekly sum", weekly_sum

        # find sum of last month
        last_month_cursor = yield db.monthly.find_one({
            'ustc_id': ustc_id,
            'time': {
                '$lt': parse.start_of_this_month(),
                '$gte': parse.start_of_last_month()
            }
        })
        if last_month_cursor is not None and last_month_cursor['total'] is not None:
            last_month_sum = last_month_cursor['total']
        else:
            last_month_sum = 0
        # print "last month sum", last_month_sum

        # find sum of this month
        this_month_sum = 0
        this_month_cursor = yield db.monthly.find_one({
            'ustc_id': ustc_id,
            'time': {
                '$gte': parse.start_of_this_month()
            }
        })
        if this_month_cursor is not None:
            this_month_sum = this_month_cursor['total']
        else:
            this_month_sum = 0
        print "this month sum", this_month_sum

        # find rank by last month sum
        usr = yield db.tmp.find_one({'ustc_id': ustc_id})
        yield db.tmp.save(usr)
        base_rank = yield db.monthly.find({
            'time': {
                '$lt': parse.start_of_this_month(),
                '$gte': parse.start_of_last_month()
            }
        }).count()
        print base_rank

        me_rank = yield db.monthly.find({
            'total': {'$gte': last_month_sum},
            'time': {
                '$lt': parse.start_of_this_month(),
                '$gte': parse.start_of_last_month()
            }
        }).count()

        # the richer, the less rate
        rate = int((float(me_rank) / float(base_rank)) * 100)

        resp = {
            'this_week': weekly_sum,
            'this_month': this_month_sum,
            'last_month': last_month_sum,
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

        # print "%s req Detail" % (self.ustc_id)

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

        # for old user, the fetching_for_new flag is false
        else:
            yield gen.Task(self.update)
            yield gen.Task(self.calculate)
            self.write(parse.to_json({'end': True}))

    @gen.coroutine
    def update(self):

        # hot fix on repeat monthly records
        yield db.monthly.remove({'ustc_id': self.ustc_id})

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

        deal = HTTPRequest(
            url="http://ecard.ustc.edu.cn/sisms/index.php/person/deal",
            method='POST',
            headers={
                'User-Agent': 'Firefox',
                'Cookie': cookie
            },
            # body='start_date=' + '2014-12-02' + '&type=&end_date=' + '2014-12-02' + '&place='
            body='start_date=' + start_time + '&type=&end_date=' + end_time + '&place='
        )
        response_data = yield gen.Task(client.fetch, deal)
        record = parse.Parser(self.ustc_id, response_data.body).read()

        if record is not None:
            for r in record:
                test = yield db.record.find_one({'time': r['time']})
                # only if no record in db.record, save a new one
                if test is None:
                    yield db.record.save(r)

            count = parse.get_record_count(response_data.body)
            if count > 50:
                for i in range(50, count, 50):
                    print self.ustc_id, 'get', i, 'start', start_time, 'end', end_time
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
                        # only if no record in db.record, save a new one
                        if test is None:
                            yield db.record.save(r)

        raise gen.Return()

    @gen.coroutine
    def fetch_record(self, time):
        # print "fetch_record"
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
                yield db.record.save(r)
                # future = db.record.save(r)
                # result = yield future

            count = parse.get_record_count(response_data.body)
            if count > 50:
                for i in range(50, count, 50):
                    print self.ustc_id, 'get', i, 'start', start_time, 'end', end_time
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
                        yield db.record.insert(r)
                        # future = db.record.insert(r)
                        # result = yield future

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
            # tmp is currently newest record
            resp = {
                'end': False,
                'time': tmp['time'].strftime('%Y-%m-%d'),
                'amount': tmp['amount'],
                'location': tmp['location']
            }

            # set flag to False if month of request has reached current month
            if parse.str_to_datetime(time + ' 00:00:00').month == parse.get_days_before(0).month:
            # if tmp['time'].month == datetime.datetime.now().month:
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
                'time': {'$first': '$time'},
                'ustc_id': {'$first': '$ustc_id'}
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

        # print "%s req Pie" % (ustc_id)

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


def make_app(static_path):
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
        # static file handler remain for debug
        (r"/", web.RedirectHandler, {'url': 'index.html'}),
        (r"/(.*)", StaticFileHandler, {'path': static_path}),
    ], db=db)


if __name__ == "__main__":

    if platform.system() == 'Darwin':
        static_path = '/Users/ewind/code/python/icard/site'
    else:
        static_path = '/root/icard-ustc/site'

    if len(sys.argv) > 1:
        ip = '10.10.13.26'
        port = int(sys.argv[1])
        if port == 0:
            exit(1)
    else:
        port = 8888
        ip = '127.0.0.1'

    dbclient = motor.MotorClient(ip, 27017)
    # database is icard and main collection is record
    db = dbclient.icard

    app = make_app(static_path)
    app.listen(port)
    IOLoop.instance().start()
