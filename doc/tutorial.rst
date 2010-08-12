=================
asynchia Tutorial
=================

Definitions
===========

SocketMap
---------
A SocketMap is responsible for deciding which handler has pending I/O. It also
provides the program's main-loop. asynchia offers SocketMaps for
select, poll and epoll by default. It automatically exposes the best of those
as asynchia.maps.DefaultSocketMap.

Notifier
--------
A Notifier is the connection between the SocketMap and the Handlers. The
SocketMap calls the Notifier's methods if it finds out a Handler has pending
I/O.

Handler
-------
A Handler manages the I/O of a socket. Consult the API documentation for more details.

Transport
---------
All I/O that is done is done through a transport. These allows the handlers to work with different transports without the need of changing them.

Example application
===================
This tutorial guides you through the development of a simple application. First we will write a server that prints everything it receives to stdout.

To begin with, we have to import asynchia. ::

    import asynchia
    import asynchia.maps

Afterwards we write a handler that will be used to handle I/O for every socket the server accepts. IOHandler enables us to use recv, send and connect (only the former is used in this example). We also tell the socket-map that we are interested in reading any data that is available at the underlying socket. You can also observe that a cool message is printed when a peer disconnects. ::

    import sys
    
    BUFFERSIZE = 4096
    class EchoHandler(asynchia.Handler):
        def __init__(self, transport):
            asynchia.IOHandler.__init__(self, transport)
            
            self.set_readable(True)
    
        def handle_read(self):
            sys.stdout.write(self.transport.read(BUFFERSIZE))
            sys.stdout.flush()
    
        def handle_close(self):
            print "Peer said bye-bye."

So much for that; this may be nice, but we also need to code the server. To do so, we inherit from AcceptHandler and override handle_accept (be aware that handle_read of AcceptHandler may not be overriden, otherwise handle_accept will not work as expected). ::

    class EchoAcceptor(asynchia.AcceptHandler):
        def handle_accept(self, sock, addr):
            Echo(asynchia.SocketTransport(self.socket_map, sock))

Now we only need to get the server up and running. We first create a socket-map, which is responsible for deciding which Handler's handle_* methods should be called when. The port chosen (25000) is completely arbitrary. ::

    def servermain():
        socketmap = asynchia.maps.DefaultSocketMap()
        server = EchoAcceptor(asynchia.SocketTransport(socketmap))
        server.transport.reuse_addr()
        server.transport.bind(('127.0.0.1', 25000))
        server.transport.listen(0)
        socketmap.run()

The server is done, now let's get to the client. Again, import asynchia. But now we will also import asynchia.protocols. ::

    import asynchia
    import asynchia.maps
    class EchoClient(asynchia.Handler):
        def handle_connect(self):
            self.sendall("Hello from the echo-client\n")

To ease the task of sending data through the transport we enhance it by mixing in the SendallTrait. This is done to reduce redundancy because Sendall trait can be used with any transport that supplies .send and .recv. ::

    class SendallSocketTransport(asynchia.SendallTrait, asynchia.SocketTransport):
        pass

Now we have to connect to the server and we're done for now. ::

    def clientmain():
        socketmap = asynchia.DefaultSocketMap()
        client = EchoClient(SendallSocketTransport(socketmap))
        client.connect(('127.0.0.1', 25000))
        socketmap.run()



