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


NULL = object()

class Tree(object):
    def __init__(self, tree=None, coords=None, root=NULL):
        if tree is None and root is not NULL:
            tree = (root, [])
        elif not (tree is not None and root is NULL):
            raise ValueError
        
        if coords is None:
            coords = []
        self.tree = tree
        self.coords = coords
    
    def __add__(self, item):
        return Tree(*add(self.tree, self.coords, item))
    
    def __iadd__(self, item):
        self.tree, coords = iadd(self.tree, self.coords, item)
        return Tree(self.tree, coords)
    
    def map(self, fn):
        return Tree(map_(tree, fn), self.coords)
    
    def add(self, old, item):
        return Tree(*add(self.tree, old.coords, item))
    
    def iadd(self, old, item):
        self.tree, coords = iadd(self.tree, old.coords, item)
        return Tree(self.tree, coords)
    
    def __repr__(self):
        return "<Tree(%r, %r)>" % (self.tree, self.coords)
    
    def __getitem__(self, item):
        if item is None:
            item = []
        if isinstance(item, (long, int)):
            item = [item]
        return get(self.tree, item)


def get(tree, coords):
    value, children = tree
    if not coords:
        return value
    else:
        return get(children[coords[0]], coords[1:])

def add_tree(tree, coords, newvalue):
    value, children =  tree
    try:
        n = coords[0]
    except IndexError:
        return (value, children + [newvalue]), [len(children)]
    
    coords = coords[1:]
    
    if n > len(children):
        raise IndexError
    
    ntree, newcoords = add(children[n], coords, newvalue)
    
    return (
        value,
        children[:n] + [ntree] + children[n + 1:]
    ), [n] + newcoords


def add(tree, coords, newvalue):
    return add_tree(tree, coords, (newvalue, []))


def _iadd_tree(tree, coords, newvalue):
    value, children =  tree
    try:
        n = coords[0]
    except IndexError:
        children.append(newvalue, [])
        return len(children) - 1
    
    coords = coords[1:]
    
    if n > len(children):
        raise IndexError
    return _iadd(children[n], coords, newvalue)


def _iadd(tree, coords, newvalue):
    return _iadd_tree(tree, coords, (newvalue, []))


def iadd(tree, coords, newvalue):
    return tree, coords + [_iadd(tree, coords, newvalue)]


def iadd_tree(tree, coords, newvalue):
    return tree, coords + [_iadd_tree(tree, coords, newvalue)]


def map_(tree, fn):
    value, children = tree
    return (fn(value), [map_(child, fn) for child in children])


if __name__ == '__main__':
    orig = (2, [(4, [])])
    added, coords = add(orig, [0], 6)
    assert added is not orig
    assert added == (2, [(4, [(6, [])])])
    assert coords == [0, 0]
    assert get(added, coords) == 6
    
    iadded, coords = iadd(orig, [0], 6)
    assert iadded is orig
    assert iadded == (2, [(4, [(6, [])])])
    assert coords == [0, 0]
    assert get(iadded, coords) == 6
    
    assert map_(orig, lambda x: 2 * x) == (4, [(8, [(12, [])])])
    
    tree = Tree(root=None)
    a = (tree + 0)
    b = a + 1
    c = b.iadd(a, 2)
    assert b.tree == c.tree == (None, [(0, [(1, []), (2, [])])])
    assert b.tree is c.tree
    assert a.tree == (None, [(0, [])])
    assert b.coords == [0, 0]
    assert c.coords == [0, 1]
    
    assert a[0] == 0
    assert b[0, 0] == 1
    assert b[0, 1] == 2
    assert c[0, 1] == 2
    
    # Get root item.
    assert a[None] is None
