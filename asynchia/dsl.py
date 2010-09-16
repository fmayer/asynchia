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

    e = s.L()['size'] + s.B()['blub'] + LFLSE('size')['string']

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
    
    from asynchia.dsl import s, SBLFLSE
    e = s.L() + s.B() + LFLSE(0)

This might appear utterly complicated at first glance, but it is not. The
first statement imports s (which is a container for binary numeric types)
and LFLSE which expands to lookback fixed-length string-expression.

The expression (which is the second statement) describes a packet which
contains three parts. The first part is an unsigned long (which is named by its
name in the struct module) in network byte-order (all binary types contained
in `s` assume network byte-order (so s.L expands to the struct format "!L");
the second part is an unsigned byte; the interesting thing in the expression
is the third part which describes a fixed-length string with the length equal
to the first element in the expression (which is referred to by its index 0):
the unsigned long.

The expression can now be used to parse and to produce packets according to the
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
from asynchia.util import b

class Container(object):
    """ Container to hold members, which are also exposed through getitem.
    Used as a container for the preconstruced SingleBinaryExpressions. """
    def __getitem__(self, item):
        return getattr(self, item)


class State(object):
    """ State of the collection done by ExprCollectorQueue. Used to enable
    lookbacks. """
    def __init__(self, parentstate=None):
        self.tbl = {}
        self.ind = 0
        self.nametbl = {}
        
        self.parent = parentstate
    
    def __getitem__(self, ind):
        if isinstance(ind, (long, int)):
            return self.tbl[ind]
        else:
            return self.nametbl[ind]
    
    def glob(self, ind):
        if ind in self.nametbl:
            return self.nametbl[ind]
        elif self.parent is not None:
            return self.parent.glob(ind)
        else:
            raise IndexError


class Expr(object):
    """ Baseclass for all expressions. """
    def __init__(self):
        self.name = None
    
    def __add__(self, other):
        return ExprAdd([self, other])
    
    def __mul__(self, other):
        return ExprMul(self, other)
    
    __rmul__ = __mul__
    
    def __getitem__(self, other):
        self.name = other
        return self


class ExprCollectorQueue(asynchia.ee.Collector):
    """ Queue to collect the data specified by the list of expressions
    passed to it. """
    def __init__(self, exprs, parentstate=None, onclose=None):
        asynchia.ee.Collector.__init__(self, onclose)
        
        self.exprs = exprs
        self.done = []
        
        self.state = State(parentstate)
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


class ExprMul(Expr):
    def __init__(self, expr, lookback):
        Expr.__init__(self)
        
        self.expr = expr
        self.lookback = lookback
    
    def __call__(self, state=None, onclose=None):
        # We do not need to copy here as the expressions can no longer
        # be changed and thus really all are the same.
        return ExprCollectorQueue(
            [self.expr] * self.lookback(state),
            state,
            onclose
        )
    
    def produce(self, value):
        result = asynchia.ee.StringInput(b(""))
        for elem in value:
            result += self.expr.produce(elem)
        return result


class ExprAdd(Expr):
    def __init__(self, exprs):
        Expr.__init__(self)
        self.exprs = exprs
    
    def __call__(self, state=None, onclose=None):
        # We need to pass a copy so ExprCollectorQueue does not pop
        # from this list. Consider creating the copy in
        # ExprCollectorQueue.__init__.
        return ExprCollectorQueue(self.exprs[:], state, onclose)
    
    def __add__(self, other):
        return ExprAdd(self.exprs + [other])
    
    # For the sake of completeness, not that it would matter in many cases.
    def __iadd__(self, other):
        self.exprs.append(other)
        return self
    
    def produce(self, value):
        result = asynchia.ee.StringInput(b(""))
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
    """ Represents data that can be expressed by a Struct. """
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
    """ Represents data that can be expressed by a Struct with a single
    member. """
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
    """ Data that should be collected in an fd. Should be combined with a
    FixedLengthExpression, lest it greedily collects all data from the
    moment it is created until no data is available. """
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
    """ Data that should be collected in a string. Should be combined with a
    FixedLengthExpression, lest it greedily collects all data from the
    moment it is created until no data is available. """
    def __call__(self, state, onclose=None):
        return asynchia.ee.StringCollector(onclose)
    
    @staticmethod
    def produce(value):
        return asynchia.ee.StringInput(value)


class FixedLenExpr(Expr):
    """ Restrict the length of the expression contained to the value retuned
    by calling glen upon construction of the collector for said expression.
    """
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
    """ Can be passed to expressions that expect a lookback.
    ind can either be a string, thus referring to the result of the expression
    with the specified name or an int referring to the result of the
    expression with the specified index.
    
    Fun can be altered to change the way the data is extracted from the 
    collector. Defaults to returning .value."""
    if isinstance(ind, (long, int)):
        def _fun(state):
            return fun(state.tbl[ind])
    else:
        def _fun(state):
            return fun(state.nametbl[ind])
    return _fun


def glob(ind, fun=(lambda x: x.value)):
    def _fun(state):
        return fun(state.glob(ind))
    return _fun


def binarylookback(ind, item=0):
    """ Convenience function for lookback(ind, lambda x: x.value[item]). """
    return lookback(ind, lambda x: x.value[item])


def const(value):
    """ Can be passed to expressions that expect a lookback and always
    returns the value passed to it. """
    def _fun(state):
        return value
    return _fun


#: Binary lookback
bl = binarylookback
lb = lookback
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


FRMT_CHARS = ('x', 'c', 'b', 'B', '?', 'h', 'H', 'i', 'I', 'l',
              'L', 'q', 'Q', 'f', 'd', 's', 'p', 'P')
s = Container()

def _single_binary(symbol):
    def _fun():
        return SingleBinaryExpr(symbol)
    return _fun

for symbol in FRMT_CHARS:
    setattr(s, symbol, _single_binary("!" + symbol))
