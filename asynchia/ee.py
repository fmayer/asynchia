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

import os
# For Python 3.x
import __builtin__ as __builtin__

import asynchia
from asynchia.util import EMPTY_BYTES

class Depleted(Exception):
    pass


class Input(object):
    """ Base-class for all Inputs. It implements __add__ to return an
    InputQueue consisting of the two operants. """
    def __init__(self, onclose=None):
        self.closed = self.inited = False
        self.onclose = onclose
    
    def tick(self, sock):
        """ Abstract method to be overridden. This should send the data
        contained in the Input over sock. """
        if self.closed:
            return True, 0
        if not self.inited:
            self.init()
    
    def init(self):
        """ Called before the first tick. """
        self.inited = True
    
    def close(self):
        """ Called after the last tick.
        
        IMPORTANT NOTE: This may be called without the Input being initalised,
        so you need to explicitely check whether it is when you want to clean
        up resources allocated in init. """
        if self.onclose is not None:
            self.onclose(self)
        self.closed = True
    
    def __add__(self, other):
        return InputQueue([self, other])


class InputQueue(Input):
    """ An InputQueue calls the tick method an object until it raises
    InputEOF, then it goes on with the next object in the queue. If no
    object is in the queue anymore, InputQueue.tick raises InputEOF (like
    any other Input that doesn't need data anymore). """
    def __init__(self, inputs=None, onclose=None):
        Input.__init__(self, onclose)
        if inputs is None:
            inputs = []
        self.inputs = inputs
    
    def tick(self, sock):
        """ Call tick method of the first object contained in the queue until
        it raises InputEOF. """
        Input.tick(self, sock)
        while True:
            inp = self.inputs[0]
            done, sent = inp.tick(sock)
            if done:
                self.inputs.pop(0)
                if not self.inputs:
                    self.close()
                    return True, sent
            if sent:
                break
        return False, sent
    
    def eof(self):
        """ Called when the last Input in the queue raises InputEOF.
        
        Return True to prevent InputQueue from raising InputEOF."""
    
    def close(self):
        """ Close all inputs contained in the queue. """
        Input.close(self)
        for inp in self.inputs:
            inp.close()
    
    def add(self, other):
        """ Add input to queue. """
        self.inputs.append(other)
    
    def __iadd__(self, other):
        self.add(other)
        return self
    
    def __nonzero__(self):
        return bool(self.inputs)
    
    def __len__(self):
        return sum(len(inp) for inp in self.inputs)


class StringInput(Input):
    """ Input that bufferedly sends a string. """
    def __init__(self, string, onclose=None):
        Input.__init__(self, onclose)
        
        self.buf = string
        self.length = len(self.buf)
    
    def tick(self, sock):
        """ Send as much of the string as possible. """
        Input.tick(self, sock)
        
        sent = sock.send(self.buf)
        self.buf = self.buf[sent:]
        self.length -= sent
        
        if not self.buf:
            self.close()
        
        return not bool(self.buf), sent
    
    def __len__(self):
        return self.length


class FileInput(Input):
    """ Input that buffers at most buffer_size bytes read from the passed fd,
    and sends them in a buffered way. This can be used to "directly" send data
    contained in a file. """
    def __init__(self, fd, length=None, buffer_size=9096, closing=True,
                 onclose=None):
        Input.__init__(self, onclose)
        
        self.cachedlen = length
        
        self.fd = fd
        self.buffer_size = buffer_size
        self.length = length
        self.closing = closing
        
        self.buf = EMPTY_BYTES
        self.eof = False
    
    def tick(self, sock):
        """ Send as much of the file as possible. """
        Input.tick(self, sock)
        if not self.eof and len(self.buf) < self.buffer_size:
            read = self.fd.read(self.buffer_size - len(self.buf))
            if not read:
                self.eof = True
            self.buf += read
        
        sent = sock.send(self.buf)        
        self.buf = self.buf[sent:]
        self.length -= sent
        
        if self.eof and not self.buf:
            self.close()
        
        return self.eof and not self.buf, sent
    
    def close(self):
        """ If FileInput is closing, close the fd. """
        Input.close(self)
        if self.closing:
            self.fd.close()
    
    @classmethod
    def from_filename(cls, filename, mode='rb', *args, **kwargs):
        """ Same as cls(fd, size, *args, **kwargs) while fd and size
        get constructed from the filename. If the mode attribute
        does not equal 'rb', the size cannot be determined
        efficienty. """
        if mode == 'rb':
            size = os.stat(filename).st_size
        else:
            size = None
        fd = open(filename, mode)
        return cls(fd, size, *args, **kwargs)
    
    def __len__(self):
        if self.cachedlen is not None:
            return self.cachedlen
        else:
            pos = self.fd.tell()
            self.fd.seek(0, 2)
            newpos = self.fd.tell()
            self.cachedlen = newpos - pos
            self.fd.seek(pos)
            return self.cachedlen


class AutoFileInput(FileInput):
    """ Same as FileInput, only that it stores samples to guess how big
    the buffer should be. """
    def __init__(self, fd, length=None, buffer_size=9096, closing=True,
                 samples=None, onclose=None):
        FileInput.__init__(self, fd, length, buffer_size, closing, onclose)
        
        if samples is None:
            self.average = asynchia.util.GradualAverage()
        else:
            self.average = asynchia.util.LimitedAverage(samples)
    
    def tick(self, sock):
        """ See FileInput.tick. """
        sent = FileInput.tick(self, sock)
        self.average.add_value(sent)
        self.buffer_size = int(round(self.average.avg))
        return sent


class FactoryInput(Input):
    """ Call factory method to obtain the next input until the factory
    raises the Depleted exception. """
    def __init__(self, factory, onclose=None):
        Input.__init__(self, onclose)
        self.factory = factory
        self.cur_inp = None
    
    def init(self):
        """ Obtain first input from factory method. """
        Input.init(self)
        self.cur_inp = self.factory()
    
    def tick(self, sock):
        """ Send data from the current input. """
        Input.tick(self, sock)
        while True:
            done, sent = self.cur_inp.tick(sock)
            if done:
                try:
                    self.cur_inp = self.factory()
                except Depleted:
                    self.close()
                    return True, sent
            if sent:
                break
        return False, sent
    
    @staticmethod
    def wrap_iterator(itr_next):
        """ Wrap the next method of an iterable in such a way that whenever
        it raises StopIteration, the wrapper raises Depleted. This is
        convenient when using FactoryCollector to obtain the collectors
        from an iterable. """
        def _wrap():
            try:
                return itr_next()
            except StopIteration:
                raise Depleted
        return _wrap


class Collector(object):
    """ This is the base-class for all collectors. Collectors read up to
    nbytes bytes of data from the protocol passed to them. """
    def __init__(self, onclose=None):
        self.inited = self.closed = False
        self.onclose = onclose
    
    def add_data(self, prot, nbytes):
        """ Override to read at most nbytes from prot and store them in the
        collector. """
        if self.closed:
            return True, 0
        
        if not self.inited:
            self.init()
    
    def close(self):
        """ Called after the last data has been added.
        
        IMPORTANT NOTE: This may be called without the Collector being
        initalised, so you need to explicitely check whether it is when you
        want to clean up resources allocated in init. """
        if self.onclose is not None:
            self.onclose(self)
        self.closed = True
    
    def init(self):
        """ Called before the first data is added to the collector. """
        self.inited = True
    
    def __add__(self, other):
        return CollectorQueue([self, other])


class StringCollector(Collector):
    """ Store data received from the socket in a string. """
    def __init__(self, onclose=None):
        Collector.__init__(self, onclose)
        
        self.intvalue = EMPTY_BYTES
    
    def add_data(self, prot, nbytes):
        """ Write at most nbytes bytes from prot to string. """
        Collector.add_data(self, prot, nbytes)
        
        received = prot.recv(nbytes)
        self.intvalue += received
        return False, len(received)
    
    @property
    def value(self):
        return self.intvalue


class FileCollector(Collector):
    """ Write data received from the socket into a fd. """
    def __init__(self, fd=None, closing=True, autoflush=False, onclose=None):
        Collector.__init__(self, onclose)
        
        self.intvalue = fd
        self.closing = closing
        self.autoflush = autoflush
    
    def add_data(self, prot, nbytes):
        """ Write at most nbytes data from prot to fd. """
        Collector.add_data(self, prot, nbytes)
        
        received = prot.recv(nbytes)
        # Let the error propagate lest it is silently ignored.
        self.intvalue.write(received)
        if self.autoflush:
            self.intvalue.flush()
        return False, len(received)
    
    def close(self):
        """ Close the fd if the FileCollector is closing. """
        Collector.close(self)
        if self.closing:
            self.intvalue.close()
    
    @property
    def value(self):
        return self.intvalue


class DelimitedCollector(Collector):
    """ Collect up to size bytes in collector and raise CollectorFull
    afterwards. """
    def __init__(self, collector, size, onclose=None):
        Collector.__init__(self, onclose)
        self.collector = collector
        self.size = size
    
    def add_data(self, prot, nbytes):
        """ Add data until the received data exceeds size. """
        Collector.add_data(self, prot, nbytes)
        
        done, nrecv = self.collector.add_data(prot, min(self.size, nbytes))
        self.size -= nrecv
        if self.size == 0:
            self.close()
        return (self.size == 0), nrecv
    
    def close(self):
        """ Close wrapped collector. """
        Collector.close(self)
        self.collector.close()
    
    def init(self):
        """ Initialise wrapped collector. """
        Collector.init(self)
        self.collector.init()
    
    @property
    def value(self):
        return self.collector.value


class NaiveDelimitedStringCollector(DelimitedCollector):
    def __init__(self, size, onclose=None):
        DelimitedCollector.__init__(self, StringCollector(), size, onclose)


class ByteArrayCollector(Collector):
    def __init__(self, size, onclose=None):
        Collector.__init__(self, onclose)
        
        self.pos = self.len_ = self.extended = 0
        self.size = size
        
        self.array = bytearray(size)
    
    def add_data(self, tnsp, nbytes):
        Collector.add_data(self, tnsp, nbytes)
        
        data = tnsp.recv(min(nbytes, self.size - self.len_))
        data = data[: self.size - self.len_]
        
        self.array[self.len_: self.len_ + len(data)] = data
        self.len_ += len(data)
        
        if self.len_ == self.size:
            self.close()
        
        return self.len_ == self.size, len(data)
    
    @property
    def value(self):
        return str(self.array)


DelimitedStringCollector = ByteArrayCollector
if hasattr(__builtin__, 'memoryview'):
    class MemoryViewCollector(Collector):
        def __init__(self, size, onclose=None):
            Collector.__init__(self, onclose)
            self.size = self.vsize = size
            self.view = self.intvalue = memoryview(bytearray(size))
        
        def add_data(self, prot, nbytes):
            """ Write at most nbytes bytes from prot to string. """
            Collector.add_data(self, prot, nbytes)
            
            nrecv = prot.recv_into(self.view, min(nbytes, self.vsize))
            self.view = self.view[nrecv:]
            self.vsize -= nrecv
            
            if self.vsize == 0:
                self.close()
            
            return (self.vsize == 0), nrecv
        
        @property
        def value(self):
            return self.intvalue.tobytes()
    
    DelimitedStringCollector = MemoryViewCollector


class CollectorQueue(Collector):
    """ Write data to the first collector until CollectorFull is raised,
    afterwards repeat with next. When the CollectorQueue gets empty it
    raises CollectorFull. """
    def __init__(self, collectors=None, onclose=None):
        Collector.__init__(self, onclose)
        if collectors is None:
            collectors = []
        self.collectors = collectors
    
    def __iadd__(self, collector):
        self.collectors.append(collector)
        return self
    
    def __add__(self, collector):
        return CollectorQueue(self.collectors + [collector])
    
    def add_collector(self, coll):
        """ Add coll to queue. """
        self.collectors.append(coll)
    
    def add_data(self, prot, nbytes):
        """ Add data to first collector until it is full. """
        Collector.add_data(self, prot, nbytes)
        while True:
            done, nrecv = self.collectors[0].add_data(prot, nbytes)
            if done:
                self.finish_collector(self.collectors.pop(0))
                if not self.collectors:
                    # Returning 
                    if not self.full():
                        # For the sake of consistency.
                        if not self.closed:
                            self.close()
                        return True, nrecv
            if nrecv:
                break
        return False, nrecv
    
    def finish_collector(self, coll):
        """ Called when a collector raises CollectorFull. """
        pass
    
    def full(self):
        """ Called when the last collector in the queue raises
        CollectorFull.
        
        Return True to prevent CollectorQueue from raising CollectorFull. """
    
    def close(self):
        """ Close collectors contained in the queue. """
        Collector.close(self)
        for collector in self.collectors:
            collector.close()
    
    @property
    def value(self):
        return None


class KeepingCollectorQueue(CollectorQueue):
    """ CollectorQueue that does not discard the collectors contained within
    after they have finished but rather appends to them to the list accessible
    through its member collected. """
    def __init__(self, collectors=None, onclose=None):
        CollectorQueue.__init__(self, collectors, onclose)
        self.collected = []
        
        self.intvalue = []
    
    def finish_collector(self, coll):
        """ Append finished collector to self.collected. """
        self.collected.append(coll)
        self.intvalue.append(coll.value)
        
    @property
    def value(self):
        return self.intvalue


class FactoryCollector(Collector):
    """ Call factory method to obtain the next collector until the factory
    raises the Depleted exception. """
    def __init__(self, factory, onclose=None):
        Collector.__init__(self, onclose)
        self.factory = factory
        self.cur_coll = None
    
    def init(self):
        """ Obtain first collector from factory method. """
        Collector.init(self)
        self.cur_coll = self.factory()
    
    def add_data(self, prot, nbytes):
        """ Add data to the current collector. """
        Collector.add_data(self, prot, nbytes)
        while True:
            done, nrecv = self.cur_coll.add_data(prot, nbytes)
            if done:
                try:
                    self.cur_coll = self.factory()
                # Wise?
                except Depleted:
                    # Redundant if?
                    if not self.closed:
                        self.close()
                    return True, nrecv
            if nrecv:
                break
        return False, nrecv
    
    @staticmethod
    def wrap_iterator(itr_next):
        """ Wrap the next method of an iterable in such a way that whenever
        it raises StopIteration, the wrapper raises Depleted. This is
        convenient when using FactoryCollector to obtain the collectors
        from an iterable. """
        def _wrap():
            try:
                return itr_next()
            except StopIteration:
                raise Depleted
        return _wrap
    
    @property
    def value(self):
        return None


class StructCollector(DelimitedCollector):
    """ Collect and unpack stru. Unpacked value can be found in .value and
    is available upon calling onclose. """
    def __init__(self, stru, onclose=None):
        DelimitedCollector.__init__(
            self, StringCollector(), stru.size, onclose
        )
        
        self.stru = stru
        self.intvalue = None
    
    def close(self):
        """ Unpack the data received and close the collector afterwards. """
        self.intvalue = self.stru.unpack(self.collector.value)
        DelimitedCollector.close(self)
    
    @property
    def value(self):
        return self.intvalue


class SingleStructValueCollector(StructCollector):
    """ Struct collector that makes the first item returned by unpack its
    value member. """
    @property
    def value(self):
        return self.intvalue[0]
    
class Handler(asynchia.Handler):
    """ asynchia handler that adds all received data to a collector,
    and reads outgoing data from an Input. """
    def __init__(self, transport, collector=None,
                 buffer_size=9046):
        asynchia.Handler.__init__(self, transport)
        
        self.queue = InputQueue()
        self.collector = collector
        self.buffer_size = buffer_size
        
        if collector is not None:
            self.transport.set_readable(True)
    
    def set_collector(self, collector, noclose=False):
        """ Set the top-level collector to collector. If noclose is False,
        the previous collector's close method is called. """
        if not noclose and self.collector is not None:
            self.collector.close()
        self.collector = collector
        if not self.transport.readable:
            self.transport.set_readable(True)
    
    def send_input(self, inp):
        """ Add inp to the main input queue. """
        self.queue.add(inp)
        if not self.transport.writeable:
            self.transport.set_writeable(True)
    
    def send_str(self, string):
        """ Convenience method for .send_input(StringInput(string)) """
        self.send_input(StringInput(string))
    
    def handle_read(self):
        """ Do the read call. """
        done, nrecv = self.collector.add_data(
            self.transport, self.buffer_size
        )
        if done:
            # We can safely assume it is readable here.
            self.transport.set_readable(False)
    
    def handle_write(self):
        """ Do the write call. """
        done, sent = self.queue.tick(self.transport)
        if done:
            # We can safely assume it is writeable here.
            self.transport.set_writeable(False)
    
    def has_data(self):
        """ Tell whether the Handler has any data to be sent. """
        return bool(self.queue)
    
    def close(self):
        """ Close top-level collector. """
        self.collector.close()
    
    def handle_error(self):
        raise


class MockHandler(object):
    """ This mocks a handler by writing everything that's passed
    to its send method to outbuf, while reading data from inbuf
    upon recv calls. """
    def __init__(self, inbuf=EMPTY_BYTES, outbuf=EMPTY_BYTES):
        self.outbuf = outbuf
        self.inbuf = inbuf
    
    def recv(self, bufsize):
        """ Return up to bufsize bytes from inbuf. Raise ValueError
        when inbuf is empty. """
        if not self.inbuf:
            return EMPTY_BYTES
        i = min(bufsize, len(self.inbuf))
        data = self.inbuf[:i]
        self.inbuf = self.inbuf[i:]
        return data
    
    def send(self, data):
        """ Write data to outbuf. """
        self.outbuf += data
        return len(data)
