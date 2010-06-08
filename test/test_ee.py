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

import string
import tempfile

import asynchia.ee

from nose.tools import eq_, assert_raises

def until_done(fun):
    while True:
        try:
            fun()
        except asynchia.ee.Depleted:
            break


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
    assert_raises(ValueError, c.fd.read, 6)


def test_filecollector_notclosing():
    c = asynchia.ee.FileCollector(
        tempfile.NamedTemporaryFile(delete=False),
        False
    )
    m = asynchia.ee.MockHandler(inbuf=string.ascii_letters)
    c.add_data(m, 10)
    c.close()
    c.fd.seek(0)
    r = ''
    while len(r) < 10:
        r += c.fd.read(10 - len(r))
    eq_(r, string.ascii_letters[:10])


def test_delimited():
    c = asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), 5
    )
    m = asynchia.ee.MockHandler(inbuf=string.ascii_letters)
    n = c.add_data(m, 10)
    eq_(n, 5)
    # As we are using a MockHandler, we can be sure the collector
    # collected all 5 bytes it was supposed to.
    assert_raises(asynchia.ee.CollectorFull, c.add_data, m, 10)
    # The collector
    eq_(c.collector.string, string.ascii_letters[:5])
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
    eq_(a.collector.string, 'a' * 5)
    eq_(b.collector.string, 'b' * 4)
    eq_(c.collector.string, 'c' * 3)


def test_factorycollector():
    def make_eq(i):
        def eq(c):
            return eq_(c.string, 5 * string.ascii_letters[i])
        return eq
    itr = (asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(make_eq(i)), 5) for i in xrange(3))
    c = asynchia.ee.FactoryCollector(
        asynchia.ee.FactoryCollector.wrap_iterator(itr.next)
        )
    m = asynchia.ee.MockHandler(inbuf='a' * 5 + 'b' * 5 + 'c' * 5 + 'd')
    until_done(lambda: c.add_data(m, 5))
    assert_raises(asynchia.ee.CollectorFull, c.add_data, m, 1)
    

def test_factoryinput():
    itr = (asynchia.ee.StringInput(5 * string.ascii_letters[i])
           for i in xrange(3))
    c = asynchia.ee.FactoryInput(
        asynchia.ee.FactoryInput.wrap_iterator(itr.next)
        )
    m = asynchia.ee.MockHandler()
    until_done(lambda: c.tick(m))
    eq_(m.outbuf, 'a' * 5 + 'b' * 5 + 'c' * 5)
    assert_raises(asynchia.ee.InputEOF, c.tick, m)
