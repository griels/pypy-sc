import py
from pypy.translator.translator import TranslationContext, graphof
from pypy.jit.hintannotator.annotator import HintAnnotator
from pypy.jit.hintannotator.bookkeeper import HintBookkeeper
from pypy.jit.hintannotator.model import *
from pypy.jit.timeshifter.timeshift import HintTimeshift
from pypy.jit.timeshifter import rtimeshift, rvalue, rtyper as hintrtyper
from pypy.jit.llabstractinterp.test.test_llabstractinterp import annotation
from pypy.jit.llabstractinterp.test.test_llabstractinterp import summary
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.objectmodel import hint, keepalive_until_here
from pypy.rpython.unroll import unrolling_iterable
from pypy.rpython.lltypesystem import rstr
from pypy.rpython.annlowlevel import PseudoHighLevelCallable
from pypy.annotation import model as annmodel
from pypy.rpython.llinterp import LLInterpreter
from pypy.objspace.flow.model import checkgraph
from pypy.annotation.policy import AnnotatorPolicy
from pypy.translator.backendopt.inline import auto_inlining
from pypy import conftest

P_NOVIRTUAL = AnnotatorPolicy()
P_NOVIRTUAL.novirtualcontainer = True

def getargtypes(annotator, values):
    return [annotation(annotator, x) for x in values]

def hannotate(func, values, policy=None, inline=None):
    # build the normal ll graphs for ll_function
    t = TranslationContext()
    a = t.buildannotator()
    argtypes = getargtypes(a, values)
    a.build_types(func, argtypes)
    rtyper = t.buildrtyper()
    rtyper.specialize()
    if inline:
        auto_inlining(t, inline)
    graph1 = graphof(t, func)
    # build hint annotator types
    hannotator = HintAnnotator(policy=policy)
    hannotator.base_translator = t
    hs = hannotator.build_types(graph1, [SomeLLAbstractConstant(v.concretetype,
                                                                {OriginFlags(): True})
                                         for v in graph1.getargs()])
    if conftest.option.view:
        hannotator.translator.view()
    return hs, hannotator, rtyper

class TimeshiftingTests(object):
    from pypy.jit.codegen.llgraph.rgenop import RGenOp

    def setup_class(cls):
        cls._cache = {}
        cls._cache_order = []

    def teardown_class(cls):
        del cls._cache
        del cls._cache_order

    def timeshift_cached(self, ll_function, values, inline, policy):
        key = ll_function, inline, policy
        try:
            result, argtypes = self._cache[key]
        except KeyError:
            if len(self._cache_order) >= 3:
                del self._cache[self._cache_order.pop(0)]
            hs, ha, rtyper = hannotate(ll_function, values,
                                       inline=inline, policy=policy)
            htshift = HintTimeshift(ha, rtyper, self.RGenOp)
            RESTYPE = htshift.originalconcretetype(
                ha.translator.graphs[0].getreturnvar())
            htshift.timeshift()
            t = rtyper.annotator.translator
            for graph in ha.translator.graphs:
                checkgraph(graph)
                t.graphs.append(graph)
            if conftest.option.view:
                from pypy.translator.tool.graphpage import FlowGraphPage
                FlowGraphPage(t, ha.translator.graphs).display()
            result = hs, ha, rtyper, htshift, RESTYPE
            self._cache[key] = result, getargtypes(rtyper.annotator, values)
            self._cache_order.append(key)
        else:
            hs, ha, rtyper, htshift, RESTYPE = result
            assert argtypes == getargtypes(rtyper.annotator, values)
        return result

    def timeshift(self, ll_function, values, opt_consts=[], inline=None,
                  policy=None):
        hs, ha, rtyper, htshift, RESTYPE = self.timeshift_cached(
            ll_function, values, inline, policy)
        # build a runner function
        original_entrypoint_graph = rtyper.annotator.translator.graphs[0]
        graph1 = ha.translator.graphs[0]
        timeshifted_entrypoint_fnptr = rtyper.type_system.getcallable(graph1)
        assert len(graph1.getargs()) == 2 + len(values)
        graph1varargs = graph1.getargs()[2:]

        argdescription = []   # list of: ("green"/"redconst"/"redvar", value)
        residual_args = []
        residual_argtypes = []
        timeshifted_entrypoint_args_s = []

        for i, (v, llvalue) in enumerate(zip(graph1varargs, values)):
            r = htshift.hrtyper.bindingrepr(v)
            residual_v = r.residual_values(llvalue)
            if len(residual_v) == 0:
                # green
                color = "green"
                s_var = annmodel.ll_to_annotation(llvalue)
                timeshifted_entrypoint_args_s.append(s_var)
            else:
                # red
                assert residual_v == [llvalue], "XXX for now"
                if i in opt_consts:
                    color = "redconst"
                else:
                    color = "redvar"
                    ARGTYPE = htshift.originalconcretetype(v)
                    residual_argtypes.append(ARGTYPE)
                    residual_args.append(llvalue)
                timeshifted_entrypoint_args_s.append(htshift.s_RedBox)
            argdescription.append((color, llvalue))

        argdescription = unrolling_iterable(argdescription)
        RGenOp = self.RGenOp
        timeshifted_entrypoint = PseudoHighLevelCallable(
            timeshifted_entrypoint_fnptr,
            [htshift.s_ResidualGraphBuilder, htshift.s_JITState]
            + timeshifted_entrypoint_args_s,
            htshift.s_ResidualGraphBuilder)
        FUNCTYPE = lltype.FuncType(residual_argtypes, RESTYPE)
        gv_functype = RGenOp.constTYPE(FUNCTYPE)

        def ll_runner():
            rgenop = RGenOp.get_rgenop_for_testing()
            builder = rtimeshift.make_builder(rgenop)
            timeshifted_entrypoint_args = ()
            for color, llvalue in argdescription:
                if color == "green":
                    timeshifted_entrypoint_args += (llvalue,)
                else:
                    TYPE = lltype.typeOf(llvalue)
                    gv_type = rgenop.constTYPE(TYPE)
                    boxcls = rvalue.ll_redboxcls(TYPE)
                    if color == "redconst":
                        gv_arg = rgenop.genconst(llvalue)
                    else:
                        gv_arg = rtimeshift.ll_geninputarg(builder, gv_type)
                    box = boxcls(gv_type, gv_arg)
                    timeshifted_entrypoint_args += (box,)
            startblock = rtimeshift.ll_end_setup_builder(builder)
            endbuilder = timeshifted_entrypoint(builder, None,
                                                *timeshifted_entrypoint_args)
            endbuilder.finish_and_return()
            gv_generated = rgenop.gencallableconst("generated", startblock,
                                                   gv_functype)
            return gv_generated

        annhelper = htshift.annhelper
        runner_graph = annhelper.getgraph(ll_runner, [], htshift.s_ConstOrVar)
        annhelper.finish()

        # run the runner
        llinterp = LLInterpreter(rtyper)
        ll_gv_generated = llinterp.eval_graph(runner_graph, [])

        # now try to run the residual graph generated by the builder
        c_generatedfn = RGenOp.reveal(ll_gv_generated)
        residual_graph = c_generatedfn.value._obj.graph
        if conftest.option.view:
            residual_graph.show()
        insns = summary(residual_graph)
        res = llinterp.eval_graph(residual_graph, residual_args)
        return insns, res


class TestTimeshift(TimeshiftingTests):

    def test_simple_fixed(self):
        py.test.skip("green return not working")
        def ll_function(x, y):
            return hint(x + y, concrete=True)
        insns, res = self.timeshift(ll_function, [5, 7])
        assert res == 12
        assert insns == {}

    def test_very_simple(self):
        def ll_function(x, y):
            return x + y
        insns, res = self.timeshift(ll_function, [5, 7])
        assert res == 12
        assert insns == {'int_add': 1}

    def test_convert_const_to_redbox(self):
        def ll_function(x, y):
            x = hint(x, concrete=True)
            tot = 0
            while x:    # conversion from green '0' to red 'tot'
                tot += y
                x -= 1
            return tot
        insns, res = self.timeshift(ll_function, [7, 2])
        assert res == 14
        assert insns == {'int_add': 7}

    def test_simple_opt_const_propagation2(self):
        def ll_function(x, y):
            return x + y
        insns, res = self.timeshift(ll_function, [5, 7], [0, 1])
        assert res == 12
        assert insns == {}

    def test_simple_opt_const_propagation1(self):
        def ll_function(x):
            return -x
        insns, res = self.timeshift(ll_function, [5], [0])
        assert res == -5
        assert insns == {}

    def test_loop_folding(self):
        def ll_function(x, y):
            tot = 0
            x = hint(x, concrete=True)        
            while x:
                tot += y
                x -= 1
            return tot
        insns, res = self.timeshift(ll_function, [7, 2], [0, 1])
        assert res == 14
        assert insns == {}

    def test_loop_merging(self):
        def ll_function(x, y):
            tot = 0
            while x:
                tot += y
                x -= 1
            return tot
        insns, res = self.timeshift(ll_function, [7, 2], [])
        assert res == 14
        assert insns['int_add'] == 2
        assert insns['int_is_true'] == 2

        insns, res = self.timeshift(ll_function, [7, 2], [0])
        assert res == 14
        assert insns['int_add'] == 2
        assert insns['int_is_true'] == 1

        insns, res = self.timeshift(ll_function, [7, 2], [1])
        assert res == 14
        assert insns['int_add'] == 1
        assert insns['int_is_true'] == 2

        insns, res = self.timeshift(ll_function, [7, 2], [0, 1])
        assert res == 14
        assert insns['int_add'] == 1
        assert insns['int_is_true'] == 1

    def test_two_loops_merging(self):
        def ll_function(x, y):
            tot = 0
            while x:
                tot += y
                x -= 1
            while y:
                tot += y
                y -= 1
            return tot
        insns, res = self.timeshift(ll_function, [7, 3], [])
        assert res == 27
        assert insns['int_add'] == 3
        assert insns['int_is_true'] == 3

    def test_convert_greenvar_to_redvar(self):
        def ll_function(x, y):
            hint(x, concrete=True)
            return x - y
        insns, res = self.timeshift(ll_function, [70, 4], [0])
        assert res == 66
        assert insns['int_sub'] == 1
        insns, res = self.timeshift(ll_function, [70, 4], [0, 1])
        assert res == 66
        assert insns == {}

    def test_green_across_split(self):
        def ll_function(x, y):
            hint(x, concrete=True)
            if y > 2:
                z = x - y
            else:
                z = x + y
            return z
        insns, res = self.timeshift(ll_function, [70, 4], [0])
        assert res == 66
        assert insns['int_add'] == 1
        assert insns['int_sub'] == 1

    def test_merge_const_before_return(self):
        def ll_function(x):
            if x > 0:
                y = 17
            else:
                y = 22
            x -= 1
            y += 1
            return y+x
        insns, res = self.timeshift(ll_function, [-70], [])
        assert res == 23-71
        assert insns == {'int_gt': 1, 'int_add': 2, 'int_sub': 2}

    def test_merge_3_redconsts_before_return(self):
        def ll_function(x):
            if x > 2:
                y = hint(54, variable=True)
            elif x > 0:
                y = hint(17, variable=True)
            else:
                y = hint(22, variable=True)
            x -= 1
            y += 1
            return y+x
        insns, res = self.timeshift(ll_function, [-70], [])
        assert res == ll_function(-70)
        insns, res = self.timeshift(ll_function, [1], [])
        assert res == ll_function(1)
        insns, res = self.timeshift(ll_function, [-70], [])
        assert res == ll_function(-70)

    def test_merge_const_at_return(self):
        py.test.skip("green return")
        def ll_function(x):
            if x > 0:
                return 17
            else:
                return 22
        insns, res = self.timeshift(ll_function, [-70], [])
        assert res == 22
        assert insns == {'int_gt': 1}

    def test_arith_plus_minus(self):
        def ll_plus_minus(encoded_insn, nb_insn, x, y):
            acc = x
            pc = 0
            while pc < nb_insn:
                op = (encoded_insn >> (pc*4)) & 0xF
                op = hint(op, concrete=True)
                if op == 0xA:
                    acc += y
                elif op == 0x5:
                    acc -= y
                pc += 1
            return acc
        assert ll_plus_minus(0xA5A, 3, 32, 10) == 42
        insns, res = self.timeshift(ll_plus_minus, [0xA5A, 3, 32, 10], [0, 1])
        assert res == 42
        assert insns == {'int_add': 2,
                         'int_sub': 1}

    def test_simple_struct(self):
        S = lltype.GcStruct('helloworld', ('hello', lltype.Signed),
                                          ('world', lltype.Signed),
                            hints={'immutable': True})
        def ll_function(s):
            return s.hello * s.world
        s1 = lltype.malloc(S)
        s1.hello = 6
        s1.world = 7
        insns, res = self.timeshift(ll_function, [s1], [])
        assert res == 42
        assert insns == {'getfield': 2,
                         'int_mul': 1}
        insns, res = self.timeshift(ll_function, [s1], [0])
        assert res == 42
        assert insns == {}

    def test_simple_array(self):
        A = lltype.GcArray(lltype.Signed, 
                            hints={'immutable': True})
        def ll_function(a):
            return a[0] * a[1]
        a1 = lltype.malloc(A, 2)
        a1[0] = 6
        a1[1] = 7
        insns, res = self.timeshift(ll_function, [a1], [])
        assert res == 42
        assert insns == {'getarrayitem': 2,
                         'int_mul': 1}
        insns, res = self.timeshift(ll_function, [a1], [0])
        assert res == 42
        assert insns == {}

    def test_simple_struct_malloc(self):
        py.test.skip("blue containers: to be reimplemented")
        S = lltype.GcStruct('helloworld', ('hello', lltype.Signed),
                                          ('world', lltype.Signed))               
        def ll_function(x):
            s = lltype.malloc(S)
            s.hello = x
            return s.hello + s.world

        insns, res = self.timeshift(ll_function, [3], [])
        assert res == 3
        assert insns == {'int_add': 1}

        insns, res = self.timeshift(ll_function, [3], [0])
        assert res == 3
        assert insns == {}

    def test_inlined_substructure(self):
        py.test.skip("blue containers: to be reimplemented")
        S = lltype.Struct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))
        def ll_function(k):
            t = lltype.malloc(T)
            t.s.n = k
            l = t.s.n
            return l
        insns, res = self.timeshift(ll_function, [7], [])
        assert res == 7
        assert insns == {}

        insns, res = self.timeshift(ll_function, [7], [0])
        assert res == 7
        assert insns == {}    

    def test_degenerated_before_return(self):
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))

        def ll_function(flag):
            t = lltype.malloc(T)
            t.s.n = 3
            s = lltype.malloc(S)
            s.n = 4
            if flag:
                s = t.s
            s.n += 1
            return s.n * t.s.n
        insns, res = self.timeshift(ll_function, [0], [])
        assert res == 5 * 3
        insns, res = self.timeshift(ll_function, [1], [])
        assert res == 4 * 4

    def test_degenerated_before_return_2(self):
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))

        def ll_function(flag):
            t = lltype.malloc(T)
            t.s.n = 3
            s = lltype.malloc(S)
            s.n = 4
            if flag:
                pass
            else:
                s = t.s
            s.n += 1
            return s.n * t.s.n
        insns, res = self.timeshift(ll_function, [1], [])
        assert res == 5 * 3
        insns, res = self.timeshift(ll_function, [0], [])
        assert res == 4 * 4

    def test_degenerated_at_return(self):
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))

        def ll_function(flag):
            t = lltype.malloc(T)
            t.n = 3.25
            t.s.n = 3
            s = lltype.malloc(S)
            s.n = 4
            if flag:
                s = t.s
            return s
        insns, res = self.timeshift(ll_function, [0], [])
        assert res.n == 4
        assert lltype.parentlink(res._obj) == (None, None)
        insns, res = self.timeshift(ll_function, [1], [])
        assert res.n == 3
        parent, parentindex = lltype.parentlink(res._obj)
        assert parentindex == 's'
        assert parent.n == 3.25

    def test_degenerated_via_substructure(self):
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))

        def ll_function(flag):
            t = lltype.malloc(T)
            t.s.n = 3
            s = lltype.malloc(S)
            s.n = 7
            if flag:
                pass
            else:
                s = t.s
            t.s.n += 1
            return s.n * t.s.n
        insns, res = self.timeshift(ll_function, [1], [])
        assert res == 7 * 4
        insns, res = self.timeshift(ll_function, [0], [])
        assert res == 4 * 4

    def test_plus_minus_all_inlined(self):
        def ll_plus_minus(s, x, y):
            acc = x
            n = len(s)
            pc = 0
            while pc < n:
                op = s[pc]
                op = hint(op, concrete=True)
                if op == '+':
                    acc += y
                elif op == '-':
                    acc -= y
                pc += 1
            return acc
        s = rstr.string_repr.convert_const("+-+")
        insns, res = self.timeshift(ll_plus_minus, [s, 0, 2], [0], inline=999)
        assert res == ll_plus_minus("+-+", 0, 2)
        assert insns == {'int_add': 2, 'int_sub': 1}

    def test_red_virtual_container(self):
        # this checks that red boxes are able to be virtualized dynamically by
        # the compiler (the P_NOVIRTUAL policy prevents the hint-annotator from
        # marking variables in blue)
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        def ll_function(n):
            s = lltype.malloc(S)
            s.n = n
            return s.n
        insns, res = self.timeshift(ll_function, [42], [], policy=P_NOVIRTUAL)
        assert res == 42
        assert insns == {}

    def test_red_propagate(self):
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        def ll_function(n, k):
            s = lltype.malloc(S)
            s.n = n
            if k < 0:
                return -123
            return s.n * k
        insns, res = self.timeshift(ll_function, [3, 8], [], policy=P_NOVIRTUAL)
        assert res == 24
        assert insns == {'int_lt': 1, 'int_mul': 1}

    def test_red_subcontainer(self):
        S = lltype.Struct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))
        def ll_function(k):
            t = lltype.malloc(T)
            s = t.s
            s.n = k
            if k < 0:
                return -123
            result = s.n * (k-1)
            keepalive_until_here(t)
            return result
        insns, res = self.timeshift(ll_function, [7], [], policy=P_NOVIRTUAL)
        assert res == 42
        assert insns == {'int_lt': 1, 'int_mul': 1, 'int_sub': 1}

    def test_merge_structures(self):
        S = lltype.GcStruct('S', ('n', lltype.Signed))
        T = lltype.GcStruct('T', ('s', lltype.Ptr(S)), ('n', lltype.Signed))

        def ll_function(flag):
            if flag:
                s = lltype.malloc(S)
                s.n = 1
                t = lltype.malloc(T)
                t.s = s
                t.n = 2
            else:
                s = lltype.malloc(S)
                s.n = 5
                t = lltype.malloc(T)
                t.s = s
                t.n = 6
            return t.n + t.s.n
        insns, res = self.timeshift(ll_function, [0], [], policy=P_NOVIRTUAL)
        assert res == 5 + 6
        assert insns == {'int_is_true': 1, 'int_add': 1}
        insns, res = self.timeshift(ll_function, [1], [], policy=P_NOVIRTUAL)
        assert res == 1 + 2
        assert insns == {'int_is_true': 1, 'int_add': 1}

    def test_call_simple(self):
        def ll_add_one(x):
            return x + 1
        def ll_function(y):
            return ll_add_one(y)
        insns, res = self.timeshift(ll_function, [5], [], policy=P_NOVIRTUAL)
        assert res == 6
        assert insns == {'int_add': 1}

    def test_call_2(self):
        def ll_add_one(x):
            return x + 1
        def ll_function(y):
            return ll_add_one(y) + y
        insns, res = self.timeshift(ll_function, [5], [], policy=P_NOVIRTUAL)
        assert res == 11
        assert insns == {'int_add': 2}

    def test_call_3(self):
        def ll_add_one(x):
            return x + 1
        def ll_two(x):
            return ll_add_one(ll_add_one(x)) - x
        def ll_function(y):
            return ll_two(y) * y
        insns, res = self.timeshift(ll_function, [5], [], policy=P_NOVIRTUAL)
        assert res == 10
        assert insns == {'int_add': 2, 'int_sub': 1, 'int_mul': 1}
