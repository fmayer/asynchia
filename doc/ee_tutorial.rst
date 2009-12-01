====================
asynchia.ee Tutorial
====================

What's asynchia.ee
==================
asynchia.ee contains facilities that ease parsing binary TCP protocols. Roughly
speaking there are two types of objects: Inputs and Collectors. Inputs provide
data to be sent while Collectors provide the space where incoming data is put.
The callable passed to onclose of either of the two is executed when the Input
or Collector is closed.

Inputs
------
Inputs are objects with a tick method, which takes any object with a send
method that returns the bytes sent, which sends as much as possible over said
object.

Collectors
----------
Collectors are objects with an add_data method which takes an object
with a recv method and the maximum amount of data to be read from selfsame.
A DelimitedCollector limits the maximum amount of bytes to be received into
the Collector passed to it. This is an excellent way of splitting messages
of known size.

An excellent combination to parse protocols where the size of the message in a
fixed-length format is sent prior to the message itself is a DelimitedCollector,
a StructCollector and any Collector in which you want to store the result.
This expects the size of the message to be sent as an unsigned integer, consult
the documentation of the struct module for more information ::

    msg_header = struct.Struct('I')

    class MessageCollector(asynchia.ee.CollectorQueue):
        def __init__(self, messagecollector, onclose=None):
            asynchia.ee.CollectorQueue.__init__(onclose=onclose)
            self.add_collector(
                asynchia.ee.StructCollector(msg_header, self.header_close)
            )
            
            self.messagecollector = messagecollector
        
        def header_close(self, coll):
            self.add_collector(asynchia.ee.DelimitedCollector(
                self.messagecollector, coll.value[0])) 


Both Inputs and Collectors can be queued with InputQueue and CollectorQueue,
respectively.

Example Application
===================
Let's implement exactly the same application we have using asynchia using asynchia.ee. You will instantly notice its benefits. ::

    import asynchia
    import asynchia.maps
    import asynchia.ee
    import sys

We can instantly write an EchoAcceptor as the EchoHandler is not needed. asynchia.ee.FileCollector(sys.stdout, False) creates a collector which writes everything that is put into it to stdout. The False needs to be passed to prevent it from closing the fd to stdout (which would have dramatic consequences) once the collector is closed. ::

    class EchoAcceptor(asynchia.AcceptHandler):
        def handle_accept(self, sock, addr):
            collector = asynchia.ee.FileCollector(sys.stdout, False)
            asynchia.ee.Handler(self.socket_map, sock, collector)

Now we can go straight to starting up the server. ::

    def servermain():
        socketmap = asynchia.maps.DefaultSocketMap()
        server = EchoAcceptor(socketmap)
        server.reuse_addr()
        server.bind(('127.0.0.1', 25000))
        server.listen(0)
        socketmap.run()

And the code for the client is simply. client.send_str(...) is a convenience method for client.send_input(asynchia.ee.StringInput(...)) ::

    def clientmain():
        socketmap = asynchia.maps.DefaultSocketMap()
        client = asynchia.ee.Handler(socketmap)
        client.connect(('127.0.0.1', 25000))
        client.send_str("Hello from the enterprisey client!\n")
        socketmap.run()

