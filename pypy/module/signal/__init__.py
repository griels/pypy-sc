
from pypy.interpreter.mixedmodule import MixedModule

class Module(MixedModule):
    interpleveldefs = {
        'signal':  'interp_signal.signal',
        'NSIG':    'interp_signal.NSIG',
        'SIG_DFL': 'interp_signal.SIG_DFL',
        'SIG_IGN': 'interp_signal.SIG_IGN',
    }

    appleveldefs = {
    }

    def buildloaders(cls):
        from pypy.module.signal import interp_signal
        for name in interp_signal.signal_names:
            signum = getattr(interp_signal, name)
            if signum is not None:
                Module.interpleveldefs[name] = 'space.wrap(%d)' % (signum,)
        super(Module, cls).buildloaders()
    buildloaders = classmethod(buildloaders)

    def __init__(self, space, *args):
        "NOT_RPYTHON"
        from pypy.module.signal.interp_signal import CheckSignalAction
        MixedModule.__init__(self, space, *args)
        # add the signal-checking callback as an action on the space
        space.pending_actions.append(CheckSignalAction(space))
