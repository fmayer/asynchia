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

import asynchia

# FIXME: Make up a nomenclature.

class Depleted(Exception):
    """ Base exception of InputEOF and CollectorFull. """
    pass


class InputEOF(Depleted):
    """ Raised by Inputs to show that they do not have no
    data to be sent anymore. """
    pass


class CollectorFull(Depleted):
    """ Raised by collectors to show that they either do not need any
    more data, or that they cannot store any data. """
    pass


class Input(object):
    """ Base-class for all Inputs. It implements __add__ to return an
    InputQueue consisting of the two operants. """
    # FIXME: Implicit __radd__ with str?
    def __init__(self, onclose=None):
        self.closed = self.inited = False
        self.onclose = onclose
    
    def tick(self, sock):
        """ Abstract method to be overridden. This should send the data
        contained in the Input over sock. """
        if self.closed:
            raise InputEOF
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
            if not self.inputs:
                if not self.eof():
                    raise InputEOF
            inp = self.inputs[0]
            try:
                sent = inp.tick(sock)
                break
            except InputEOF:
                self.inputs.pop(0)
        return sent
    
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
        if not self.buf:
            raise InputEOF
        
        sent = sock.send(self.buf)
        self.buf = self.buf[sent:]
        self.length -= sent
        
        return sent
    
    def __len__(self):
        return self.length


class FileInput(Input):
    """ Input that buffers at most buffer_size bytes read from the passed fd,
    and sends them in a buffered way. This can be used to "directly" send data
    contained in a file. """
    def __init__(self, fd, length=None, buffer_size=9096, closing=True,
                 onclose=None):
        Input.__init__(self, onclose)
        if length is None:
            pos = fd.tell()
            fd.seek(-1, 2)
            newpos = fd.tell()
            length = newpos - pos
            fd.seek(pos)
        
        self.fd = fd
        self.buffer_size = buffer_size
        self.length = length
        self.closing = closing
        
        self.buf = ''        
        self.eof = False
    
    def tick(self, sock):
        """ Send as much of the file as possible. """
        Input.tick(self, sock)
        if not self.eof and len(self.buf) < self.buffer_size:
            read = self.fd.read(self.buffer_size - len(self.buf))
            if not read:
                self.eof = True
            self.buf += read
        
        if self.eof and not self.buf:
            self.close()
            raise InputEOF
        
        sent = sock.send(self.buf)        
        self.buf = self.buf[sent:]
        self.length -= sent
        return sent
    
    def close(self):
        """ If FileInput is closing, close the fd. """
        Input.close(self)
        if self.closing:
            self.fd.close()
    
    @classmethod
    def from_filename(cls, filename, *args, **kwargs):
        """ Same as cls(fd, size, *args, **kwargs) while fd and size
        get constructed from the filename. """
        stat = os.stat(filename)
        fd = open(filename)
        return cls(fd, stat.st_size, *args, **kwargs)
    
    def __len__(self):
        return self.length


class AutoFileInput(FileInput):
    """ Same as FileInput, only that it stores samples to guess how big
    the buffer should be. """
    def __init__(self, fd, length=None, buffer_size=9096, closing=True,
                 samples=100, onclose=None):
        FileInput.__init__(self, fd, length, buffer_size, closing, onclose)
        
        self.samples = samples
        self.sample = []
    
    def tick(self, sock):
        """ See FileInput.tick. """
        sent = FileInput.tick(self, sock)
        if len(self.sample) == self.samples:
            # Replace oldest sample with new one.
            self.sample.pop(0)
        self.sample.append(sent)
        self.buffer_size = int(round(sum(self.sample) / len(self.sample)))
        return sent


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
            raise CollectorFull
        
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
        
        self.string = ''
    
    def add_data(self, prot, nbytes):
        """ Write at most nbytes bytes from prot to string. """
        Collector.add_data(self, prot, nbytes)
        
        received = prot.recv(nbytes)
        self.string += received
        return len(received)


class FileCollector(Collector):
    """ Write data received from the socket into a fd. """
    def __init__(self, fd=None, closing=True, autoflush=False, onclose=None):
        Collector.__init__(self, onclose)
        
        self.fd = fd
        self.closing = closing
        self.autoflush = autoflush
    
    def add_data(self, prot, nbytes):
        """ Write at most nbytes data from prot to fd. """
        Collector.add_data(self, prot, nbytes)
        
        received = prot.recv(nbytes)
        try:
            self.fd.write(received)
        except ValueError:
            # I/O operation on closed file. This shouldn't be happening.
            raise CollectorFull
        else:
            if self.autoflush:
                self.fd.flush()
        return len(received)
    
    def close(self):
        """ Close the fd if the FileCollector is closing. """
        Collector.close(self)
        if self.closing:
            self.fd.close()


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
        
        if self.size > 0:
            nrecv = self.collector.add_data(prot, min(self.size, nbytes))
            self.size -= nrecv
            return nrecv
        else:
            if not self.closed:
                self.close()
            raise CollectorFull
    
    def close(self):
        """ Close wrapped collector. """
        Collector.close(self)
        self.collector.close()
    
    def init(self):
        """ Initialise wrapped collector. """
        Collector.init(self)
        self.collector.init()


class CollectorQueue(Collector):
    """ Write data to the first collector until CollectorFull is raised,
    afterwards repeat with next. When the CollectorQueue gets empty it
    raises CollectorFull. """
    def __init__(self, collectors=None, onclose=None):
        Collector.__init__(self, onclose)
        if collectors is None:
            collectors = []
        self.collectors = collectors
    
    def add_collector(self, coll):
        """ Add coll to queue. """
        self.collectors.append(coll)
    
    def add_data(self, prot, nbytes):
        """ Add data to first collector until it is full. """
        Collector.add_data(self, prot, nbytes)
        while True:
            try:
                nrecv = self.collectors[0].add_data(prot, nbytes)
                break
            except CollectorFull:
                self.finish_collector(self.collectors.pop(0))
                if not self.collectors:
                    # Returning 
                    if not self.full():
                        raise CollectorFull
        return nrecv
    
    def finish_collector(self, coll):
        """ Called when a collector raises CollectorFull. """
        pass
    
    def full(self):
        """ Called when the last collector in the queue raises
        CollectorFull.
        
        Return True to prevent CollectorQueue from raising CollectorFull. """
        if not self.closed:
            self.close()
    
    def close(self):
        """ Close collectors contained in the queue. """
        Collector.close(self)
        for collector in self.collectors:
            collector.close()


class StructCollector(DelimitedCollector):
    """ Collect and unpack stru. Unpacked value can be found in .value and
    is available upon calling onclose. """
    def __init__(self, stru, onclose=None):
        DelimitedCollector.__init__(
            self, StringCollector(), stru.size, onclose
        )
        
        self.stru = stru
        self.value = None
    
    def close(self):
        """ Unpack the data received and close the collector afterwards. """
        self.value = self.stru.unpack(self.collector.string)
        DelimitedCollector.close(self)


class Handler(asynchia.IOHandler):
    """ asynchia handler that adds all received data to a collector,
    and reads outgoing data from an Input. """
    def __init__(self, socket_map, sock=None, collector=None,
                 buffer_size=9046):
        asynchia.IOHandler.__init__(self, socket_map, sock)
        
        self.queue = InputQueue()
        self.collector = collector
        self.buffer_size = buffer_size
        
        if collector is not None:
            self.set_readable(True)
    
    def set_collector(self, collector):
        """ Set the top-level collector to collector. """
        self.collector = collector
        if not self.readable:
            self.set_readable(True)
    
    def send_input(self, inp):
        """ Add inp to the main input queue. """
        self.queue.add(inp)
        if not self.writeable:
            self.set_writeable(True)
    
    def send_str(self, string):
        """ Convenience method for .send_input(StringInput(string)) """
        self.send_input(StringInput(string))
    
    def handle_read(self):
        """ Do the read call. """
        try:
            self.collector.add_data(self, self.buffer_size)
        except CollectorFull:
            # We can safely assume it is readable here.
            self.set_readable(False)
    
    def handle_write(self):
        """ Do the write call. """
        try:
            sent = self.queue.tick(self)
        except InputEOF:
            # We can safely assume it is writeable here.
            self.set_writeable(False)
    
    def has_data(self):
        """ Tell whether the Handler has any data to be sent. """
        return bool(self.queue)


class MockHandler(object):
    """ This mocks a handler by writing everything that's passed
    to its send method to outbuf, while reading data from inbuf
    upon recv calls. """
    def __init__(self, inbuf='', outbuf=''):
        self.outbuf = outbuf
        self.inbuf = inbuf
    
    def recv(self, bufsize):
        """ Return up to bufsize bytes from inbuf. Raise ValueError
        when inbuf is empty. """
        if not self.inbuf:
            raise ValueError
        i = min(bufsize, len(self.inbuf))
        data = self.inbuf[:i]
        self.inbuf = self.inbuf[i:]
        return data
    
    def send(self, data):
        """ Write data to outbuf. """
        self.outbuf += data
        return len(data)
