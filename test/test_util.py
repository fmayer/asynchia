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

import asynchia.util

from nose.tools import eq_

def test_socketpair():
    data = 'a'
    a, b = asynchia.util.socketpair()
    a.send(data)
    # One byte must at least be received.
    eq_(b.recv(len(data)), data)


def test_idpool():
    pool = asynchia.util.IDPool()
    eq_(pool.get(), 0)
    eq_(pool.get(), 1)
    eq_(pool.get(), 2)
    pool.release(1)
    eq_(pool.get(), 1)
    pool.reset()
    eq_(pool.get(), 0)
    eq_(pool.get(), 1)
    eq_(pool.get(), 2)
    pool.release(1)
    eq_(pool.get(), 1)    


def test_ipv4():
    eq_(asynchia.util.parse_ipv4('127.0.0.1:12345'), ('127.0.0.1', 12345))


def test_ipv6():
    eq_(
        asynchia.util.parse_ipv6(
            '[2001:0db8:85a3:08d3:1319:8a2e:0370:7344]:443'
            ),
        ('2001:0db8:85a3:08d3:1319:8a2e:0370:7344', 443)
    )


def test_ip():
    eq_(asynchia.util.parse_ip('127.0.0.1:12345'), ('127.0.0.1', 12345))
    eq_(
        asynchia.util.parse_ip(
            '[2001:0db8:85a3:08d3:1319:8a2e:0370:7344]:443'
            ),
        ('2001:0db8:85a3:08d3:1319:8a2e:0370:7344', 443)
    )
