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

"""
Socket-maps are there to decide which sockets have I/O to be done
and call the appropriate handle functions at the Handlers.

If select.poll is available, you will have PollSocketMap available and
also assigned to DefaultSocketMap, which otherwise defaults to
SelectSocketMap.

If select.epoll is available, you will have EPollSocketMap available and
also assigned to DefaultSocketMap, which otherwise defaults to either
PollSocketMap or SelectSocketMap.
"""

import select
import socket
import errno

import asynchia
import asynchia.util

class InterruptContextManager(object):
    """ Allow with socketmap.interrupt() """
    def __init__(self, socket_map, changeflags):
        self.socket_map = socket_map
        self.changeflags = changeflags
    
    def __enter__(self):
        self.socket_map.start_interrupt(self.changeflags)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.socket_map.end_interrupt(self.changeflags)


class ControlSocketSocketMap(asynchia.SocketMap):
    """ Socket-map with an internal socket-pair that can be used to
    interrupt it. """
    def __init__(self, notifier):
        asynchia.SocketMap.__init__(self, notifier)
        # IMPORTANT! These have to be blocking!
        self.controlsender, self.controlreceiver = asynchia.util.socketpair()
    
    def interrupt(self, changeflags=False):
        """ Return context manager for the interruption of this
        socket-map. """
        return InterruptContextManager(self, changeflags)
    
    def do_interrupt(self):
        """ Call this in the socket-map when you have found out that there is
        data to read on the controlreceiver. """
        # Read the "s" that started the interrupt
        self.controlreceiver.recv(1)
        # Send the "i" that signals the interrupt succeeded.
        self.controlreceiver.send("i")
        # Read the "e" that will end the interrupt.
        self.controlreceiver.recv(1)


class FragileSocketMap(ControlSocketSocketMap):
    """ The socket-map has to be interrupted before internals are
    changed. """
    def start_interrupt(self, changeflags=False):
        """ See SocketMap.start_interrupt. """
        self.controlsender.send('s')
        self.controlsender.recv(1)
    
    def end_interrupt(self, changeflags=False):
        """ See SocketMap.end_interrupt. """
        self.controlsender.send('e')


class RobustSocketMap(ControlSocketSocketMap):
    """ The socket-map has to be stopped and resumed after internals
    are changed. """
    def __init__(self, notifier=None):
        ControlSocketSocketMap.__init__(self, notifier)
        self.needresp = False
    
    def start_interrupt(self, changeflags=False):
        """ See SocketMap.start_interrupt. """
        if not changeflags:
            # Same as FragileSocketMap.start_interrupt.
            self.controlsender.send('s')
            self.controlsender.recv(1)
        else:
            self.needresp = True
    
    def end_interrupt(self, changeflags=False):
        """ See SocketMap.end_interrupt. """
        if not changeflags:
            # Same as FragileSocketMap.end_interrupt.
            self.controlsender.send('e')
        else:
            self.controlsender.send('s')
            self.controlsender.recv(1)
            self.controlsender.send('e')
    
    def close(self):
        """ Signal the interrupt is finished to any thread that may be
        waiting, as the program, waiting for the thread to finish,
        would not be able to exit otherwise. """
        if self.needresp:
            self.controlreceiver.send('i')
            self.needresp = False
        


class RockSolidSocketMap(ControlSocketSocketMap):
    """ The socket-map automatically refreshes its internal while it's
    "sleeping". """
    def start_interrupt(self, changeflags=False):
        """ See SocketMap.start_interrupt. """
        if not changeflags:
            # Same as FragileSocketMap.start_interrupt.
            self.controlsender.send('s')
            self.controlsender.recv(1)
    
    def end_interrupt(self, changeflags=False):
        """ See SocketMap.end_interrupt. """
        if not changeflags:
            # Same as FragileSocketMap.end_interrupt.
            self.controlsender.send('e')


class SelectSocketMap(FragileSocketMap):
    """ Decide which sockets have I/O to do using select.select. """
    def __init__(self, notifier=None):
        FragileSocketMap.__init__(self, notifier)
        self.writers = []
        self.socket_list = []
        
        self.socket_list.append(self.controlreceiver)
    
    def add_transport(self, handler):
        """ See SocketMap.add_transport. """
        if handler in self.socket_list:
            raise ValueError("Handler %r already in socket map!" % handler)
        self.socket_list.append(handler)
        if handler.readable:
            self.add_reader(handler)
        if handler.writeable:
            self.add_writer(handler)
    
    def del_transport(self, handler):
        """ See SocketMap.del_transport. """
        self.socket_list.remove(handler)
        if handler.readable:
            self.del_reader(handler)
        if handler.writeable:
            self.del_writer(handler)
        if handler.awaiting_connect:
            self.del_writer(handler)
        pass
    
    def add_writer(self, handler):
        """ See SocketMap.add_writer. """
        self.writers.append(handler)
    
    def del_writer(self, handler):
        """ See SocketMap.del_writer. """
        self.writers.remove(handler)
    
    def add_reader(self, handler):
        """ See SocketMap.add_reader. """
        pass
    
    def del_reader(self, handler):
        """ See SocketMap.del_reader. """
        pass
    
    def poll(self, timeout):
        """ Poll for I/O. """
        interrupted = False
        read, write, expt = select.select(self.socket_list,
                                          self.writers,
                                          self.socket_list, timeout)
        for obj in read:
            if obj is not self.controlreceiver:
                try:
                    if obj.connected:
                        obj.socket.send('')
                except socket.error, err:
                    if err.errno == errno.EPIPE:
                        self.notifier.close_obj(obj)
                    else:
                        raise
                else:
                    self.notifier.read_obj(obj)
            else:
                interrupted = True
        for obj in write:
            self.notifier.write_obj(obj)
        for obj in expt:
            self.notifier.except_obj(obj)
        
        if interrupted:
            self.do_interrupt()
    
    def run(self):
        """ Periodically poll for I/O. """
        while True:
            self.poll(None)
    
    def close(self):
        """ See SocketMap.close """
        for handler in self.socket_list[1:]:
            self.notifier.cleanup_obj(handler)


class PollSocketMap(RobustSocketMap):
    """ Decide which sockets have I/O to do using select.poll. 
    
    Do not refer to this class without explicitely checking for its existance
    first, it may not exist on some platforms (it is known not to on Windows).
    """
    def __init__(self, notifier=None):
        RobustSocketMap.__init__(self, notifier)
        self.socket_list = {}
        self.poller = select.poll()
        
        self.controlfd = self.controlreceiver.fileno()
        self.poller.register(self.controlfd, select.POLLIN | select.POLLPRI)
    
    def add_transport(self, handler):
        """ See SocketMap.add_transport. """
        fileno = handler.fileno()
        if fileno in self.socket_list:
            raise ValueError("Socket with fileno %d already "
                             "in socket map!" % fileno)
        self.socket_list[fileno] = handler
        self.poller.register(fileno, self.create_flags(handler))
    
    def del_transport(self, handler):
        """ See SocketMap.del_transport. """
        fileno = handler.fileno()
        del self.socket_list[fileno]
        self.poller.unregister(fileno)
    
    def poll(self, timeout):
        """ Poll for I/O. """
        interrupted = False
        active = self.poller.poll(timeout)
        for fileno, flags in active:
            if fileno == self.controlfd:
                interrupted = True
                continue
            obj = self.socket_list[fileno]
            if flags & (select.POLLIN | select.POLLPRI):
                self.notifier.read_obj(obj)
            if flags & select.POLLOUT:
                self.notifier.write_obj(obj)
            if flags & (select.POLLERR | select.POLLNVAL):
                self.notifier.except_obj(obj)
            if flags & select.POLLHUP:
                self.notifier.close_obj(obj)
        if interrupted:
            self.do_interrupt()
    
    def run(self):
        """ Periodically poll for I/O. """
        while True:
            self.poll(None)
    
    def handler_changed(self, handler):
        """ Update flags for handler. """
        # self.poller.register is compatible to 2.5 whilst
        # self.poller.modify is not.
        self.poller.register(handler.fileno(), self.create_flags(handler))
    
    # We just update the flags of the object, doesn't matter what has
    # changed.
    add_writer = del_writer = add_reader = del_reader = handler_changed
    
    @staticmethod
    def create_flags(handler):
        """ Generate appropriate flags for handler. These flags will
        represent the current state of the handler (if it is readable,
        the flags say so too). """
        flags = select.POLLERR | select.POLLHUP | select.POLLNVAL
        if handler.readable:
            flags |= select.POLLIN | select.POLLPRI
        if handler.writeable or handler.awaiting_connect:
            flags |= select.POLLOUT
        return flags
    
    def close(self):
        """ See SocketMap.close """
        RobustSocketMap.close(self)
        for handler in self.socket_list.itervalues():
            self.notifier.cleanup_obj(handler)


class EPollSocketMap(RockSolidSocketMap):
    """ Decide which sockets have I/O to do using select.epoll. 
    
    Do not refer to this class without explicitely checking for its existance
    first, it may not exist on some platforms (it is known not to on Windows).
    """
    def __init__(self, notifier=None):
        RockSolidSocketMap.__init__(self, notifier)
        self.socket_list = {}
        self.poller = select.epoll()
        
        self.controlfd = self.controlreceiver.fileno()
        self.poller.register(self.controlfd, select.EPOLLIN | select.EPOLLPRI)
    
    def add_transport(self, handler):
        """ See SocketMap.add_transport. """
        fileno = handler.fileno()
        if fileno in self.socket_list:
            raise ValueError("Socket with fileno %d already "
                             "in socket map!" % fileno)
        self.socket_list[fileno] = handler
        self.poller.register(fileno, self.create_flags(handler))
    
    def del_transport(self, handler):
        """ See SocketMap.del_transport. """
        fileno = handler.fileno()
        del self.socket_list[fileno]
        self.poller.unregister(fileno)
    
    def poll(self, timeout):
        """ Poll for I/O. """
        # While select.poll is alright with None, select.epoll expects
        # -1 for no timeout,
        if timeout is None:
            timeout = -1
        
        interrupted = False
        active = self.poller.poll(timeout)
        for fileno, flags in active:
            if fileno == self.controlfd:
                interrupted = True
                continue
            obj = self.socket_list[fileno]
            if flags & (select.EPOLLIN | select.EPOLLPRI):
                self.notifier.read_obj(obj)
            if flags & select.EPOLLOUT:
                self.notifier.write_obj(obj)
            if flags & select.EPOLLERR:
                self.notifier.except_obj(obj)
            if flags & select.EPOLLHUP:
                self.notifier.close_obj(obj)
        if interrupted:
            self.do_interrupt()
    
    def run(self):
        """ Periodically poll for I/O. """
        while True:
            self.poll(None)
    
    def handler_changed(self, handler):
        """ Update flags for handler. """
        self.poller.modify(handler.fileno(), self.create_flags(handler))
    
    # We just update the flags of the object, doesn't matter what has
    # changed.
    add_writer = del_writer = add_reader = del_reader = handler_changed
    
    @staticmethod
    def create_flags(handler):
        """ Generate appropriate flags for handler. These flags will
        represent the current state of the handler (if it is readable,
        the flags say so too). """
        flags = select.EPOLLERR | select.EPOLLHUP
        if handler.readable:
            flags |= select.EPOLLIN | select.EPOLLPRI
        if handler.writeable or handler.awaiting_connect:
            flags |= select.EPOLLOUT
        return flags
    
    def close(self):
        """ See SocketMap.close """
        for handler in self.socket_list.itervalues():
            self.notifier.cleanup_obj(handler)


# It is possible to only get hangup events by applying the hack presented
# at http://paste.pocoo.org/show/245033/

# The concept of exceptional socket state does not exist on BSD, to quote
# the manpage of select on FreeBSD:
#     The only exceptional condition detectable is out-of-band data
#     received on a socket.
# Thus we need not call notifier.except_obj in this socket-map.
class KQueueSocketMap(RockSolidSocketMap):
    def __init__(self, nevents=100, notifier=None):
        RockSolidSocketMap.__init__(self, notifier)
        self.socket_list = {}
        self.queue = select.kqueue()
        
        self.nevents = nevents
        
        self.controlfd = self.controlreceiver.fileno()
        self.queue.control(
            [select.kevent(self.controlfd,
                           select.KQ_FILTER_READ,
                           select.KQ_EV_ADD)], 0
        )
    
    def add_transport(self, handler):
        """ See SocketMap.add_transport. """
        if handler in self.socket_list:
            raise ValueError("Handler %r already in socket map!" % handler)
        self.socket_list[handler.fileno()] = handler
        
        self.queue.control(
            [select.kevent(handler, select.KQ_FILTER_WRITE, select.KQ_EV_ADD)],
            0
        )
        
        if handler.readable:
            self.add_reader(handler)
        if handler.writeable:
            self.add_writer(handler)
    
    def del_transport(self, handler):
        """ See SocketMap.del_transport. """
        self.socket_list.pop(handler.fileno())
        
        self.queue.control(
            [select.kevent(
                handler, select.KQ_FILTER_WRITE, select.KQ_EV_DELETE)
             ],
            0
        )
        
        if handler.readable:
            self.del_reader(handler)
        if handler.writeable or handler.awaiting_connect:
            self.del_writer(handler)
    
    def add_writer(self, handler):
        """ See SocketMap.add_writer. """
        pass
    
    def del_writer(self, handler):
        """ See SocketMap.del_writer. """
        pass
    
    def add_reader(self, handler):
        """ See SocketMap.add_reader. """
        self.queue.control(
            [select.kevent(handler, select.KQ_FILTER_READ, select.KQ_EV_ADD)],
            0
        )
    
    def del_reader(self, handler):
        """ See SocketMap.del_reader. """
        self.queue.control(
            [select.kevent(
                handler, select.KQ_FILTER_READ, select.KQ_EV_DELETE)
             ],
            0
        )
    
    def poll(self, timeout=None):
        interrupted = False
        
        res = self.queue.control(None, self.nevents, timeout)
        
        for event in res:
            if event.ident == self.controlfd:
                interrupted = True
                continue
            handler = self.socket_list[event.ident]
            if event.filter == select.KQ_FILTER_READ:
                self.notifier.read_obj(handler)
            if event.filter == select.KQ_FILTER_WRITE:
                self.notifier.write_obj(handler)
            if event.flags == select.KQ_EV_EOF:
                self.notifier.close_obj(handler)
        
        if interrupted:
            self.do_interrupt()
    
    def close(self):
        self.queue.close()
        for handler in self.socket_list.itervalues():
            self.notifier.cleanup_obj(handler)


DefaultSocketMap = SelectSocketMap

if hasattr(select, 'poll'):
    DefaultSocketMap = PollSocketMap
else:
    del PollSocketMap

if hasattr(select, 'epoll'):
    DefaultSocketMap = EPollSocketMap
else:
    del EPollSocketMap

if hasattr(select, 'kqueue'):
    DefaultSocketMap = KQueueSocketMap
else:
    del KQueueSocketMap
