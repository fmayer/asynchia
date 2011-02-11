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

def _coroutine(obj, fun, args, kwargs):
    """ Implementation detail. """
    try:
        obj.success(fun(*args, **kwargs))
    except Exception, e:
        obj.err(e)


def threaded_coroutine(fun, *args, **kwargs):
    """ Run fun(*args, **kwargs) in a thread and return a DataNotifier
    notifying upon availability of the return value of the function. """
    obj = Deferred()
    threading.Thread(
        target=_coroutine, args=(obj, fun, args, kwargs)
    ).start()
    return obj


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
            self.deferred.success(None)
        except CoroutineReturn, e:
            self.deferred.success(e.args[0])
        except Exception, e:
            self.deferred.err(e)
        else:
            result.add(self.success_databack, self.error_databack)
    
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


class Blueprint(object):
    def __init__(self, callback=None, errback=None, children=None, refs=None):
        if refs is None:
            refs = {}
        
        if children is None:
            children = []
        self.children = children
        self.cachedsuccess = self.cachederror = _NULL
        
        self.event = threading.Event()
        
        if errback is None:
            errback = self._default_errback
        if callback is None:
            callback = self._default_callback
        self._callback = callback
        self._errback = errback
        
        self.refs = refs
    
    def instance(self):
        return Deferred(
            self._callback, self._errback,
            [c.instance() for c in self.children], copy.copy(self.refs)
        )
    
    def __copy__(self):
        return self.__class__(
            self._callback, self._errback,
            [copy.copy(c) for c in self.children], copy.copy(self.refs)
        )
    
    def add_node(self, node):
        node = copy.copy(node)
        if self.cachedsuccess is not _NULL:
            node.success(self.cachedsuccess)
        elif self.cachederror is not _NULL:
            node.err(self.cachederror)
        else:
            self.children.append(node)
        return node
    
    def add_chain(self, chain):
        node = self.add_node(chain)
        while True:
            try:
                node = node.children[0]
            except IndexError:
                break
        return node
    
    def add(self, callback=None, errback=None, children=None):
        node = self.__class__(callback, errback, children)
        return self.add_node(node)
    
    add_blueprint = add_node

    @staticmethod
    def _default_errback(err):
        raise err
    
    @staticmethod
    def _default_callback(value):
        return value
    
    def errback(self, errback):
        self._errback = errback
        return self
    
    def callback(self, callback):
        self._callback = callback
        return self
    
    def wrapinstance(self):
        # As self is no real callable, it does not get bound to
        # instances.
        def _fun(*args, **kwargs):
            node = self.instance()
            node(*args, **kwargs)
            return node
        return _fun
    
    def ref(self, item):
        for n, elem in enumerate(self.children):
            if elem is item:
                return [n]
            else:
                npos = elem.ref(item)
                if npos is not None:
                    return [n] + npos
    
    def deref(self, pos):
        item = self
        for n in pos:
            item = item.children[n]
        return item
    
    def __setitem__(self, name, item):
        self.refs[name] = self.ref(item)
    
    def __getitem__(self, name):
        return self.deref(self.refs[name])


class Chain(Blueprint):
    def add_node(self, node):
        if self.children:
            raise TypeError
        return super(Chain, self).add_node(node)


class Deferred(Blueprint):
    def wrap(self):
        # As self is no real callable, it does not get bound to
        # instances.
        def _fun(*args, **kwargs):
            return self(*args, **kwargs)
        return _fun
    
    def wait(self, timeout=None):
        self.event.wait(timeout)
    
    def synchronize(self, timeout=None):
        self.wait(timeout)
        if self.cachederror is not _NULL:
            raise self.cachederror
        if self.cachedsuccess is not _NULL:
            return self.cachedsuccess
    
    def _visit(self, callback, *args, **kwargs):
        try:
            value = callback(*args, **kwargs)
        except Exception, e:
            self._error_callback(e)
        else:
            if isinstance(value, Deferred):
                value.add(
                    self._success_callback, self._error_callback
                )
            else:
                if isinstance(value, Escape):
                    value = value.deferred
                self._success_callback(value)
    
    def success(self, *args, **kwargs):
        self._visit(self._callback, *args, **kwargs)
    
    def err(self, data):
        self._visit(self._errback, data)
    
    def add_blueprint(self, node):
        node = node.instance()
        
        if self.cachedsuccess is not _NULL:
            node.success(self.cachedsuccess)
        elif self.cachederror is not _NULL:
            node.err(self.cachederror)
        else:
            self.children.append(node)
        return node
    
    def add_chain(self, chain):
        return super(Deferred, self).add_chain(
            chain.instance()
        )
    
    def _success_callback(self, data):
        for child in self.children:
            child.success(data)
        self.cachedsuccess = data
        self.event.set()
    
    def _error_callback(self, data):
        for child in self.children:
            child.err(data)
        self.cachederror = data
        self.event.set()
    
    __call__ = success
