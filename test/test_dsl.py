from nose.tools import eq_, assert_raises

import asynchia.ee

from asynchia.dsl import b, SBLFLSE

def until_done(fun):
    while True:
        d, s = fun()
        if d:
            break


def test_example():
    e = b.L + b.B + SBLFLSE(0)
    a = e(None)
    m = asynchia.ee.MockHandler(inbuf=e.produce((5, 1, 'ABCDE')) + 'FG')
    until_done(lambda: a.add_data(m, 120))
    
    eq_(tuple(a.value), (5, 1, 'ABCDE'))
