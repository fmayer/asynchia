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


class BufferedSendHandler(asynchia.IOHandler):
    """ Buffer the data that's sent if it couldn't be sent as
    one piece. """
    def __init__(self, socket_map, sock):
        asynchia.IOHandler.__init__(self, socket_map, sock)
        self.write_buffer = ''
    
    def sendall(self, data):
        """ Write data, if necessary, over multiple send calls. """
        self.write_buffer += data
        if data and not self.writeable:
            self.set_writeable(True)
    
    def handle_write(self):
        """ Do not override. """
        sent = self.send(self.write_buffer)
        self.write_buffer = self.write_buffer[sent:]
        if not self.write_buffer and self.writeable:
            self.set_writeable(False)
            self.buffer_empty()
    
    def buffer_empty(self):
        """ Callback that is called when the buffer becomes empty. """


class LineHandler(BufferedSendHandler):
    """ Use this for line-based protocols. """
    delimiter = None
    buffer_size = 4096
    def __init__(self, socket_map, sock):
        BufferedSendHandler.__init__(self, socket_map, sock)
        self.read_buffer = ''
        if not self.readable:
            self.set_readable(True)
    
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
    
    def send_line(self, line):
        """ Send line. """
        self.sendall(line + self.delimiter)
    
    def line_received(self, line):
        """ Override. """
        pass
