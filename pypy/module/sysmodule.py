from pypy.interpreter.error import OperationError
from pypy.interpreter.extmodule import ExtModule
from pypy.interpreter.gateway import interp2app
import os, pypy

import sys as cpy_sys

class Sys(ExtModule):
    """ Template for PyPy's 'sys' module.

    Currently we only provide a handful of attributes.
    """

    __name__ = 'sys'

    def __init__(self, space):
        opd = os.path.dirname
        pypydir = opd(opd(os.path.abspath(pypy.__file__)))
        appdir = os.path.join(pypydir, 'pypy', 'appspace')
        self.path = [appdir] + [p for p in cpy_sys.path if p!= pypydir]
        self.w_modules = space.newdict([])
        ExtModule.__init__(self, space)

    stdout = cpy_sys.stdout
    stderr = cpy_sys.stderr
    maxint = cpy_sys.maxint

    def _setmodule(self, w_module):
        """ put a module into the modules list """
        w_name = self.space.getattr(w_module, self.space.wrap('__name__'))
        self.space.setitem(self.w_modules, w_name, w_module)

    def displayhook(self, w_x):
        space = self.space
        w = space.wrap
        if not space.is_true(space.is_(w_x, space.w_None)):
            try:
                print space.unwrap(self.space.repr(w_x))
            except OperationError:
                print "! could not print", w_x
            space.setitem(space.w_builtins, w('_'), w_x)

    def _getframe(self):
        # XXX No Argument Accepted Yet
        f = self.space.getexecutioncontext().framestack.items[-1]
        return self.space.wrap(f)
    app__getframe = interp2app(_getframe)
