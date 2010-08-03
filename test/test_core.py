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
import socket
import threading

import asynchia
import asynchia.maps
import asynchia.util

from nose.tools import eq_, assert_raises

class Container(object):
    pass

def tes_interrupt(map_):
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
    mo.poll(None)
    eq_(container.flag, True)


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
    def tes_changeflag(map_):
        container = Container()
        container.done = False
        container.thr = None        
        
        class Serv(asynchia.Server):
            def __init__(
                self, socket_map, sock=None, handlercls=asynchia.IOHandler
                ):
                asynchia.Server.__init__(self, socket_map, sock, handlercls)
                self.clients = []
            
            def new_connection(self, handler, addr):
                self.clients.append(handler)
        
        
        class Handler(asynchia.IOHandler):
            def __init__(self, socket_map, sock=None, container=None):
                asynchia.IOHandler.__init__(self, socket_map, sock)
                self.container = container
            
            def handle_connect(self):
                container.thr = threading.Thread(
                    target=subthread, args=(self.socket_map, self)
                )
                container.thr.start()
            
            def handle_write(self):
                container.done = True
                self.set_writeable(False)
            
            # Prevent exception from being suppressed.
            def handle_error(self):
                raise
        
        mo = map_()
        s = Serv(mo)
        s.bind(('127.0.0.1', 0))
        # We know we'll only get one connection.
        s.listen(1)
        
        c = Handler(mo, None, container)
        c.connect(s.socket.getsockname())
        n = 0
        while (not container.done):
            mo.poll(None)
            n += 1
            if n > 10 ** 6:
                eq_(True, False, 'Timeout')
        mo.close()
        container.thr.join(10)
        eq_(container.thr.isAlive(), False)
    return tes_changeflag
    
def tes_remove(map_):
    mo = map_()
    container = Container()
    container.done = False
    
    class Serv(asynchia.Server):
        def __init__(
            self, socket_map, sock=None, handlercls=asynchia.IOHandler
            ):
            asynchia.Server.__init__(self, socket_map, sock, handlercls)
            self.clients = []
        
        def new_connection(self, handler, addr):
            self.clients.append(handler)
    
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
            self.set_writeable(True)
        
        def handle_write(self):
            container.done = True
            
        # Prevent exception from being suppressed.
        def handle_error(self):
            raise
    
    mo = map_()
    s = Serv(mo)
    s.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    s.listen(1)
    
    c = Handler(mo, None, container)
    c.connect(s.socket.getsockname())
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(10 - (time.time() - s))
    eq_(container.done, True)
    mo.del_handler(c)
    container.done = False
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(10 - (time.time() - s))
    mo.close()
    eq_(container.done, False)


def tes_remove2(map_):
    mo = map_()
    container = Container()
    container.done = False
    
    class Serv(asynchia.Server):
        def __init__(
            self, socket_map, sock=None, handlercls=asynchia.IOHandler
            ):
            asynchia.Server.__init__(self, socket_map, sock, handlercls)
            self.clients = []
        
        def new_connection(self, handler, addr):
            self.clients.append(handler)
    
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
        
        def handle_connect(self):
            self.set_writeable(True)
        
        def handle_write(self):
            container.done = True
            
        # Prevent exception from being suppressed.
        def handle_error(self):
            raise
    
    mo = map_()
    s = Serv(mo)
    s.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    s.listen(1)
    
    c = Handler(mo, None, container)
    c.connect(s.socket.getsockname())
    s = time.time()
    while (not container.done):
        mo.poll(None)
    mo.del_handler(c)
    container.done = False
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(10 - (time.time() - s))
    mo.close()
    eq_(container.done, False)


def tes_close(map_):
    mo = map_()
    container = Container()
    container.done = False
    
    a, b = asynchia.util.socketpair()
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
        
        def handle_close(self):
            container.done = True
    
    
    mo = map_()
    
    c = Handler(mo, a, container)
    b.close()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(10 - (time.time() - s))
    mo.close()
    eq_(container.done, True)


def tes_close_read(map_):
    mo = map_()
    container = Container()
    container.done = False
    
    a, b = asynchia.util.socketpair()
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
            
            self.set_readable(True)
        
        def handle_close(self):
            container.done = True
    
    
    mo = map_()
    
    c = Handler(mo, a, container)
    b.close()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(10 - (time.time() - s))
    mo.close()
    eq_(container.done, True)


def tes_close_write(map_):
    mo = map_()
    container = Container()
    container.done = False
    
    a, b = asynchia.util.socketpair()
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
            
            self.set_writeable(True)
        
        def handle_close(self):
            container.done = True
    
    
    mo = map_()
    
    c = Handler(mo, a, container)
    b.close()
    s = time.time()
    while not container.done and time.time() < s + 10:
        mo.poll(10 - (time.time() - s))
    mo.close()
    eq_(container.done, True)


def test_maps():
    maps = \
         (getattr(asynchia.maps, name) for name in 
          [
              'SelectSocketMap',
              'PollSocketMap',
              'EPollSocketMap',
              'KQueueSocketMap',
          ]
          if hasattr(asynchia.maps, name)
          )
    
    tests = [
        tes_interrupt, t_changeflag(ctx), t_changeflag(std),
        tes_remove, tes_remove2, tes_close, tes_close_read,
        tes_close_write
    ]
    
    for m in maps:
        for test in tests:
            yield test, m


def test_error():
    container = Container()
    container.done = False
    
    class Serv(asynchia.Server):
        def __init__(
            self, socket_map, sock=None, handlercls=asynchia.IOHandler
            ):
            asynchia.Server.__init__(self, socket_map, sock, handlercls)
            self.clients = []
        
        def new_connection(self, handler, addr):
            self.clients.append(handler)
    
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
        
        def handle_write(self):
            raise ValueError
        
        # Prevent exception from being suppressed.
        def handle_error(self):
            self.container.done = True
    
    mo = asynchia.maps.DefaultSocketMap()
    s = Serv(mo)
    s.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    s.listen(1)
    
    c = Handler(mo, None, container)
    c.connect(s.socket.getsockname())
    
    c.set_writeable(True)
    
    while not container.done:
        mo.poll(None)

def test_connfailed():
    container = Container()
    container.done = False
    
    class Handler(asynchia.IOHandler):
        def __init__(self, socket_map, sock=None, container=None):
            asynchia.IOHandler.__init__(self, socket_map, sock)
            self.container = container
        
        def handle_connect_failed(self, err):
            container.done = True
    
    mo = asynchia.maps.DefaultSocketMap()
    c = Handler(mo, None, container)
    try:
        c.connect(('wrong.invalid', 81))
    except socket.error:
        container.done = True
        
    
    while not container.done:
        mo.poll(None)


def test_pingpong():
    mo = asynchia.maps.DefaultSocketMap()
    a, b = asynchia.util.socketpair()
    ha = asynchia.IOHandler(mo, a)
    hb = asynchia.IOHandler(mo, b)
    
    ha.set_writeable(True)
    hb.set_readable(True)
    
    ha.handle_write = lambda: ha.send("Foo")
    hb.handle_read = lambda: eq_(hb.recv(3), 'Foo')


if __name__ == '__main__':
    tes_remove2(asynchia.maps.SelectSocketMap)
