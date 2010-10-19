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
import socket
import pickle
import collections
import multiprocessing

from Queue import Empty

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
        self.nmap = {}
        
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
            except Empty:
                break
    
    def register(self, notifier):
        notifier.pool = self
        if not self.run(notifier):
            self.notifiers.append(notifier)
    
    def unregister(self, notifier):
        self.notifiers.remove(notifier)
    
    def free(self, notifier):
        self.running -= 1
        self.handle_squeue()
        
        del self.nmap[notifier]
        self._fill_slots()
    
    def _fill_slots(self):
        while self.notifiers and self.running < self.procs:
            noti = self.notifiers.popleft()
            if not self.run(noti):
                self.notifiers.appendleft(noti)
    
    def run(self, notifier):            
        try:
            id_ = self.imap.iterkeys().next()
        except StopIteration:
            return False
        
        self.running += 1
        
        queue, proc = self.imap.pop(id_)
        queue.put(
            (
                notifier.fun, notifier.args, notifier.kwargs, notifier.addr,
                notifier.pwd, notifier.id_
            )
        )
        self.wmap[id_] = (queue, proc)
        self.nmap[notifier] = (queue, proc, id_)
        return True
    
    def terminate(self, notifier):
        """ Kill the process for whose data the specified notifer is currently
        waiting. """
        try:
            queue, proc, id_ = self.nmap[notifier]
        except KeyError:
            return False
        
        del self.wmap[id_]
        
        self.running -= 1
        proc.terminate()
        
        queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=self.worker, args=(queue, self.statusq, id_)
        )
            
        proc.start()
        self.imap[id_] = (queue, proc)
        
        self._fill_slots()
    
    @staticmethod
    def worker(queue, statusq, wid_):
        """ The function run in the client that loops and reads the jobs from 
        queue (as a tuple containing the function, the positional arguments to
        be passed to it, the keyword arguments to be passed to it, the address
        of the server waiting for the reply, its password and the job-id that
        enables the server to associate the result with the corresponding
        notifier) until it is supplied None as the function. Also puts the 
        worker-id into the status-queue to tell the pool that the worker is
        ready to execute a new job. """
        while True:
            fun, args, kwargs, addr, pwd, id_ = queue.get()
            if fun is None:
                break
            _mp_client(fun, args, kwargs, addr, pwd, id_)
            statusq.put(wid_)
    
    
class _MPServerHandler(asynchia.Handler):
    """ Implementation detail. """
    BUFFER = 2048
    def __init__(self, transport, serv):
        asynchia.Handler.__init__(self, transport)
        self.data = b('')
        self.serv = serv
        
        self.transport.set_readable(True)
    
    def handle_read(self):
    """ Implementation detail. """
        self.data += self.transport.recv(self.BUFFER)
    
    def handle_close(self):
    """ Implementation detail. """
        # The password is not contained in a pickle tuple (which would be
        # far easier and straightforward) to avoid unpickling untrusted
        # data.
        id_, self.data = self.data.split(b('|'), 1)
        notifier = self.serv.get_notifier(int(id_))
        if self.data[:len(notifier.pwd)] == notifier.pwd:
            notifier.submit(
                pickle.loads(self.data[len(notifier.pwd):])
            )
            self.serv.release_notifier(int(id_))
        
        if notifier.pool is not None:
            notifier.pool.free(notifier)


class MPServer(asynchia.Server):
    """ Server managing the mapping of job-ids to notifiers and accepting
    connections of worker clients. """
    def __init__(self, transport):
        asynchia.Server.__init__(
            self, transport,
            lambda tr: _MPServerHandler(tr, self)
        )
        self.handler = None
        self.idpool = IDPool()
        self.notimap = {}
    
    def add_notifier(self, noti):
        """ Add a notifier and get the id that is to be passed to the
        corresponding worker process. """
        id_ = self.idpool.get()
        self.notimap[id_] = noti
        return id_
    
    def get_notifier(self, id_):
        """ Get the notifier corresponding to the id. """
        return self.notimap[id_]
    
    def release_notifier(self, id_):
        self.idpool.release(id_)
        self.notimap.pop(id_)


def _mp_client(fun, args, kwargs, addr, pwd, id_):
    sock = socket.socket()
    while True:
        try:
            sock.connect(addr)
        except socket.error:
            # FIXME: Only retry in certain cases, lest we enter
            # an infinite loop.
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
        
        self.pool = None
        self.proc = None
    
    def start_standalone_proc(self):
        self.proc = multiprocessing.Process(
            target=_mp_client,
            args=(self.fun, self.args, self.kwargs,
                  self.addr, self.pwd, self.id_
            )
        )
        
        self.proc.start()
    
    def terminate_proc(self):
        if self.proc is not None:
            self.proc.terminate()
            return True
        elif self.pool is not None:
            return self.pool.terminate(self)
        return False
