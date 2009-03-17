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

""" asynchia is a minimalistic asynchronous networking library. """

import errno
import socket


connection_lost = (errno.ECONNRESET, errno.ENOTCONN,
                   errno.ESHUTDOWN, errno.ECONNABORTED)


class SocketMap:
    """ Decide which sockets have I/O to be done and tell the notifier
    to call the appropriate methods of their Handle objects. """
    def __init__(self, notifier=None):
        if notifier is None:
            notifier = Notifier()
        self.notifier = notifier
    
    def add_handler(self, obj):
        """ Add handler to the socket-map. This gives the SocketMap
        the responsibility to call its handle_read, handle_write,
        handle_close and handle_connect upon new I/O events. """
        raise NotImplementedError
    
    def del_handler(self, obj):
        """ Remove handler from the socket-map. It will no longer have its
        handle_read, handle_write, handle_close and handle_connect methods
        called upon new I/O events. """
        raise NotImplementedError


class Notifier:
    """ Call handle functions of the object with error handling. """
    @staticmethod
    def read_obj(obj):
        """ Call handle_read of the object. If any error occurs within it,
        call handle_error of the object. If it is the first read event call
        the handle_connect method. """
        if not obj.connected:
            obj.connected = True
            obj.handle_connect()
        
        if not obj.readable():
            # This shouldn't be happening!
            return
        try:
            obj.handle_read()
        except Exception:
            obj.handle_error()
    
    @staticmethod
    def write_obj(obj):
        """ Call handle_write of the object. If any error occurs within it,
        call handle_error of the object. If it is the first write event call
        the handle_connect method. """
        if not obj.connected:
            obj.connected = True
            obj.handle_connect()
        
        if not obj.writeable():
            # This shouldn't be happening!
            return
        try:
            obj.handle_write()
        except Exception:
            obj.handle_error()
    
    @staticmethod
    def except_obj(obj):
        """ Call handle_except of the object. If any error occurs within it,
        call handle_error of the object.  """
        if not obj.readable():
            # This shouldn't be happening!
            return
        try:
            obj.handle_except(
                obj.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            )
        except Exception:
            obj.handle_error()
    
    @staticmethod
    def close_obj(obj):
        """ Call handle_close of the object. If any error occurs within it,
        call handle_error of the object.  """
        try:
            obj.handle_close()
        except Exception:
            obj.handle_error()        


class Handler:
    """ Handle a socket object. Call this objects handle_* methods upon I/O """
    def __init__(self, socket_map, sock):
        self.addr = None
        self.connected = False
        self.socket_map = socket_map
        self.socket = None
        if sock is not None:
            self.set_socket(sock)
    
    def set_socket(self, sock):
        """ Set socket as the socket of the handler.
        If the socket is already connected do not call handle_connect
        anymore.
        
        The socket is automatically put into non-blocking mode.
        
        If the Handler already had a socket, remove it out of the SocketMap
        and add it with its new socket. """
        if self.socket:
            self.socket_map.del_handler(self)
        
        sock.setblocking(0)
        try:
            self.addr = sock.getpeername()
            self.connected = True
        except socket.error, err:
            if err.args[0] == errno.ENOTCONN:
                self.connected = False
            else:
                raise
        
        self.socket = sock
        self.socket_map.add_handler(self)
    
    def readable(self):
        """ Indicate whether the handler is interested in reading data. """
        return True
    
    def writeable(self):
        """ Indicate whether the handler is interested in writing data. """
        return True
    
    def fileno(self):
        """ Return fileno of underlying socket object.
        Needed for select.select. """
        return self.socket.fileno()
    
    def handle_read(self):
        """ Handle read I/O at socket. """
        pass
    
    def handle_write(self):
        """ Handle write I/O at socket. """
        pass
    
    def handle_error(self):
        """ Handle error in handler. """
        pass
    
    def handle_except(self, err):
        """ Handle exception state at error. """
        pass
    
    def handle_connect(self):
        """ Connection established. """
        pass
    
    def handle_close(self):
        """ Connection closed. """
        pass


class AcceptHandler(Handler):
    """ Handle socket that accepts connections. """
    def handle_read(self):
        """ Do not override. """
        sock, addr = self.accept()
        if sock is not None:
            self.handle_accept(sock, addr)
    
    def handle_accept(self, sock, addr):
        """ Accept connection from addr at sock. """
        pass
    
    def listen(self, num):
        """ Listen for a maximum of num connections. """
        return self.socket.listen(num)
    
    def bind(self, addr):
        """ Bind to address. """
        self.addr = addr
        return self.socket.bind(addr)
    
    def accept(self):
        """ Accept incoming connection. """
        try:
            conn, addr = self.socket.accept()
            return conn, addr
        except socket.error, err:
            if err.args[0] == errno.EWOULDBLOCK:
                pass
            else:
                raise
    
    def reuse_addr(self):
        """ Reuse the address. """
        self.socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR,
            self.socket.getsockopt(socket.SOL_SOCKET,
                                   socket.SO_REUSEADDR) | 1
        )



class IOHandler(Handler):
    """ Handle socket that sends and receives data. """
    def send(self, data):
        """ Send data. """
        try:
            return self.socket.send(data)
        except socket.error, err:
            if err.args[0] == errno.EWOULDBLOCK:
                return 0
            elif err.args[0] in connection_lost:
                self.handle_close()
                return 0
            else:
                raise
    
    def recv(self, buffer_size):
        """ Receive at most buffer_size bytes of data. """
        try:
            data = self.socket.recv(buffer_size)
            if not data:
                self.handle_close()
            return data
        except socket.error, err:
            if err.args[0] in connection_lost:
                self.handle_close()
                return ''
            else:
                raise
    
    def connect(self, address):
        """ Connect to (host, port). """
        self.connected = False
        err = self.socket.connect_ex(address)
        if err in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
            return
        if err in (0, errno.EISCONN):
            self.addr = address
            self.handle_connect()
        else:
            raise socket.error(err, errno.errorcode[err])
