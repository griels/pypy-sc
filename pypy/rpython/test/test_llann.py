from pypy.rpython.lltypesystem.lltype import *
from pypy.annotation import model as annmodel
from pypy.rpython.annlowlevel import annotate_lowlevel_helper
from pypy.objspace.flow import FlowObjSpace 

# helpers

def annotated_calls(ann, ops=('simple_call,')):
    for block in ann.annotated:
        for op in block.operations:
            if op.opname in ops:
                yield op

def derived(op, orig):
    if op.args[0].value.__name__.startswith(orig):
        return op.args[0].value
    else:
        return None

class TestLowLevelAnnotateTestCase:
    def setup_class(cls): 
        cls.space = FlowObjSpace() 

    from pypy.translator.annrpython import RPythonAnnotator

    def annotate(self, ll_function, argtypes):
        self.a = self.RPythonAnnotator()
        graph = annotate_lowlevel_helper(self.a, ll_function, argtypes)
        return self.a.binding(graph.getreturnvar())

    def test_simple(self):
        S = GcStruct("s", ('v', Signed))
        def llf():
            s = malloc(S)
            return s.v
        s = self.annotate(llf, [])
        assert s.knowntype == int

    def test_simple2(self):
        S = Struct("s", ('v', Signed))
        S2 = GcStruct("s2", ('a',S), ('b',S))
        def llf():
            s = malloc(S2)
            return s.a.v+s.b.v
        s = self.annotate(llf, [])
        assert s.knowntype == int

    def test_array(self):
        A = GcArray(('v', Signed))
        def llf():
            a = malloc(A, 1)
            return a[0].v
        s = self.annotate(llf, [])
        assert s.knowntype == int

    def test_prim_array(self):
        A = GcArray(Signed)
        def llf():
            a = malloc(A, 1)
            return a[0]
        s = self.annotate(llf, [])
        assert s.knowntype == int

    def test_prim_array_setitem(self):
        A = GcArray(Signed)
        def llf():
            a = malloc(A, 1)
            a[0] = 3
            return a[0]
        s = self.annotate(llf, [])
        assert s.knowntype == int        
        
    def test_cast_simple_widening(self):
        S2 = Struct("s2", ('a', Signed))
        S1 = Struct("s1", ('sub1', S2), ('sub2', S2))
        PS1 = Ptr(S1)
        PS2 = Ptr(S2)
        def llf(p1):
            p2 = p1.sub1
            p3 = cast_pointer(PS1, p2)
            return p3
        s = self.annotate(llf, [annmodel.SomePtr(PS1)])
        assert isinstance(s, annmodel.SomePtr)
        assert s.ll_ptrtype == PS1

    def test_cast_simple_widening_from_gc(self):
        S2 = GcStruct("s2", ('a', Signed))
        S1 = GcStruct("s1", ('sub1', S2), ('x', Signed))
        PS1 = Ptr(S1)
        def llf():
            p1 = malloc(S1)
            p2 = p1.sub1
            p3 = cast_pointer(PS1, p2)
            return p3
        s = self.annotate(llf, [])
        assert isinstance(s, annmodel.SomePtr)
        assert s.ll_ptrtype == PS1

    def test_cast_pointer(self):
        S3 = GcStruct("s3", ('a', Signed))
        S2 = GcStruct("s3", ('sub', S3))
        S1 = GcStruct("s1", ('sub', S2))
        PS1 = Ptr(S1)
        PS2 = Ptr(S2)
        PS3 = Ptr(S3)
        def llf():
            p1 = malloc(S1)
            p2 = p1.sub
            p3 = p2.sub
            p12 = cast_pointer(PS1, p2)
            p13 = cast_pointer(PS1, p3)
            p21 = cast_pointer(PS2, p1)
            p23 = cast_pointer(PS2, p3)
            p31 = cast_pointer(PS3, p1)
            p32 = cast_pointer(PS3, p2)
            return p12, p13, p21, p23, p31, p32
        s = self.annotate(llf, [])
        assert [x.ll_ptrtype for x in s.items] == [PS1, PS1, PS2, PS2, PS3, PS3]
            

    def test_array_length(self):
        A = GcArray(('v', Signed))
        def llf():
            a = malloc(A, 1)
            return len(a)
        s = self.annotate(llf, [])
        assert s.knowntype == int

    def test_funcptr(self):
        F = FuncType((Signed,), Signed)
        PF = Ptr(F)
        def llf(p):
            return p(0)
        s = self.annotate(llf, [annmodel.SomePtr(PF)])
        assert s.knowntype == int
 

    def test_ll_calling_ll(self):
        A = GcArray(Float)
        B = GcArray(Signed)
        def ll_make(T, n):
            x = malloc(T, n)
            return x
        def ll_get(T, x, i):
            return x[i]
        def llf():
            a = ll_make(A, 3)
            b = ll_make(B, 2)
            a[0] = 1.0
            b[1] = 3
            y0 = ll_get(A, a, 1)
            y1 = ll_get(B, b, 1)
            #
            a2 = ll_make(A, 4)
            a2[0] = 2.0
            return ll_get(A, a2, 1)
        s = self.annotate(llf, [])
        a = self.a
        assert s == annmodel.SomeFloat()

        seen = {}
        ngraphs = len(a.translator.graphs)

        vTs = []
        for call in annotated_calls(a):
            if derived(call, "ll_"):

                func, T = [x.value for x in call.args[0:2]]
                if (func, T) in seen:
                    continue
                seen[func, T] = True
                
                desc = a.bookkeeper.getdesc(func)
                g = desc.specialize([a.binding(x) for x in call.args[1:]])

                args = g.getargs()
                rv = g.getreturnvar()
                if func is ll_get:                    
                    vT, vp, vi = args
                    assert a.binding(vT) == a.bookkeeper.immutablevalue(T)
                    assert a.binding(vi).knowntype == int
                    assert a.binding(vp).ll_ptrtype.TO == T
                    assert a.binding(rv) == annmodel.lltype_to_annotation(T.OF)
                elif func is ll_make:
                    vT, vn = args
                    assert a.binding(vT) == a.bookkeeper.immutablevalue(T)
                    assert a.binding(vn).knowntype == int
                    assert a.binding(rv).ll_ptrtype.TO == T
                else:
                    assert False, func
                vTs.append(vT)

        assert len(seen) == 4

        return a, vTs # reused by a test in test_rtyper
 
    def test_ll_calling_ll2(self):
        A = GcArray(Float)
        B = GcArray(Signed)
        def ll_make(T, n):
            x = malloc(T, n)
            return x
        def ll_get(x, i):
            return x[i]
        def makelen4(T):
            return ll_make(T, 4)
        def llf():
            a = ll_make(A, 3)
            b = ll_make(B, 2)
            a[0] = 1.0
            b[1] = 3
            y0 = ll_get(a, 1)
            y1 = ll_get(b, 1)
            #
            a2 = makelen4(A)
            a2[0] = 2.0
            return ll_get(a2, 1)
        s = self.annotate(llf, [])
        a = self.a
        assert s == annmodel.SomeFloat()

        seen = {}

        def q(v):
            s = a.binding(v)
            if s.is_constant():
                return s.const
            else:
                return s.ll_ptrtype
        
        vTs = []

        for call in annotated_calls(a):
            if derived(call, "ll_")  or derived(call, "makelen4"):

                func, T = [q(x) for x in call.args[0:2]]
                if (func, T) in seen:
                    continue
                seen[func, T] = True

                desc = a.bookkeeper.getdesc(func)
                g = desc.specialize([a.binding(x) for x in call.args[1:]])

                args = g.getargs()
                rv = g.getreturnvar()

                if func is ll_make:
                    vT, vn = args
                    assert a.binding(vT) == a.bookkeeper.immutablevalue(T)
                    assert a.binding(vn).knowntype == int
                    assert a.binding(rv).ll_ptrtype.TO == T
                    vTs.append(vT)
                elif func is makelen4:
                    vT, = args
                    assert a.binding(vT) == a.bookkeeper.immutablevalue(T)
                    assert a.binding(rv).ll_ptrtype.TO == T
                    vTs.append(vT)
                elif func is ll_get:
                    vp, vi = args
                    assert a.binding(vi).knowntype == int
                    assert a.binding(vp).ll_ptrtype == T
                    assert a.binding(rv) == annmodel.lltype_to_annotation(
                        T.TO.OF)
                else:
                    assert False, func

        assert len(seen) == 5

        return a, vTs # reused by a test in test_rtyper

    def test_getRuntimeTypeInfo(self):
        S = GcStruct('s', ('x', Signed))
        attachRuntimeTypeInfo(S)
        def llf():
            return getRuntimeTypeInfo(S)
        s = self.annotate(llf, [])
        assert isinstance(s, annmodel.SomePtr)
        assert s.ll_ptrtype == Ptr(RuntimeTypeInfo)
        assert s.const == getRuntimeTypeInfo(S)

    def test_runtime_type_info(self):
        S = GcStruct('s', ('x', Signed))
        attachRuntimeTypeInfo(S)
        def llf(p):
            return runtime_type_info(p)
        s = self.annotate(llf, [annmodel.SomePtr(Ptr(S))])
        assert isinstance(s, annmodel.SomePtr)
        assert s.ll_ptrtype == Ptr(RuntimeTypeInfo)
        
