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

import copy
import threading
import itertools

import asynchia
from asynchia.util import b

_NULL = object()
SUCCESS = object()
ERROR = object()

class CoroutineReturn(BaseException):
    pass


class Escape(object):
    """ Prevent the return value of a callback from being treated specially if
    it is a Deferred """
    def __init__(self, deferred):
        self.deferred = deferred


class Coroutine(object):
    """ Create coroutine from given iterator. Yielding None will pause the co-
    routine until continuation by the given PauseContext. Yielding a
    DataNotifier will send the requested value to the coroutine once
    available. Yielding an instance of Coroutine.return_ will end execution
    of the coroutine and send the return value to any coroutines that may be
    waiting for it or calls any callbacks associated with it. """    
    def __init__(self, itr, deferred=None):
        self.itr = itr
        if deferred is None:
            deferred = Deferred()
        self.deferred = deferred
    
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
            result.callbacks.add(self.success_databack, self.error_databack)
    
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
    
    def synchronize(self, timeout=None):
        return self.deferred.synchronize(timeout)


class Signal(object):
    def __init__(self):
        self.listeners = []
        self.once_listeners = []
    
    def fire(self, *args, **kwargs):
        for listener in itertools.chain(self.listeners, self.once_listeners):
            listener(*args, **kwargs)
        
        self.once_listeners[:] = []
    
    def listen(self, listener):
        self.listeners.append(listener)
    
    def listen_once(self, listener):
        self.once_listeners.append(listener)


class Node(object):
    def __init__(self, callback=None, errback=None, children=None):
        if children is None:
            children = []
        self.children = children
        self.cachedsuccess = self.cachederror = _NULL
        
        self.event = threading.Event()
        
        if errback is None:
            errback = self.default_errback
        if callback is None:
            callback = self.default_callback
        self._callback = callback
        self._errback = errback
    
    def copy(self):
        return self.__class__(
            self._callback, self._errback, [c.copy() for c in self.children]
        )
    
    def success_callback(self, data):
        for child in self.children:
            child.success(data)
        self.cachedsuccess = data
        self.event.set()
    
    def error_callback(self, data):
        for child in self.children:
            child.err(data)
        self.cachederror = data
        self.event.set()
    
    def add(self, callback=None, errback=None, children=None):
        node = Node(callback, errback, children)
        if self.cachedsuccess is not _NULL:
            node.success(self.cachedsuccess)
        elif self.cachederror is not _NULL:
            node.err(self.cachederror)
        else:
            self.children.append(node)
        return node
    
    def add_blueprint(self, node):
        node = node.copy()
        
        if self.cachedsuccess is not _NULL:
            node.success(self.cachedsuccess)
        elif self.cachederror is not _NULL:
            node.err(self.cachederror)
        else:
            self.children.append(node)
        return node
    
    def wait(self, timeout=None):
        self.event.wait(timeout)
    
    def synchronize(self, timeout=None):
        self.wait(timeout)
        if self.cachederror is not _NULL:
            raise self.cachederror
        if self.cachedsuccess is not _NULL:
            return self.cachedsuccess
    
    def visit(self, callback, *args, **kwargs):
        try:
            value = callback(*args, **kwargs)
        except Exception, e:
            self.error_callback(e)
        else:
            if isinstance(value, Deferred):
                value.callbacks.add(
                    self.success_callback, self.error_callback
                )
            else:
                if isinstance(value, Escape):
                    value = value.deferred
                self.success_callback(value)
    
    def success(self, *args, **kwargs):
        self.visit(self._callback, *args, **kwargs)
    
    def err(self, data):
        self.visit(self._errback, data)

    @staticmethod
    def default_errback(err):
        raise err
    
    @staticmethod
    def default_callback(value):
        return value
    
    def errback(self, errback):
        self._errback = errback
        return self
    
    def callback(self, callback):
        self._callback = callback
        return self
    
    def wrap(self):
        def _fun(*args, **kwargs):
            return self(*args, **kwargs)
        return _fun
    
    __call__ = success
    


class Deferred(object):
    def __init__(self, callbacks=None):
        if callbacks is None:
            callbacks = Node() 
        self.callbacks = callbacks
    
    def submit_error(self, data):
        self.callbacks.error_callback(data)
    
    def submit_success(self, data):
        self.callbacks.success_callback(data)
    
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
    
    def wait(self, timeout=None):
        self.callbacks.wait(timeout)
    
    def synchronize(self, timeout=None):
        return self.callbacks.synchronize(timeout)
    
    @staticmethod
    def maybe(fun, *args, **kwargs):
        try:
            value = fun(*args, **kwargs)
        except Exception, e:
            return Deferred(Node(data=(ERROR, e)))
        else:
            if isinstance(value, Deferred):
                return value
            return Deferred(Node(data=(SUCCESS, value)))


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
    print c.synchronize()
    
    e = Deferred()
    def callb1(value):
        print value
        return e
    
    def callb2(value):
        print value
        return value + '2'
    
    d = Deferred()
    foo = d.callbacks.add(callb1).add(callb2).add(callb2)
    d.submit_success('hello')
    d.callbacks.add(callb1)
    
    print 'foo'
    e.submit_success('world')
    print 'bar'
    print foo.add(callb2).synchronize()
    
    f = Deferred()
    c = Node(lambda x, y: x + y)
    c.add(callb2)
    c.wrap()('foo', 'bar')
    f.submit_success('hey')

    d = Deferred()
    
    class Foo(object):
        c = Node(lambda self, y: d)
        c.add(callb2)
        
        c = c.wrap()
        
        def __init__(self, x):
            self.x = x
    
    f = Foo('foo')
    f.c('bar')
    f.c('baz')
    d.submit_success('foo')
    
    c = Node()
    c.add(callb2)
    
    a = Deferred()
    b = Deferred()
    
    print '--'
    n = Node()
    n.add(callb2)
    
    a.callbacks.add_blueprint(n)
    b.callbacks.add_blueprint(n).add(callb2)
    
    a.submit_success('foo')
    b.submit_success('bar')
