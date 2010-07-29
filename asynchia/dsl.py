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

import struct

import asynchia.ee

class Container(object):
    pass


class State(object):
    def __init__(self):
        self.tbl = {}
        self.n = 0


class Expr(object):
    def __init__(self, noproduce=False):
        self.noproduce = noproduce
    
    def __add__(self, other):
        return ExprAdd(self, other)


class ExprCollectorQueue(asynchia.ee.Collector):
    def __init__(self, exprs):
        asynchia.ee.Collector.__init__(self)
        
        self.exprs = exprs
        self.done = []
        
        self.state = State()
        self.state.tbl = self.done
        
        self.coll = None
    
    def __add__(self, other):
        self.exprs.append(other)
        return self
    
    def add_data(self, prot, nbytes):
        asynchia.ee.Collector.add_data(self, prot, nbytes)
        if self.coll is None:
            self.coll = self.exprs.pop(0)(self.state)
        while True:
            done, nrecv = self.coll.add_data(prot, nbytes)
            if done:
                self.done.append(self.coll)
                self.state.n += 1
                if not self.exprs:
                    if not self.closed:
                        self.close()
                    return True, nrecv
                else:
                    self.coll = None
            if nrecv:
                break
        return False, nrecv
    
    def __iter__(self):
        return iter(self.done)
    
    @property
    def value(self):
        return (elem.value for elem in self.done)


class ExprAdd(Expr):
    def __init__(self, one, other):
        self.exprs = [one, other]
    
    def __call__(self, state):
        # We need to pass a copy so ExprCollectorQueue does not pop
        # from this list. Consider creating the copy in
        # ExprCollectorQueue.__init__.
        return ExprCollectorQueue(self.exprs[:])
    
    def __add__(self, other):
        if isinstance(other, ExprAdd):
            self.exprs.extend(other)
        else:
            self.exprs.append(other)
        return self
    
    def produce(self, value):
        result = ""
        for expr, elem in zip(self.exprs, value):
            result += expr.produce(elem)
        return result


class BinaryExpr(Expr):
    def __init__(self, pattern):
        self.pattern = pattern
    
    def __call__(self, state):
        return asynchia.ee.StructCollector(
            struct.Struct(self.pattern),
        )
    
    def produce(self, value):
        return struct.pack(self.pattern, value)


class StringExpr(Expr):
    def __call__(self, state):
        return asynchia.ee.StringCollector()
    
    def produce(self, value):
        return value


class FixedLenExpr(Expr):
    def __init__(self, glen, expr):
        self.glen = glen
        self.expr = expr
    
    def __call__(self, state):
        return asynchia.ee.DelimitedCollector(
            self.expr(state), self.glen(state)
        )
    
    def produce(self, value):
        return self.expr.produce(value)


def lookback(n, fun):
    def _fun(state):
        return fun(state.tbl[n])
    return _fun


def binarylookback(n, i=0):
    def _fun(state):
        return state.tbl[n].value[i]
    return _fun


def const(v):
    def _fun(state):
        return v
    return _fun


#: Binary lookback
bl = binarylookback
#: Fixed-length expression
FLE = FixedLenExpr
#: String expression
SE = StringExpr
#: Binary expression
BE = BinaryExpr

#: Binary-lookback fixed-length string-expression
def BLFLSE(n):
    return FixedLenExpr(binarylookback(n), StringExpr())

FRMT_CHARS = ('x', 'c', 'b', 'B', '?', 'h', 'H', 'i', 'I', 'l',
              'L', 'q', 'Q', 'f', 'd', 's', 'p', 'P')
b = Container()
for symbol in FRMT_CHARS:
    setattr(b, symbol, BinaryExpr("!" + symbol))

if __name__ == '__main__':
    # Actual debug here.
    e = b.L + b.B + BLFLSE(0)
