# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2010 Florian Mayer

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

# This does currently not work, which is most probably due to a bug
# in the standard library.

import ssl
import _ssl

import asynchia
from asynchia.util import is_closed


class SSLSocketTransport(asynchia.SocketTransport):
    def __init__(self, socket_map, sock=None, handler=None,
                 keyfile=None, certfile=None, server_side=False,
                 cert_reqs=0, ssl_version=2, ca_certs=None):
        self.keyfile = keyfile
        self.certfile = certfile
        self.server_side = server_side
        self.cert_reqs = cert_reqs
        self.ssl_version = ssl_version
        self.ca_certs = ca_certs
        
        self.shook_hands = False
        
        asynchia.SocketTransport.__init__(self, socket_map, sock, handler)
        
        self.savedwrite = self.writeable
        self.savedread = self.readable
    
    def set_readable(self, value, nosave=False):
        if not nosave and not self.shook_hands:
            self.savedread = value
        else:
            asynchia.SocketTransport.set_readable(self, value)
    
    def set_writeable(self, value, nosave=False):
        if not nosave and not self.shook_hands:
            self.savedwrite = value
        else:
            asynchia.SocketTransport.set_writeable(self, value)
    
    def get_readable(self):
        return asynchia.SocketTransport.get_readable(self)
    
    def get_writeable(self):
        return asynchia.SocketTransport.get_writeable(self)
    
    def set_socket(self, sock):
        sock = ssl.wrap_socket(
                sock, self.keyfile, self.certfile, self.server_side,
                self.cert_reqs, self.ssl_version, self.ca_certs,
                do_handshake_on_connect=False
        )
        
        asynchia.SocketTransport.set_socket(self, sock)
    
    def _do_handshake(self):
        try:
            # Reset read- and writeability.
            self.set_readable(False, True)
            self.set_writeable(False, True)
            
            self.socket.do_handshake()
        
        except ssl.SSLError, err:
            if err.args[0] == ssl.SSL_ERROR_WANT_READ:
                self.set_readable(True, True)
            elif err.args[0] == ssl.SSL_ERROR_WANT_WRITE:
                self.set_writeable(True, True)
            else:
                raise
        
        else:       
            self.shook_hands = True
            self.set_writeable(self.savedwrite)
            self.set_readable(self.savedread)
            
            asynchia.SocketTransport.handle_connect(self)
    
    def handle_connect(self):        
        self.socket._sslobj = _ssl.sslwrap(
            self.socket._sock, False, self.socket.keyfile, self.socket.certfile,
            self.socket.cert_reqs, self.socket.ssl_version,
            self.socket.ca_certs
        )
        
        self.socket.getpeername()
        self._do_handshake()
        
    
    def handle_write(self):
        if self.shook_hands:
            asynchia.SocketTransport.handle_write(self)
        
        self._do_handshake()
    
    def handle_read(self):
        if self.shook_hands:
            asynchia.SocketTransport.handle_read(self)
        
        self._do_handshake()
    
    writeable = property(get_writeable, set_writeable)
    readable = property(get_readable, set_readable)
    
    def is_closed(self):
        return is_closed(self.socket._sock)


if __name__ == '__main__':
    import sys
    import asynchia.maps
    
    class Hand(asynchia.Handler):
        def handle_connect(self):
            print 'yay'
        def handle_read(self):
            sys.stdout.write(self.transport.recv(20))
    
    sm = asynchia.maps.DefaultSocketMap()
    ssltr = SSLSocketTransport(sm)
    print ssltr.socket
    ssltr.connect(('github.com', 443))
        
    Hand(ssltr)
    
    sm.run()
    
