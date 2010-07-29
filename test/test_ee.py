# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2009 Florian Mayer

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

import os
import string
import struct
import tempfile

import asynchia.ee

from nose.tools import eq_, assert_raises

def del_strcoll(size):
    return asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), size
    )

def until_done(fun):
    while True:
        d, s = fun()
        if d:
            break


def test_inputqueue():
    m = asynchia.ee.MockHandler()
    a = asynchia.ee.StringInput('a' * 5)
    b = asynchia.ee.StringInput('b' * 5)
    c = asynchia.ee.StringInput('c' * 5)
    q = asynchia.ee.InputQueue([a, b, c])
    
    until_done(lambda: q.tick(m))
    eq_(m.outbuf, 'a' * 5 + 'b' * 5 + 'c' * 5)


def test_stringinput():
    m = asynchia.ee.MockHandler()
    i = asynchia.ee.StringInput(string.ascii_letters)
    i.tick(m)
    eq_(m.outbuf, string.ascii_letters)


def test_fileinput():
    data = open(__file__).read()
    m = asynchia.ee.MockHandler()
    i = asynchia.ee.FileInput.from_filename(__file__)
    eq_(len(i), len(data))
    until_done(lambda: i.tick(m))
    i.close()
    eq_(m.outbuf, data)


def test_fileinput_closing():
    i = asynchia.ee.FileInput.from_filename(__file__)
    i.close()
    # I/O operation on closed file.
    assert_raises(ValueError, i.fd.read, 6)


def test_notclosing():
    i = asynchia.ee.FileInput.from_filename(__file__, closing=False)
    i.close()
    # Verify file is not closed.
    eq_(i.fd.read(0), '')


def test_filecollector_closing():
    c = asynchia.ee.FileCollector(
        tempfile.NamedTemporaryFile(delete=False)
    )
    m = asynchia.ee.MockHandler(inbuf=string.ascii_letters)
    c.add_data(m, 10)
    c.close()
    # I/O operation on closed file.
    assert_raises(ValueError, c.value.read, 6)


def test_filecollector_notclosing():
    c = asynchia.ee.FileCollector(
        tempfile.NamedTemporaryFile(delete=False),
        False
    )
    m = asynchia.ee.MockHandler(inbuf=string.ascii_letters)
    c.add_data(m, 10)
    c.close()
    c.value.seek(0)
    r = ''
    while len(r) < 10:
        r += c.value.read(10 - len(r))
    eq_(r, string.ascii_letters[:10])


def test_delimited():
    c = asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), 5
    )
    m = asynchia.ee.MockHandler(inbuf=string.ascii_letters)
    n = c.add_data(m, 10)
    eq_(n[1], 5)
    # As we are using a MockHandler, we can be sure the collector
    # collected all 5 bytes it was supposed to.
    eq_(c.add_data(m, 10)[0], True)
    # The collector
    eq_(c.collector.value, string.ascii_letters[:5])
    eq_(m.inbuf, string.ascii_letters[5:])
    

def test_collectorqueue():
    a = asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), 5
    )
    b = asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), 4
    )
    c = asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), 3
    )
    
    q = asynchia.ee.CollectorQueue([a, b, c])
    
    m = asynchia.ee.MockHandler(inbuf='a' * 5 + 'b' * 4 + 'c' * 3)
    until_done(lambda: q.add_data(m, 5))
    eq_(a.collector.value, 'a' * 5)
    eq_(b.collector.value, 'b' * 4)
    eq_(c.collector.value, 'c' * 3)


def test_factorycollector():
    def make_eq(i):
        def eq(c):
            return eq_(c.value, 5 * string.ascii_letters[i])
        return eq
    itr = (asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(make_eq(i)), 5) for i in xrange(3))
    c = asynchia.ee.FactoryCollector(
        asynchia.ee.FactoryCollector.wrap_iterator(itr.next)
        )
    m = asynchia.ee.MockHandler(inbuf='a' * 5 + 'b' * 5 + 'c' * 5 + 'd')
    until_done(lambda: c.add_data(m, 5))
    eq_(c.add_data(m, 1)[0], True)
    

def test_factoryinput():
    itr = (asynchia.ee.StringInput(5 * string.ascii_letters[i])
           for i in xrange(3))
    c = asynchia.ee.FactoryInput(
        asynchia.ee.FactoryInput.wrap_iterator(itr.next)
        )
    m = asynchia.ee.MockHandler()
    until_done(lambda: c.tick(m))
    eq_(m.outbuf, 'a' * 5 + 'b' * 5 + 'c' * 5)
    eq_(c.tick(m)[0], True)


def test_close():
    c = asynchia.ee.DelimitedCollector(asynchia.ee.StringCollector(), 5)
    m = asynchia.ee.MockHandler('abcde')
    c.add_data(m, 10)
    # As of now, the collector is only closed at the next call.
    eq_(c.closed, True)


def test_inputadd():
    m = asynchia.ee.MockHandler()
    q = asynchia.ee.StringInput('a') + asynchia.ee.StringInput('b')
    id1 = id(q)
    q += asynchia.ee.StringInput('c')
    id2 = id(q)
    eq_(id1, id2)
    until_done(lambda: q.tick(m))
    eq_(m.outbuf, 'abc')


def test_closeinqueue():
    q = asynchia.ee.InputQueue()
    a = asynchia.ee.Input()
    q.add(a)
    q.close()
    eq_(a.closed, True)


def test_lenpredict():
    strings = ['a' * i for i in xrange(1, 20)]
    for string in strings:
        fd = tempfile.NamedTemporaryFile(delete=True)
        try:
            fd.write(string)
            fd.flush()
            fd.seek(0)
            c = asynchia.ee.FileInput(fd)
            eq_(c.length, len(string))
        finally:
            fd.close()


def test_collectoradd():
    a = del_strcoll(5)
    b = del_strcoll(6)
    
    q = a + b
    m = asynchia.ee.MockHandler('a' * 5 + 'b' * 6)
    until_done(lambda: q.add_data(m, 2))
    eq_(a.collector.value, 'a' * 5)
    eq_(b.collector.value, 'b' * 6)


def test_autoflush():
    fd = tempfile.NamedTemporaryFile(delete=True)
    fc = asynchia.ee.FileCollector(fd, autoflush=True)
    
    i = 0
    m = asynchia.ee.MockHandler('a' * 20000000)
    
    while m.inbuf:
        d, n = fc.add_data(m, 8000000)
        i += n
        
        eq_(os.stat(fd.name).st_size, i)


def test_strucollector():
    s = struct.Struct('!dh')
    c = asynchia.ee.StructCollector(s)
    m = asynchia.ee.MockHandler(s.pack(14, 25))
    until_done(lambda: c.add_data(m, 2))
    eq_(c.value, (14, 25))
    