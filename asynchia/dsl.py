# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2010 Florian Mayer

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

""" A domain-specific language to conveniently define the structure of packets
in binary protocols.

An elementary expression is an object implementing the Expr interface (which
is preferably an interface of a subclass of Expr and thus consistenly
integrates with other Exprs). It needs to implement the __call__(state)
and the produce(value) methods where __call__ returns the appropriate
collector to collect the data described by the expression and produce
returns the input that encodes the value passed to it according to the
expression.

By default the following expressions are defined by the module::

    - BinaryExpr (BE)
    - SingleBinaryExpr (SBE)
    - StringExpr (SE)
    - FixedLenExpr (FLE)
    - FileExpression (FE)

Two methods are provided to lookback data earlier collected in order to
construct the collector. binarylookback(ind, item=0) (also exported as bl)
gets the item specified from the binary data parsed from the expression at
the index ind (zero-index) of the ExprAdd the respective expression is
contained within. It is also possible to use positions relative to the
current one (-1 is the element before the one the lookback is passed to).
singlebinarylookback (also exported as sbl) does likewise for
SingleBinaryExpr (and is arguably more useful, see the Example section).
The only Expr in this module that takes a lookback as a parameter is
FixedLenExpr which limits whichever expression is contained in it
to the number of bytes aquired by the lookback function.

Attributes can be named by passing the name in square brackets. It is
also possible to refer to expressions by the name given to them in
lookbacks. ::

    e = b.L['size'] + b.B['blub'] + LFLSE('size')['string']

The tuple of values collected can be converted into a dictionary that
maps the name of the expression to the respective value by calling the
tonamed method of the ExprAdd. ::

    a = e()
    [Collecting of data takes place]
    tup = a.values
    dic = e.tonamed(tup)

Example
=======
Packets are described by expressions which can be converted to collectors
whenever a packet of that type should be parsed. Complex expressions can
be created by adding expressions, resulting in ExprAdds (but that is semi-
internal API which you do not necessarily need to care about, unless you
try to write your own types of expressions).

Let us henceforth consider the following simple example::
    
    from asynchia.dsl import b, SBLFLSE
    e = b.L + b.B + LFLSE(0)

This might appear utterly complicated at first glance, but it is not. The
first statement imports b (which is a container for binary numeric types)
and LFLSE which expands to lookback fixed-length string-expression.

The expression (which is the second statement) describes a packet which
contains three parts. The first part is an unsigned long (which is named by its
name in the struct module) in network byte-order (all binary types contained
in `b` assume network byte-order (so b.L expands to the struct format "!L");
the second part is an unsigned byte; the interesting thing in the expression
is the third part which describes a fixed-length string with the length equal
to the first element in the expression (which is referred to by its index 0):
the unsigned long.

The expression can now be used to parse and to produce pacets according to the
given format. An asynchia.ee collector can be created by calling the
expression ::

    collector = e()

You can now pass the protocol to the add_data method of the collector and it
will collect the data as specified. Any other data (which appears after the
whole packet has been read) is left in the protocol.

To create a packet you need to call the expression's produce method and pass
a tuple of the data you want to construct a package of. This operation
returns an asynchia.ee.Input that can directly be passed to be sent by
an asynchia.Handler. ::

    data = e.produce((5, 2, 'ABCDE'))

In this case it is important that the first number equals the length of the
string, as the system does not derive it from the length of the string
(though you are advised to do so in your client code).
"""

import struct

import asynchia.ee

class Container(object):
    def __getitem__(self, item):
        return getattr(self, item)


class State(object):
    def __init__(self):
        self.tbl = {}
        self.ind = 0
        self.nametbl = {}


class Expr(object):
    def __init__(self):
        self.name = None
    
    def __add__(self, other):
        return ExprAdd(self, other)
    
    def __getitem__(self, other):
        self.name = other
        return self


class ExprCollectorQueue(asynchia.ee.Collector):
    def __init__(self, exprs, onclose=None):
        asynchia.ee.Collector.__init__(self, onclose)
        
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
            self.expr = self.exprs.pop(0)
            self.coll = self.expr(self.state)
        while True:
            done, nrecv = self.coll.add_data(prot, nbytes)
            if done:
                self.done.append(self.coll)
                if self.expr.name is not None:
                    self.state.nametbl[self.expr.name] = self.coll
                self.state.ind += 1
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
        Expr.__init__(self)
        self.exprs = [one, other]
    
    def __call__(self, state=None, onclose=None):
        # We need to pass a copy so ExprCollectorQueue does not pop
        # from this list. Consider creating the copy in
        # ExprCollectorQueue.__init__.
        return ExprCollectorQueue(self.exprs[:], onclose)
    
    def __add__(self, other):
        self.exprs.append(other)
        return self
    
    def produce(self, value):
        result = asynchia.ee.StringInput("")
        for expr, elem in zip(self.exprs, value):
            result += expr.produce(elem)
        return result
    
    def tonamed(self, tup):
        d = {}
        for expr, elem in zip(self.exprs, tup):
            if expr.name is not None:
                d[expr.name] = elem
        return d


class BinaryExpr(Expr):
    def __init__(self, pattern):
        Expr.__init__(self)
        self.pattern = pattern
    
    def __call__(self, state, onclose=None):
        return asynchia.ee.StructCollector(
            struct.Struct(self.pattern),
            onclose
        )
    
    def produce(self, value):
        return asynchia.ee.StringInput(
            struct.pack(self.pattern, *value)
        )


class SingleBinaryExpr(Expr):
    def __init__(self, pattern):
        Expr.__init__(self)
        self.pattern = pattern
    
    def __call__(self, state, onclose=None):
        return asynchia.ee.SingleStructValueCollector(
            struct.Struct(self.pattern),
            onclose
        )
    
    def produce(self, value):
        return asynchia.ee.StringInput(
            struct.pack(self.pattern, value)
        )


class FileExpr(Expr):
    def __init__(self, fd, closing=False, autoflush=True):
        Expr.__init__(self)
        self.fd = fd
        self.closing = closing
        self.autoflush = autoflush
    
    def __call__(self, state, onclose=None):
        return asynchia.ee.FileCollector(
            self.fd, self.closing, self.autoflush, onclose
        )
    
    @staticmethod
    def produce(value):
        return asynchia.ee.FileInput(value, closing=False)


class StringExpr(Expr):
    def __call__(self, state, onclose=None):
        return asynchia.ee.StringCollector(onclose)
    
    @staticmethod
    def produce(value):
        return asynchia.ee.StringInput(value)


class FixedLenExpr(Expr):
    def __init__(self, glen, expr):
        Expr.__init__(self)
        self.glen = glen
        self.expr = expr
    
    def __call__(self, state, onclose=None):
        return asynchia.ee.DelimitedCollector(
            self.expr(state), self.glen(state), onclose
        )
    
    def produce(self, value):
        return self.expr.produce(value)


def lookback(ind, fun=(lambda x: x.value)):
    if isinstance(ind, basestring):
        def _fun(state):
            return fun(state.nametbl[ind])
    else:
        def _fun(state):
            return fun(state.tbl[ind])
    return _fun


def binarylookback(ind, item=0):
    def _fun(state):
        return state.tbl[ind].value[item]
    return _fun


def singlebinarylookback(ind, item=0):
    def _fun(state):
        return state.tbl[ind].value
    return _fun


def const(value):
    def _fun(state):
        return value
    return _fun


#: Binary lookback
bl = binarylookback
sbl = singlebinarylookback
#: Fixed-length expression
FLE = FixedLenExpr
#: String expression
SE = StringExpr
#: Binary expression
BE = BinaryExpr
SBE = SingleBinaryExpr
FE = FileExpr


def FLSE(glen):
    return FixedLenExpr(glen, StringExpr())

#: Lookback fixed-length string-expression
def LFLSE(ind, fun=(lambda x: x.value)):
    return FixedLenExpr(lookback(ind, fun), StringExpr())

#: Single-binary lookback fixed-length string-expression
def SBLFLSE(ind):
    return FixedLenExpr(lookback(ind), StringExpr())


FRMT_CHARS = ('x', 'c', 'b', 'B', '?', 'h', 'H', 'i', 'I', 'l',
              'L', 'q', 'Q', 'f', 'd', 's', 'p', 'P')
b = Container()
for symbol in FRMT_CHARS:
    setattr(b, symbol, SingleBinaryExpr("!" + symbol))

if __name__ == '__main__':
    # Actual debug here.
    e = b.L['size'] + b.B['blub'] + SBLFLSE(0)['string']
