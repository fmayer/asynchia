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

from __future__ import with_statement

import time
import errno
import socket
import threading

import asynchia
import asynchia.maps
import asynchia.util

import asynchia.forthcoming

b = asynchia.util.b

import unittest

def _override_socketpair(fun):
    def _fun(*args, **kwargs):
        bu = getattr(socket, 'socketpair', None)
        del socket.socketpair
        try:
            return fun(*args, **kwargs)
        finally:
            if bu is not None:
                socket.socketpair = bu
    return _fun


class Container(object):
    pass


def dnr_forthcoming_wakeup(self, map_):
    container = Container()
    container.flag = False
    
    mo = map_()
    
    mainthread = threading.currentThread()
    
    def thr(nf):
        time.sleep(2)
        nf.inject(12)
    
    def callb(data):
        self.assertEquals(data, 12)
        self.assertEquals(threading.currentThread(), mainthread)
        
        container.flag = True
    
    nf = asynchia.forthcoming.DataNotifier(mo)
    nf.add_databack(callb)
    th = threading.Thread(target=thr, args=(nf,))
    th.start()
    
    s = time.time()
    while not container.flag and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEquals(container.flag, True)


def dnr_interrupt(self, map_):
    container = Container()
    container.flag = False
    mo = map_()
    def thread(container):
        mo.start_interrupt()
        try:
            time.sleep(4)
        finally:
            container.flag = True
            mo.end_interrupt()
    threading.Thread(target=thread, args=(container, )).start()
    s = time.time()
    while not container.flag and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEqual(container.flag, True)


cf_done = False
cf_thr = None

        
def std(mo, hand):
    time.sleep(1)
    mo.start_interrupt(True)
    try:
        hand.set_writeable(True)
    finally:
        mo.end_interrupt(True)


def ctx(mo, hand):
    time.sleep(1)
    with mo.interrupt(True):
        hand.set_writeable(True)


def t_changeflag(subthread):
    def dnr_changeflag(self, map_):
        container = Container()
        container.done = False
        container.thr = None        
        
        class Serv(asynchia.Server):
            def __init__(
                self, transport, handlercls=asynchia.Handler
                ):
                asynchia.Server.__init__(self, transport, handlercls)
                self.clients = []
            
            def new_connection(self, handler, addr):
                self.clients.append(handler)
        
        
        class Handler(asynchia.Handler):
            def __init__(self, transport, container=None):
                asynchia.Handler.__init__(self, transport)
                self.container = container
            
            def handle_connect(self):
                container.thr = threading.Thread(
                    target=subthread,
                    args=[self.transport.socket_map, self.transport]
                )
                container.thr.start()
            
            def handle_write(self):
                container.done = True
                self.transport.set_writeable(False)
            
            # Prevent exception from being suppressed.
            def handle_error(self):
                raise
        
        mo = map_()
        s = Serv(asynchia.SocketTransport(mo))
        s.transport.bind(('127.0.0.1', 0))
        # We know we'll only get one connection.
        s.transport.listen(1)
        
        c = Handler(asynchia.SocketTransport(mo), container)
        c.transport.connect(s.transport.socket.getsockname())
        n = 0
        s = time.time()
        while not container.done and time.time() < s + 10:
            mo.poll(abs(10 - (time.time() - s)))
        self.assertEqual(container.done, True)
        mo.close()
        container.thr.join(10)
        self.assertEqual(container.thr.isAlive(), False)
    return dnr_changeflag
    
def dnr_remove(self, map_):
    mo = map_()
    container = Container()
    container.done = False
    
    class Serv(asynchia.Server):
        def __init__(
            self, transport, handlercls=asynchia.Handler
            ):
            asynchia.Server.__init__(self, transport, handlercls)
            self.clients = []
        
        def new_connection(self, handler, addr):
            self.clients.append(handler)
    
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
            self.transport.set_writeable(True)
        
        def handle_write(self):
            container.done = True
            
        # Prevent exception from being suppressed.
        def handle_error(self):
            raise
    
    mo = map_()
    s = Serv(asynchia.SocketTransport(mo))
    s.transport.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    s.transport.listen(1)
    
    c = Handler(asynchia.SocketTransport(mo), container)
    c.transport.connect(s.transport.socket.getsockname())
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEqual(container.done, True)
    mo.del_transport(c.transport)
    container.done = False
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    mo.close()
    self.assertEqual(container.done, False)


def dnr_remove2(self, map_):
    mo = map_()
    container = Container()
    container.done = False
    
    class Serv(asynchia.Server):
        def __init__(
            self, transport, handlercls=asynchia.Handler
            ):
            asynchia.Server.__init__(self, transport, handlercls)
            self.clients = []
        
        def new_connection(self, handler, addr):
            self.clients.append(handler)
    
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
        
        def handle_connect(self):
            self.transport.set_writeable(True)
        
        def handle_write(self):
            container.done = True
            
        # Prevent exception from being suppressed.
        def handle_error(self):
            raise
    
    mo = map_()
    s = Serv(asynchia.SocketTransport(mo))
    s.transport.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    s.transport.listen(1)
    
    c = Handler(asynchia.SocketTransport(mo), container)
    c.transport.connect(s.transport.socket.getsockname())
    s = time.time()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEqual(container.done,  True)
    mo.del_transport(c.transport)
    container.done = False
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    mo.close()
    self.assertEqual(container.done, False)


def dnr_close(self, map_):
    mo = map_()
    container = Container()
    container.done = False
    
    a, b = asynchia.util.socketpair()
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
        
        def handle_close(self):
            container.done = True
    
    
    mo = map_()
    
    c = Handler(asynchia.SocketTransport(mo, a), container)
    b.close()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    mo.close()
    self.assertEqual(container.done, True)


def dnr_close_read(self, map_):
    mo = map_()
    container = Container()
    container.done = False
    
    a, b = asynchia.util.socketpair()
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
            
            self.transport.set_readable(True)
        
        def handle_close(self):
            container.done = True
    
    
    mo = map_()
    
    c = Handler(asynchia.SocketTransport(mo, a), container)
    b.close()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    mo.close()
    self.assertEqual(container.done, True)


def dnr_close_write(self, map_):
    mo = map_()
    container = Container()
    container.done = False
    
    a, b = asynchia.util.socketpair()
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
            
            self.transport.set_writeable(True)
        
        def handle_close(self):
            container.done = True
    
    
    mo = map_()
    
    c = Handler(asynchia.SocketTransport(mo, a), container)
    b.close()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    mo.close()
    self.assertEqual(container.done, True)


def dnr_connfailed(self, map_):
    container = Container()
    container.done = False
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
        
        def handle_connect_failed(self, err):
            container.done = True
    
    mo = map_()
    c = Handler(asynchia.SocketTransport(mo), container)
    try:
        c.transport.connect(('wrong.invalid', 81))
    except socket.error:
        container.done = True
        
    
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEqual(container.done, True)

def dnr_connfailed2(self, map_):
    container = Container()
    container.done = False
    
    class Handler(asynchia.Handler):
        def __init__(self, transport, container=None):
            asynchia.Handler.__init__(self, transport)
            self.container = container
        
        def handle_connect_failed(salf, err):
            if err != errno.ECONNREFUSED:
                self.assertEqual(True, False)
            container.done = True
        
        def handle_connect(salf):
            self.assertEqual(True, False)
    
    mo = map_()
    c = Handler(asynchia.SocketTransport(mo), container)
    
    acceptor = socket.socket()
    # Random port. Only accept local connections.
    acceptor.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    acceptor.listen(1)
    
    name = acceptor.getsockname()
    
    acceptor.close()
    
    try:
        c.transport.connect(name)
    except socket.error:
        container.done = True
    
    s = time.time()
    while not container.done and time.time() < s + 30:
        mo.poll(abs(10 - (time.time() - s)))
    self.assertEqual(container.done, True)

    
def dnr_closed(self, map_):
    mo = map_()
    mo.close()
    self.assertRaises(asynchia.SocketMapClosedError, mo.poll, 10)


class TestCore(unittest.TestCase):    
    def test_error(self):
        container = Container()
        container.done = False
        
        class Serv(asynchia.Server):
            def __init__(
                self, transport, handlercls=asynchia.Handler
                ):
                asynchia.Server.__init__(self, transport, handlercls)
                self.clients = []
            
            def new_connection(self, handler, addr):
                self.clients.append(handler)
        
        
        class Handler(asynchia.Handler):
            def __init__(self, transport, container=None):
                asynchia.Handler.__init__(self, transport)
                self.container = container
            
            def handle_write(self):
                raise ValueError
            
            # Prevent exception from being suppressed.
            def handle_error(self):
                self.container.done = True
        
        mo = asynchia.maps.DefaultSocketMap()
        s = Serv(asynchia.SocketTransport(mo))
        s.transport.bind(('127.0.0.1', 0))
        # We know we'll only get one connection.
        s.transport.listen(1)
        
        c = Handler(asynchia.SocketTransport(mo), container)
        c.transport.connect(s.transport.socket.getsockname())
        
        c.transport.set_writeable(True)
        
        s = time.time()
        while not container.done and time.time() < s + 10:
            mo.poll(abs(10 - (time.time() - s)))
        self.assertEqual(container.done, True)
    
    
    def test_pingpong(self):
        mo = asynchia.maps.DefaultSocketMap()
        a, b = asynchia.util.socketpair()
        ha = asynchia.Handler(asynchia.SocketTransport(mo, a))
        hb = asynchia.Handler(asynchia.SocketTransport(mo, b))
        
        ha.transport.set_writeable(True)
        hb.transport.set_readable(True)
        
        ha.handle_write = lambda: ha.send(b("Foo"))
        hb.handle_read = lambda: self.assertEqual(hb.recv(3), b('Foo'))
    
    if hasattr(socket, 'socketpair'):
        test_pingpong2 = _override_socketpair(test_pingpong)

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

wsocketpair = [
    dnr_close, dnr_close_read,dnr_close_write, dnr_connfailed,
    dnr_connfailed2, dnr_forthcoming_wakeup
]

tests = [
    dnr_interrupt, t_changeflag(ctx), t_changeflag(std),
    dnr_remove, dnr_remove2, dnr_closed
] + wsocketpair

if hasattr(socket, 'socketpair'):
    tests += map(_override_socketpair, wsocketpair)

i = 0

for m in maps:
    for test in tests:
        name = 'test_' + test.__name__[4:] + '_' + m.__name__ + str(i)
        fun = _genfun(m, test)
        fun.__name__ = name
        setattr(TestCore, name, fun)
        i += 1

if __name__ == '__main__':
    unittest.main()
