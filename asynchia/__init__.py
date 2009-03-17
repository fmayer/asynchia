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


import errno
import socket


connection_lost = (errno.ECONNRESET, errno.ENOTCONN,
                   errno.ESHUTDOWN, errno.ECONNABORTED)


class SocketMap:
    def __init__(self, notifier=None):
        if notifier is None:
            notifier = Notifier()
        self.notifier = notifier
    
    def add_handler(self, obj):
        raise NotImplementedError
    
    def del_handler(self, obj):
        raise NotImplementedError


class Notifier:
    @staticmethod
    def read_obj(obj):
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
        if not obj.connected:
            obj.connected = True
            obj.handle_connect()
        
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
        try:
            obj.handle_close()
        except Exception:
            obj.handle_error()        


class Handler:
    def __init__(self, socket_map, sock):
        self.connected = False
        self.socket_map = socket_map
        self.socket = sock
        if sock is not None:
            self.set_socket(sock)
    
    def set_socket(self, sock):
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
        return True

    def writable(self):
        return True
    
    def fileno(self):
        return self.socket.fileno()
    
    def handle_read(self):
        pass
    
    def handle_write(self):
        pass
    
    def handle_error(self):
        pass
    
    def handle_except(self, err):
        pass
    


class AcceptHandler(Handler):
    def handle_read(self):
        sock, addr = self.accept()
        if sock is not None:
            self.handle_accept(sock, addr)
    
    def handle_accept(self, sock, addr):
        pass

    def listen(self, num):
        self.accepting = True
        if os.name == 'nt' and num > 5:
            num = 5
        return self.socket.listen(num)

    def bind(self, addr):
        self.addr = addr
        return self.socket.bind(addr)
    
    def accept(self):
        try:
            conn, addr = self.socket.accept()
            return conn, addr
        except socket.error, err:
            if err.args[0] == EWOULDBLOCK:
                pass
            else:
                raise
    
    def reuse_addr(self):
        self.socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR,
            self.socket.getsockopt(socket.SOL_SOCKET,
                                   socket.SO_REUSEADDR) | 1
        )



class IOHandler(Handler):
    def send(self, data):
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
        self.connected = False
        err = self.socket.connect_ex(address)
        if err in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
            return
        if err in (0, errno.EISCONN):
            self.addr = address
            self.handle_connect()
        else:
            raise socket.error(err, errorcode[err])

