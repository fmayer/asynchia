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

""" Auxiliary functions. """

import sys
import errno
import math
import socket
import threading
import collections

import asynchia.const

class GradualAverage(object):
    """ Memory-efficient average to which values may gradually be added
    over time. Its value can be accessed via the avg member. """
    def __init__(self, values=None):
        if values is None:
            self.avg = self.len = 0.0
        else:
            self.len = float(len(values))
            self.avg = sum(values) / self.len
    
    def add_value(self, value):
        """ Add value to the average. """
        self.avg = (self.avg * self.len + value) / (self.len + 1)
        self.len += 1
    
    def add_values(self, values):
        """ Add values to the average. This is more effective than using
        add_value multiple times. """
        self.avg = (
            self.avg * self.len + sum(values)
            ) / (self.len + len(values))
        self.len += len(values)


class LimitedAverage(object):
    """ Average considering the last samples values added to it. Its value
    can be accessed via the avg member. Stores up to samples objects in a
    deque and thus has a higher memory usage than GradualAverage (and a
    different use case). """
    def __init__(self, samples, values=None):
        self.cache = None
        
        self.samples = samples
        if values is None:
            self.values = collections.deque()
        else:
            self.values = collections.deque(values)
        
            for _ in xrange(len(values) - samples):
                self.values.popleft()
    
    def add_value(self, value):
        """ Add value to the average. """
        # Invalidate possibly existing cache.
        self.cache = None
        if len(self.values) == self.samples:
            self.values.popleft()
        self.values.append(value)
    
    def add_values(self, values):
        """ Add values to the average. This is more effective than using
        add_value multiple times. """
        # Invalidate possibly existing cache.
        self.cache = None
        self.values.extend(values)
        for _ in xrange(len(values) - self.samples):
            self.values.popleft()
    
    @property
    def avg(self):
        if self.cache is not None:
            return self.cache
        else:
            self.cache = sum(self.values) / float(len(self.values))
            return self.cache


class IDPool(object):
    """
    Pool that returns unique identifiers in a thread-safe way.
    
    Identifierers obtained using the get method are guaranteed to not be
    returned by it again until they are released using the release method.
    
        >>> pool = IDPool()
        >>> pool.get()
        0
        >>> pool.get()
        1
        >>> pool.get()
        2
        >>> pool.release(1)
        >>> pool.get()
        1
        >>> 
    """
    def __init__(self):
        self.max_id = -1
        self.free_ids = []
        
        self._lock = threading.Lock()
    
    def get(self):
        """ Return a new integer that is unique in this pool until
        it is released. """
        self._lock.acquire()
        try:
            if self.free_ids:
                return self.free_ids.pop()
            else:
                self.max_id += 1
                return self.max_id
        finally:
            self._lock.release()
    
    def release(self, id_):
        """ Release the id. It can now be returned by get again.
        
        Will reset the IDPool if the last id in use is released. """
        self._lock.acquire()
        try:
            self.free_ids.append(id_)
            if len(self.free_ids) == self.max_id + 1:
                self.reset()
        finally:
            self._lock.release()
    
    def reset(self):
        """ Reset the state of the IDPool. This should only be called when
        no identifier is in use. """
        self.max_id = -1
        self.free_ids = []


def socketpair():
    """ Return pair of connected sockets. Unlike socket.socketpair this
    is platform independant. However, if socket.socketpair is available,
    it is used here as well. """
    if hasattr(socket, 'socketpair'):
        # Unix.
        return socket.socketpair()
    
    try:
        acceptor = socket.socket()
        # Random port. Only accept local connections.
        acceptor.bind(('127.0.0.1', 0))
        # We know we'll only get one connection.
        acceptor.listen(1)

        one = socket.socket()
        one.connect(acceptor.getsockname())
        
        other = acceptor.accept()[0]
    finally:
        acceptor.close()
    return one, other


def parse_ipv4(string, default_port=-1):
    """ Return (host, port) from IPv4 IP. """
    split = string.split(':')
    if len(split) == 1:
        return string, default_port
    elif len(split) == 2:
        return split[0], int(split[1])
    else:
        raise ValueError("Cannot interpret %r as IPv4 address!" % string)


def parse_ipv6(string, default_port=-1):
    """ Return (host, port) from IPv6 IP. """
    if '[' in string and ']' in string:
        split = string.split(']:')
        if len(split) == 1:
            return string[1: -1], default_port
        else:
            return split[0][1:], int(split[1])
    elif not '[' in string and not ']' in string:
        return string, default_port
    else:
        raise ValueError("Cannot interpret %r as IPv6 address!" % string)


def parse_ip(string, default_port=-1):
    """ Return (host, port) from input string. This tries to automatically
    determine whether the address is IPv4 or IPv6.
    
    If no port is found default_port, which defaults to -1 is used.
    
    >>> parse_ip('127.0.0.1:1234')
    ('127.0.0.1', 1234)
    >>> parse_ip('[2001:0db8:85a3:08d3:1319:8a2e:0370:7344]:443')
    ('2001:0db8:85a3:08d3:1319:8a2e:0370:7344', 443)
    """
    if string.count(':') > 1:
        return parse_ipv6(string, default_port)
    else:
        return parse_ipv4(string, default_port)


def goodsize(maxsize):
    """ Return biggest power of two that is less or equal to maxsize.
    
    Powers of two are considered good values to be passed to the recv
    method of sockets. To quote the python documentation of the socket
    module:

        For best match with hardware and network realities,
        the value of bufsize should be a relatively small power of 2,
        for example, 4096.
"""
    return 2 ** math.floor(math.log(maxsize, 2))


def is_closed(sock):
    """ Find out whether a socked is closed or not.
    Does only work on non-blocking sockets! """
    if sock.type != socket.SOCK_STREAM:
        raise ValueError("Socket is not stream socket.")
    
    try:
        rcv = sock.recv(1, socket.MSG_PEEK)
    except socket.error, err:
        if err.args[0] in asynchia.const.trylater:
            return False
        if err.args[0] == errno.ENOTCONN:
            return False
        else:
            raise
    else:
        return not rcv


def is_unconnected(sock):
    """ Find out whether a socket has not yet been connected.
    Does only work on non-blocking sockets! """
    if sock.type != socket.SOCK_STREAM:
        raise ValueError("Socket is not stream socket.")
    
    try:
        sock.recv(0)
    except socket.error, err:
        if err.args[0] == errno.ENOTCONN:
            return True
        elif err.args[0] in asynchia.const.trylater:
            return False
        else:
            raise
    return False


if sys.version_info >= (3, 0):
    def b(s):
        return s.encode('utf-8')
else:
    b = str


EMPTY_BYTES = b('')

if sys.version_info >= (3, 0):
    def byte_std(stream):
        return stream.buffer
else:
    def byte_std(stream):
        return stream
