from pypy.annotation import policy
from pypy.annotation import model as annmodel
from pypy.annotation.annrpython import RPythonAnnotator, BlockedInference
from pypy.annotation.annrpython import raise_nicer_exception
from pypy.objspace.flow.model import Variable
from pypy.jit.hintannotator import model as hintmodel
from pypy.jit.hintannotator.bookkeeper import HintBookkeeper
from pypy.rpython.lltypesystem import lltype


class HintAnnotatorPolicy(policy.AnnotatorPolicy):

    def __init__(self, novirtualcontainer     = False,
                       oopspec                = False,
                       entrypoint_returns_red = True):
        self.novirtualcontainer     = novirtualcontainer
        self.oopspec                = oopspec
        self.entrypoint_returns_red = entrypoint_returns_red

    def look_inside_graph(self, graph):
        return True


class StopAtXPolicy(HintAnnotatorPolicy):
    """Useful for tests."""

    def __init__(self, *funcs):
        HintAnnotatorPolicy.__init__(self, novirtualcontainer=True,
                                     oopspec=True)
        self.funcs = funcs

    def look_inside_graph(self, graph):
        try:
            if graph.func in self.funcs:
                return False
        except AttributeError:
            pass
        return True


class HintAnnotator(RPythonAnnotator):

    def __init__(self, translator=None, base_translator=None, policy=None):
        if policy is None:
            policy = HintAnnotatorPolicy()
        self.base_translator = base_translator
        assert base_translator is not None      # None not supported any more
        bookkeeper = HintBookkeeper(self)        
        RPythonAnnotator.__init__(self, translator, policy=policy,
                                  bookkeeper=bookkeeper)
        self.exceptiontransformer = base_translator.getexceptiontransformer()
        
    def build_types(self, origgraph, input_args_hs):
        desc = self.bookkeeper.getdesc(origgraph)
        flowgraph = desc.specialize(input_args_hs)
        return self.build_graph_types(flowgraph, input_args_hs)

    def consider_op_malloc(self, hs_TYPE):
        TYPE = hs_TYPE.const
        if self.policy.novirtualcontainer:
            return hintmodel.SomeLLAbstractVariable(lltype.Ptr(TYPE))
        else:
            vstructdef = self.bookkeeper.getvirtualcontainerdef(TYPE)
            return hintmodel.SomeLLAbstractContainer(vstructdef)

    consider_op_zero_malloc = consider_op_malloc

    def consider_op_malloc_varsize(self, hs_TYPE, hs_length):
        TYPE = hs_TYPE.const
        if self.policy.novirtualcontainer:
            return hintmodel.SomeLLAbstractVariable(lltype.Ptr(TYPE))
        else:
            vcontainerdef = self.bookkeeper.getvirtualcontainerdef(TYPE)
            return hintmodel.SomeLLAbstractContainer(vcontainerdef)

    consider_op_zero_malloc_varsize = consider_op_malloc_varsize

    def consider_op_zero_gc_pointers_inside(self, hs_v):
        pass

    def consider_op_keepalive(self, hs_v):
        pass

    def consider_op_debug_log_exc(self, hs_v):
        pass

    def consider_op_debug_assert(self, hs_v, *args_hs):
        pass

    def consider_op_resume_point(self, hs_v, *args_hs):
        pass

    def consider_op_ts_metacall(self, hs_metafunc, *args_hs):
        RESTYPE = self.bookkeeper.current_op_concretetype()
        return hintmodel.variableoftype(RESTYPE)

    def simplify(self):
        RPythonAnnotator.simplify(self, extra_passes=[])

    def noreturnvalue(self, op):
        assert op.result.concretetype is lltype.Void, (
            "missing annotation for the return variable of %s" % (op,))
        return hintmodel.s_void

HintAnnotator._registeroperations(hintmodel)
