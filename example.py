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
    def handle_read(self):
        read = self.recv(4096)
        sys.stdout.write(read)
    
    def handle_error(self):
        traceback.print_exc()


class EchoAcceptor(asynchia.AcceptHandler):
    def handle_accept(self, sock, addr):
        Echo(self.socket_map, sock)


if __name__ == '__main__':
    # This should show "Foo" in your console.
    m = asynchia.maps.SelectSocketMap()
    a = EchoAcceptor(m, socket.socket())
    a.reuse_addr()
    a.bind(('', 25000))
    a.listen(0)
    
    c = EchoClient(m, socket.socket())
    c.connect(('', 25000))
    
    m.run()
