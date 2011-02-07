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

from __future__ import with_statement

import unittest

import asynchia
import asynchia.maps


def check_list(lst, handler):
    for transport in lst:
        if hasattr(transport, 'handler'):
            if transport.handler is handler:
                return True
    return False


class TestDefaults(unittest.TestCase):
    def test_default_socketmap(self):
        m = asynchia.maps.SelectSocketMap()
        with asynchia.defaults.with_socket_map(m):
            a = asynchia.Handler()
            a.transport.reuse_addr()
            a.transport.bind(('127.0.0.1', 25000))
            a.transport.listen(0)
            
            h = asynchia.Handler()
            
            a.transport.set_writeable(False)
        self.assertRaises(AttributeError, asynchia.Handler)
        self.assertTrue(check_list(m.socket_list, h))
        self.assertTrue(check_list(m.socket_list, a))
        a.transport.close()
        h.transport.close()
    
    def test_nested(self):
        def nestedfn():
            a = asynchia.Handler()
            a.transport.reuse_addr()
            a.transport.bind(('127.0.0.1', 25000))
            a.transport.listen(0)
            
            h = asynchia.Handler()
            
            a.transport.set_writeable(False)
            return a, h
        m = asynchia.maps.SelectSocketMap()
        with asynchia.defaults.with_socket_map(m):
            a, h = nestedfn()
        self.assertRaises(AttributeError, asynchia.Handler)
        self.assertTrue(check_list(m.socket_list, h))
        self.assertTrue(check_list(m.socket_list, a))

if __name__ == '__main__':
    unittest.main()
