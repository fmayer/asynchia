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

import itertools

from collections import deque

from asynchia.util import EMPTY_BYTES

class NaiveBuffer(object):
    def __init__(self, data=EMPTY_BYTES):
        self.buf = data
    
    def read(self, nbytes):
        data = self.buf[:min(len(self.buf), nbytes)]
        self.buf = self.buf[min(len(self.buf), nbytes):]
        return data
    
    def put(self, data):
        self.buf += data
    
    def add_data(self, tnsp, nbytes):
        rcv = tnsp.recv(nbytes)
        self.buf += rcv
        return False, rcv
    
    def splitfront(self, at):
        split = self.buf.split(1)
        self.buf = split[-1]
        return split[:-1]
    
    def splitall(self, at):
        split = self.buf.split()
        self.buf = split[-1]
        return split[:-1]


class ByteArrayBuffer(object):
    def __init__(self, size):
        self.pos = self.len_ = self.extended = 0
        self.size = size
        
        self.array = bytearray(size)
    
    def extend(self, n):
        self.array.extend(itertools.repeat(0, n))
        self.size += n
        self.extended += 1
    
    def read(self, nbytes=None):
        if nbytes is not None:
            n = min(nbytes, self.len_ - self.pos)
        else:
            n =  self.len_ - self.pos
        
        data = self.array[self.pos: self.pos + n]
        self.pos += n
        
        return self.pos == self.size, data
    
    def splitfront(self, at):
        pos = self.array[self.pos:].find(at)
        if pos == -1:
            return self.pos == self.size, None
        
        return self.read(pos + len(at))
    
    def splitall(self, at):
        while True:
            split = self.splitfront(at)
            if split is not None:
                yield split
            else:
                break
    
    def put(self, data):
        data = data[: self.size - self.len_]
        self.array[self.len_: self.len_ + len(data)] = data
        self.len_ += len(data)
        return self.len_ == self.size, len(data)
    
    def memoryview(self):
        return memoryview(self.array)[self.len_:]
    
    def add_data(self, tnsp, nbytes):
        try:
            mv = self.memoryview()
        except NameError:
            return self.put(
                tnsp.recv(min(nbytes, self.size - self.len_))
            )
        else:
            recv = tnsp.recv_into(mv, min(nbytes, self.size - self.len_))
            self.len_ += recv
            return self.len_ == self.size, recv
    

class BufferQ(object):
    def __init__(self, size):
        self.size = size
        
        buf = ByteArrayBuffer(size)
        self.rbuffers = deque([buf])
        self.wbuffers = deque([buf])
    
    def _read_done(self):
        self.rbuffers.popleft()
    
    def _write_done(self):
        self.wbuffers.popleft()
            
        if not self.wbuffers:
            buf = ByteArrayBuffer(self.size)
            self.rbuffers.append(buf)
            self.wbuffers.append(buf)
    
    def read(self, nbytes):
        data = bytearray(0)
        while len(data) < nbytes:
            done, rdata = self.rbuffers[0].read(nbytes)
            if done:
                self._read_done()
            if not rdata:
                break
            else:
                data += rdata
        return data
    
    def put(self, data):
        while data:
            done, recv = self.wbuffers[0].put(data)
            if done:
                self._write_done()
            data = data[recv:]
    
    def add_data(self, tnsp, nbytes):
        done, recv = self.wbuffers[0].add_data(tnsp, nbytes)
        if done:
            self._write_done()
        return done, recv
    
    def splitall(self, at):
        while True:
            split = self.splitfront(at)
            if split is not None:
                yield split
            else:
                break
    
    def splitfront(self, at):
        n = 0
        lastread = 0
        while True:
            done, split = self.rbuffers[n].splitfront(at)
            if split is not None:
                if n > 0 and lastread < n:
                    old = bytearray()
                    for i in xrange(lastread, n):
                        old += self.rbuffers[i].read()[1]
                    split = old + split
                return split
            else:
                if n == len(self.rbuffers) - 1:
                    break
                else:
                    n += 1
