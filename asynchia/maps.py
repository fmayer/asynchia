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

import time
import select

import asynchia
import asynchia.util


# Fragile- and StrongSocketMap?
# Fragile has 
#     def start_interrupt(self):
#         self.controlsender.send('s')
#         self.controlsender.recv(1)
#     def end_interrupt(self):
#         self.controlsender.send('e')
# Strong has
#     def start_interrupt(self):
#         pass
#     def end_interrupt(self):
#         self.controlsender.send('se')
#         self.controlsender.recv(1)
class InterruptableSocketMap(asynchia.SocketMap):
    def __init__(self, notifier):
        asynchia.SocketMap.__init__(self, notifier)
        # IMPORTANT! These have to be blocking!
        self.controlsender, self.controlreceiver = asynchia.util.socketpair()
    
    def start_interrupt(self):
        self.controlsender.send('s')
        self.controlsender.recv(1)
    
    def end_interrupt(self):
        self.controlsender.send('e')
    
    def do_interrupt(self):
        # Read the "s" that started the interrupt
        self.controlreceiver.recv(1)
        # Send the "i" that signals the interrupt succeeded.
        self.controlreceiver.send("i")
        # Read the "e" that will end the interrupt.
        self.controlreceiver.recv(1)
    
    start_changeflags = start_interrupt
    end_changeflags = end_interrupt


class SelectSocketMap(InterruptableSocketMap):
    """ Decide which sockets have I/O to do using select.select. """
    def __init__(self, notifier=None):
        InterruptableSocketMap.__init__(self, notifier)
        self.readers = []
        self.writers = []
        self.socket_list = []
        
        self.readers.append(self.controlreceiver)
    
    def add_handler(self, handler):
        """ See SocketMap.add_handler. """
        if handler in self.socket_list:
            raise ValueError("Handler %r already in socket map!" % handler)
        self.socket_list.append(handler)
        if handler.readable:
            self.add_reader(handler)
        if handler.writeable:
            self.add_writer(handler)
    
    def del_handler(self, handler):
        """ See SocketMap.del_handler. """
        self.socket_list.remove(handler)
        if handler.readable:
            self.del_reader(handler)
        if handler.writeable:
            self.del_writer(handler)
    
    def add_writer(self, handler):
        """ See SocketMap.add_writer. """
        self.writers.append(handler)
    
    def del_writer(self, handler):
        """ See SocketMap.del_writer. """
        self.writers.remove(handler)
    
    def add_reader(self, handler):
        """ See SocketMap.add_reader. """
        self.readers.append(handler)
    
    def del_reader(self, handler):
        """ See SocketMap.del_reader. """
        self.readers.remove(handler)
    
    def poll(self, timeout):
        """ Poll for I/O. """
        interrupted = False
        read, write, expt = select.select(self.readers,
                                          self.writers,
                                          self.socket_list, timeout)
        for obj in read:
            if obj is not self.controlreceiver:
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


class PollSocketMap(InterruptableSocketMap):
    """ Decide which sockets have I/O to do using select.poll. 
    
    Do not refer to this class without explicitely checking for its existance
    first, it may not exist on some platforms (it is known not to on Windows).
    """
    def __init__(self, notifier=None):
        InterruptableSocketMap.__init__(self, notifier)
        self.socket_list = {}
        self.poller = select.poll()
        
        self.controlfd = self.controlreceiver.fileno()
        self.poller.register(self.controlfd, select.POLLIN | select.POLLPRI)
    
    def add_handler(self, handler):
        """ See SocketMap.add_handler. """
        fileno = handler.fileno()
        if fileno in self.socket_list:
            raise ValueError("Socket with fileno %d already "
                             "in socket map!" % fileno)
        self.socket_list[fileno] = handler
        self.poller.register(fileno, self.create_flags(handler))
    
    def del_handler(self, handler):
        """ See SocketMap.del_handler. """
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
        self.poller.modify(handler.fileno(), self.create_flags(handler))
    
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


class EPollSocketMap(InterruptableSocketMap):
    """ Decide which sockets have I/O to do using select.epoll. 
    
    Do not refer to this class without explicitely checking for its existance
    first, it may not exist on some platforms (it is known not to on Windows).
    """
    def __init__(self, notifier=None):
        InterruptableSocketMap.__init__(self, notifier)
        self.socket_list = {}
        self.poller = select.epoll()
        
        self.controlfd = self.controlreceiver.fileno()
        self.poller.register(self.controlfd, select.EPOLLIN | select.EPOLLPRI)
    
    def add_handler(self, handler):
        """ See SocketMap.add_handler. """
        fileno = handler.fileno()
        if fileno in self.socket_list:
            raise ValueError("Socket with fileno %d already "
                             "in socket map!" % fileno)
        self.socket_list[fileno] = handler
        self.poller.register(fileno, self.create_flags(handler))
    
    def del_handler(self, handler):
        """ See SocketMap.del_handler. """
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
    
    # select.epoll does this for us. See http://tinyurl.com/nblkcm.
    start_changeflags = end_changeflags = lambda s: None


DefaultSocketMap = SelectSocketMap

if hasattr(select, 'poll'):
    DefaultSocketMap = PollSocketMap
else:
    del PollSocketMap

if hasattr(select, 'epoll'):
    DefaultSocketMap = EPollSocketMap
else:
    del EPollSocketMap
