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

import asynchia.ee

from benchutil import *


def _mk_parser(col, mp, size):
    trnsp = mock_handler(mp, os.urandom(size))
    sub = itertools.repeat(range(250, 20000))
    chunks = []
    x = size
    while x > 0:
        chunks.append(min(x, sub.next()))
        x -= chunks[-1]

    ptcl = reduce(
        operator.add,
        map(asynchia.ee.DelimitedStringCollector, chunks)
    )
    
    def _cls(x):
        col.submit(time.time())
    
    ptcl.onclose = _cls
    
    hndl = asynchia.ee.Handler(trnsp, ptcl)


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        sample = int(sys.argv[1])
        len_ = int(sys.argv[2])
    else:
        sample = 50
        len_ = 5000000
    run(_mk_parser, sample, len_)
