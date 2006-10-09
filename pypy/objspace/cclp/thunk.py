from pypy.module._stackless.coroutine import _AppThunk
from pypy.module._stackless.interp_coroutine import AbstractThunk

from pypy.objspace.cclp.misc import w
from pypy.objspace.cclp.global_state import sched
from pypy.objspace.cclp.types import W_Var, W_CVar, W_Future, W_FailedValue, \
     ConsistencyError, Solution, W_AbstractDomain
from pypy.objspace.cclp.interp_var import interp_wait, interp_entail, \
     interp_bind, interp_free, interp_wait_or

from pypy.objspace.std.listobject import W_ListObject
from pypy.objspace.std.listobject import W_TupleObject
from pypy.rpython.objectmodel import we_are_translated

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
        sched.uler.trace_vars(self._coro, logic_args(self.args.unpack()))
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                w(".! exceptional EXIT of procedure", str(id(self._coro)), "with", str(exc))
                sched.uler.dirty_traced_vars(self._coro, W_FailedValue(exc))
            else:
                w(".! clean EXIT of procedure", str(id(self._coro)))
        finally:
            sched.uler.remove_thread(self._coro)
            sched.uler.schedule()


class FutureThunk(_AppThunk):
    def __init__(self, space, w_callable, args, w_Result, coro):
        _AppThunk.__init__(self, space, coro.costate, w_callable, args)
        self.w_Result = w_Result 
        self._coro = coro

    def call(self):
        w(".! initial thunk CALL in", str(id(self._coro)))
        sched.uler.trace_vars(self._coro, logic_args(self.args.unpack()))
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                w(".! exceptional EXIT of future", str(id(self._coro)), "with", str(exc))
                failed_val = W_FailedValue(exc)
                self.space.bind(self.w_Result, failed_val)
                sched.uler.dirty_traced_vars(self._coro, failed_val)
            else:
                w(".! clean EXIT of future", str(id(self._coro)),
                  "-- setting future result", str(self.w_Result), "to",
                  str(self.costate.w_tempval))
                self.space.unify(self.w_Result, self.costate.w_tempval)
        finally:
            sched.uler.remove_thread(self._coro)
            sched.uler.schedule()

class CSpaceThunk(_AppThunk):
    "for a constraint script/logic program"
    def __init__(self, space, w_callable, args, coro):
        _AppThunk.__init__(self, space, coro.costate, w_callable, args)
        self._coro = coro

    def call(self):
        w("-- initial thunk CALL in", str(id(self._coro)))
        sched.uler.trace_vars(self._coro, logic_args(self.args.unpack()))
        cspace = self._coro._cspace
        space = self.space
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                # maybe app_level let something buble up ...
                w("-- exceptional EXIT of DISTRIBUTOR", str(id(self._coro)), "with", str(exc))
                failed_value = W_FailedValue(exc)
                sched.uler.dirty_traced_vars(self._coro, failed_value)
                interp_bind(cspace._solution, failed_value)
                cspace.fail()
            else:
                w("-- clean EXIT of DISTRIBUTOR (success)", str(id(self._coro)))
                sol = cspace._solution
                assert isinstance(sol, W_Var)
                interp_bind(sol, self.costate.w_tempval)
                outcome = sol.w_bound_to
                if not (isinstance(outcome, W_ListObject) or \
                        isinstance(outcome, W_TupleObject)):
                    w("WARNING: return value type of the script was not a list or tuple, we fail ...")
                    cspace.fail()
                    return
                assert interp_free(cspace._choice)
                interp_bind(cspace._choice, self.space.newint(1))
        finally:
            interp_bind(cspace._finished, self.space.w_True)
            sched.uler.remove_thread(self._coro)
            sched.uler.schedule()


class PropagatorThunk(AbstractThunk):
    def __init__(self, space, w_constraint, coro):
        self.space = space
        self.coro = coro
        self.const = w_constraint

    def call(self):
        try:
            cspace = self.coro._cspace
            try:
                while 1:
                    entailed = self.const.revise()
                    if entailed:
                        break
                    # we will block on domains being pruned
                    wait_list = []
                    _vars = self.const._variables
                    assert isinstance(_vars, list)
                    for var in _vars:
                        assert isinstance(var, W_CVar)
                        dom = var.w_dom
                        assert isinstance(dom, W_AbstractDomain)
                        wait_list.append(dom.give_synchronizer())
                    #or the cspace being dead
                    wait_list.append(cspace._finished)
                    interp_wait_or(self.space, wait_list)
                    if not interp_free(cspace._finished):
                        break
            except ConsistencyError:
                cspace.fail()
            except Exception: # rpython doesn't like just except:\n ...
                if not we_are_translated():
                    import traceback
                    traceback.print_exc()
        finally:
            sched.uler.remove_thread(self.coro)
            sched.uler.schedule()

