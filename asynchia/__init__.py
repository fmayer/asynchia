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

""" asynchia is a minimalist asynchronous networking library. """

import os
import errno
import socket
import Queue as queue

import traceback

from asynchia.util import EMPTY_BYTES, is_unconnected, socketpair, b
from asynchia.const import trylater, connection_lost, inprogress

__version__ = '0.1.3'

class CallSynchronized(object):
    def __init__(self, handler, sock):
        self.sock = sock
        self.handler = handler
    
    def call(self, fun):
        self.handler.funs.put(fun)
        self.sock.send(b('a'))


class SocketMapClosedError(Exception):
    pass

def _unawait_conn(obj):
    """ Helper function for Notifier. """
    obj.stop_awaiting_connect()
    obj.connected = True
    # Errno of the asynchronous connect function.
    err = obj.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
    if err:
        try:
            obj.connected = False
            obj.handle_connect_failed(err)
        except Exception:
            obj.handle_error()
    else:
        try:
            obj.handle_connect()
        except Exception:
            obj.handle_error()


class SocketMap(object):
    """ Decide which sockets have I/O to be done and tell the notifier
    to call the appropriate methods of their Handle objects. """
    def __init__(self, notifier=None):
        if notifier is None:
            notifier = Notifier()
        self.notifier = notifier
        self.closed = False
    
    def constructed(self):
        wakeup, other = socketpair()
        self.callsync = CallSynchronized(
            _CallSynchronizedHandler(
                SocketTransport(self, other)
                ),
            wakeup
        )
    
    def call_synchronized(self, fun):
        self.callsync.call(fun)
    
    def poll(self, timeout=None):
        raise NotImplementedError
    
    def run(self):
        """ Periodically poll for I/O. """
        while True:
            try:
                self.poll(None)
            except SocketMapClosedError:
                return
    
    def add_transport(self, obj):
        """ Add handler to the socket-map. This gives the SocketMap
        the responsibility to call its handle_read, handle_write,
        handle_close and handle_connect upon new I/O events. """
        raise NotImplementedError
    
    def del_transport(self, obj):
        """ Remove handler from the socket-map. It will no longer have its
        handle_read, handle_write, handle_close and handle_connect methods
        called upon new I/O events. """
        raise NotImplementedError
    
    def add_reader(self, obj):
        """ Add handler as a reader.
        This indicates he wishes to read data. """
        raise NotImplementedError
    
    def del_reader(self, obj):
        """ Delete handler as a reader.
        This indicates he no longer wants to read data until added again """
        raise NotImplementedError
    
    def add_writer(self, obj):
        """ Add handler as a writer.
        This indicates he wishes to send data. """
        raise NotImplementedError
    
    def del_writer(self, obj):
        """ Delete handler as a writer.
        This indicates he no longer wants to send data until added again """
        raise NotImplementedError
    
    def start_interrupt(self, changeflags=False):
        """ Stop the socket-map until end_interrupt is called. """
        raise NotImplementedError
    
    def end_interrupt(self, changeflags=False):
        """ Resume the socket-map. """
        raise NotImplementedError
    
    def interrupt(self, changeflags=False):
        """ Return a context-manager that automatically resumes the
        socket-map when the block is left. """
        raise NotImplementedError
    
    def close(self):
        """ Call the handle_cleanup methods of all handlers contained
        in the socket-map, indicating that they are void. """
        self.closed = True
    
    def is_empty(self):
        raise NotImplementedError


class Notifier(object):
    """ Call handle functions of the object with error handling. """
    @staticmethod
    def read_obj(obj):
        """ Call handle_read of the object. If any error occurs within it,
        call handle_error of the object. If it is the first read event call
        the handle_connect method. """
        if obj.awaiting_connect:
            _unawait_conn(obj)
        
        if not obj.readable:
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
        if obj.awaiting_connect:
            _unawait_conn(obj)
        
        if not obj.writeable:
            # This should only be happening if the object was just connected.
            return
        try:
            obj.handle_write()
        except Exception:
            obj.handle_error()
    
    @staticmethod
    def except_obj(obj):
        """ Call handle_except of the object. If any error occurs within it,
        call handle_error of the object.  """
        if obj.awaiting_connect:
            _unawait_conn(obj)
        
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
        if obj.awaiting_connect:
            _unawait_conn(obj)
        try:
            obj.handle_close()
        except Exception:
            obj.handle_error()
        
        try:
            obj.handle_cleanup()
        except Exception:
            obj.handle_error()
    
    @staticmethod
    def cleanup_obj(obj):
        """ Call handle_cleanup of the object. If any error occurs within it,
        call handle_error of the object. """
        try:
            obj.handle_cleanup()
        except Exception:
            obj.handle_error()


class Transport(object):
    """ All I/O is done over Transports. This enables Handlers to be written
    in a generic way and used with different transports. """
    def __init__(self, handler=None):
        self.handler = None
        
        self.closed = False
        self.cleanedup = False
    
    def recv_into(self, buf, nbytes, *args):
        if nbytes is None:
            nbytes = len(buf)
        rcv = self.recv(nbytes, *args)
        buf[:len(rcv)] = rcv
        return len(rcv)
    
    def recv(self, nbytes, *args):
        """ Override. """
        raise NotImplementedError
    
    def send(self, string, *args):
        """ Override. """
        raise NotImplementedError
    
    def handle_read(self):
        """ Handle read I/O at socket. """
        if self.handler is not None:
            self.handler.handle_read()
    
    def handle_write(self):
        """ Handle write I/O at socket. """
        if self.handler is not None:
            self.handler.handle_write()
    
    def handle_error(self):
        """ Handle error in handler. """
        # This is the sanest default.
        if self.handler is not None:
            self.handler.handle_error()
    
    def handle_except(self, err):
        """ Handle exception state at error. """
        if self.handler is not None:
            self.handler.handle_except(err)
    
    def handle_connect(self):
        """ Connection established. """
        if self.handler is not None:
            self.handler.handle_connect()
    
    def handle_connect_failed(self, err):
        """ Connection couldn't be established. """
        if self.handler is not None:
            self.handler.handle_connect_failed(err)
    
    def handle_close(self):
        """ Connection closed. Note that this is only called if the
        connection is closed by the remote end! """
        # Ensure the handler is only called once, even if multiple connection
        # closed events should be fired (which could happen due to the code
        # in SocketTransport.send).
        try:
            if self.handler is not None and not self.closed:
                self.handler.handle_close()
                self.closed = True
        finally:
            self.closed = True
    
    def handle_cleanup(self):
        """ Called whenever the Handler is voided, for whatever reason.
        This may be the shutdown of the program, the closing of the
        connection by the local end or the like. """
        try:
            if self.handler is not None and not self.cleanedup:
                self.handler.handle_cleanup()
                self.cleanedup = True
        finally:
            self.cleanedup = True


class SocketTransport(Transport):
    """ A transport that uses a socket to send and receive data. """
    def __init__(self, socket_map, sock=None, handler=None):
        super(SocketTransport, self).__init__(handler)
        # Make no assumptions on what we want to do with the handler.
        # The user will need to explicitely make it read- or writeable.
        if sock is None:
            sock = defaultsocket_factory()
        self._readable = False
        self._writeable = False
        
        self.awaiting_connect = False
        
        self.connected = False
             
        self.socket_map = socket_map
        self.socket = None
        self.set_socket(sock)
    
    def close(self):
        """ Close the socket. """
        self.socket_map.del_transport(self)
        self.connected = False
        try:
            self.socket.close()
        except socket.error, err:
            if err.args[0] not in (errno.ENOTCONN, errno.EBADF):
                raise
        finally:
            self.socket_map.notifier.cleanup_obj(self)
    
    def set_socket(self, sock):
        """ Set socket as the socket of the handler.
        If the socket is already connected do not call handle_connect
        anymore.
        
        The socket is automatically put into non-blocking mode.
        
        If the Handler already had a socket, remove it out of the SocketMap
        and add it with its new socket. """
        await = False
        if self.socket:
            # If we had a socket before, we are still in the SocketMap.
            # Remove us out of it.
            self.socket_map.del_transport(self)
        
        sock.setblocking(0)
        if is_unconnected(sock):
            await = True
            self.connected = False
        else:
            self.connected = True
            # To provide consistency. If an async socket that already had
            # .connect called on it, we couldn't tell whether handle_connect
            # will be called or not if we wouldn't call it here.
            self.handle_connect()
        
        self.socket = sock
        self.socket_map.add_transport(self)
        if await:
            self.await_connect()
    
    def get_readable(self):
        """ Check whether handler wants to read data. """
        return self._readable
    
    def set_readable(self, value):
        """ Set whether handler wants to read data. """
        if self._readable == value:
            # The state hasn't changed. Calling the SocketMap's handlers
            # again might confuse it.
            return
        
        self._readable = value
        if value:
            self.socket_map.add_reader(self)
        else:
            self.socket_map.del_reader(self)
    
    def get_writeable(self):
        """ Check whether handler wants to write data. """
        return self._writeable
    
    def set_writeable(self, value):
        """ Set whether handler wants to write data. """
        if self._writeable == value:
            # The state hasn't changed. Calling the SocketMap's handlers
            # again might confuse it.
            return
        
        self._writeable = value
        # If we are waiting for the connect write-event,
        # the handler is
        #   a) Already in the writers list if we want to add it to it.
        #   b) Needs to remain in the writers list if we wanted to
        #      remove it.
        if not self.awaiting_connect:
            if value:
                self.socket_map.add_writer(self)
            else:
                self.socket_map.del_writer(self)
    
    readable = property(get_readable, set_readable)
    writeable = property(get_writeable, set_writeable)
    
    def await_connect(self):
        """ Add handler to its socket-map's writers if necessary.
        
        At the next write-event from the socket-map handle_connect will
        be called. """
        # If we are already writeable, the handler is already in the
        # socket-map's writers.
        self.awaiting_connect = True
        if not self.writeable:
            self.socket_map.add_writer(self)
    
    def stop_awaiting_connect(self):
        """ Remove handler from its socket-map's writers if necessary.
       
        At the next write-event from the socket-map handle_connect will
        not be called. """
        # Because of the way E/PollSocketMap works, the flag has to be
        # set before del_writer is called!
        self.awaiting_connect = False
        # If we are writeable, the handler needs to remain in the
        # socket-map's writers.
        if not self.writeable:
            self.socket_map.del_writer(self)
    
    def fileno(self):
        """ Return fileno of underlying socket object.
        Needed for select.select. """
        return self.socket.fileno()
    
    def listen(self, num):
        """ Listen for a maximum of num connections. """
        if not self.readable:
            self.set_readable(True)
        return self.socket.listen(num)
    
    def bind(self, addr):
        """ Bind to address. """
        return self.socket.bind(addr)
    
    def accept(self):
        """ Accept incoming connection. Return (conn, addr). If either of
        them is None, no connection could be accepted. """
        try:
            conn, addr = self.socket.accept()
            return conn, addr
        except socket.error, err:
            if err.args[0] in trylater:
                # Make the API of returning a tuple of two objects consistent.
                return None, None
            else:
                raise
    
    def reuse_addr(self):
        """ Reuse the address. """
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    def send(self, data, flags=0):
        """ Send data.
    
        flags is constructed by ORing zero or more of the following values.
        
        MSG_OOB
            Sends out-of-band data on sockets that support this notion
            (e.g. SOCK_STREAM); the underlying protocol must also support
            out-of-band data.
        MSG_DONTROUTE
            Don't use a gateway to send out the packet, only send to hosts on
            directly connected networks. This is usually used only by diagnostic
            or routing programs. This is only defined for protocol families that
            route; packet sockets don't.
        MSG_DONTWAIT
            Enables non-blocking operation; if the operation would block,
            EAGAIN is returned.
        MSG_NOSIGNAL
            Requests not to send SIGPIPE on errors on stream oriented sockets
            when the other end breaks the connection. The EPIPE error is still
            returned.
        MSG_CONFIRM
            (Linux 2.3+ only) Tell the link layer that forward process happened:
            you got a successful reply from the other side. If the link layer
            doesn't get this it'll regularly reprobe the neighbour
            (e.g. via a unicast ARP). Only valid on SOCK_DGRAM and SOCK_RAW
            sockets and currently only implemented for IPv4 and IPv6.
            See arp(7) for details. """
        try:
            return self.socket.send(data, flags)
        except socket.error, err:
            if err.args[0] in trylater:
                return 0
            elif err.args[0] == errno.EPIPE:
                self.socket_map.notifier.close_obj(self)
                return 0
            else:
                raise
    
    def recv(self, buffer_size, flags=0):
        """ Receive at most buffer_size bytes of data.
        
        flags may be constructed by ORing zero or more of the following values:
        MSG_PEEK
            Peeks at an incoming message.
            The data is treated as unread and the next recv() or similar
            function shall still return this data.
        MSG_OOB
            Requests out-of-band data.
            The significance and semantics of out-of-band data
            are protocol-specific.
        MSG_WAITALL
            On SOCK_STREAM sockets this requests that the function block
            until the full amount of data can be returned.
            The function may return the smaller amount of data if the
            socket is a message-based socket, if a signal is caught,
            if the connection is terminated, if MSG_PEEK was specified,
            or if an error is pending for the socket. """
        try:
            data = self.socket.recv(buffer_size, flags)
            if not data:
                self.socket_map.notifier.close_obj(self)
            return data
        except socket.error, err:
            if err.args[0] in connection_lost:
                self.socket_map.notifier.close_obj(self)
                return EMPTY_BYTES
            else:
                raise
    
    def recv_into(self, buf, nbytes, flags=0):
        try:
            data = self.socket.recv_into(buf, nbytes, flags)
            if not data:
                self.socket_map.notifier.close_obj(self)
            return data
        except socket.error, err:
            if err.args[0] in connection_lost:
                self.socket_map.notifier.close_obj(self)
                return EMPTY_BYTES
            else:
                raise
    
    def peek(self, buffer_size):
        return self.recv(buffer_size, socket.MSG_PEEK)
    
    def connect(self, address):
        """ Connect to (host, port). """
        err = self.socket.connect_ex(address)
        # EWOULDBLOCK is only expected with WinSock.
        if err in inprogress:
            if not self.awaiting_connect:
                self.connected = False
                self.await_connect()
            return
        elif err == 0:
            if self.awaiting_connect:
                self.stop_awaiting_connect()
            self.connected = True
            self.handle_connect()
        else:
            # Used to be `raise socket.error(err, os.strerror(err))` but
            # it is a better idea to have all handling of connection
            # failed in the same place.
            try:
                self.handle_connect_failed(err)
            except Exception:
                self.handle_error()


class SendallTrait(object):
    """ Enhance Transport with sendall that buffers data and sends it all,
    if necessary in multiple steps. Mix into the transport to use.
    
        class SendAllTransport(asynchia.SendallTrait, asynchia.SocketTransport):
            pass
    """
    def __init__(self, *args, **kwargs):
        super(SendallTrait, self).__init__(*args, **kwargs)
        self.__buf = EMPTY_BYTES
        self.__savewriteable = None
    
    def set_writeable(self, value):
        """ If sendall is active, save the value passed and set it to that
        after sendall is finished. """
        if not self.__buf:
            super(SendallTrait, self).set_writeable(value)
        else:
            self.__savewriteable = value
    
    def get_writeable(self):
        """ Necessary for the property. """
        return super(SendallTrait, self).get_writeable()
    
    def sendall(self, data):
        """ Send all of data, if necessary in multiple steps. """
        if not self.__buf:
            self.__savewritable = self.writeable
        self.set_writeable(True)
        self.__buf += data
    
    def handle_write(self):
        """ Internal. """
        if not self.__buf:
            if self.__savewriteable is not None:
                super(SendallTrait, self).set_writeable(self.__savewriteable)
                self.__savewriteable = None
        
            if self.handler is not None and self.writeable:
                super(SendallTrait, self).handle_write()
        else:
            sent = super(SendallTrait, self).send(self.__buf)
            self.__buf = self.__buf[sent:]
    
    writeable = property(get_writeable, set_writeable)


class Handler(object):
    """ Handle a socket object. Call this objects handle_* methods upon I/O """
    # Dummy handlers.
    def __init__(self, transport):
        self.transport = transport
        
        self.transport.handler = self
    
    def handle_read(self):
        """ Handle read I/O at socket. """
        pass
    
    def handle_write(self):
        """ Handle write I/O at socket. """
        pass
    
    def handle_error(self):
        """ Handle error in handler. """
        # This is the sanest default.
        traceback.print_exc()
    
    def handle_except(self, err):
        """ Handle exception state at error. """
        pass
    
    def handle_connect(self):
        """ Connection established. """
        pass
    
    def handle_connect_failed(self, err):
        """ Connection couldn't be established. """
        pass
    
    def handle_close(self):
        """ Connection closed. Note that this is only called if the
        connection is closed by the remote end! """
        pass
    
    def handle_cleanup(self):
        """ Called whenever the Handler is voided, for whatever reason.
        This may be the shutdown of the program, the closing of the
        connection by the local end or the like. """


class AcceptHandler(Handler):
    """ Handle socket that accepts connections. """
    def __init__(self, transport=None):
        Handler.__init__(self, transport)
    
    def handle_read(self):
        """ Do not override. """
        sock, addr = self.transport.accept()
        if sock is not None:
            self.handle_accept(sock, addr)
    
    def handle_accept(self, sock, addr):
        """ Accept connection from addr at sock. """
        pass


class Server(AcceptHandler):
    """ Automatically create an instance of handlercls for every
    connection. """
    def __init__(self, transport, handlercls=Handler):
        AcceptHandler.__init__(self, transport)
        self.handlercls = handlercls
    
    def handle_accept(self, sock, addr):
        """ Instantiate the handler class. """
        handler = self.handlercls(
            SocketTransport(self.transport.socket_map, sock)
        )
        self.new_connection(handler, addr)
        return handler
    
    def new_connection(self, handler, addr):
        """ Called after a new handler has been created. """
    
    def serve_forever(self, addr, num):
        """ Serve a maximum of num connections at a time at addr. """
        self.transport.bind(addr)
        self.transport.listen(num)
        try:
            self.transport.socket_map.run()
        finally:
            self.transport.close()


class _CallSynchronizedHandler(Handler):
    """ Implementation detail. """
    def __init__(self, transport, per_run=1):
        Handler.__init__(self, transport)
        self.transport.set_readable(True)
        
        self.funs = queue.Queue()
        self.per_run = per_run
    
    def handle_read(self):
        """ Implementation detail. """
        for _ in self.transport.recv(self.per_run):
            try:
                self.funs.get_nowait()()
            except queue.Empty:
                break

defaultsocket_factory = socket.socket
