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
import asynchia.ee
import asynchia.maps
import asynchia.protocols


class EchoAcceptor(asynchia.AcceptHandler):
    def handle_accept(self, sock, addr):
        collector = asynchia.ee.FileCollector(sys.stdout, False)
        asynchia.ee.Handler(self.socket_map, sock, collector)
    
    def handle_error(self):
        raise


if __name__ == '__main__':
    # This should show "Foo" in your console.
    m = asynchia.maps.DefaultSocketMap()
    a = EchoAcceptor(m, socket.socket())
    a.reuse_addr()
    a.bind(('127.0.0.1', 25000))
    a.listen(0)
    
    c = asynchia.ee.Handler(m, socket.socket())
    c.connect(('127.0.0.1', 25000))
    c.send_input(asynchia.ee.StringInput("Foo\n"))
    
    try:
        m.run()
    finally:
        m.close()
