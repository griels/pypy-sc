# Package initialisation
from pypy.interpreter.mixedmodule import MixedModule

class Module(MixedModule):
    """CLR module"""

    appleveldefs = {
        'ArrayList': 'app_dotnet.ArrayList',
    }
    
    interpleveldefs = {
        '_CliObject_internal': 'interp_dotnet.W_CliObject',
    }
