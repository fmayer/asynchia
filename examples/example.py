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

from asynchia.util import b, byte_std

class SendAllTransport(asynchia.SendallTrait, asynchia.SocketTransport):
    pass


class EchoClient(asynchia.Handler):
    def handle_connect(self):
        self.transport.sendall(b("Foo\n"))


class Echo(asynchia.Handler):
    def __init__(self, transport=None):
        asynchia.Handler.__init__(self, transport)
        if not self.transport.readable:
            self.transport.set_readable(True)
        self.transport.set_writeable(False)
        
    def handle_read(self):
        read = self.transport.recv(4096)
        byte_std(sys.stdout).write(read)
        byte_std(sys.stdout).flush()
    
    def handle_cleanup(self):
        print "Goodbye"


class EchoAcceptor(asynchia.AcceptHandler):
    def handle_accept(self, sock, addr):
        Echo(
            asynchia.SocketTransport(
                self.transport.socket_map, sock
            )
        )


if __name__ == '__main__':
    # This should show "Foo" in your console.
    # When you close this program, it should print "Goodbye".
    m = asynchia.maps.DefaultSocketMap()
    a = EchoAcceptor(asynchia.SocketTransport(m))
    a.transport.reuse_addr()
    a.transport.bind(('127.0.0.1', 25000))
    a.transport.listen(0)
    
    h = EchoAcceptor(a)
    
    a.transport.set_writeable(False)
    
    c = EchoClient(SendAllTransport(m))
    c.transport.connect(('127.0.0.1', 25000))
    
    c.transport.set_writeable(False)
    
    try:
        print m.run()
    finally:
        m.close()
