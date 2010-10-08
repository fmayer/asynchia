# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2010 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import itertools
import inspect
import struct

import unittest

import asynchia.ee
import asynchia.dsl

from asynchia.util import b
from asynchia.dsl import LFLSE, lookback, FLSE
from asynchia.dsl import s as db

StringInput = None

try:
    from inspect import isgenerator
except ImportError:
    from types import GeneratorType
    def isgenerator(obj):
        return isinstance(obj, GeneratorType)


def exhaust(itr):
    result = []
    for elem in itr:
        if isgenerator(elem):
            result.append(exhaust(iter(elem)))
        else:
            result.append(elem)
    return result


def until_done(fun):
    while True:
        d, s = fun()
        if d:
            break
    

class TestDSL(unittest.TestCase):
    def setUp(self):
        global StringInput
        StringInput = asynchia.ee.StringInput 
        asynchia.ee.StringInput = lambda x: x
    
    def tearDown(self):
        asynchia.ee.StringInput = StringInput
    
    def test_expradd(self):
        o1, o2, o3 = db.L(), db.L(), db.L()
        a = o1 + o2
        b = a + o3
        self.assertEqual(a.exprs, [o1, o2])
        self.assertEqual(b.exprs, [o1, o2, o3])
    
    def test_LFLSE(self):
        e = db.L() + db.B() + LFLSE(-1)
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        a = e(None)
        until_done(lambda: a.add_data(m, 120))
        
        self.assertEqual(tuple(a.value), (5, 1, b('A')))
    
        
    def test_two_instances(self):
        e = db.L() + db.B() + LFLSE(-1)
        a = e()
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        until_done(lambda: a.add_data(m, 120))
        
        self.assertEqual(tuple(a.value), (5, 1, b('A')))
        c = e()
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        until_done(lambda: c.add_data(m, 120))
        
        self.assertEqual(tuple(a.value), (5, 1, b('A')))
    
    
    def test_example(self):
        e = db.L() + db.B() + LFLSE(0)
        a = e(None)
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        until_done(lambda: a.add_data(m, 120))
        
        self.assertEqual(tuple(a.value), (5, 1, b('ABCDE')))
    
    
    def test_nested(self):
        i = [2, b('AB'), [5, b('ABCDE')], [5, b('ABCDE')]]
        
        a = db.B() + LFLSE(0)
        c = db.B() + LFLSE(0) + a + a
        
        d = c.produce(i)
        
        p = c(None)
        
        m = asynchia.ee.MockHandler(inbuf=d + b('FG'))
        until_done(lambda: p.add_data(m, 120))
        
        self.assertEqual(exhaust(iter(p.value)), i)
    
    
    def test_named(self):
        e = db.L()['size'] + db.B()['blub'] + FLSE(lookback('size'))['string']
        
        a = e(None)
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        until_done(lambda: a.add_data(m, 120))
        
        self.assertEqual(tuple(a.value), (5, 1, b('ABCDE')))
        self.assertEqual(m.inbuf, b('FG'))
    
    
    def test_tonamed(self):
        e = db.L()['size'] + db.B()['blub'] + FLSE(lookback('size'))['string']
        
        a = e(None)
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        until_done(lambda: a.add_data(m, 120))
        
        d = e.tonamed(a.value)
        self.assertEqual(d['size'], 5)
        self.assertEqual(d['blub'], 1)
        self.assertEqual(d['string'], b('ABCDE'))
    
    
    def test_tonamed2(self):
        e = db.L()['size'] + db.L()['blub'] + FLSE(lookback('size'))['string']
        
        a = e(None)
        m = asynchia.ee.MockHandler(
            inbuf=e.produce((5, 1, b('ABCDE'))) + b('FG')
        )
        until_done(lambda: a.add_data(m, 120))
        
        d = e.tonamed(a.value)
        self.assertEqual(d['size'], 5)
        self.assertEqual(d['blub'], 1)
        self.assertEqual(d['string'], b('ABCDE'))
    
    def test_mul(self):
        x = db.B() + lookback(0) * db.B()
        c = x()
        
        prod = x.produce((3, (1, 2, 5)))
        
        self.assertEqual(
            prod,
            struct.pack('!BBBB', 3, 1, 2, 5)
        )
        m = asynchia.ee.MockHandler(prod + b('x'))
        until_done(lambda: c.add_data(m, 10))
        self.assertEqual(exhaust(c.value), [3, [1, 2, 5]])
    
    def test_mul2(self):
        x = db.B() + db.B() * lookback(0)
        c = x()
        
        prod = x.produce((3, (1, 2, 5)))
        
        self.assertEqual(
            prod,
            struct.pack('!BBBB', 3, 1, 2, 5)
        )
        m = asynchia.ee.MockHandler(prod + b('x'))
        until_done(lambda: c.add_data(m, 10))
        self.assertEqual(exhaust(c.value), [3, [1, 2, 5]])
    
    def test_nested_mul(self):
        x = db.B() + (lambda x: 2) * ((lambda x: x.parent[0].value) * db.B())
        c = x()
        
        prod = x.produce((3, ((1, 2, 5), (4, 5, 6))))
        
        self.assertEqual(
            prod,
            struct.pack('!BBBBBBB', 3, 1, 2, 5, 4, 5, 6)
        )
        m = asynchia.ee.MockHandler(prod + b('x'))
        until_done(lambda: c.add_data(m, 10))
        self.assertEqual(exhaust(c.value), [3, [[1, 2, 5], [4, 5, 6]]])

    def test_nested_mul_glob(self):
        x = db.B()['foo'] + (lambda x: 2) * ((lambda x: x.glob('foo').value) * db.B())
        c = x()
        
        prod = x.produce((3, ((1, 2, 5), (4, 5, 6))))
        
        self.assertEqual(
            prod,
            struct.pack('!BBBBBBB', 3, 1, 2, 5, 4, 5, 6)
        )
        m = asynchia.ee.MockHandler(prod + b('x'))
        until_done(lambda: c.add_data(m, 10))
        self.assertEqual(exhaust(c.value), [3, [[1, 2, 5], [4, 5, 6]]])
    

if __name__ == '__main__':
    unittest.main()
