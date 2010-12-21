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

import time
import itertools

import asynchia.protocols

from benchutil import *


def _mk_parser(col, mp, size, lines):
    class Handler(asynchia.protocols.LineHandler):
        delimiter = '\n'
        def __init__(self, transport):
            asynchia.protocols.LineHandler.__init__(self, transport)
            self.n = 0
        
        def line_received(self, line):
            self.n += 1
            if self.n == lines:
                col.submit(time.time())
    data = '\n'.join(
        os.urandom(size).replace('\n', '\0')
        for _ in xrange(lines)
    ) + '\n'
    trnsp = mock_handler(mp, data)
    
    Handler(trnsp)


if __name__ == '__main__':
    if len(sys.argv) >= 4:
        sample = int(sys.argv[1])
        len_ = int(sys.argv[2])
        lines = int(sys.argv[3])
    else:
        sample = 50
        len_ = 50000
        lines = 10
    print sample, len_, lines
    run(_mk_parser, sample, len_, lines)
