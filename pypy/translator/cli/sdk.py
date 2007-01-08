import platform
import py

class AbstractSDK(object):
    def _check_helper(cls, helper):
        if py.path.local.sysfind(helper) is None:
            py.test.skip("%s is not on your path." % helper)
        else:
            return helper
    _check_helper = classmethod(_check_helper)

    def runtime(cls):
        for item in cls.RUNTIME:
            cls._check_helper(item)
        return cls.RUNTIME
    runtime = classmethod(runtime)

    def ilasm(cls):
        return cls._check_helper(cls.ILASM)
    ilasm = classmethod(ilasm)

    def csc(cls):
        return cls._check_helper(cls.CSC)
    csc = classmethod(csc)

    def peverify(cls):
        return cls._check_helper(cls.PEVERIFY)
    peverify = classmethod(peverify)

class MicrosoftSDK(AbstractSDK):
    RUNTIME = []
    ILASM = 'ilasm'    
    CSC = 'csc'
    PEVERIFY = 'peverify'

class MonoSDK(AbstractSDK):
    RUNTIME = ['mono']
    ILASM = 'ilasm2'
    CSC = 'gmcs'
    PEVERIFY = 'peverify' # it's not part of mono, but we get a meaningful skip message

if platform.system() == 'Windows':
    SDK = MicrosoftSDK
else:
    SDK = MonoSDK
