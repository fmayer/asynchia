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
import threading

import asynchia
import asynchia.maps

from nose.tools import eq_, assert_raises

def tes_interrupt(map_):
    container = type('Container', (object,), {})()
    container.flag = False
    mo = map_()
    def thread(container):
        mo.start_interrupt()
        try:
            time.sleep(4)
            pass
        finally:
            container.flag = True
            mo.end_interrupt()
    threading.Thread(target=thread, args=(container, )).start()
    mo.poll(None)
    eq_(container.flag, True)


cf_done = False
cf_thr = None
    
def tes_changeflag(map_):
    def subthread(mo, hand):
        time.sleep(1)
        mo.start_interrupt(True)
        try:
            hand.set_writeable(True)
        finally:
            mo.end_interrupt(True)
            mo
            pass
    
    
    class Serv(asynchia.Server):
        def __init__(
            self, socket_map, sock=None, handlercls=asynchia.IOHandler
            ):
            asynchia.Server.__init__(self, socket_map, sock, handlercls)
            self.clients = []
        
        def new_connection(self, handler, addr):
            self.clients.append(handler)
    
    
    class Handler(asynchia.IOHandler):    
        def handle_connect(self):
            global cf_thr
            cf_thr = threading.Thread(
                target=subthread, args=(self.socket_map, self)
            )
            cf_thr.start()
        
        def handle_write(self):
            global cf_done
            cf_done = True
        
        # Prevent exception from being suppressed.
        def handle_error(self):
            raise
    
    mo = map_()
    s = Serv(mo)
    s.bind(('127.0.0.1', 0))
    # We know we'll only get one connection.
    s.listen(1)
    
    c = Handler(mo)
    c.connect(s.socket.getsockname())
    i = 0
    while (not cf_done):
        mo.poll(None)
        i += 1
        if i > 10 ** 6:
            eq_(True, False, 'Timeout')
    cf_thr.join()    


def test_maps():
    maps = \
         (getattr(asynchia.maps, name) for name in 
          [
              'SelectSocketMap',
              'PollSocketMap',
              'EPollSocketMap',
          ]
          if hasattr(asynchia.maps, name)
          )
    tests = [tes_interrupt, tes_changeflag]
    for m in maps:
        for test in tests:
            yield test, m
    