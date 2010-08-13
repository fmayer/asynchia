====================
asynchia.ee Tutorial
====================

What's asynchia.dsl
===================
asynchia.dsl is a module offering a convenient way of expressing binary packets. The specification of a packet can be used both to parse and to produce packets of the specified type.

Example
=======
Packets are described by expressions which can be converted to collectors
whenever a packet of that type should be parsed. Complex expressions can
be created by adding expressions, resulting in ExprAdds (but that is semi-
internal API which you do not necessarily need to care about, unless you
try to write your own types of expressions).

Let us henceforth consider the following simple example::
    
    from asynchia.dsl import b, SBLFLSE
    e = b.L() + b.B() + LFLSE(0)

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

Attributes can be named by passing the name in square brackets. It is
also possible to refer to expressions by the name given to them in
lookbacks. The following expression is indentical to the one initially considered. ::

    e = b.L()['size'] + b.B()['blub'] + LFLSE('size')['string']

The tuple of values collected can be converted into a dictionary that
maps the name of the expression to the respective value by calling the
tonamed method of the ExprAdd. ::

    a = e()
    [Collecting of data takes place]
    tup = a.values
    dic = e.tonamed(tup)
