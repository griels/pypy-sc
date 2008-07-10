
from pypy.interpreter.mixedmodule import MixedModule 

class Module(MixedModule):
    """An itertools module."""

    interpleveldefs = {
        'count'     : 'interp_itertools.W_Count',
        'dropwhile' : 'interp_itertools.W_DropWhile',
        'repeat'    : 'interp_itertools.W_Repeat',
        'takewhile' : 'interp_itertools.W_TakeWhile',
    }

    appleveldefs = {
    }
