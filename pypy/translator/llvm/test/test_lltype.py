
import py

from pypy.rpython import lltype

from pypy.translator.llvm.genllvm import compile_function
from pypy.translator.llvm import database, codewriter
from pypy.rpython import rarithmetic 

py.log.setconsumer("genllvm", py.log.STDOUT)
py.log.setconsumer("genllvm database prepare", None)

S = lltype.Struct("base", ('a', lltype.Signed), ('b', lltype.Signed))

def test_struct_constant1():
    P = lltype.GcStruct("s",
                        ('signed', lltype.Signed),
                        ('unsigned', lltype.Unsigned),
                        ('float', lltype.Float),
                        ('char', lltype.Char),
                        ('bool', lltype.Bool),
                        ('unichar', lltype.UniChar)
                        )

    s = lltype.malloc(P)
    s.signed = 2
    s.unsigned = rarithmetic.r_uint(1)
    def struct_constant():
        x1 = s.signed + s.unsigned
        return x1
    f = compile_function(struct_constant, [])
    assert f() == struct_constant()

def test_struct_constant2():
    S2 = lltype.GcStruct("struct2", ('a', lltype.Signed), ('s1', S), ('s2', S))

    s = lltype.malloc(S2)
    s.a = 5
    s.s1.a = 2
    s.s1.b = 4
    s.s2.b = 3
    def struct_constant():
        return s.a + s.s2.b + s.s1.a + s.s1.b
    f = compile_function(struct_constant, [])
    assert f() == struct_constant()

def test_struct_constant3():
    structs = []
    cur = S
    for n in range(20):
        cur = lltype.Struct("struct%s" % n,  ("s", cur))
        structs.append(cur)
    TOP = lltype.GcStruct("top", ("s", cur))
        
    top = lltype.malloc(TOP)
    cur = top.s
    for ii in range(20):
        cur = cur.s
    cur.a = 10
    cur.b = 5
    def struct_constant():
        return (top.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.a -
                top.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.s.b)
    
    f = compile_function(struct_constant, [])
    assert f() == struct_constant()

def test_struct_constant4():
    SPTR = lltype.GcStruct('sptr', ('a', lltype.Signed))
    STEST = lltype.GcStruct('test', ('sptr', lltype.Ptr(SPTR)))
    s = lltype.malloc(STEST)
    s.sptr = lltype.malloc(SPTR)
    s.sptr.a = 21
    def struct_constant():
        return s.sptr.a * 2
    f = compile_function(struct_constant, [])
    assert f() == struct_constant()

def test_struct_constant5():
    SPTR = lltype.GcStruct('sptr', ('a', lltype.Signed), ('b', S))
    STEST = lltype.GcStruct('test', ('sptr', lltype.Ptr(SPTR)))
    s = lltype.malloc(STEST)
    s.sptr = lltype.malloc(SPTR)
    s.sptr.a = 21
    s.sptr.b.a = 11
    s.sptr.b.b = 10
    def struct_constant():
        return s.sptr.a + s.sptr.b.a + s.sptr.b.b
    f = compile_function(struct_constant, [])
    assert f() == struct_constant()

def test_struct_constant6():
    U = lltype.Struct('inlined', ('z', lltype.Signed))
    T = lltype.GcStruct('subtest', ('y', lltype.Signed))
    S = lltype.GcStruct('test', ('x', lltype.Ptr(T)), ('u', U), ('p', lltype.Ptr(U)))

    s = lltype.malloc(S)
    s.x = lltype.malloc(T)
    s.x.y = 42
    s.u.z = -100
    s.p = s.u
    def struct_constant():
        return s.x.y + s.p.z
    f = compile_function(struct_constant, [])
    assert f() == struct_constant()

def test_aliasing():
    B = lltype.Struct('B', ('x', lltype.Signed))
    A = lltype.Array(B)
    global_a = lltype.malloc(A, 5, immortal=True)
    global_b = global_a[3]
    def aliasing(i):
        global_b.x = 17
        return global_a[i].x
    f = compile_function(aliasing, [int])
    assert f(2) == 0
    assert f(3) == 17

def test_aliasing2():
    B = lltype.Struct('B', ('x', lltype.Signed))
    A = lltype.Array(B)
    C = lltype.Struct('C', ('x', lltype.Signed), ('bptr', lltype.Ptr(B)))
    global_a = lltype.malloc(A, 5, immortal=True)
    global_c = lltype.malloc(C, immortal=True)
    global_c.bptr = global_a[3]
    def aliasing(i):
        global_c.bptr.x = 17
        return global_a[i].x
    f = compile_function(aliasing, [int])
    assert f(2) == 0
    assert f(3) == 17    

def test_array_constant():
    A = lltype.GcArray(lltype.Signed)
    a = lltype.malloc(A, 3)
    a[0] = 100
    a[1] = 101
    a[2] = 102
    def array_constant():
        return a[0] + a[1] + a[2]    
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_array_constant2():
    A = lltype.GcArray(lltype.Signed)
    a = lltype.malloc(A, 3)
    a[0] = 100
    a[1] = 101
    a[2] = 102
    def array_constant():
        a[0] = 0
        return a[0] + a[1] + a[2]    
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_array_constant3():
    A = lltype.GcArray(('x', lltype.Signed))
    a = lltype.malloc(A, 3)
    a[0].x = 100
    a[1].x = 101
    a[2].x = 102
    def array_constant():
        return a[0].x + a[1].x + a[2].x    
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_struct_array1():
    A = lltype.GcArray(lltype.Signed)
    STEST = lltype.GcStruct('test', ('aptr', lltype.Ptr(A)))
    s = lltype.malloc(STEST)
    s.aptr = a = lltype.malloc(A, 2)
    a[0] = 100
    a[1] = 101
    def array_constant():
        return s.aptr[1] - a[0]
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_struct_array2():
    A = lltype.Array(lltype.Signed)
    STEST = lltype.GcStruct('test', ('a', lltype.Signed), ('b', A))
    s = lltype.malloc(STEST, 2)
    s.a = 41
    s.b[0] = 100
    s.b[1] = 101
    def array_constant():
        return s.b[1] - s.b[0] + s.a
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_struct_array3():
    A = lltype.Array(lltype.Signed)
    STEST = lltype.GcStruct('test', ('a', lltype.Signed), ('b', A))
    SBASE = lltype.GcStruct('base', ('p', lltype.Ptr(STEST)))
    s = lltype.malloc(STEST, 2)
    s.a = 41
    s.b[0] = 100
    s.b[1] = 101
    b = lltype.malloc(SBASE)
    b.p = s
    def array_constant():
        s = b.p
        return s.b[1] - s.b[0] + s.a
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_struct_opaque():
    PRTTI = lltype.Ptr(lltype.RuntimeTypeInfo)
    S = lltype.GcStruct('s', ('a', lltype.Signed), ('r', PRTTI))
    s = lltype.malloc(S)
    s.a = 42
    def array_constant():
        return s.a
    f = compile_function(array_constant, [])
    assert f() == array_constant()

def test_floats():
    " test pbc of floats "
    F = lltype.GcStruct("f",
                        ('f1', lltype.Float),
                        ('f2', lltype.Float),
                        ('f3', lltype.Float),
                        ('f4', lltype.Float),
                        ('f5', lltype.Float),
                        )
    floats = lltype.malloc(F)
    floats.f1 = 1.25
    floats.f2 = 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000.252984
    floats.f3 = float(29050000000000000000000000000000000000000000000000000000000000000000)
    floats.f4 = 1e300 * 1e300
    nan = floats.f5 = floats.f4/floats.f4
    def floats_fn():
        res  = floats.f1 == 1.25
        res += floats.f2 > 1e100
        res += floats.f3 > 1e50        
        res += floats.f4 > 1e200
        res += floats.f5 == nan
        return res
    
    f = compile_function(floats_fn, [])
    assert f() == floats_fn()
