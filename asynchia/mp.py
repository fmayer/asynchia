import os
import socket
import pickle
import collections
import multiprocessing

try:
    import queue
except ImportError:
    import Queue as queue

import asynchia
from asynchia.forthcoming import DataNotifier
from asynchia.util import IDPool, b


class MPPool(object):
    def __init__(self, procs, notifiers=None):
        if notifiers is None:
            notifiers = []
        self.notifiers = collections.deque(notifiers)
        
        self.procs = procs
        self.running = 0
        
        self.wmap = {}
        self.imap = {}
        
        self.statusq = multiprocessing.Queue()
        
        for id_ in xrange(procs):
            queue = multiprocessing.Queue()
            proc = multiprocessing.Process(
                target=self.worker, args=(queue, self.statusq, id_)
            )
            
            proc.start()
            self.imap[id_] = (queue, proc)
    
    def handle_squeue(self):
        while True:
            try:
                id_ = self.statusq.get_nowait()
                self.imap[id_] = self.wmap.pop(id_)
            except queue.Empty:
                break
    
    def register(self, notifier):
        notifier.pool = self
        if not self.run(notifier):
            self.notifiers.append(notifier)
    
    def free(self):
        self.running -= 1
        
        self.handle_squeue()
        
        while self.notifiers and self.running < self.procs:
            if not self.run(self.notifiers.popleft()):
                break
    
    def run(self, notifier):            
        try:
            id_ = self.imap.iterkeys().next()
        except StopIteration:
            return False
        
        self.running += 1
        
        q, proc = self.imap.pop(id_)
        q.put(
            (
                notifier.fun, notifier.args, notifier.kwargs, notifier.addr,
                notifier.pwd, notifier.id_
            )
        )
        self.wmap[id_] = (q, proc)
        return True
        
    
    @staticmethod
    def worker(queue, statusq, wid_):
        while True:
            fun, args, kwargs, addr, pwd, id_ = queue.get()
            if fun is None:
                break
            _mp_client(fun, args, kwargs, addr, pwd, id_)
            statusq.put(wid_)
    
    
class _MPServerHandler(asynchia.Handler):
    BUFFER = 2048
    def __init__(self, tr, serv):
        asynchia.Handler.__init__(self, tr)
        self.data = ''
        self.serv = serv
        
        self.transport.set_readable(True)
    
    def handle_read(self):
        self.data += self.transport.recv(self.BUFFER)
    
    def handle_close(self):
        # The password is not contained in a pickle tuple (which would be
        # far easier and straightforward) to avoid unpickling untrusted
        # data.
        id_, self.data = self.data.split(b('|'), 1)
        notifier = self.serv.get_notifier(int(id_))
        if self.data[:len(notifier.pwd)] == notifier.pwd:
            notifier.submit(
                pickle.loads(self.data[len(notifier.pwd):])
            )
        if notifier.pool is not None:
            notifier.pool.free()


class MPServer(asynchia.Server):
    def __init__(self, transport):
        asynchia.Server.__init__(
            self, transport,
            lambda tr: _MPServerHandler(tr, self)
        )
        self.handler = None
        self.idpool = IDPool()
        self.notimap = {}
    
    def add_notifier(self, noti):
        id_ = self.idpool.get()
        self.notimap[id_] = noti
        return id_
    
    def get_notifier(self, id_):
        self.idpool.release(id_)
        return self.notimap.pop(id_)


def _mp_client(fun, args, kwargs, addr, pwd, id_):
    sock = socket.socket()
    while True:
        try:
            sock.connect(addr)
        except socket.error:
            pass
        else:
            break
    
    data = b(id_) + b('|') + pwd + pickle.dumps(fun(*args, **kwargs))
    while data:
        sent = sock.send(data)
        data = data[sent:]
    
    sock.close()
    

class MPNotifier(DataNotifier):
    def __init__(self, socket_map, fun, args=None, kwargs=None, serv=None,
                 pwdstr=10):
        DataNotifier.__init__(self, socket_map)
        
        if args is None:
            args = tuple()
        if kwargs is None:
            kwargs = {}
        pwd = os.urandom(pwdstr)
        
        if serv is None:
            serv = MPServer(
                asynchia.SocketTransport(socket_map)
            )
            serv.transport.bind(('127.0.0.1', 0))
            serv.transport.listen(0)
        self.id_ = serv.add_notifier(self)
        
        self.serv = serv
        
        self.fun = fun
        self.args = args
        self.kwargs = kwargs
        self.addr = serv.transport.socket.getsockname()
        self.pwd = pwd
    
    def start_standalone_proc(self):
        proc = multiprocessing.Process(
            target=_mp_client,
            args=(self.fun, self.args, self.kwargs,
                  self.addr, self.pwd, self.id_
            )
        )
        
        proc.start()
