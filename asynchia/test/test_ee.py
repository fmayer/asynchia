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
from asynchia.util import b

import unittest

def get_named_tempfile(delete):
    try:
        return tempfile.NamedTemporaryFile(delete=delete)
    except TypeError:
        f = tempfile.NamedTemporaryFile()
        if not delete and os.name != "nt":
            def close():
                f.close_called = True
                f.file.close()
            f.close = close
        return f


def del_strcoll(size):
    return asynchia.ee.DelimitedCollector(
        asynchia.ee.StringCollector(), size
    )

def until_done(fun):
    while True:
        d, s = fun()
        if d:
            break

class TestEE(unittest.TestCase):
    def test_inputqueue(self):
        m = asynchia.ee.MockHandler()
        a = asynchia.ee.StringInput(b('a') * 5)
        c = asynchia.ee.StringInput(b('b') * 5)
        d = asynchia.ee.StringInput(b('c') * 5)
        q = asynchia.ee.InputQueue([a, c, d])
        
        until_done(lambda: q.tick(m))
        self.assertEqual(m.outbuf, b('a') * 5 + b('b') * 5 + b('c') * 5)
    
    
    def test_stringinput(self):
        m = asynchia.ee.MockHandler()
        i = asynchia.ee.StringInput(b(string.ascii_letters))
        i.tick(m)
        self.assertEqual(m.outbuf, b(string.ascii_letters))
    
    
    def test_fileinput(self):
        data = open(__file__, 'rb').read()
        m = asynchia.ee.MockHandler()
        i = asynchia.ee.FileInput.from_filename(__file__)
        self.assertEqual(len(i), len(data))
        until_done(lambda: i.tick(m))
        i.close()
        self.assertEqual(m.outbuf, data)
    
    
    def test_fileinput_closing(self):
        i = asynchia.ee.FileInput.from_filename(__file__)
        i.close()
        # I/O operation on closed file.
        self.assertRaises(ValueError, i.fd.read, 6)
    
    
    def test_notclosing(self):
        i = asynchia.ee.FileInput.from_filename(__file__, closing=False)
        i.close()
        # Verify file is not closed.
        self.assertEqual(i.fd.read(0), b(''))
    
    
    def test_filecollector_closing(self):
        c = asynchia.ee.FileCollector(
            get_named_tempfile(delete=False)
        )
        m = asynchia.ee.MockHandler(inbuf=b(string.ascii_letters))
        c.add_data(m, 10)
        c.close()
        # I/O operation on closed file.
        self.assertRaises(ValueError, c.value.read, 6)
    
    
    def test_filecollector_notclosing(self):
        c = asynchia.ee.FileCollector(
            get_named_tempfile(delete=False),
            False
        )
        m = asynchia.ee.MockHandler(inbuf=b(string.ascii_letters))
        c.add_data(m, 10)
        c.close()
        c.value.seek(0)
        r = b('')
        while len(r) < 10:
            r += c.value.read(10 - len(r))
        self.assertEqual(r, b(string.ascii_letters[:10]))
    
    
    def test_delimited(self):
        c = asynchia.ee.DelimitedCollector(
            asynchia.ee.StringCollector(), 5
        )
        m = asynchia.ee.MockHandler(inbuf=b(string.ascii_letters))
        n = c.add_data(m, 10)
        self.assertEqual(n[1], 5)
        # As we are using a MockHandler, we can be sure the collector
        # collected all 5 bytes it was supposed to.
        self.assertEqual(c.add_data(m, 10)[0], True)
        # The collector
        self.assertEqual(c.collector.value, b(string.ascii_letters[:5]))
        self.assertEqual(m.inbuf, b(string.ascii_letters[5:]))
        
    
    def test_collectorqueue(self):
        a = asynchia.ee.DelimitedCollector(
            asynchia.ee.StringCollector(), 5
        )
        c = asynchia.ee.DelimitedCollector(
            asynchia.ee.StringCollector(), 4
        )
        d = asynchia.ee.DelimitedCollector(
            asynchia.ee.StringCollector(), 3
        )
        
        q = asynchia.ee.CollectorQueue([a, c, d])
        
        m = asynchia.ee.MockHandler(inbuf=b('a') * 5 + b('b') * 4 + b('c') * 3)
        until_done(lambda: q.add_data(m, 5))
        self.assertEqual(a.collector.value, b('a') * 5)
        self.assertEqual(c.collector.value, b('b') * 4)
        self.assertEqual(d.collector.value, b('c') * 3)
    
    
    def test_factorycollector(self):
        def make_eq(i):
            def eq(c):
                return self.assertEqual(c.value, b(5 * string.ascii_letters[i]))
            return eq
        itr = (asynchia.ee.DelimitedCollector(
            asynchia.ee.StringCollector(make_eq(i)), 5) for i in xrange(3))
        c = asynchia.ee.FactoryCollector(
            asynchia.ee.FactoryCollector.wrap_iterator(itr.next)
            )
        m = asynchia.ee.MockHandler(
            inbuf=b('a') * 5 + b('b') * 5 + b('c') * 5 + b('d'))
        until_done(lambda: c.add_data(m, 5))
        self.assertEqual(c.add_data(m, 1)[0], True)
        
    
    def test_factoryinput(self):
        itr = (asynchia.ee.StringInput(b(5 * string.ascii_letters[i]))
               for i in xrange(3))
        c = asynchia.ee.FactoryInput(
            asynchia.ee.FactoryInput.wrap_iterator(itr.next)
            )
        m = asynchia.ee.MockHandler()
        until_done(lambda: c.tick(m))
        self.assertEqual(m.outbuf, b('a') * 5 + b('b') * 5 + b('c') * 5)
        self.assertEqual(c.tick(m)[0], True)
    
    
    def test_close(self):
        c = asynchia.ee.DelimitedCollector(asynchia.ee.StringCollector(), 5)
        m = asynchia.ee.MockHandler(b('abcde'))
        c.add_data(m, 10)
        self.assertEqual(c.closed, True)
    
    
    def test_inputadd(self):
        m = asynchia.ee.MockHandler()
        q = asynchia.ee.StringInput(b('a')) + asynchia.ee.StringInput(b('b'))
        id1 = id(q)
        q += asynchia.ee.StringInput(b('c'))
        id2 = id(q)
        self.assertEqual(id1, id2)
        until_done(lambda: q.tick(m))
        self.assertEqual(m.outbuf, b('abc'))
    
    
    def test_closeinqueue(self):
        q = asynchia.ee.InputQueue()
        a = asynchia.ee.Input()
        q.add(a)
        q.close()
        self.assertEqual(a.closed, True)
    
    
    def test_lenpredict(self):
        strings = [b('a') * i for i in xrange(1, 20)]
        for string in strings:
            fd = get_named_tempfile(delete=True)
            try:
                fd.write(string)
                fd.flush()
                fd.seek(0)
                c = asynchia.ee.FileInput(fd)
                self.assertEqual(len(c), len(string))
            finally:
                fd.close()
    
    
    def test_fromfilename(self):
        strings = [
            b('a' + '\n') * i + b('b' + '\r\n') * j
            for i in xrange(1, 20)
            for j in xrange(1, 20)
        ]
        for string in strings:
            fd = get_named_tempfile(delete=True)
            try:
                fd.write(string)
                fd.flush()
                fd.seek(0)
                c = asynchia.ee.FileInput.from_filename(fd.name, 'r')
                self.assertEqual(len(c), len(string))
            finally:
                fd.close()
    
    
    def test_collectoradd(self):
        a = del_strcoll(5)
        c = del_strcoll(6)
        
        q = a + c
        m = asynchia.ee.MockHandler(b('a') * 5 + b('b') * 6)
        until_done(lambda: q.add_data(m, 2))
        self.assertEqual(a.collector.value, b('a') * 5)
        self.assertEqual(c.collector.value, b('b') * 6)
    
    
    def test_autoflush(self):
        fd = get_named_tempfile(delete=True)
        fc = asynchia.ee.FileCollector(fd, autoflush=True)
        
        i = 0
        m = asynchia.ee.MockHandler(b('a') * 20000000)
        
        while m.inbuf:
            d, n = fc.add_data(m, 8000000)
            i += n
            
            self.assertEqual(os.stat(fd.name).st_size, i)
    
    
    def test_strucollector(self):
        s = struct.Struct('!dh')
        c = asynchia.ee.StructCollector(s)
        m = asynchia.ee.MockHandler(s.pack(14, 25))
        until_done(lambda: c.add_data(m, 2))
        self.assertEqual(c.value, (14, 25))

if __name__ == '__main__':
    unittest.main()
