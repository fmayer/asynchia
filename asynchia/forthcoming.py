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
from asynchia.util import b

_NULL = object()

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
        self.data = _NULL
        
        self.event = threading.Event()
        
        self.socket_map = socket_map
    
    def add_coroutine(self, coroutine):
        """ Add coroutine that waits for the submission of this data. """
        if self.data is _NULL:
            self.coroutines.append(coroutine)
        else:
            coroutine.send(self.data)
    
    def add_databack(self, callback):
        """ Add databack (function that receives the the data-notifier data
        upon submission as arguments). """
        if self.data is _NULL:
            self.dcallbacks.append(callback)
        else:
            callback(self.data)
    
    def add_callback(self, callback):
        """ Add callback (function that only receives the data upon
        submission as an argument). """
        if self.data is _NULL:
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
        self.socket_map.call_synchronized(lambda: self.submit(data))
    
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
        ).start()
        return datanot
