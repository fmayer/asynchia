# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2009 Florian Mayer <florian.mayer@bitsrc.org>

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

import asynchia.ee
import asynchia.maps
import asynchia.util

import benchutil

class SendAllTransport(asynchia.SendallTrait, asynchia.SocketTransport):
    pass


def mock_handler(mp, inbuf):
    a, b = asynchia.util.socketpair()
    sender = SendAllTransport(mp, a)
    sender.sendall(inbuf)
    
    recvr = asynchia.SocketTransport(mp, b)
    return recvr


class ParseEE(benchutil.AsyncBenchmark):
    def __init__(self, mp, size):
        self.trnsp = mock_handler(mp, os.urandom(size))
        sub = itertools.repeat(range(250, 20000))
        chunks = []
        x = size
        while x > 0:
            chunks.append(min(x, sub.next()))
            x -= chunks[-1]
    
        self.ptcl = reduce(
            operator.add,
            map(asynchia.ee.DelimitedStringCollector, chunks)
        )
        
        self.ptcl.onclose = lambda _: self.submit_async(time.time())
    
    def run(self):
        hndl = asynchia.ee.Handler(self.trnsp, self.ptcl)


def done(_):
    raise asynchia.SocketMapClosedError


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        sample = int(sys.argv[1])
        len_ = int(sys.argv[2])
    else:
        sample = 50
        len_ = 5000000
    mp = asynchia.maps.DefaultSocketMap()
    run = benchutil.Runner([ParseEE(mp, len_) for _ in xrange(sample)], done)
    run.start()
    mp.run()
    print run.result
