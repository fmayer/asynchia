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

import os
import time
import operator
import itertools
import threading

import asynchia
import asynchia.ee
import asynchia.maps
import asynchia.util


class SendAllTransport(asynchia.SendallTrait, asynchia.SocketTransport):
    pass


def mock_handler(inbuf):
    mp = asynchia.maps.DefaultSocketMap()
    
    a, b = asynchia.util.socketpair()
    sender = SendAllTransport(mp, a)
    sender.sendall(inbuf)
    
    recvr = asynchia.SocketTransport(mp, b)
    return recvr, mp

    
def until_done(fun):
    while True:
        d, s = fun()
        if d:
            break


def timed(fun, *args, **kwargs):
    start = time.time()
    ret = fun(*args, **kwargs)
    stop = time.time()
    return ret, stop - start


def parse_strings(size):
    trnsp = asynchia.ee.MockHandler(os.urandom(size))
    sub = itertools.repeat(range(20))
    chunks = []
    x = size
    while x > 0:
        chunks.append(min(x, sub.next()))
        x -= chunks[-1]

    ptcl = reduce(
        operator.add,
        map(asynchia.ee.DelimitedStringCollector, chunks)
    )
    
    until_done(lambda: ptcl.add_data(trnsp, 1024))


print timed(parse_strings, 10000000)
    
    