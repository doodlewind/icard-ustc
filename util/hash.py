import hashlib


def calculate(code):
    return int(hashlib.sha1(str(code)).hexdigest(), 16) % 10000000


def generate_token(ustc_id):
    feature = ustc_id[-3:]
    return calculate(feature)

if __name__ == '__main__':
    a = generate_token("PB12203251")
    print a
    print hashlib.sha1('798110090727').hexdigest()
    data = "{'amount': u'3.00', 'location': u'\u4e2d\u56fd\u79d1\u5b66\u6280\u672f\u5927\u5b66(\u5168\u6821).\u52b3\u670d\u516c\u53f8(\u4e2d\u79d1\u5546\u5e97050901).\u897f\u533a\u767e\u8d27.\u8d85\u5e02#1', 'time': u'2014-09-24 09:38:10', 'balance': u'43.02', 'type': u'\u6d88\u8d39', 'id': 8184241L, 'user': {'grade': '12', 'hash': 8184241L, 'school': '203', 'type': 'PB'}}"
