# coding=utf-8
from bs4 import BeautifulSoup
from datetime import datetime
from datetime import timedelta
from datetime import date
import hash
import json

__doc__ = """when pass in data, must go with a ustc_id"""


def to_json(record, escape_time=False):
    if not escape_time:
        pass
    else:
        if isinstance(record, list):
            for r in record:
                # print 'r', r
                r['time'] = r['time'].strftime('%Y-%m-%d %H:%M:%S')
                if '_id' in r:
                    del r['_id']
        else:
            # print 'record', record
            record['time'] = record['time'].strftime('%Y-%m-%d %H:%M:%S')
            if '_id' in record:
                del record['_id']
    return json.dumps(record)


def find_name(html):
    start = html.find('lue">')
    end = html.find('<td width="99')
    return html[start + 5: end - 21].replace('<', '').replace('>', '')


def str_to_datetime(item):
    assert isinstance(item, str) or isinstance(item, unicode)
    return datetime.strptime(item, '%Y-%m-%d %H:%M:%S')


def datetime_to_str(item):
    assert isinstance(item, datetime)
    return item.strftime('%Y-%m-%d')


def plus_one_day(date):
    date = date.strftime('%Y-%m-%d')
    month = int(date[5: 7]) % 12 + 1

    if month > 9:
        date = '%s%s-01' % (date[0:5], str(month))
    else:
        date = '%s0%s-01' % (date[0:5], str(month))

    return date


def get_date():
    date_list = [
        # '2013-09-01', '2013-09-30',
        # '2013-10-01', '2013-10-31',
        # '2013-11-01', '2013-11-30',
        # '2013-12-01', '2013-12-31',
        # '2014-01-01', '2014-01-31',
        # '2014-02-01', '2014-02-28',
        # '2014-03-01', '2014-03-31',
        # '2014-04-01', '2014-04-30',
        '2014-05-01', '2014-05-31',
        '2014-06-01', '2014-06-30',
        '2014-07-01', '2014-07-31',
        '2014-08-01', '2014-08-31',
        '2014-09-01', '2014-09-30',
        '2014-10-01', datetime.now().strftime('%Y-%m-%d')
    ]
    return date_list


def get_last_day(date):
    month = int(date[5: 7]) % 12 + 1

    if month > 9:
        end_date = '%s%s%s' % (date[0:5], str(month), date[7:10])
    else:
        end_date = '%s0%s%s' % (date[0:5], str(month), date[7:10])

    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    delta = timedelta(days=1)
    now = datetime.now()
    if end_date - delta > now:
        return now.strftime('%Y-%m-%d')
    else:
        return (end_date - delta).strftime('%Y-%m-%d')


def start_of_this_month():
    now = datetime.today()
    return datetime.strptime(now.strftime('%Y-%m-01 00:00:00'), '%Y-%m-%d %H:%M:%S')


def get_days_before(count):
    now = datetime.now()
    delta = timedelta(days=count)
    return datetime.strptime((now - delta).strftime('%Y-%m-%d 00:00:00'), '%Y-%m-%d %H:%M:%S')


'''
# old interface
def get_date(type):
    year = int(datetime.now().strftime('%Y'))
    month = int(datetime.now().strftime('%m'))
    date = int(datetime.now().strftime('%d'))

    if type == 'start':
        start_month = (month - 3) % 12 + 1
        if start_month > month:
            start_year = year - 1
        else:
            start_year = year
        return '%s-%s-01' % (start_year, start_month)

    elif type == 'end':
        return '%s-%s-%s' % (year, month, date)
'''


def start_of_this_week():
    now = datetime.today()
    # return now - delta
    delta = timedelta(days=date.today().weekday())
    return now - delta


def get_record_count(html):
    if isinstance(html, str):
        html = html.decode('utf-8')
    pointer = html.find(u'条记录')
    count = ''
    for char in html[pointer - 5:pointer]:
        if char == '1' or char == '2' or char == '3' or char == '4' or char == '5' \
                or char == '6' or char == '7' or char == '8' or char == '9' or char == '0':
            count += char
    return int(count)


class Parser():
    def __init__(self, ustc_id=None, data=None):
        self.ustc_id = ustc_id
        if data:
            self.data = data.replace('&nbsp;', '')
        self.type = None
        self.grade = None
        self.school = None
        self.hash = None

    def parse_id(self):
        # not used
        self.type = self.ustc_id[0:2]
        self.grade = self.ustc_id[2:4]
        self.school = self.ustc_id[4:7]
        self.hash = hash.calculate(self.ustc_id[7:10])
        user = {
            'type': self.type,
            'grade': self.grade,
            'school': self.school,
            'hash': self.hash
        }
        return user

    def read(self):
        # save ustc_id directly into collection
        # user = self.parse_id()
        soup = BeautifulSoup(self.data)
        table = soup.find('tbody', 'stripe').find_all('td')
        data = []
        if len(table) < 6:
            return


        for i in range(0, len(table), 6):
            record = {
                'ustc_id': self.ustc_id,
                # 'time': table[i+1].string,
                'time': datetime.strptime(table[i + 1].string, '%Y-%m-%d %H:%M:%S'),
                'location': self.filter_word(table[i + 2].string),
                'type': table[i + 3].string,
                'amount': float(table[i + 4].string),
                'balance': float(table[i + 5].string)
            }
            data.append(record)
        return data

    def read_page(self):
        record = self.read()

        # convert datetime to str
        for r in record:
            r['time'] = r['time'].strftime('%Y-%m-%d %H:%M:%S')
        return json.dumps(record)

    def filter_word(self, text):
        text = text.replace(u'\\', '.')
        words = [
            [u'中国科学技术大学(全校).', ''],
            [u'中国科大后勤集团饮食中心.', ''],
            [u'中国科学技术大学.', ''],
            [u'中快餐饮.东区', u'东区'],
            [u'劳服公司(中科商店050901).', ''],
            [u'中国科大后勤集团总务中心.', ''],
            [u'矽谷快餐(天辉).矽谷', u'西区.矽谷快餐'],
            [u'办公室.教三', u'西区.办公室.教三复印室'],
            [u'队.巴士组', ''],
            [u'绿光', u'西区.绿光'],
            [u'合肥开心英语书店', u'东区.开心英语书店'],
            # [u'合肥', ''],
            # [u'合肥市', ''],
            # [u'合肥市包河区', ''],
            # [u'合肥市蜀山区', ''],
            # [u'合肥市瑶海区', '']
        ]
        for word in words:
            text = text.replace(word[0], word[1])
        return text

if __name__ == '__main__':
    data = open('test.html').read().decode('utf-8')
    p = Parser(ustc_id='PB12203251', data=data)
    # print p.read_page().decode('unicode-escape')
    q = Parser(ustc_id='PB12203251')
    p.parse_id()

    # print 'str_to_datetime', str_to_datetime('2014-10-17 15:03:00')
    # test_time = datetime.now()
    # print 'datetime_to_str', datetime_to_str(test_time)
    # print 'get_record_count', get_record_count(open('test.html').read())
    # # print 'get current date', get_date()
    # print 'last day of 2014-10', get_last_day('2014-10-01')
    # print 'plus one day from now', plus_one_day(datetime.now())
    # print '10 days before now', get_days_before(10)
    # print 'start of this week', start_of_this_week()
    # print 'start of this month', start_of_this_month()
    #
    # print datetime.now().month
