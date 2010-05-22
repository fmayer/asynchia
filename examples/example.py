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

""" Server that prints everything it receives to standard output. """


import sys
import socket
import traceback

import asynchia
import asynchia.maps
import asynchia.protocols


class EchoClient(asynchia.IOHandler):
    def handle_connect(self):
        self.send("Foo\n")


class Echo(asynchia.IOHandler):
    def __init__(self, socket_map, sock):
        asynchia.IOHandler.__init__(self, socket_map, sock)
        if not self.readable:
            self.set_readable(True)
        
    def handle_read(self):
        read = self.recv(4096)
        sys.stdout.write(read)
        sys.stdout.flush()
    
    def handle_cleanup(self):
        print "Goodbye"


class EchoAcceptor(asynchia.AcceptHandler):
    def handle_accept(self, sock, addr):
        Echo(self.socket_map, sock)


if __name__ == '__main__':
    # This should show "Foo" in your console.
    # When you close this program, it should print "Goodbye".
    m = asynchia.maps.DefaultSocketMap()
    a = EchoAcceptor(m, socket.socket())
    a.reuse_addr()
    a.bind(('127.0.0.1', 25000))
    a.listen(0)
    
    c = EchoClient(m, socket.socket())
    c.connect(('127.0.0.1', 25000))
    
    try:
        m.run()
    finally:
        m.close()
