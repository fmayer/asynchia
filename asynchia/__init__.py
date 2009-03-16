import socket


class SocketMap:
    def __init__(self, notifier=None):
        if notifier is None:
            notifier = Notifier()
        self.notifier = notifier
    
    def add_handler(self, obj):
        pass
    
    def del_handler(self, obj):
        pass


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

class Handler:
    def __init__(self, socket_map, sock):
        self.socket_map = socket_map
        self.socket = sock
        if sock is not None:
            self.set_socket(sock)
    
    def set_socket(self, sock):
        pass


class AcceptHandler(Handler):
    def handle_read(self):
        sock, addr = self.accept()
        if sock is not None:
            self.handle_accept(sock, addr)
    
    def handle_accept(self, sock, addr):
        pass


class IOHandler(Handler):
    def send(self, data):
        pass
    
    def recv(self, buffer_size):
        pass
