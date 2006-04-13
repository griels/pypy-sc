from pypy.rpython.lltypesystem.lltype import *

def isweak(p, T):
    return p._weak and typeOf(p).TO == T

def test_basics():
    S0 = GcStruct("s0", ('a', Signed), ('b', Signed))
    assert S0.a == Signed
    assert S0.b == Signed
    s0 = malloc(S0)
    print s0
    assert typeOf(s0) == Ptr(S0)
    assert s0.a == 0
    assert s0.b == 0
    assert typeOf(s0.a) == Signed
    s0.a = 1
    s0.b = s0.a
    assert s0.a == 1
    assert s0.b == 1
    # simple array
    Ar = GcArray(('v', Signed))
    x = malloc(Ar,0)
    print x
    assert len(x) == 0
    x = malloc(Ar,3)
    print x
    assert typeOf(x) == Ptr(Ar)
    assert isweak(x[0], Ar.OF)
    assert typeOf(x[0].v) == Signed
    assert x[0].v == 0
    x[0].v = 1
    x[1].v = 2
    x[2].v = 3
    assert [x[z].v for z in range(3)] == [1, 2, 3]
    #
    def define_list(T):
        List_typ = GcStruct("list",
                ("items", Ptr(GcArray(('item',T)))))
        def newlist():
            l = malloc(List_typ)
            items = malloc(List_typ.items.TO, 0)
            l.items = items
            return l

        def append(l, newitem):
            length = len(l.items)
            newitems = malloc(List_typ.items.TO, length+1)
            i = 0
            while i<length:
              newitems[i].item = l.items[i].item
              i += 1
            newitems[length].item = newitem
            l.items = newitems

        def item(l, i):
            return l.items[i].item

        return List_typ, newlist, append, item

    List_typ, inewlist, iappend, iitem = define_list(Signed)

    l = inewlist()
    assert typeOf(l) == Ptr(List_typ)
    iappend(l, 2)
    iappend(l, 3)
    assert len(l.items) == 2
    assert iitem(l, 0) == 2
    assert iitem(l, 1) == 3

    IWrap = GcStruct("iwrap", ('v', Signed))
    List_typ, iwnewlist, iwappend, iwitem = define_list(Ptr(IWrap))

    l = iwnewlist()
    assert typeOf(l) == Ptr(List_typ)
    iw2 = malloc(IWrap)
    iw3 = malloc(IWrap)
    iw2.v = 2
    iw3.v = 3
    assert iw3.v == 3
    iwappend(l, iw2)
    iwappend(l, iw3)
    assert len(l.items) == 2
    assert iwitem(l, 0).v == 2
    assert iwitem(l, 1).v == 3

    # not allowed
    S = Struct("s", ('v', Signed))
    List_typ, iwnewlistzzz, iwappendzzz, iwitemzzz = define_list(S) # works but
    l = iwnewlistzzz()
    S1 = GcStruct("strange", ('s', S))
    py.test.raises(TypeError, "iwappendzzz(l, malloc(S1).s)")

def test_varsizestruct():
    S1 = GcStruct("s1", ('a', Signed), ('rest', Array(('v', Signed))))
    py.test.raises(TypeError, "malloc(S1)")
    s1 = malloc(S1, 4)
    assert s1.a == 0
    assert isweak(s1.rest, S1.rest)
    assert len(s1.rest) == 4
    assert isweak(s1.rest[0], S1.rest.OF)
    assert typeOf(s1.rest[0].v) == Signed
    assert s1.rest[0].v == 0
    py.test.raises(IndexError, "s1.rest[4]")
    py.test.raises(IndexError, "s1.rest[-1]")

    s1.a = 17
    s1.rest[3].v = 5
    assert s1.a == 17
    assert s1.rest[3].v == 5

    py.test.raises(TypeError, "Struct('invalid', ('rest', Array(('v', Signed))), ('a', Signed))")
    py.test.raises(TypeError, "Struct('invalid', ('rest', GcArray(('v', Signed))), ('a', Signed))")
    py.test.raises(TypeError, "Struct('invalid', ('x', Struct('s1', ('a', Signed), ('rest', Array(('v', Signed))))))")
    py.test.raises(TypeError, "Struct('invalid', ('x', S1))")

def test_substructure_ptr():
    S3 = Struct("s3", ('a', Signed))
    S2 = Struct("s2", ('s3', S3))
    S1 = GcStruct("s1", ('sub1', S2), ('sub2', S2))
    p1 = malloc(S1)
    assert isweak(p1.sub1, S2)
    assert isweak(p1.sub2, S2)
    assert isweak(p1.sub1.s3, S3)
    p2 = p1.sub1
    assert isweak(p2.s3, S3)

def test_gc_substructure_ptr():
    S1 = GcStruct("s2", ('a', Signed))
    S2 = Struct("s3", ('a', Signed))
    S0 = GcStruct("s1", ('sub1', S1), ('sub2', S2))
    p1 = malloc(S0)
    assert typeOf(p1.sub1) == Ptr(S1)
    assert isweak(p1.sub2, S2)

def test_cast_simple_widening():
    S2 = Struct("s2", ('a', Signed))
    S1 = Struct("s1", ('sub1', S2), ('sub2', S2))
    p1 = malloc(S1, immortal=True)
    p2 = p1.sub1
    p3 = p2
    assert typeOf(p3) == Ptr(S2)
    p4 = cast_pointer(Ptr(S1), p3)
    assert typeOf(p4) == Ptr(S1)
    assert p4 == p1
    py.test.raises(TypeError, "cast_pointer(Ptr(S1), p1.sub2)")
    SUnrelated = Struct("unrelated")
    py.test.raises(TypeError, "cast_pointer(Ptr(SUnrelated), p3)")
    S1bis = Struct("s1b", ('sub1', S2))
    p1b = malloc(S1bis, immortal=True)
    p2 = p1b.sub1
    py.test.raises(TypeError, "cast_pointer(Ptr(S1), p2)")

def test_cast_simple_widening2():
    S2 = GcStruct("s2", ('a', Signed))
    S1 = GcStruct("s1", ('sub1', S2))
    p1 = malloc(S1)
    p2 = p1.sub1
    assert typeOf(p2) == Ptr(S2)
    p3 = cast_pointer(Ptr(S1), p2)
    assert p3 == p1
    p2 = malloc(S2)
    py.test.raises(RuntimeError, "cast_pointer(Ptr(S1), p2)")

def test_cast_pointer():
    S3 = GcStruct("s3", ('a', Signed))
    S2 = GcStruct("s3", ('sub', S3))
    S1 = GcStruct("s1", ('sub', S2))
    p1 = malloc(S1)
    p2 = p1.sub
    p3 = p2.sub
    assert typeOf(p3) == Ptr(S3)
    assert typeOf(p2) == Ptr(S2)
    p12 = cast_pointer(Ptr(S1), p2)
    assert p12 == p1
    p13 = cast_pointer(Ptr(S1), p3)
    assert p13 == p1
    p21 = cast_pointer(Ptr(S2), p1)
    assert p21 == p2
    p23 = cast_pointer(Ptr(S2), p3)
    assert p23 == p2
    p31 = cast_pointer(Ptr(S3), p1)
    assert p31 == p3
    p32 = cast_pointer(Ptr(S3), p2)
    assert p32 == p3
    p3 = malloc(S3)
    p2 = malloc(S2)
    py.test.raises(RuntimeError, "cast_pointer(Ptr(S1), p3)")
    py.test.raises(RuntimeError, "cast_pointer(Ptr(S1), p2)")
    py.test.raises(RuntimeError, "cast_pointer(Ptr(S2), p3)")
    S0 = GcStruct("s0", ('sub', S1))
    p0 = malloc(S0)
    assert p0 == cast_pointer(Ptr(S0), p0)
    p3 = cast_pointer(Ptr(S3), p0)
    p03 = cast_pointer(Ptr(S0), p3)
    assert p0 == p03
    S1bis = GcStruct("s1b", ('sub', S2))
    assert S1bis != S1
    p1b = malloc(S1bis)
    p3 = p1b.sub.sub
    assert typeOf(p3) == Ptr(S3)
    assert p1b == cast_pointer(Ptr(S1bis), p3)
    py.test.raises(TypeError, "cast_pointer(Ptr(S1), p3)")

def test_best_effort_gced_parent_detection():
    S2 = Struct("s2", ('a', Signed))
    S1 = GcStruct("s1", ('sub1', S2), ('sub2', S2), ('tail', Array(('e', Signed))))
    p1 = malloc(S1, 1)
    p2 = p1.sub2
    assert p2.a == 0
    p3 = p1.tail
    p3[0].e = 1
    assert p3[0].e == 1
    del p1
    import gc
    gc.collect()
    py.test.raises(RuntimeError, "p2.a")
    py.test.raises(RuntimeError, "p3[0]")

def test_best_effort_gced_parent_for_arrays():
    A1 = GcArray(('v', Signed))
    p1 = malloc(A1, 10)
    p1[5].v=3
    assert p1[0].v == 0
    assert p1[9].v == 0
    assert p1[5].v == 3
    p1_5 = p1[5]
    del p1
    import gc
    gc.collect()
    py.test.raises(RuntimeError, "p1_5.v")        

def test_examples():
    A1 = GcArray(('v', Signed))
    S = GcStruct("s", ('v', Signed))
    St = GcStruct("st", ('v', Signed),('trail', Array(('v', Signed))))

    PA1 = Ptr(A1)
    PS = Ptr(S)
    PSt = Ptr(St)

    ex_pa1 = PA1._example()
    ex_ps  = PS._example()
    ex_pst = PSt._example()

    assert typeOf(ex_pa1) == PA1
    assert typeOf(ex_ps) == PS
    assert typeOf(ex_pst) == PSt

    assert ex_pa1[0].v == 0
    assert ex_ps.v == 0
    assert ex_pst.v == 0
    assert ex_pst.trail[0].v == 0

def test_functions():
    F = FuncType((Signed,), Signed)
    py.test.raises(TypeError, "Struct('x', ('x', F))")

    PF = Ptr(F)
    pf = PF._example()
    assert pf(0) == 0
    py.test.raises(TypeError, pf, 0, 0)
    py.test.raises(TypeError, pf, 'a')

def test_truargs():
    F = FuncType((Void, Signed, Void, Unsigned), Float)
    assert Void not in F._trueargs()

def test_inconsistent_gc_containers():
    A = GcArray(('y', Signed))
    S = GcStruct('b', ('y', Signed))
    py.test.raises(TypeError, "Struct('a', ('x', S))")
    py.test.raises(TypeError, "GcStruct('a', ('x', Signed), ('y', S))")
    py.test.raises(TypeError, "Array(('x', S))")
    py.test.raises(TypeError, "GcArray(('x', S))")
    py.test.raises(TypeError, "Struct('a', ('x', A))")
    py.test.raises(TypeError, "GcStruct('a', ('x', A))")

def test_forward_reference():
    F = GcForwardReference()
    S = GcStruct('abc', ('x', Ptr(F)))
    F.become(S)
    assert S.x == Ptr(S)
    py.test.raises(TypeError, "GcForwardReference().become(Struct('abc'))")
    ForwardReference().become(Struct('abc'))
    hash(S)

def test_nullptr():
    S = Struct('s')
    p0 = nullptr(S)
    assert not p0
    assert typeOf(p0) == Ptr(S)


def test_nullptr_cast():
    S = Struct('s')
    p0 = nullptr(S)
    assert not p0
    S1 = Struct("s1", ('s', S))
    p10 = cast_pointer(Ptr(S1), p0)
    assert typeOf(p10) == Ptr(S1)
    assert not p10
    

def test_hash():
    S = ForwardReference()
    S.become(Struct('S', ('p', Ptr(S))))
    assert S == S
    hash(S)   # assert no crash, and force the __cached_hash computation
    S1 = Struct('S', ('p', Ptr(S)))
    assert S1 == S
    assert S == S1
    assert hash(S1) == hash(S)

def test_array_with_non_container_elements():
    As = GcArray(Signed)
    a = malloc(As, 3)
    assert typeOf(a) == Ptr(As)
    assert a[0] == 0
    assert a[1] == 0
    assert a[2] == 0
    a[1] = 3
    assert a[1] == 3
    S = GcStruct('s', ('x', Signed))
    s = malloc(S)
    py.test.raises(TypeError, "a[1] = s")
    S = GcStruct('s', ('x', Signed))
    py.test.raises(TypeError, "Array(S)")
    py.test.raises(TypeError, "Array(As)")
    S = Struct('s', ('x', Signed))
    A = GcArray(S)
    a = malloc(A, 2)
    s = S._container_example() # should not happen anyway
    py.test.raises(TypeError, "a[0] = s")
    S = Struct('s', ('last', Array(S)))
    py.test.raises(TypeError, "Array(S)")

def test_immortal_parent():
    S1 = GcStruct('substruct', ('x', Signed))
    S  = GcStruct('parentstruct', ('s1', S1))
    p = malloc(S, immortal=True)
    p1 = p.s1
    p1.x = 5
    del p
    p = cast_pointer(Ptr(S), p1)
    assert p.s1.x == 5

def test_getRuntimeTypeInfo():
    S = GcStruct('s', ('x', Signed))
    py.test.raises(ValueError, "getRuntimeTypeInfo(S)")
    pinf0 = attachRuntimeTypeInfo(S)
    assert pinf0._obj.about == S
    pinf = getRuntimeTypeInfo(S)
    assert pinf == pinf0
    pinf1 = getRuntimeTypeInfo(S)
    assert pinf == pinf1
    Z = GcStruct('z', ('x', Unsigned))
    attachRuntimeTypeInfo(Z)
    assert getRuntimeTypeInfo(Z) != pinf0
    Sbis = GcStruct('s', ('x', Signed))
    attachRuntimeTypeInfo(Sbis)
    assert getRuntimeTypeInfo(Sbis) != pinf0
    assert Sbis != S # the attached runtime type info distinguishes them

def test_getRuntimeTypeInfo_destrpointer():
    S = GcStruct('s', ('x', Signed))
    def f(s):
        s.x = 1
    def type_info_S(p):
        return getRuntimeTypeInfo(S)
    qp = functionptr(FuncType([Ptr(S)], Ptr(RuntimeTypeInfo)), 
                     "type_info_S", 
                     _callable=type_info_S)
    dp = functionptr(FuncType([Ptr(S)], Void), 
                     "destructor_funcptr", 
                     _callable=f)
    pinf0 = attachRuntimeTypeInfo(S, qp, destrptr=dp)
    assert pinf0._obj.about == S
    pinf = getRuntimeTypeInfo(S)
    assert pinf == pinf0
    pinf1 = getRuntimeTypeInfo(S)
    assert pinf == pinf1
    assert pinf._obj.destructor_funcptr == dp
    assert pinf._obj.query_funcptr == qp

def test_runtime_type_info():
    S = GcStruct('s', ('x', Signed))
    attachRuntimeTypeInfo(S)
    s = malloc(S)
    assert runtime_type_info(s) == getRuntimeTypeInfo(S)
    S1 = GcStruct('s1', ('sub', S), ('x', Signed))
    attachRuntimeTypeInfo(S1)
    s1 = malloc(S1)
    assert runtime_type_info(s1) == getRuntimeTypeInfo(S1)
    assert runtime_type_info(s1.sub) == getRuntimeTypeInfo(S1)
    assert runtime_type_info(cast_pointer(Ptr(S), s1)) == getRuntimeTypeInfo(S1)
    def dynamic_type_info_S(p):
        if p.x == 0:
            return getRuntimeTypeInfo(S)
        else:
            return getRuntimeTypeInfo(S1)
    fp = functionptr(FuncType([Ptr(S)], Ptr(RuntimeTypeInfo)), 
                     "dynamic_type_info_S", 
                     _callable=dynamic_type_info_S)
    attachRuntimeTypeInfo(S, fp)
    assert s.x == 0
    assert runtime_type_info(s) == getRuntimeTypeInfo(S)
    s.x = 1
    py.test.raises(RuntimeError, "runtime_type_info(s)")
    assert s1.sub.x == 0
    py.test.raises(RuntimeError, "runtime_type_info(s1.sub)")
    s1.sub.x = 1
    assert runtime_type_info(s1.sub) == getRuntimeTypeInfo(S1)
    
def test_flavor_malloc():
    S = Struct('s', ('x', Signed))
    py.test.raises(TypeError, malloc, S)
    p = malloc(S, flavor="raw")
    assert typeOf(p).TO == S
    assert not isweak(p, S)
    
def test_opaque():
    O = OpaqueType('O')
    p1 = opaqueptr(O, 'p1', hello="world")
    assert typeOf(p1) == Ptr(O)
    assert p1._obj.hello == "world"
    assert parentlink(p1._obj) == (None, None)
    S = GcStruct('S', ('stuff', O))
    p2 = malloc(S)
    assert typeOf(p2) == Ptr(S)
    assert typeOf(p2.stuff) == Ptr(O)
    assert parentlink(p2.stuff._obj) == (p2._obj, 'stuff')

def test_is_atomic():
    U = Struct('inlined', ('z', Signed))
    A = Ptr(RuntimeTypeInfo)
    P = Ptr(GcStruct('p'))
    Q = GcStruct('q', ('i', Signed), ('u', U), ('p', P))
    O = OpaqueType('O')
    F = GcForwardReference()
    assert A._is_atomic() is True
    assert P._is_atomic() is False
    assert Q.i._is_atomic() is True
    assert Q.u._is_atomic() is True
    assert Q.p._is_atomic() is False
    assert Q._is_atomic() is False
    assert O._is_atomic() is False
    assert F._is_atomic() is False

def test_adtmeths():
    def h_newstruct():
        return malloc(S)
    
    S = GcStruct('s', ('x', Signed), 
                 adtmeths={"h_newstruct": h_newstruct})

    s = S.h_newstruct()

    assert typeOf(s) == Ptr(S)

    def h_alloc(n):
        return malloc(A, n)

    def h_length(a):
        return len(a)

    A = GcArray(Signed,
                adtmeths={"h_alloc": h_alloc,
                          "h_length": h_length})

    a = A.h_alloc(10)

    assert typeOf(a) == Ptr(A)
    assert len(a) == 10

    assert a.h_length() == 10

def test_adt_typemethod():
    def h_newstruct(S):
        return malloc(S)
    h_newstruct = typeMethod(h_newstruct)
    
    S = GcStruct('s', ('x', Signed), 
                 adtmeths={"h_newstruct": h_newstruct})

    s = S.h_newstruct()

    assert typeOf(s) == Ptr(S)

    Sprime = GcStruct('s', ('x', Signed), 
                      adtmeths={"h_newstruct": h_newstruct})

    assert S == Sprime

def test_cast_primitive():
    cases = [
        (Float, 1, 1.0),
        (Signed, 1.0, 1),
        (Unsigned, 1.0, 1),
        (Signed, r_uint(-1), -1),
        (Unsigned, -1, r_uint(-1)),
        (Char, ord('a'), 'a'),
        (Char, False,  chr(0)),
        (Signed, 'x', ord('x')),
        (Unsigned, u"x", ord(u'x')),
    ]
    for TGT, orig_val, expect in cases:
         res = cast_primitive(TGT, orig_val)
         assert typeOf(res) == TGT
         assert res == expect

def test_cast_identical_array_ptr_types():
    A = GcArray(Signed)
    PA = Ptr(A)
    a = malloc(A, 2)
    assert cast_pointer(PA, a) == a
        
def test_array_with_no_length():
    A = GcArray(Signed, hints={'nolength': True})
    a = malloc(A, 10)
    py.test.raises(TypeError, len, a)

def test_dissect_ll_instance():
    assert list(dissect_ll_instance(1)) == [(Signed, 1)]
    GcS = GcStruct("S", ('x', Signed))
    s = malloc(GcS)
    s.x = 1
    assert list(dissect_ll_instance(s)) == [(Ptr(GcS), s), (GcS, s._obj), (Signed, 1)]
    
    A = GcArray(('x', Signed))
    a = malloc(A, 10)
    for i in range(10):
        a[i].x = i
    expected = [(Ptr(A), a), (A, a._obj)]
    for t in [((A.OF, a._obj.items[i]), (Signed, i)) for i in range(10)]:
        expected.extend(t)
    assert list(dissect_ll_instance(a)) == expected

    R = GcStruct("R", ('r', Ptr(GcForwardReference())))
    R.r.TO.become(R)

    r = malloc(R)
    r.r = r
    r_expected = [(Ptr(R), r), (R, r._obj)]
    assert list(dissect_ll_instance(r)) == r_expected

    B = GcArray(Ptr(R))
    b = malloc(B, 2)
    b[0] = b[1] = r
    b_expected = [(Ptr(B), b), (B, b._obj)]
    assert list(dissect_ll_instance(b)) == b_expected + r_expected

    memo = {}
    assert list(dissect_ll_instance(r, None, memo)) == r_expected
    assert list(dissect_ll_instance(b, None, memo)) == b_expected

def test_fixedsizearray():
    A = FixedSizeArray(Signed, 5)
    assert A.OF == Signed
    assert A.length == 5
    assert A.item0 == A.item1 == A.item2 == A.item3 == A.item4 == Signed
    assert A._names == ('item0', 'item1', 'item2', 'item3', 'item4')
    a = malloc(A, immortal=True)
    a[0] = 5
    a[4] = 83
    assert a[0] == 5
    assert a[4] == 83
    assert a.item4 == 83
    py.test.raises(IndexError, "a[5] = 183")
    py.test.raises(IndexError, "a[-1]")
    assert len(a) == 5

    S = GcStruct('S', ('n1', Signed),
                      ('a', A),
                      ('n2', Signed))
    s = malloc(S)
    s.a[3] = 17
    assert s.a[3] == 17
    assert len(s.a) == 5
    py.test.raises(TypeError, "s.a = a")

def test_cast_subarray_pointer():
    for a in [malloc(GcArray(Signed), 5),
              malloc(FixedSizeArray(Signed, 5), immortal=True)]:
        a[0] = 0
        a[1] = 10
        a[2] = 20
        a[3] = 30
        a[4] = 40
        BOX = Ptr(FixedSizeArray(Signed, 2))
        b01 = cast_subarray_pointer(BOX, a, 0)
        b12 = cast_subarray_pointer(BOX, a, 1)
        b23 = cast_subarray_pointer(BOX, a, 2)
        b34 = cast_subarray_pointer(BOX, a, 3)
        assert b01[0] == 0
        assert b01[1] == 10
        assert b12[0] == 10
        assert b12[1] == 20
        assert b23[0] == 20
        assert b23[1] == 30
        assert b34[0] == 30
        assert b34[1] == 40
        b23[0] = 23
        assert a[2] == 23
        b12[1] += 1
        assert a[2] == 24
        # out-of-bound access is allowed, if it's within the parent's bounds
        assert len(b23) == 2
        assert b23[-1] == 10
        assert b12[3] == 40
        py.test.raises(IndexError, "b01[-1]")
        py.test.raises(IndexError, "b34[2]")
        py.test.raises(IndexError, "b12[4]")

def test_cast_structfield_pointer():
    S = GcStruct('S', ('x', Signed), ('y', Signed))
    A = FixedSizeArray(Signed, 1)
    s = malloc(S)
    a = cast_structfield_pointer(Ptr(A), s, 'y')
    a[0] = 34
    assert s.y == 34
    py.test.raises(IndexError, "a[1]")
