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

import time
import unittest
import threading

from copy import copy

import asynchia.maps
import asynchia.defer as fc

class Container(object): pass

def dnr_inject(self, map_):
    container = Container()
    container.run = False
    container.main_thread = None
    
    main_thread = threading.currentThread()
    
    def in_thread(mo, noti, container):
        container.main_thread = threading.currentThread() == main_thread
        mo.call_synchronized(lambda: noti.success("foobar"))
    
    def mkfun(container):
        def _fun(data):
            self.assertEqual(data, "foobar")
            self.assertEqual(threading.currentThread(), main_thread)
            container.run = True
        return _fun
    
    mo = map_()
    noti = fc.Deferred()
    noti.add(mkfun(container))
    self.assertEquals(container.run, False)
    
    threading.Thread(target=in_thread, args=(mo, noti, container)).start()
    
    s = time.time()
    while not container.run and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEquals(container.run, True)
    self.assertEquals(container.main_thread, False)
    

def dnr_databack_beforedata(self, map_):
    container = Container()
    container.run = False
    def mkfun(container):
        def _fun(data):
            self.assertEqual(data, "foobar")
            container.run = True
        return _fun
    
    mo = map_()
    noti = fc.Deferred()
    noti.add(mkfun(container))
    self.assertEquals(container.run, False)
    noti.success("foobar")
    self.assertEquals(container.run, True)


def dnr_databack_afterdata(self, map_):
    container = Container()
    container.run = False
    def mkfun(container):
        def _fun(data):
            self.assertEqual(data, "foobar")
            container.run = True
        return _fun
    
    mo = map_()
    noti = fc.Deferred()
    noti.success("foobar")
    noti.add(mkfun(container))
    self.assertEquals(container.run, True)


def dnr_coroutines(self, map_):
    container = Container()
    container.run = False
    
    def mkfun(container):
        def _fun(data):
            self.assertEqual(data, "foobar")
            container.run = True
        return _fun
    
    mo = map_()
    noti = fc.Deferred()
    
    def foo(noti):
        data = yield noti
        fc.Coroutine.return_(data)
    
    coroutine = fc.Coroutine(
        foo(noti), deferred=fc.Deferred()
    )
    conoti = coroutine.deferred
    coroutine.send()
    
    conoti.add(mkfun(container))
    self.assertEquals(container.run, False)
    noti.success("foobar")
    self.assertEquals(container.run, True)


def mkcoroutine():
    class HTTP404(Exception):
        pass
    
    a = fc.Deferred()
    def bar(err):
        # Request result of network I/O.
        blub = (yield a)
        if err:
            raise HTTP404
        fc.Coroutine.return_(blub)
    def foo(err):
        # Wait for completion of new coroutine which - in turn - waits
        # for I/O.
        try:
            blub = yield fc.Coroutine.call_itr(bar(err), None)
        except HTTP404:
            blub = 404
        fc.Coroutine.return_("yay %s" % blub)
    
    return a, foo


def callb2(value):
    return value + '2'


class TestForthcoming(unittest.TestCase):
    def test_synchronize_coroutine(self):
        a, test_coroutine = mkcoroutine()
        c = fc.Coroutine(test_coroutine(False), None)
        c.send()
        # Network I/O complete.
        a.success('yay')
        self.assertEquals(c.synchronize(), 'yay yay')
    
    def test_synchronize_coroutine_error(self):
        a, test_coroutine = mkcoroutine()
        c = fc.Coroutine(test_coroutine(True), None)
        c.send()
        # Network I/O complete.
        a.success('yay')
        self.assertEquals(c.synchronize(), 'yay 404')
    
    def test_deferred_add_after_submit(self):
            e = fc.Deferred()
            def callb1(value):
                return e
            
            d = fc.Deferred()
            foo = d.add(callb1).add(callb2).add(callb2)
            d.success('hello')
            d.add(callb1)
            
            e.success('world')
            self.assertEqual(foo.synchronize(), 'world22')
            self.assertEqual(foo.add(callb2).synchronize(), 'world222')
    
    def test_wrap(self):        
        c = fc.Deferred(lambda x, y: x + y)
        d = c.add(callb2)
        c.wrap()('foo', 'bar')
        
        self.assertEqual(d.synchronize(), 'foobar2')
    
    def test_deco(self):
        class Foo(object):
            def __init__(self, x):
                self.x = x
            
            @fc.Deferred
            def _c(self, y):
                return self.x + y
            
            c = _c.wrapinstance()
            
            @_c.add
            def d(self, x):
                return x + '1'
            
            _c['result'] = d
        
        foo = Foo('foo')
        d = foo.c('bar')
        self.assertEquals(d['result'].synchronize(), 'foobar1')
    
    def test_class_wrapinstance(self):
        class Foo(object):
            c = fc.Blueprint(lambda self, y: self.x + y)
            c.add(callb2)
            
            c = c.wrapinstance()
            
            def __init__(self, x):
                self.x = x
        
        f = Foo('foo')
        r1_1 = f.c('bar')
        r1_2 = f.c('baz')
        
        b = Foo('spam')
        r2_1 = b.c('bar')
        r2_2 = b.c('baz')
        
        self.assertEqual(r1_1.synchronize(), 'foobar')
        self.assertEqual(r1_2.synchronize(), 'foobaz')
        
        self.assertEqual(r2_1.synchronize(), 'spambar')
        self.assertEqual(r2_2.synchronize(), 'spambaz')
    
    def test_ref(self):
        b = fc.Blueprint()
        b['end'] = b.add(lambda n: 2 * n).add(lambda n: 3 + n)
         
        n = fc.Deferred()
        end = n.add_blueprint(b)['end'].add(lambda x: 2 * x)
        n(1)
        self.assertEqual(end.synchronize(), 10)
    
    def test_immutability(self):
        c = fc.Chain()
        c.add(lambda n: 2 * n).add(lambda n: 3 + n)
        
        e = fc.Chain()
        e.add_chain(c).add(lambda n: 3 * n).add(lambda n: 2 + n)
        
        n = fc.Deferred()
        end1 = n.add_chain(e)
        
        x = fc.Deferred()
        end2 = x.add_chain(c)
        n(1)
        x(2)
        
        self.assertEqual(end1.synchronize(), 17)
        self.assertEqual(end2.synchronize(), 7)

def _genfun(map_, test):
    def _fun(self):
        return test(self, map_)
    return _fun

maps = \
     (map_ for map_ in
      [
          asynchia.maps.SelectSocketMap,
          asynchia.maps.PollSocketMap,
          asynchia.maps.EPollSocketMap,
          asynchia.maps.KQueueSocketMap,
      ]
      if map_.available
      )

tests = [
    dnr_databack_afterdata, dnr_databack_beforedata, dnr_inject,
    dnr_coroutines
]

i = 0

for m in maps:
    for test in tests:
        name = 'test_' + test.__name__[4:] + '_' + m.__name__ + str(i)
        fun = _genfun(m, test)
        fun.__name__ = name
        setattr(TestForthcoming, name, fun)
        i += 1

if __name__ == '__main__':
    unittest.main()
