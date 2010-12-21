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

import time
import threading

class Benchmark(object):
    def set_up(self):
        pass
    
    def run(self):
        pass
    
    def tear_down(self):
        pass


class SequentialBenchmark(Benchmark):
    def execute(self, callback):
        start = time.time()
        self.run()
        stop = time.time()
        callback(stop - start)


class AsyncBenchmark(Benchmark):
    def __init__(self):
        self.start = None
        self.stop = None
        self.callback = None
    
    def set_start(self, start):
        self.start = start
    
    def submit_async(self, stop=None):
        if stop is None:
            stop = time.time()
        self.callback(stop - self.start)
    
    def execute(self, callback):
        self.start = time.time()
        self.callback = callback
        self.run()


class TimeResult(object):
    def __init__(self, data=None):
        if data is None:
            data = []
        
        self.data = data
        self.total = None
    
    def mean(self):
        return sum(self.data) / float(len(self.data))
    
    def stdev(self, sample=True, mean_=None):
        if mean_ is None:
            mean_ = self.mean()
        return sum((x - mean_) ** 2 for x in self.data) / float(
            len(self.data) - int(sample)
        )
    
    def mean_stdev(self):
        mean = self.mean()
        stdev = self.stdev(mean_=mean)
        return mean, stdev
    
    def add_data(self, time_elapsed):
        self.data.append(time_elapsed)
    
    def __repr__(self):
        return "<TimeResult(%r)>" % self.data


class Runner(object):
    def __init__(self, benchmarks=None, done_callback=None):
        if benchmarks is None:
            benchmarks = []
        self.benchmarks = benchmarks
        self.waiting = self.result = None
        self.done = threading.Event()
        self.done_callback = done_callback
    
    def callback(self, data):
        self.waiting -= 1
        self.result.add_data(data)
        
        if self.waiting == 0:
            self.done.set()
            if self.done_callback is not None:
                self.done_callback()
    
    def start(self, result=None):
        self.waiting = len(self.benchmarks)
        
        if result is None:
            result = TimeResult()
        self.result = result
        
        for benchmark in self.benchmarks:
            benchmark.set_up()
        
        for benchmark in self.benchmarks:
            benchmark.execute(self.callback)
    
    def wait(self):
        self.done.wait()
        self.done.clear()
        return self.result
    
    def add_benchmark(self, benchmark):
        self.benchmarks.append(benchmark)


if __name__ == '__main__':
    class MyBench(AsyncBenchmark):
        def run(self):
            self.submit_async(time.sleep(1))
    
    runner = Runner([MyBench() for _ in xrange(5)])
    runner.start()
    print runner.wait()
