from pypy.interpreter.mixedmodule import MixedModule 

class Module(MixedModule):
    """A demo built-in module based on ctypes."""

    interpleveldefs = {
        'measuretime'      : 'demo.measuretime',
        'sieve'            : 'demo.sieve',
    }

    appleveldefs = {
        'DemoError'        : 'app_demo.DemoError',
    }
