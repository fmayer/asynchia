#! /usr/bin/env python
# -*- coding: us-ascii -*-

# asynchia - asynchronous networking library
# Copyright (C) 2010 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
import optparse
import sys
import imp
import os

from itertools import chain

PATH = os.path.abspath(os.path.dirname(__file__))
MODULES = ['test_core', 'test_dsl', 'test_ee', 'test_util']


class DummyTestRunner:
    def run(self, test):
        result = unittest.TestResult()
        test(result)
        return result


def run_all(test_runner=None, but=None):
    if but is None:
        but = []
    
    if test_runner is None:
        test_runner = DummyTestRunner()
    
    for elem in but:
        if elem.strip() in MODULES:
            MODULES.remove(elem)
    
    mod = map(__import__, MODULES)
    test_cases = chain(*[unittest.findTestCases(mod) for mod in mod])
    suite = unittest.TestSuite(test_cases)
    result = test_runner.run(suite)
    return result


if __name__ == '__main__':
    result = run_all(unittest.TextTestRunner(), sys.argv[1:])
    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)
