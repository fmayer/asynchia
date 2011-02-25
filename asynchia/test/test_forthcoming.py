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

import asynchia.maps
import asynchia.forthcoming as fc

class Container(object): pass

def dnr_inject(self, map_):
    container = Container()
    container.run = False
    container.main_thread = None
    
    main_thread = threading.currentThread()
    
    def in_thread(noti, container):
        container.main_thread = threading.currentThread() == main_thread
        noti.inject("foobar")
    
    def mkfun(container):
        def _fun(data):
            self.assertEqual(data, "foobar")
            self.assertEqual(threading.currentThread(), main_thread)
            container.run = True
        return _fun
    
    mo = map_()
    noti = fc.DataNotifier(mo)
    noti.add_databack(mkfun(container))
    self.assertEquals(container.run, False)
    
    threading.Thread(target=in_thread, args=(noti, container)).start()
    
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
    noti = fc.DataNotifier(mo)
    noti.add_databack(mkfun(container))
    self.assertEquals(container.run, False)
    noti.submit("foobar")
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
    noti = fc.DataNotifier(mo)
    noti.submit("foobar")
    noti.add_databack(mkfun(container))
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
    noti = fc.DataNotifier(mo)
    
    def foo(noti):
        data = yield noti
        yield fc.Coroutine.return_(data)
    
    coroutine = fc.Coroutine(
        foo(noti),datanotifier=fc.DataNotifier(mo)
    )
    conoti = coroutine.datanotifier
    coroutine.call()
    
    conoti.add_databack(mkfun(container))
    self.assertEquals(container.run, False)
    noti.submit("foobar")
    self.assertEquals(container.run, True)


class TestForthcoming(unittest.TestCase):
    pass


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
