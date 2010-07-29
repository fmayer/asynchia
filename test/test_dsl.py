from nose.tools import eq_, assert_raises

import asynchia.ee

from asynchia.dsl import b, SBLFLSE

import itertools
import inspect

def exhaust(itr):
    result = []
    for elem in itr:
        if inspect.isgenerator(elem):
            result.append(exhaust(iter(elem)))
        else:
            result.append(elem)
    return result


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


def test_nested():
    i = [2, 'AB', [5, 'ABCDE']]
    
    a = b.B + SBLFLSE(0)
    c = b.B + SBLFLSE(0) + a
    
    d = c.produce((2, 'AB', (5, 'ABCDE')))
    
    p = c(None)
    
    m = asynchia.ee.MockHandler(inbuf=d + 'FG')
    until_done(lambda: p.add_data(m, 120))
    
    eq_(exhaust(iter(p.value)), i)
