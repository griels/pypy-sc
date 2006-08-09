from pypy.module._stackless.coroutine import _AppThunk
from pypy.objspace.cclp.misc import w
from pypy.objspace.cclp.global_state import scheduler
from pypy.objspace.cclp.types import W_Var, W_Future, W_FailedValue


def logic_args(args):
    "returns logic vars found in unpacked normalized args"
    assert isinstance(args, tuple)
    pos = args[0]
    kwa = args[1]
    pos_l = [arg for arg in pos
             if isinstance(arg, W_Var)]
    kwa_l = [arg for arg in kwa.keys()
             if isinstance(arg, W_Var)]
    return pos_l + kwa_l

#-- Thunk -----------------------------------------


class ProcedureThunk(_AppThunk):
    def __init__(self, space, w_callable, args, coro):
        _AppThunk.__init__(self, space, coro.costate, w_callable, args)
        self._coro = coro

    def call(self):
        w(".! initial (returnless) thunk CALL in", str(id(self._coro)))
        scheduler[0].trace_vars(self._coro, logic_args(self.args.unpack()))
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                w(".! exceptional EXIT of", str(id(self._coro)), "with", str(exc))
                scheduler[0].dirty_traced_vars(self._coro, W_FailedValue(exc))
                self._coro._dead = True
            else:
                w(".! clean (valueless) EXIT of", str(id(self._coro)))
        finally:
            scheduler[0].remove_thread(self._coro)
            scheduler[0].schedule()


class FutureThunk(_AppThunk):
    def __init__(self, space, w_callable, args, w_Result, coro):
        _AppThunk.__init__(self, space, coro.costate, w_callable, args)
        self.w_Result = w_Result 
        self._coro = coro

    def call(self):
        w(".! initial thunk CALL in", str(id(self._coro)))
        scheduler[0].trace_vars(self._coro, logic_args(self.args.unpack()))
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                w(".! exceptional EXIT of", str(id(self._coro)), "with", str(exc))
                failed_val = W_FailedValue(exc)
                self.space.bind(self.w_Result, failed_val)
                scheduler[0].dirty_traced_vars(self._coro, failed_val)
                self._coro._dead = True
            else:
                w(".! clean EXIT of", str(id(self._coro)),
                  "-- setting future result", str(self.w_Result), "to",
                  str(self.costate.w_tempval))
                self.space.unify(self.w_Result, self.costate.w_tempval)
        finally:
            scheduler[0].remove_thread(self._coro)
            scheduler[0].schedule()

SPACE_FAILURE = 0
SPACE_SOLUTION = 1

class CSpaceThunk(_AppThunk):
    def __init__(self, space, w_callable, args, coro):
        _AppThunk.__init__(self, space, coro.costate, w_callable, args)
        self._coro = coro

    def call(self):
        w(". initial (returnless) thunk CALL in", str(id(self._coro)))
        scheduler[0].trace_vars(self._coro, logic_args(self.args.unpack()))
        cspace = self._coro._cspace
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                w(".% exceptional EXIT of", str(id(self._coro)), "with", str(exc))
                scheduler[0].dirty_traced_vars(self._coro, W_FailedValue(exc))
                self._coro._dead = True
                self.space.bind(cspace._choice, self.space.wrap(SPACE_FAILURE))
            else:
                w(".% clean (valueless) EXIT of", str(id(self._coro)))
                self.space.bind(cspace._choice, self.space.wrap(SPACE_SOLUTION))
        finally:
            scheduler[0].remove_thread(self._coro)
            scheduler[0].schedule()


from pypy.interpreter.argument import Arguments
from pypy.module._stackless.interp_coroutine import AbstractThunk

class PropagatorThunk(AbstractThunk):
    def __init__(self, space, w_constraint, coro, Merged):
        self.space = space
        self.coro = coro
        self.const = w_constraint
        self.Merged = Merged

    def call(self):
        try:
            while 1:
                entailed = self.const.revise()
                if entailed:
                    break
                Obs = W_Var(self.space)
                self.space.entail(self.Merged, Obs)
                for Sync in [var.w_dom.give_synchronizer()
                             for var in self.const._variables]:
                    self.space.entail(Sync, Obs)
                self.space.wait(Obs)
        finally:
            self.coro._dead = True
            scheduler[0].remove_thread(self.coro)
            scheduler[0].schedule()

