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
    c.send()
    # Network I/O complete.
    a.submit('blub')
"""

import threading

import asynchia
from asynchia.util import b

_NULL = object()
SUCCESS = object()
ERROR = object()

class CoroutineReturn(BaseException):
    pass


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
    def __init__(self, itr, socket_map, pcontext=None, deferred=None):
        self.itr = itr
        if deferred is None:
            deferred = FireOnceDeferred(socket_map)
        self.deferred = deferred
        self.pcontext = pcontext
    
    def send(self, data=None):
        """ Start (or resume) execution of the coroutine. """
        if data is None:
            status, data = SUCCESS, None
        else:
            status, data = data
        try:
            if status is SUCCESS:
                result = self.itr.send(data)
            else:
                result = self.itr.throw(data)
        except StopIteration, e:
            self.deferred.submit_success(None)
        except CoroutineReturn, e:
            self.deferred.submit_success(e.args[0])
        except Exception, e:
            self.deferred.submit_error(e)
        else:
            if result is None:
                if self.pcontext is not None:
                    self.pcontext.pause(self)
                else:
                    raise ValueError("No PauseContext.")
            else:
                result.success_signal.listen(self.success_databack)
                result.error_signal.listen(self.error_databack)
    
    __call__ = send
    
    def success_databack(self, data=None):
        self.send((SUCCESS, data))
    
    def error_databack(self, data=None):
        self.send((ERROR, data))
    
    @classmethod
    def call_itr(cls, itr, socket_map):
        """ Create a coroutine from the given iterator, start it
        and return the DataNotifier. """
        coroutine = cls(itr, socket_map)
        coroutine.send()
        return coroutine.deferred
    
    @staticmethod
    def return_(obj):
        raise CoroutineReturn(obj)
    
    def wait(self):
        self.deferred.wait()
        if self.deferred.error_signal.data is not _NULL:
            # first element of args
            raise self.deferred.error_signal.data[0][0]
        if self.deferred.success_signal.data is not _NULL:
            return self.deferred.success_signal.data[0][0]


class Signal(object):
    def __init__(self, socket_map):
        self.listeners = []
        self.socket_map = socket_map
    
    def fire(self, *args, **kwargs):
        for listener in self.listeners:
            listener(*args, **kwargs)
    
    def fire_synchronized(self, *args, **kwargs):
        self.socket_map.call_synchronized(
            lambda: self.fire(*args, **kwargs)
        )
    
    def listen(self, listener):
        self.listeners.append(listener)


class FireOnceSignal(Signal):
    def __init__(self, socket_map):
        super(FireOnceSignal, self).__init__(socket_map)
        self.data = _NULL
        self.event = threading.Event()
        self.finished = False
    
    def fire(self, *args, **kwargs):
        super(FireOnceSignal, self).fire(*args, **kwargs)
        
        self.data = (args, kwargs)
        self.finished = True
        self.event.set()
    
    def listen(self, listener):
        if self.data is _NULL:
            super(FireOnceSignal, self).listen(listener)
        else:
            args, kwargs = self.data
            listener(*args, **kwargs)


class Deferred(object):
    def __init__(self, socket_map, success=None, error=None):
        if success is None:
            success = FireOnceSignal(socket_map)
        if error is None:
            error = FireOnceSignal(socket_map)
        self.success_signal = success
        self.error_signal = error
    
    def submit_error(self, *args, **kwargs):
        self.error_signal.fire(*args, **kwargs)
    
    def submit_success(self, *args, **kwargs):
        self.success_signal.fire(*args, **kwargs)
    
    def success(self, callback):
        self.success_signal.listen(callback)
        return self
    
    def error(self, callback):
        self.error_signal.listen(callback)
        return self
    
    def __call__(self, *args, **kwargs):
        self.success(*args, **kwargs)
    
    @staticmethod
    def _coroutine(obj, fun, args, kwargs):
        """ Implementation detail. """
        try:
            obj.submit_success(fun(*args, **kwargs))
        except Exception, e:
            obj.submit_error(e)
    
    @classmethod
    def threaded_coroutine(cls, socket_map, fun, *args, **kwargs):
        """ Run fun(*args, **kwargs) in a thread and return a DataNotifier
        notifying upon availability of the return value of the function. """
        obj = cls(socket_map)
        threading.Thread(
            target=cls._coroutine, args=(obj, fun, args, kwargs)
        ).start()
        return obj


class FireOnceDeferred(Deferred):
    def __init__(self, *args, **kwargs):
        super(FireOnceDeferred, self).__init__(*args, **kwargs)
        self.event = threading.Event()
    
    def submit_error(self, *args, **kwargs):
        super(FireOnceDeferred, self).submit_error(*args, **kwargs)
        self.event.set()
    
    def submit_success(self, *args, **kwargs):
        super(FireOnceDeferred, self).submit_success(*args, **kwargs)
        self.event.set()
    
    def wait(self, timeout=None):
        self.event.wait(timeout)


if __name__ == '__main__':
    class HTTP404(Exception):
        pass
    
    a = Deferred(None)
    def bar():
        # Request result of network I/O.
        blub = (yield a)
        Coroutine.return_(blub)
    def foo():
        # Wait for completion of new coroutine which - in turn - waits
        # for I/O.
        try:
            blub = yield Coroutine.call_itr(bar(), None)
        except HTTP404:
            blub = 404
        Coroutine.return_("yay %s" % blub)
    
    c = Coroutine(foo(), None)
    c.send()
    # Network I/O complete.
    a.submit_success('yay')
    print c.wait()
