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

import os
import sys

script_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
mod_path = os.path.abspath(os.path.join(script_path, 'doc', 'modules'))
args = [
    'asynchia' + x for x in
    ['.dsl', '.ee', '.defer', '', '.maps', '.protocols',
     '.qtmap', '.util']
]

idx = """
API Documentation
=================

%s""".strip()

if __name__ == '__main__':
    for module in args:
        with open(os.path.join(mod_path, module + '.rst'), 'w') as fd:
            fd.write(module + '\n')
            fd.write(len(module) * '=' + '\n\n')
            fd.write('.. automodule:: %s\n' % module)
            fd.write('    :members:\n')
    
    with open(os.path.join(mod_path, 'index.rst'), 'w') as fd:
        fd.write(
            idx % "\n    ".join(
                ['.. toctree::', ':maxdepth: 2', ''] + sorted(args)
            )
        )
