import os
import sys

script_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
mod_path = os.path.abspath(os.path.join(script_path, 'doc', 'modules'))
args = [
    'asynchia' + x for x in
    ['.dsl', '.ee', '.forthcoming', '', '.maps', '.protocols',
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