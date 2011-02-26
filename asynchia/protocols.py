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

""" Commonly used protocols. """

import asynchia
from asynchia.util import EMPTY_BYTES
from asynchia.buffer import BufferQ, NaiveBuffer

class LineHandler(asynchia.Handler):
    """ Use this for line-based protocols. """
    delimiter = None
    buffer_size = 4096
    def __init__(self, transport=None):
        asynchia.Handler.__init__(self, transport)
        self.read_buffer = NaiveBuffer()
        if not self.transport.readable:
            self.transport.set_readable(True)
    
    def parse_buffer(self):
        """ Call the line_received method for any lines delimited by
        self.delimited that are in the buffer. """
        for line in self.read_buffer.splitall(self.delimiter):
            self.line_received(line)
    
    def handle_read(self):
        """ We got inbound data. Extend our buffer and see if we have
        got lines in it. """
        self.read_buffer.add_data(self.transport, self.buffer_size)
        self.parse_buffer()
    
    def send_line(self, line):
        """ Send line. To use this SendallTrait must be mixed into
        your transport! """
        self.transport.sendall(line + self.delimiter)
    
    def line_received(self, line):
        """ Override. """
        pass
