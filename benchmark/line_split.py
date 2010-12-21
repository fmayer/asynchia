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
import itertools

import benchutil

import asynchia.maps
import asynchia.protocols

class SendAllTransport(asynchia.SendallTrait, asynchia.SocketTransport):
    pass


def mock_handler(mp, inbuf):
    a, b = asynchia.util.socketpair()
    sender = SendAllTransport(mp, a)
    sender.sendall(inbuf)
    
    recvr = asynchia.SocketTransport(mp, b)
    return recvr


class Handler(asynchia.protocols.LineHandler):
    delimiter = '\n'
    def __init__(self, transport, lines, bench):
        asynchia.protocols.LineHandler.__init__(self, transport)
        self.n = 0
        self.lines = lines
        self.bench = bench
    
    def line_received(self, line):
        self.n += 1
        if self.n == self.lines:
            self.bench.submit_async(time.time())


class ParseEE(benchutil.AsyncBenchmark):
    def __init__(self, mp, size, lines):

        data = '\n'.join(
            os.urandom(size).replace('\n', '\0')
            for _ in xrange(lines)
        ) + '\n'
        self.trnsp = mock_handler(mp, data)
        self.lines = lines
    
    def run(self):
        Handler(self.trnsp, self.lines, self)


def mkdone(mp):
    def done(_):
        mp.close()
    return done


if __name__ == '__main__':
    if len(sys.argv) >= 4:
        sample = int(sys.argv[1])
        len_ = int(sys.argv[2])
        lines = int(sys.argv[3])
    else:
        sample = 50
        len_ = 50000
        lines = 10
    mp = asynchia.maps.DefaultSocketMap()
    run = benchutil.Runner(
        [ParseEE(mp, len_, lines) for _ in xrange(sample)], mkdone(mp)
    )
    run.start()
    mp.run()
    print run.result
