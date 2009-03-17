# -*- coding: us-ascii *-*

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

""" Commonly used protocols. """

import asynchia


class BufferedWriteHandler(asynchia.IOHandler):
    """ Buffer the data that's sent if it couldn't be sent as
    one piece. """
    def __init__(self, socket_map, sock):
        asynchia.IOHandler.__init__(self, socket_map, sock)
        self.write_buffer = ''
    
    def buffered_write(self, data):
        """ Write data, if necessary, over multiple send calls. """
        self.write_buffer += data
    
    def writeable(self):
        """ If there's data in the buffer, we want to write. """
        return bool(self.write_buffer)
    
    def handle_write(self):
        """ Do not override. """
        sent = self.send(self.write_buffer)
        self.write_buffer = self.write_buffer[sent:]


class LineHandler(BufferedWriteHandler):
    """ Use this for line-based protocols. """
    delimiter = None
    buffer_size = 4096
    def __init__(self, socket_map, sock):
        BufferedWriteHandler.__init__(self, socket_map, sock)
        self.read_buffer = ''
    
    def split_buffer(self):
        """ Split buffer into the different lines. """
        split = self.read_buffer.split(self.delimiter)
        self.read_buffer = split.pop()
        return split
    
    def parse_buffer(self):
        """ Call the line_received method for any lines delimited by
        self.delimited that are in the buffer. """
        for line in self.split_buffer():
            self.line_received(line)
    
    def handle_read(self):
        """ We got inbound data. Extend our buffer and see if we have
        got lines in it. """
        self.read_buffer += self.recv(self.buffer_size)
        self.parse_buffer()
    
    def line_received(self, line):
        """ Override. """
        pass
