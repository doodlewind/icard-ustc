'''
import motor

client = motor.MotorClient('localhost', 27017)
db = client.test_database
card = db.card
result = card.find_one({'type': 'fuck'})
print result
'''
if __name__ == '__main__':
    for i in range(2, 96):
        print '#attach pic %i.jpg' % i
