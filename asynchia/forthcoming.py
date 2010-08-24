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

import threading

import asynchia

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
        self.handler = ThreadedDataHandler(
            asynchia.SocketTransport(socket_map, other),
            self
        )
    
    def add_coroutine(self, coroutine):
        """ Add coroutine that waits for the submission of this data. """
        self.coroutines.append(coroutine)
    
    def add_databack(self, callback):
        """ Add databack (function that receives the the data-notifier data
        upon submission as arguments). """
        self.dcallbacks.append(callback)
    
    def add_callback(self, callback):
        """ Add callback (function that only receives the data upon
        submission as an argument). """
        self.rcallbacks.append(callback)
    
    # Good idea?
    def poll(self):
        """ Poll whether result has already been submitted. """
        return self.finished
    
    def submit(self, data):
        """ Submit data; send it to any coroutines that may be registered and
        call any data- and callbacks that may be registered. """
        # Good idea?
        self.data = data
        for callback in self.dcallbacks:
            callback(data)
        for callback in self.rcallbacks:
            callback(self, data)
        for coroutine in self.coroutines:
            coroutine.send(data)
        # Good idea?
        self.coroutines[:] = []
        
        self.event.set()
        self.data = None
        
        self.finished = True
    
    def inject(self, data):
        self.injected = data
        self.wakeup.send('a')
    
    def wait(self, timeout=None):
        """ Block execution of current thread until the data is available.
        Return requested data. """
        self.event.wait(timeout)
        return self.data


class ThreadedDataHandler(asynchia.Handler):
    def __init__(self, transport, datanotifier):
        asynchia.Handler.__init__(self, transport)
        self.transport.set_readable(True)
        
        self.datanotifier = datanotifier
    
    def handle_read(self):
        self.transport.recv(1)
        self.datanotifier.submit(self.datanotifier.injected)
