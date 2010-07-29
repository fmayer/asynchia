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

from nose.tools import eq_, assert_raises

import asynchia.ee
from asynchia.dsl import b, SBLFLSE


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
    i = [2, 'AB', [5, 'ABCDE'], [5, 'ABCDE']]
    
    a = b.B + SBLFLSE(0)
    c = b.B + SBLFLSE(0) + a + a
    
    d = c.produce(i)
    
    p = c(None)
    
    m = asynchia.ee.MockHandler(inbuf=d + 'FG')
    until_done(lambda: p.add_data(m, 120))
    
    eq_(exhaust(iter(p.value)), i)
