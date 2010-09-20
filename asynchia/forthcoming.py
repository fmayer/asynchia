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

""" Facilities to refer to data that is not yet available.

Example:

    # Usually acquired by a call that results in network I/O.
    # Global variable for demostration purposes.
    a = DataNotifier()
    def bar():
        # Request result of network I/O.
        blub = yield a
        yield Coroutine.return_(blub)
    def foo():
        # Wait for completion of new coroutine which - in turn - waits
        # for I/O. 
        blub = yield Coroutine.call_itr(bar())
        print "yay %s" % blub
    
    c = Coroutine(foo())
    c.call()
    # Network I/O complete.
    a.submit('blub')
"""

import os
import threading
try:
    import multiprocessing
except ImportError:
    multiprocessing = None
else:
    import socket
    import pickle

import asynchia
from asynchia.util import b

class PauseContext(object):
    """ Collection of Coroutines which are currently paused but not waiting
    for any data. They are paused to prevent too much time to be spent in
    them, preventing possibly important I/O from being done. """
    def __init__(self):
        self.paused = []
    
    def unpause(self):
        """ Continue all paused coroutines. """
        for coroutine in self.paused:
            coroutine.call()
        self.paused[:] = []
    
    def pause(self, coroutine):
        """ Add coroutine to the list of paused coroutines. """
        self.paused.append(coroutine)


class Coroutine(object):
    """ Create coroutine from given iterator. Yielding None will pause the co-
    routine until continuation by the given PauseContext. Yielding a
    DataNotifier will send the requested value to the coroutine once
    available. Yielding an instance of Coroutine.return_ will end execution
    of the coroutine and send the return value to any coroutines that may be
    waiting for it or calls any callbacks associated with it. """
    class return_:
        """ Yield an instance of this to signal that the coroutine finished
        with the given return value (defaults to None). """
        def __init__(self, obj=None):
            self.obj = obj
    
    def __init__(self, itr, pcontext=None, datanotifier=None):
        self.itr = itr
        if datanotifier is None:
            datanotifier = DataNotifier()
        self.datanotifier = datanotifier
        self.pcontext = pcontext
    
    def send(self, data):
        """ Send requested data to coroutine. """
        try:
            self.handle_result(self.itr.send(data))
        except StopIteration:
            self.datanotifier.submit(None)
    
    def call(self):
        """ Start (or resume) execution of the coroutine. """
        try:
            self.handle_result(self.itr.next())
        except StopIteration:
            self.datanotifier.submit(None)
    
    def handle_result(self, result):
        """ Internal. """
        if result is None:
            if self.pcontext is not None:
                self.pcontext.pause(self)
            else:
                raise ValueError("No PauseContext.")
        elif isinstance(result, Coroutine.return_):
            self.datanotifier.submit(result.obj)
        else:
            result.add_coroutine(self)
    
    @classmethod
    def call_itr(cls, itr):
        """ Create a coroutine from the given iterator, start it
        and return the DataNotifier. """
        coroutine = cls(itr)
        coroutine.call()
        return coroutine.datanotifier


class DataNotifier(object):
    """ Call registered callbacks and send data to registered coroutines
    at submission of data. """
    def __init__(self, socket_map):
        self.dcallbacks = []
        self.rcallbacks = []
        self.coroutines = []
        self.finished = False
        self.data = None
        
        self.event = threading.Event()
        
        self.wakeup, other = asynchia.util.socketpair()
        self.handler = _ThreadedDataHandler(
            asynchia.SocketTransport(socket_map, other),
            self
        )
    
    def add_coroutine(self, coroutine):
        """ Add coroutine that waits for the submission of this data. """
        if self.data is None:
            self.coroutines.append(coroutine)
        else:
            coroutine.send(self.data)
    
    def add_databack(self, callback):
        """ Add databack (function that receives the the data-notifier data
        upon submission as arguments). """
        if self.data is None:
            self.dcallbacks.append(callback)
        else:
            callback(self.data)
    
    def add_callback(self, callback):
        """ Add callback (function that only receives the data upon
        submission as an argument). """
        if self.data is None:
            self.rcallbacks.append(callback)
        else:
            callback(self, self.data)
    
    def poll(self):
        """ Poll whether result has already been submitted. """
        return self.finished
    
    def submit(self, data):
        """ Submit data; send it to any coroutines that may be registered and
        call any data- and callbacks that may be registered. """
        self.data = data
        for callback in self.dcallbacks:
            callback(data)
        for callback in self.rcallbacks:
            callback(self, data)
        for coroutine in self.coroutines:
            coroutine.send(data)
        
        self.coroutines[:] = []
        self.rcallbacks[:] = []
        self.dcallbacks[:] = []
        
        # Wake up threads waiting for the data.
        self.event.set()
        
        self.finished = True
    
    def inject(self, data):
        """ Submit data and ensure their callbacks are called in the main
        thread. """
        self.injected = data
        self.wakeup.send(b('a'))
    
    def wait(self, timeout=None):
        """ Block execution of current thread until the data is available.
        Return requested data. """
        self.event.wait(timeout)
        return self.data
    
    @staticmethod
    def _coroutine(datanotifier, fun, args, kwargs):
        """ Implementation detail. """
        datanotifier.inject(fun(*args, **kwargs))
    
    @classmethod
    def threaded_coroutine(cls, socket_map, fun, *args, **kwargs):
        """ Run fun(*args, **kwargs) in a thread and return a DataNotifier
        notifying upon availability of the return value of the function. """
        datanot = cls(socket_map)
        threading.Thread(
            target=cls._coroutine, args=(datanot, fun, args, kwargs)
        )
        return datanot



if multiprocessing is not None:
    class _MPServerHandler(asynchia.Handler):
        BUFFER = 2048
        def __init__(self, tr, notifier, pwd):
            asynchia.Handler.__init__(self, tr)
            self.notifier = notifier
            self.data = ''
            self.pwd = pwd
            
            self.transport.set_readable(True)
        
        def handle_read(self):
            self.data += self.transport.recv(self.BUFFER)
        
        def handle_close(self):
            if self.data[:len(self.pwd)] == self.pwd:
                self.notifier.submit(pickle.loads(self.data[len(self.pwd):]))
    
    
    class _MPServer(asynchia.Server):
        def __init__(self, transport, notifier, pwd):
            asynchia.Server.__init__(
                self, transport, lambda tr: _MPServerHandler(tr, notifier, pwd)
            )
        
        def new_connection(self, handler, addr):
            self.transport.close()
    
    
    def _mp_client(fun, args, kwargs, addr, pwd):
        sock = socket.socket()
        sock.connect(addr)
        
        data = pwd + pickle.dumps(fun(*args, **kwargs))
        while data:
            sent = sock.send(data)
            data = data[sent:]
        
        sock.close()
        
    
    class MPNotifier(DataNotifier):
        def __init__(self, socket_map, fun, args=None, kwargs=None, pwdstr=10):
            DataNotifier.__init__(self, socket_map)
            
            if args is None:
                args = tuple()
            if kwargs is None:
                kwargs = {}
            pwd = os.urandom(pwdstr)
            
            serv = _MPServer(
                asynchia.SocketTransport(socket_map), self, pwd
            )
            serv.transport.bind(('127.0.0.1', 0))
            serv.transport.listen(1)
        
            # MPDataNotifier?
            self.proc = multiprocessing.Process(
                target=_mp_client,
                args=(fun, args, kwargs,
                      serv.transport.socket.getsockname(), pwd
                )
            )
            
            self.proc.start()


class _ThreadedDataHandler(asynchia.Handler):
    """ Implementation detail. """
    def __init__(self, transport, datanotifier):
        asynchia.Handler.__init__(self, transport)
        self.transport.set_readable(True)
        
        self.datanotifier = datanotifier
    
    def handle_read(self):
        """ Implementation detail. """
        self.transport.recv(1)
        self.datanotifier.submit(self.datanotifier.injected)
        # Not needed anymore.
        self.transport.close()
