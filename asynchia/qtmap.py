# -*- coding: us-ascii -*-

# asynchia.qtmap - SocketMap for Qt
# Copyright (C) 2008 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" This module is - unlike the rest of asynchia - licensed under the terms
of the GNU GPL! """

import asynchia
import socket
import errno

from PyQt4 import QtCore, QtGui


class SocketNotifier(QtCore.QSocketNotifier):
    """ Notificate about socket I/O using Qt facilities """
    def __init__(self, watched, notifier, type_ ):
        QtCore.QSocketNotifier.__init__(self, watched.transport.fileno(), type_)
        self.watched = watched
        self.notifier = notifier
        self.fun = None
        if type_ == QtCore.QSocketNotifier.Read:
            self.fun = self.read
        elif type_ == QtCore.QSocketNotifier.Write:
            self.fun = self.write
        elif type_ == QtCore.QSocketNotifier.Exception:
            self.fun = self.except_
        QtCore.QObject.connect(self, QtCore.SIGNAL("activated(int)"), self.fun)
    
    def disable(self):
        """ Temporarily disable notification on I/O. """
        self.setEnabled(False)
    
    def enable(self):
        """ Re-enable notification on I/O. """
        self.setEnabled(True)
    
    def shutdown(self):
        """ Permanentely disable notification on I/O. """
        QtCore.QObject.disconnect(
            self, QtCore.SIGNAL("activated(int)"), self.fun
        )
        self.setEnabled(False)
        self.fun = self.watched = None
        self.deleteLater()
    
    def read(self, _sock=None):
        """ Read I/O to do. """
        self.notifier.read_obj(self.watched)
    
    def write(self, _sock=None):
        """ Write I/O to do. """
        try:
            self.watched.socket.getpeername()
        except socket.error, err:
            if err.args[0] == errno.ENOTCONN:
                return
            else:
                raise
        self.notifier.write_obj(self.watched)
    
    def except_(self, _sock=None):
        """ Exception I/O to do. """
        self.notifier.except_obj(self.watched)


class QSocketMap(asynchia.SocketMap):
    """ Decide which sockets have I/O to do using Qt facilities. """
    def __init__(self, notifier=None):
        asynchia.SocketMap.__init__(self, notifier)
        self.handler_map = {}
    
    def add_transport(self, handler):
        """ See asynchia.SocketMap.add_transport """
        read = SocketNotifier(
            handler, self.notifier, QtCore.QSocketNotifier.Read
        )
        write = SocketNotifier(
            handler, self.notifier, QtCore.QSocketNotifier.Write
        )
        exception = SocketNotifier(
            handler, self.notifier, QtCore.QSocketNotifier.Exception
        )
        
        if handler.readable:
            read.enable()
        else:
            read.disable()
        
        if handler.writeable:
            write.enable()
        else:
            write.disable()
        exception.enable()
        
        self.handler_map[handler] = {
            'read': read,
            'write': write,
            'exception': exception
        }
    
    def del_transport(self, handler):
        """ See asynchia.SocketMap.del_transport """
        for notifier in self.handler_map[handler].iteritems():
            notifier.shutdown()
        del self.handler_map[handler]
    
    def add_reader(self, handler):
        """ See asynchia.SocketMap.add_reader """
        self.handler_map[handler]['read'].enable()
    
    def del_reader(self, handler):
        """ See asynchia.SocketMap.del_reader """
        self.handler_map[handler]['read'].disable()
    
    def add_writer(self, handler):
        """ See asynchia.SocketMap.add_writer """
        self.handler_map[handler]['write'].enable()
    
    def del_writer(self, handler):
        """ See asynchia.SocketMap.del_writer """
        self.handler_map[handler]['write'].disable()
    
    def close(self):
        """ See asynchia.SocketMap.close """
        for handler in self.handler_map:
            self.notifier.cleanup_obj(handler)
        self.handler_map.clear()
    
    def is_empty(self):
        return bool(self.handler_map)
