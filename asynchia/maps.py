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

If select.poll is available, you will have PollSocketMap avaiable and
also assigned to DefaultSocketMap, which otherwise defaults to
SelectSocketMap.
"""

import select

import asynchia


class SelectSocketMap(asynchia.SocketMap):
    """ Decide which sockets have I/O to do using select.select. """
    def __init__(self, notifier=None):
        asynchia.SocketMap.__init__(self, notifier)
        self.readers = []
        self.writers = []
        self.socket_list = []
    
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
        try:
            self.writers.remove(handler)
        except:
            print handler
            raise
    
    def add_reader(self, handler):
        """ See SocketMap.add_reader. """
        self.readers.append(handler)
    
    def del_reader(self, handler):
        """ See SocketMap.del_reader. """
        self.readers.remove(handler)
    
    def poll(self, timeout):
        """ Poll for I/O. """
        read, write, expt = select.select(self.readers,
                                          self.writers,
                                          self.socket_list, timeout)
        for obj in read:
            self.notifier.read_obj(obj)
        for obj in write:
            self.notifier.write_obj(obj)
        for obj in expt:
            self.notifier.except_obj(obj)
    
    def run(self):
        """ Periodically poll for I/O. """
        while True:
            self.poll(None)


class PollSocketMap(asynchia.SocketMap):
    """ Decide which sockets have I/O to do using select.poll. 
    
    Do not refer to this class without explicitely checking for its existance
    first, it may not exist on some platforms (it is know not to on Windows).
    """
    def __init__(self, notifier=None):
        asynchia.SocketMap.__init__(self, notifier)
        self.socket_list = {}
    
    def add_handler(self, handler):
        """ See SocketMap.add_handler. """
        fileno = handler.fileno()
        if fileno in self.socket_list:
            raise ValueError("Socket with fileno %d already "
                             "in socket map!" % fileno)
        self.socket_list[fileno] = handler
    
    def del_handler(self, handler):
        """ See SocketMap.del_handler. """
        fileno = handler.fileno()
        del self.socket_list[fileno]
    
    def poll(self, timeout):
        """ Poll for I/O. """
        poller = select.poll()
        for fileno, obj in self.socket_list.iteritems():
            flags = select.POLLERR | select.POLLHUP | select.POLLNVAL
            if obj.readable:
                flags |= select.POLLIN | select.POLLPRI
            if obj.writeable or obj.awaiting_connect:
                flags |= select.POLLOUT
            poller.register(fileno, flags)
        
        active = poller.poll(timeout)
        for fileno, flags in active:
            obj = self.socket_list[fileno]
            if flags & (select.POLLIN | select.POLLPRI):
                self.notifier.read_obj(obj)
            if flags & select.POLLOUT:
                self.notifier.write_obj(obj)
            if flags & (select.POLLERR | select.POLLNVAL):
                self.notifier.except_obj(obj)
            if flags & select.POLLHUP:
                self.notifier.close_obj(obj)
    
    def run(self):
        """ Periodically poll for I/O. """
        while True:
            self.poll(None)
    
    # We don't care about these, we just check for read/writeable
    # in PollSocketMap.poll. These are more important for GUI socket-
    # maps.
    def add_writer(self, handler):
        """ No-op. Not needed when using select.poll. """
    
    def del_writer(self, handler):
        """ No-op. Not needed when using select.poll. """
    
    def add_reader(self, handler):
        """ No-op. Not needed when using select.poll. """
    
    def del_reader(self, handler):
        """ No-op. Not needed when using select.poll. """


if not hasattr(select, 'poll'):
    del PollSocketMap
    DefaultSocketMap = SelectSocketMap
else:
    # Usually it's a better idea to use select.poll
    # than to use select.select.
    DefaultSocketMap = PollSocketMap
