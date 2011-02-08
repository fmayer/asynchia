# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2011 Florian Mayer

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


from itertools import izip_longest
from pprint import pprint

class Tree(object):
    def __init__(self, tree=None, coords=None):
        if tree is None:
            tree = (None, [])
        if coords is None:
            coords = [0]
        self.tree = tree
        self.coords = coords
    
    def __add__(self, item):
        return Tree(add(self.tree, self.coords, item))


def add(tree, coords, newvalue):
    value, children =  tree
    try:
        n = coords[0]
    except IndexError:
        return (value, children + [(newvalue, [])]), [len(children)]
    
    coords = coords[1:]
    
    if n > len(children):
        raise IndexError
    
    ntree, newcoords = add(children[n], coords, newvalue)
    
    return (
        value,
        children[:n] + [ntree] + children[n + 1:]
    ), [n] + newcoords


def _iadd(tree, coords, newvalue):
    value, children =  tree
    try:
        n = coords[0]
    except IndexError:
        children.append((newvalue, []))
        return len(children) - 1
    
    coords = coords[1:]
    
    if n > len(children):
        raise IndexError
    return _iadd(children[n], coords, newvalue)


def iadd(tree, coords, newvalue):
    return tree, coords + [_iadd(tree, coords, newvalue)]


def map_(fn, tree):
    value, children = tree
    return (fn(value), [map_(fn, child) for child in children])


if __name__ == '__main__':
    orig = (2, [(4, [])])
    added, coords = add(orig, [0], 6)
    assert added is not orig
    assert added == (2, [(4, [(6, [])])])
    assert coords == [0, 0]
    
    iadded, coords = iadd(orig, [0], 6)
    assert iadded is orig
    assert iadded == (2, [(4, [(6, [])])])
    assert coords == [0, 0]
    
    assert map_(lambda x: 2 * x, orig) == (4, [(8, [(12, [])])])
    pprint(add(orig, [0], 2))
