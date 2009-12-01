# pypentago - a board game
# Copyright (C) 2008 Florian Mayer

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

from __future__ import with_statement

import tarfile
import bz2
import gzip
import sys
import os
import re
import imp

from contextlib import closing
from StringIO import StringIO
from optparse import OptionParser

from mercurial.dispatch import dispatch


s_path = os.path.abspath(os.path.dirname(__file__))


BUFFER = 4096
NAME = 'asynchia'
RELEASE_DIR = os.path.join(s_path, os.pardir, 'release/')
SRC_PATH = os.path.abspath(os.path.join(s_path, os.pardir))
PKG_DIR = os.path.join(SRC_PATH, 'asynchia')
VERSION_REGEX = re.compile("^VERSION = (.+?)$", re.MULTILINE)
INIT_VERSION_REGEX = re.compile("^__version__ = (.+?)$", re.MULTILINE)


def buffered_write(dest, src, buffer_size):
    read = src.read(buffer_size)
    while read:
        dest.write(read)
        read = src.read(buffer_size)


def create_files(version, output):
    tar_io = StringIO()
    
    tar = tarfile.TarFile(mode='w', fileobj=tar_io)
    tar.add(SRC_PATH, '-'.join((NAME, version)))
    tar.close()
    
    for out_file in output:
        tar_io.seek(0)
        with closing(out_file) as bz:
            buffered_write(bz, tar_io, BUFFER)

def update_setup(version):
    s = os.path.join(SRC_PATH, 'setup.py')
    with open(s) as setup:
        read = setup.read()
    new = VERSION_REGEX.sub('VERSION = %r' % version, read)
    with open(s, 'w') as setup:
        setup.write(new)

    m = os.path.join(PKG_DIR, '__init__.py')
    with open(m) as init:
        read = init.read()
    new = INIT_VERSION_REGEX.sub('__version__ = %r' % version, read)
    with open(m, 'w') as init:
        init.write(new)


def hg_commit(msg):
    dispatch(['commit', '-m', msg])


def hg_tag(name):
    dispatch(['tag', name])


def release(version, force=False, setup=True, commit=True,
            tag=True, packages=True):
    if tests:
        if not run_tests():
            print "Testsuite failed!"
            if not force:
                sys.exit(1)
    
    if setup:
        update_setup(version)
        if commit:
            hg_commit('Release version %s' % version)
    if tag:
        hg_tag(version)
    if packages:
        if not os.path.exists(RELEASE_DIR):
            os.mkdir(RELEASE_DIR)
    
        release_file = os.path.join(RELEASE_DIR, '-'.join((NAME, version)))
        files = [bz2.BZ2File(release_file + '.tar.bz2', 'w'),
                 gzip.GzipFile(release_file + '.tar.gz', 'w')]
        create_files(version, files)


def main():
    parser = OptionParser()
    
    parser.add_option("-f", "--force", action="store_true", dest="force",
                      default=False, help="Ignore non-critical problems.")
    
    parser.add_option("-t", "--no-tag", action="store_false",
                      dest="tag", default=True, help="Don't run unittests.")
    
    parser.add_option("-c", "--no-commit", action="store_false",
                      dest="commit", default=True, help="Do not commit.")
    
    parser.add_option("-s", "--no-setup", action="store_false",
                      dest="setup", default=True,
                      help="Do not update version setup file.")
    
    parser.add_option("-p", "--no-packages", action="store_false",
                      dest="packages", default=True,
                      help="Do not create archives.")
    
    options, args = parser.parse_args()
    if len(args) != 1:
        print "Invalid number of arguments"
        return 2
    release(args[0], force=options.force,
            setup=options.setup, commit=options.commit,
            tag=options.tag, packages=options.packages)
    return 0


if __name__ == '__main__':
    sys.exit(main())
