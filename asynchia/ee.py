# (C) 2009 by Florian Mayer

import os

import asynchia

# TODO: Either make Inputs return -1 when they are out of data,
# or make Collectors throw CollectorFull when they don't need
# consequent data.

class InputEOF(Exception):
    pass


class Input(object):
    # FIXME: Implicit __radd__ with str?
    def __init__(self):
        pass
    
    def tick(self, sock):
        raise NotImplementedError
    
    def close(self):
        pass
    
    def __add__(self, other):
        return InputQueue([self, other])


class InputQueue(Input):
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
    def __init__(self):
        self.inited = self.closed = False
    
    def add_data(self, prot, nbytes):
        raise NotImplementedError
    
    def close(self):
        self.closed = True
    
    def init(self):
        self.inited = True


class StringCollector(Collector):
    def __init__(self):
        Collector.__init__(self)
        
        self.string = ''
    
    def add_data(self, prot, nbytes):
        if self.done:
            return -1
        received = prot.recv(nbytes)
        self.string += received
        return len(received)


class FileCollector(Collector):
    def __init__(self, fd=None):
        Collector.__init__(self)
        
        self.fd = fd
    
    def add_data(self, prot, nbytes):
        received = prot.recv(nbytes)
        try:
            self.fd.write(received)
        except ValueError:
            # I/O operation on closed file.
            return -1
        return len(received)
    
    def close(self):
        Collector.close(self)
        self.fd.close()


class DelimitedCollector(Collector):
    def __init__(self, collector, size):
        Collector.__init__(self)
        self.collector = collector
        self.size = size
    
    def add_data(self, prot, nbytes):
        if self.size > 0:
            nrecv = self.collector.add_data(prot, min(self.size, nbytes))
            self.size -= nrecv
            return nrecv
        else:
            return -1


class CollectorQueue(Collector):
    # TODO: .close
    def __init__(self, collectors=None):
        CollectorQueue.__init__(self)
        if collectors is None:
            collectors = []
        self.collectors = collectors
    
    def add_data(self, prot, nbytes):
        if not self.collectors[0].inited:
            self.collectors[0].init()
        nrecv = self.collectors[0].add_data(prot, nbytes)
        if nrecv == -1:
            self.finish_collector(self.collectors.pop(0))
            self.collectors[0].close()
            if self.collectors:
                return 0
            else:
                return -1
        return nrecv
    
    def finish_collector(self, coll):
        pass

    
class Partitioner(CollectorQueue):
    def __init__(self, collectors=None, default=None):
        CollectorQueue.__init__(self, collectors)
        self.default = default
    
    def add_collector(self, collector, stopdefault=False):
        self.collectors.append(collector)
        if stopdefault and self.collectors[0] is self.default:
            self.rules.pop(0)
    
    def add_data(self, prot, nbytes):
        if not self.collectors:
            self.collectors.append(self.default)
        nrecv = CollectorQueue.add_data(self, prot, nbytes)


class Protocol(asynchia.IOHandler):
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
        if self.collector.add_data(self, self.buffer_size) == -1:
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
