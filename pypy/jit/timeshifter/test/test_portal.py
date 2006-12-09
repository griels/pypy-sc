from pypy import conftest
from pypy.translator.translator import graphof
from pypy.jit.timeshifter.test.test_timeshift import hannotate, getargtypes
from pypy.jit.timeshifter.hrtyper import HintRTyper
from pypy.jit.timeshifter.test.test_timeshift import P_NOVIRTUAL
from pypy.jit.timeshifter.test.test_vlist import P_OOPSPEC
from pypy.rpython.llinterp import LLInterpreter
from pypy.objspace.flow.model import checkgraph, summary
from pypy.rlib.objectmodel import hint

import py.test

class PortalTest(object):
    from pypy.jit.codegen.llgraph.rgenop import RGenOp

    small = True

    def setup_class(cls):
        cls._cache = {}
        cls._cache_order = []

    def teardown_class(cls):
        del cls._cache
        del cls._cache_order

    def postprocess_timeshifting(self):
        self.readportalgraph = self.hrtyper.readportalgraph
        self.readallportalsgraph = self.hrtyper.readallportalsgraph
        
    def _timeshift_from_portal(self, main, portal, main_args,
                              inline=None, policy=None,
                              backendoptimize=False):
        # decode the 'values' if they are specified as strings
        if hasattr(main, 'convert_arguments'):
            assert len(main.convert_arguments) == len(main_args)
            main_args = [decoder(value) for decoder, value in zip(
                                        main.convert_arguments,
                                        main_args)]
        key = main, portal, inline, policy, backendoptimize
        try:
            cache, argtypes = self._cache[key]
        except KeyError:
            pass
        else:
            self.__dict__.update(cache)
            assert argtypes == getargtypes(self.rtyper.annotator, main_args)
            return main_args

        hs, ha, self.rtyper = hannotate(main, main_args, portal=portal,
                                   policy=policy, inline=inline,
                                   backendoptimize=backendoptimize)

        t = self.rtyper.annotator.translator
        self.maingraph = graphof(t, main)
        # make the timeshifted graphs
        self.hrtyper = HintRTyper(ha, self.rtyper, self.RGenOp)
        origportalgraph = graphof(t, portal)
        self.hrtyper.specialize(origportalgraph=origportalgraph,
                           view = conftest.option.view and self.small)

        for graph in ha.translator.graphs:
            checkgraph(graph)
            t.graphs.append(graph)

        if conftest.option.view and self.small:
            t.view()
        self.postprocess_timeshifting()
        self.readportalgraph = self.hrtyper.readportalgraph

        # Populate the cache
        if len(self._cache_order) >= 3:
            del self._cache[self._cache_order.pop(0)]
        cache = self.__dict__.copy()
        self._cache[key] = cache, getargtypes(self.rtyper.annotator, main_args)
        self._cache_order.append(key)
        return main_args

    
    def timeshift_from_portal(self, main, portal, main_args,
                              inline=None, policy=None,
                              backendoptimize=False):
        main_args = self._timeshift_from_portal(main, portal, main_args,
                                                inline=inline, policy=policy,
                                                backendoptimize=backendoptimize)
        self.main_args = main_args
        self.main_is_portal = main is portal
        llinterp = LLInterpreter(self.rtyper)
        res = llinterp.eval_graph(self.maingraph, main_args)
        return res

    def check_insns(self, expected=None, **counts):
        # XXX only works if the portal is the same as the main
        llinterp = LLInterpreter(self.rtyper)
        if self.main_is_portal:
            residual_graph = llinterp.eval_graph(self.readportalgraph,
                                                 self.main_args)._obj.graph
        else:
            residual_graphs = llinterp.eval_graph(self.readallportalsgraph, [])
            assert residual_graphs.ll_length() == 1
            residual_graph = residual_graphs.ll_getitem_fast(0)._obj.graph
            
        self.insns = summary(residual_graph)
        if expected is not None:
            assert self.insns == expected
        for opname, count in counts.items():
            assert self.insns.get(opname, 0) == count

class TestPortal(PortalTest):
            
    def test_simple(self):

        def main(code, x):
            return evaluate(code, x)

        def evaluate(y, x):
            hint(y, concrete=True)
            z = y+x
            return z

        res = self.timeshift_from_portal(main, evaluate, [3, 2])
        assert res == 5

        res = self.timeshift_from_portal(main, evaluate, [3, 5])
        assert res == 8

        res = self.timeshift_from_portal(main, evaluate, [4, 7])
        assert res == 11
    
    def test_main_as_portal(self):
        def main(x):
            return x

        res = self.timeshift_from_portal(main, main, [42])
        assert res == 42

    def test_multiple_portal_calls(self):
        def ll_function(n):
            hint(None, global_merge_point=True)
            k = n
            if k > 5:
                k //= 2
            k = hint(k, promote=True)
            k *= 17
            return hint(k, variable=True)

        res = self.timeshift_from_portal(ll_function, ll_function, [4],
                                         policy=P_NOVIRTUAL)
        assert res == 68
        self.check_insns(int_floordiv=1, int_mul=0)

        res = self.timeshift_from_portal(ll_function, ll_function, [4],
                                         policy=P_NOVIRTUAL)
        assert res == 68
        self.check_insns(int_floordiv=1, int_mul=0)

    def test_dfa_compile(self):
        from pypy.lang.automata.dfa import getautomaton, convertdfa, recognizetable
        a = getautomaton()
        dfatable, final_states = convertdfa(a)
        def main(gets):
            s = ["aaaaaaaaaab", "aaaa"][gets]
            return recognizetable(dfatable, s, final_states)

        res = self.timeshift_from_portal(main, recognizetable, [0], policy=P_NOVIRTUAL)
        assert res

        res = self.timeshift_from_portal(main, recognizetable, [1], policy=P_NOVIRTUAL)
        assert not res

    def test_dfa_compile2(self):
        from pypy.lang.automata.dfa import getautomaton, convertagain, recognizeparts
        more = [convertagain(getautomaton()), convertagain(getautomaton())]
        def main(gets, gets2):
            alltrans, final_states = more[gets2]
            s = ["aaaaaaaaaab", "aaaa"][gets]
            return recognizeparts(alltrans, final_states, s)

        res = self.timeshift_from_portal(main, recognizeparts, [0, 0], policy=P_NOVIRTUAL)
        assert res

        # XXX unfortunately we have to create a new version each time - because of pbc
        res = self.timeshift_from_portal(main, recognizeparts, [1, 0], policy=P_NOVIRTUAL)
        assert not res

    def test_dfa_compile3(self):
        from pypy.lang.automata.dfa import getautomaton, recognize3
        def main(gets):
            auto = getautomaton()
            s = ["aaaaaaaaaab", "aaaa"][gets]
            return recognize3(auto, s)

        res = self.timeshift_from_portal(main, recognize3, [0],
                                         policy=P_OOPSPEC)
        assert res

        res = self.timeshift_from_portal(main, recognize3, [1],
                                         policy=P_OOPSPEC)
        assert not res

    def test_method_call_nonpromote(self):
        class Base(object):
            pass
        class Int(Base):
            def __init__(self, n):
                self.n = n
            def double(self):
                return Int(self.n * 2)
            def get(self):
                return self.n
        class Str(Base):
            def __init__(self, s):
                self.s = s
            def double(self):
                return Str(self.s + self.s)
            def get(self):
                return ord(self.s[4])

        def ll_main(n):
            if n > 0:
                o = Int(n)
            else:
                o = Str('123')
            return ll_function(o)

        def ll_function(o):
            hint(None, global_merge_point=True)
            return o.double().get()

        res = self.timeshift_from_portal(ll_main, ll_function, [5], policy=P_NOVIRTUAL)
        assert res == 10
        self.check_insns(indirect_call=2)

        res = self.timeshift_from_portal(ll_main, ll_function, [0], policy=P_NOVIRTUAL)
        assert res == ord('2')
        self.check_insns(indirect_call=2)

    def test_method_call_promote(self):
        class Base(object):
            pass
        class Int(Base):
            def __init__(self, n):
                self.n = n
            def double(self):
                return Int(self.n * 2)
            def get(self):
                return self.n
        class Str(Base):
            def __init__(self, s):
                self.s = s
            def double(self):
                return Str(self.s + self.s)
            def get(self):
                return ord(self.s[4])

        def ll_main(n):
            if n > 0:
                o = Int(n)
            else:
                o = Str('123')
            return ll_function(o)

        def ll_function(o):
            hint(None, global_merge_point=True)
            hint(o.__class__, promote=True)
            return o.double().get()

        res = self.timeshift_from_portal(ll_main, ll_function, [5], policy=P_NOVIRTUAL)
        assert res == 10
        self.check_insns(indirect_call=0)

        res = self.timeshift_from_portal(ll_main, ll_function, [0], policy=P_NOVIRTUAL)
        assert res == ord('2')
        self.check_insns(indirect_call=0)

    def test_virt_obj_method_call_promote(self):
        class Base(object):
            pass
        class Int(Base):
            def __init__(self, n):
                self.n = n
            def double(self):
                return Int(self.n * 2)
            def get(self):
                return self.n
        class Str(Base):
            def __init__(self, s):
                self.s = s
            def double(self):
                return Str(self.s + self.s)
            def get(self):
                return ord(self.s[4])

        def ll_make(n):
            if n > 0:
                return Int(n)
            else:
                return Str('123')

        def ll_function(n):
            hint(None, global_merge_point=True)
            o = ll_make(n)
            hint(o.__class__, promote=True)
            return o.double().get()

        res = self.timeshift_from_portal(ll_function, ll_function, [5], policy=P_NOVIRTUAL)
        assert res == 10
        self.check_insns(indirect_call=0, malloc=0)

        res = self.timeshift_from_portal(ll_function, ll_function, [0], policy=P_NOVIRTUAL)
        assert res == ord('2')
        self.check_insns(indirect_call=0, malloc=0)

    def test_simple_recursive_portal_call(self):

        def main(code, x):
            return evaluate(code, x)

        def evaluate(y, x):
            hint(y, concrete=True)
            if y <= 0:
                return x
            z = 1 + evaluate(y - 1, x)
            return z

        res = self.timeshift_from_portal(main, evaluate, [3, 2])
        assert res == 5

        res = self.timeshift_from_portal(main, evaluate, [3, 5])
        assert res == 8

        res = self.timeshift_from_portal(main, evaluate, [4, 7])
        assert res == 11
    

    def test_simple_recursive_portal_call2(self):

        def main(code, x):
            return evaluate(code, x)

        def evaluate(y, x):
            hint(y, concrete=True)
            if x <= 0:
                return y
            z = evaluate(y, x - 1) + 1
            return z

        res = self.timeshift_from_portal(main, evaluate, [3, 2])
        assert res == 5

        res = self.timeshift_from_portal(main, evaluate, [3, 5])
        assert res == 8

        res = self.timeshift_from_portal(main, evaluate, [4, 7])
        assert res == 11
    
    def test_simple_recursive_portal_call_with_exc(self):

        def main(code, x):
            return evaluate(code, x)

        class Bottom(Exception):
            pass

        def evaluate(y, x):
            hint(y, concrete=True)
            if y <= 0:
                raise Bottom
            try:
                z = 1 + evaluate(y - 1, x)
            except Bottom:
                z = 1 + x
            return z

        res = self.timeshift_from_portal(main, evaluate, [3, 2])
        assert res == 5

        res = self.timeshift_from_portal(main, evaluate, [3, 5])
        assert res == 8

        res = self.timeshift_from_portal(main, evaluate, [4, 7])
        assert res == 11
    
