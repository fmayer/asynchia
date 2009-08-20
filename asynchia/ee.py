# (C) 2009 by Florian Mayer

import os

import asynchia

# FIXME: Make up a nomenclature.

class InputEOF(Exception):
    """ Raised by Inputs to show that they do not have no
    data to be sent anymore. """
    pass


class CollectorFull(Exception):
    """ Raised by collectors to show that they either do not need any
    more data, or that they cannot store any data. """
    pass


class Input(object):
    """ Base-class for all Inputs. It implements __add__ to return an
    InputQueue consisting of the two operants. """
    # FIXME: Implicit __radd__ with str?
    def __init__(self):
        pass
    
    def tick(self, sock):
        """ Abstract method to be overridden. This should send the data
        contained in the Input over sock. """
        raise NotImplementedError
    
    def close(self):
        pass
    
    def __add__(self, other):
        return InputQueue([self, other])


class InputQueue(Input):
    """ An InputQueue calls the tick method an object until it raises
    InputEOF, then it goes on with the next object in the queue. If no
    object is in the queue anymore, InputQueue.tick raises InputEOF (like
    any other Input that doesn't need data anymore). """
    def __init__(self, inputs=None):
        Input.__init__(self)
        if inputs is None:
            inputs = []
        self.inputs = inputs
    
    def tick(self, sock):
        while True:
            if not self.inputs:
                raise InputEOF
            inp = self.inputs[0]
            try:
                sent = inp.tick(sock)
                break
            except InputEOF:
                self.inputs.pop(0)
        return sent
    
    def close(self):
        for inp in self.inputs:
            inp.close()
    
    def add(self, other):
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
    def __init__(self, string):
        Input.__init__(self)
        
        self.buf = string
        self.length = len(self.buf)
    
    def tick(self, sock):        
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
    def __init__(self, fd, length=None, buffer_size=9096, closing=True):
        Input.__init__(self)
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
                 samples=100):
        FileInput.__init__(self, fd, length, buffer_size, closing)
        
        self.samples = samples
        self.sample = []
    
    def tick(self, sock):
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
    def __init__(self):
        self.inited = self.closed = False
    
    def add_data(self, prot, nbytes):
        if self.closed:
            raise CollectorFull
    
    def close(self):
        self.closed = True
    
    def init(self):
        self.inited = True


class StringCollector(Collector):
    """ Store data received from the socket in a string. """
    def __init__(self):
        Collector.__init__(self)
        
        self.string = ''
    
    def add_data(self, prot, nbytes):
        Collector.add_data(self, prot, nbytes)
        
        received = prot.recv(nbytes)
        self.string += received
        return len(received)


class FileCollector(Collector):
    """ Write data received from the socket into a fd. """
    def __init__(self, fd=None):
        Collector.__init__(self)
        
        self.fd = fd
    
    def add_data(self, prot, nbytes):
        Collector.add_data(self, prot, nbytes)
        
        received = prot.recv(nbytes)
        try:
            self.fd.write(received)
        except ValueError:
            # I/O operation on closed file.
            raise CollectorFull
        return len(received)
    
    def close(self):
        Collector.close(self)
        self.fd.close()


class DelimitedCollector(Collector):
    """ Collect up to size bytes in collector and raise CollectorFull
    afterwards. """
    def __init__(self, collector, size):
        Collector.__init__(self)
        self.collector = collector
        self.size = size
    
    def add_data(self, prot, nbytes):
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
        Collector.close(self)
        self.collector.close()
    
    def init(self):
        Collector.init(self)
        self.collector.init()


class CollectorQueue(Collector):
    """ Write data to the first collector until CollectorFull is raised,
    afterwards repeat with next. When the CollectorQueue gets empty it
    raises CollectorFull. """
    def __init__(self, collectors=None):
        Collector.__init__(self)
        if collectors is None:
            collectors = []
        self.collectors = collectors
    
    def add_data(self, prot, nbytes):
        Collector.add_data(self, prot, nbytes)
        while True:
            if not self.collectors[0].inited:
                self.collectors[0].init()
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
        pass
    
    def full(self):
        if not self.closed:
            self.close()
    
    def close(self):
        Collector.close(self)
        if self.collectors and self.collectors[0].inited:
            self.collectors[0].close()

    
class Partitioner(CollectorQueue):
    def __init__(self, collectors=None, default=None):
        CollectorQueue.__init__(self, collectors)
        self.default = default
    
    def add_collector(self, collector, stopdefault=False):
        self.collectors.append(collector)
        if stopdefault and self.collectors[0] is self.default:
            self.rules.pop(0)
    
    def add_data(self, prot, nbytes):
        nrecv = CollectorQueue.add_data(self, prot, nbytes)
    
    def full(self):
        self.collectors.append(self.default)
        return True
    
    def close(self):
        CollectorQueue.close(self)
        if self.default is not None and self.default.inited:
            self.default.close()


class Handler(asynchia.IOHandler):
    def __init__(self, collector=None, buffer_size=9046):
        self.queue = InputQueue()
        self.collector = collector
        self.buffer_size = buffer_size
        
        if collector is not None:
            self.set_readable(True)
    
    def set_collector(self, collector):
        self.collector = collector
        if not self.readable:
            self.set_readable(True)
    
    def send_input(self, inp):
        self.queue.add(inp)
        if not self.writeable:
            self.set_writeable(True)
    
    def send_str(self, string):
        """ Convenience method for .send_input(StringInput(string)) """
        self.send_input(StringInput(string))
    
    def handle_read(self):
        try:
            self.collector.add_data(self, self.buffer_size)
        except CollectorFull:
            # We can safely assume it is readable here.
            self.set_readable(False)
    
    def handle_write(self):
        try:
            sent = self.queue.tick(self)
        except InputEOF:
            # We can safely assume it is writeable here.
            self.set_writeable(False)
    
    def has_data(self):
        return bool(self.queue)


class MockHandler(object):
    def __init__(self, inbuf='', outbuf=''):
        self.outbuf = outbuf
        self.inbuf = inbuf
    
    def recv(self, bufsize):
        if not self.inbuf:
            raise ValueError
        i = min(bufsize, len(self.inbuf))
        data = self.inbuf[:i]
        self.inbuf = self.inbuf[i:]
        return data
    
    def send(self, data):
        self.outbuf += data
        
    
if __name__ == '__main__':
    a = DelimitedCollector(StringCollector(), 5)
    b = DelimitedCollector(StringCollector(), 4)
    c = DelimitedCollector(StringCollector(), 3)
    
    q = CollectorQueue([a, b, c])
    
    m = MockHandler(inbuf='a' * 5 + 'b' * 4 + 'c' * 3)
    while True:
        try:
            q.add_data(m, 5)
        except (ValueError, CollectorFull):
            # The MockProtocol is out of data or the CollectorQueue is full.
            break
    print a.collector.string
    print b.collector.string
    print c.collector.string
