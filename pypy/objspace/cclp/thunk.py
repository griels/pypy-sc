from pypy.module._stackless.coroutine import _AppThunk
from pypy.module._stackless.interp_coroutine import AbstractThunk

from pypy.objspace.cclp.misc import w
from pypy.objspace.cclp.global_state import scheduler
from pypy.objspace.cclp.types import W_Var, W_CVar, W_Future, W_FailedValue, \
     ConsistencyError, Solution, W_AbstractDomain
from pypy.objspace.cclp.interp_var import interp_wait, interp_entail, \
     interp_bind, interp_free, interp_wait_or

from pypy.objspace.std.listobject import W_ListObject
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
        scheduler[0].trace_vars(self._coro, logic_args(self.args.unpack()))
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                w(".! exceptional EXIT of procedure", str(id(self._coro)), "with", str(exc))
                scheduler[0].dirty_traced_vars(self._coro, W_FailedValue(exc))
                self._coro._dead = True
            else:
                w(".! clean EXIT of procedure", str(id(self._coro)))
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
                w(".! exceptional EXIT of future", str(id(self._coro)), "with", str(exc))
                failed_val = W_FailedValue(exc)
                self.space.bind(self.w_Result, failed_val)
                scheduler[0].dirty_traced_vars(self._coro, failed_val)
                self._coro._dead = True
            else:
                w(".! clean EXIT of future", str(id(self._coro)),
                  "-- setting future result", str(self.w_Result), "to",
                  str(self.costate.w_tempval))
                self.space.unify(self.w_Result, self.costate.w_tempval)
        finally:
            scheduler[0].remove_thread(self._coro)
            scheduler[0].schedule()

class CSpaceThunk(_AppThunk):
    "for a constraint script/logic program"
    def __init__(self, space, w_callable, args, coro):
        _AppThunk.__init__(self, space, coro.costate, w_callable, args)
        self._coro = coro

    def is_distributor(self):
        return self._coro == self._coro._cspace.distributor

    def call(self):
        w("-- initial thunk CALL in", str(id(self._coro)))
        scheduler[0].trace_vars(self._coro, logic_args(self.args.unpack()))
        cspace = self._coro._cspace
        cspace.distributor = self._coro
        space = self.space
        try:
            try:
                _AppThunk.call(self)
            except Exception, exc:
                # maybe app_level sent something ...
                w("-- exceptional EXIT of cspace", str(id(self._coro)), "with", str(exc))
                failed_value = W_FailedValue(exc)
                scheduler[0].dirty_traced_vars(self._coro, failed_value)
                self._coro._dead = True
                if self.is_distributor():
                    cspace.fail()
                interp_bind(cspace._solution, failed_value)
            else:
                w("-- clean (valueless) EXIT of cspace", str(id(self._coro)))
                interp_bind(cspace._solution, self.costate.w_tempval)
                if self.is_distributor():
                    interp_bind(cspace._choice, space.newint(1))
        finally:
            scheduler[0].remove_thread(self._coro)
            scheduler[0].schedule()


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
            self.coro._dead = True
            scheduler[0].remove_thread(self.coro)
            scheduler[0].schedule()


class DistributorThunk(AbstractThunk):
    def __init__(self, space, w_distributor, coro):
        self.space = space
        self.coro = coro
        self.dist = w_distributor

    def call(self):
        coro = self.coro
        cspace = coro._cspace
        try:
            cspace.distributor = coro
            dist = self.dist
            try:
                while dist.distributable():
                    choice = cspace.choose(dist.fanout())
                    dist.w_distribute(choice)
                w("-- DISTRIBUTOR thunk exited because a solution was found")
                #XXX assert that all propagators are entailed
                sol = cspace._solution
                assert isinstance(sol, W_Var)
                varset = sol.w_bound_to
                assert isinstance(varset, W_ListObject)
                for var in varset.wrappeditems:
                    assert isinstance(var, W_CVar)
                    dom = var.w_dom
                    assert isinstance(dom, W_AbstractDomain)
                    assert dom.size() == 1
                    interp_bind(var, dom.get_values()[0])
                assert interp_free(cspace._choice)
                interp_bind(cspace._choice, self.space.newint(1))
            except ConsistencyError, e:
                w("-- DISTRIBUTOR thunk exited because", str(e))
                interp_bind(cspace._choice, self.space.newint(0))
            except:
                if not we_are_translated():
                    import traceback
                    traceback.print_exc()
        finally:
            interp_bind(cspace._finished, self.space.w_True)
            coro._dead = True
            scheduler[0].remove_thread(coro)
            scheduler[0].schedule()
        
