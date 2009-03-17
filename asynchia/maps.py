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

import select

import asynchia


class SelectSocketMap(asynchia.SocketMap):
    def __init__(self, notifier=None):
        asynchia.SocketMap.__init__(self, notifier)
        self.socket_list = []
    
    def add_handler(self, handler):
        self.socket_list.append(handler)
    
    def del_handler(self, handler):
        self.socket_list.remove(handler)
    
    def poll(self, timeout):
        read_list = (obj for obj in self.socket_list if obj.readable())
        write_list = (obj for obj in self.socket_list
                      if obj.writeable() or not obj.connected)
        
        read, write, expt = select.select(read_list,
                                          write_list,
                                          self.socket_list)
        
        for obj in read:
            self.notifier.read_obj(obj)
        for obj in write:
            self.notifier.write_obj(obj)
        for obj in expt:
            self.notifier.except_obj(obj)
    
    def run(self):
        while True:
            self.poll(None)
