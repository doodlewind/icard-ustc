import mechanize
import logging
import thread
import time
import random

logging.basicConfig(
    level=logging.DEBUG,
    format='(%(threadName)-10s) %(message)s',
)


def visit():
    start_time = time.time()
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.open('http://127.0.0.1:8888')
    elapsed_time = time.time() - start_time
    logging.warning('%s seconds for request' % elapsed_time)


for i in range(0, 1000):
    thread.start_new_thread(visit, ())
    '''
    time.sleep(random.randint(0, 2))
    for j in range(0, random.randint(0, 3)):
        thread.start_new_thread(visit, ())
    '''


time.sleep(10000000)
