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
import sys
import time
import operator
import itertools
import threading

import asynchia
import asynchia.ee
import asynchia.maps
import asynchia.util


def mean(lst):
    return sum(lst) / float(len(lst))


def stdev(lst, sample=True, mean_=None):
    if mean_ is None:
        mean_ = mean(lst)
    return sum((x - mean_) ** 2 for x in lst) / float(len(lst) - int(sample))


class SendAllTransport(asynchia.SendallTrait, asynchia.SocketTransport):
    pass


def mock_handler(mp, inbuf):
    a, b = asynchia.util.socketpair()
    sender = SendAllTransport(mp, a)
    sender.sendall(inbuf)
    
    recvr = asynchia.SocketTransport(mp, b)
    return recvr


def until_done(fun):
    while True:
        d, s = fun()
        if d:
            break


class Col(object):
    def __init__(self, n):
        self.n = n
        self.times = []
        self.start = time.time()
    
    def submit(self, tme):
        self.times.append(tme)
        self.n -= 1
        if not self.n:
            data = [tme - self.start for tme in self.times]
            print mean(data)
            print stdev(data)
            print data
            sys.exit(0)


def timed(fun, *args, **kwargs):
    start = time.time()
    ret = fun(*args, **kwargs)
    stop = time.time()
    return ret, stop - start


def run(fun, n, *args):
    col = Col(n)
    mp = asynchia.maps.DefaultSocketMap()
    for _ in xrange(n):
        fun(col, mp, *args)
    mp.run()
