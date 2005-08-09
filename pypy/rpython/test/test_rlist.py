from pypy.translator.translator import Translator
from pypy.rpython.lltype import *
from pypy.rpython.rtyper import RPythonTyper
from pypy.rpython.rlist import *
from pypy.rpython.rslice import ll_newslice
from pypy.rpython.rint import signed_repr
from pypy.rpython.test.test_llinterp import interpret
from pypy.rpython.test.test_llinterp import find_exception


def sample_list():    # [42, 43, 44, 45]
    rlist = ListRepr(signed_repr)
    rlist.setup()
    l = ll_newlist(rlist.lowleveltype, 3)
    ll_setitem(l, 0, 42)
    ll_setitem(l, -2, 43)
    ll_setitem_nonneg(l, 2, 44)
    ll_append(l, 45)
    return l

def check_list(l1, expected):
    assert ll_len(l1) == len(expected)
    for i, x in zip(range(len(expected)), expected):
        assert ll_getitem_nonneg(l1, i) == x

def test_rlist_basic():
    l = sample_list()
    assert ll_getitem(l, -4) == 42
    assert ll_getitem_nonneg(l, 1) == 43
    assert ll_getitem(l, 2) == 44
    assert ll_getitem(l, 3) == 45
    assert ll_len(l) == 4
    check_list(l, [42, 43, 44, 45])

def test_rlist_set_del():
    l = sample_list()
    ll_setitem(l, -1, 99)
    check_list(l, [42, 43, 44, 99])
    ll_setitem_nonneg(l, 1, 77)
    check_list(l, [42, 77, 44, 99])
    ll_delitem_nonneg(l, 0)
    check_list(l, [77, 44, 99])
    ll_delitem(l, -2)
    check_list(l, [77, 99])
    ll_delitem(l, 1)
    check_list(l, [77])
    ll_delitem(l, 0)
    check_list(l, [])

def test_rlist_extend_concat():
    l = sample_list()
    ll_extend(l, l)
    check_list(l, [42, 43, 44, 45] * 2)
    l1 = ll_concat(l, l)
    assert l1 != l
    check_list(l1, [42, 43, 44, 45] * 4)

def test_rlist_slice():
    l = sample_list()
    check_list(ll_listslice_startonly(l, 0), [42, 43, 44, 45])
    check_list(ll_listslice_startonly(l, 1), [43, 44, 45])
    check_list(ll_listslice_startonly(l, 2), [44, 45])
    check_list(ll_listslice_startonly(l, 3), [45])
    check_list(ll_listslice_startonly(l, 4), [])
    for start in range(5):
        for stop in range(start, 8):
            s = ll_newslice(start, stop)
            check_list(ll_listslice(l, s), [42, 43, 44, 45][start:stop])

def test_rlist_delslice():
    l = sample_list()
    ll_listdelslice_startonly(l, 3)
    check_list(l, [42, 43, 44])
    ll_listdelslice_startonly(l, 0)
    check_list(l, [])
    for start in range(5):
        for stop in range(start, 8):
            l = sample_list()
            s = ll_newslice(start, stop)
            ll_listdelslice(l, s)
            expected = [42, 43, 44, 45]
            del expected[start:stop]
            check_list(l, expected)

def test_rlist_setslice():
    n = 100
    for start in range(5):
        for stop in range(start, 5):
            l1 = sample_list()
            l2 = sample_list()
            expected = [42, 43, 44, 45]
            for i in range(start, stop):
                expected[i] = n
                ll_setitem(l2, i, n)
                n += 1
            s = ll_newslice(start, stop)
            l2 = ll_listslice(l2, s)
            ll_listsetslice(l1, s, l2)
            check_list(l1, expected)

# ____________________________________________________________

def rtype(fn, argtypes=[]):
    t = Translator(fn)
    t.annotate(argtypes)
    typer = RPythonTyper(t.annotator)
    typer.specialize()
    #t.view()
    t.checkgraphs()
    return t


def test_simple():
    def dummyfn():
        l = [10, 20, 30]
        return l[2]
    rtype(dummyfn)

def test_append():
    def dummyfn():
        l = []
        l.append(5)
        l.append(6)
        return l[0]
    rtype(dummyfn)

def test_len():
    def dummyfn():
        l = [5, 10]
        return len(l)
    rtype(dummyfn)

def test_iterate():
    def dummyfn():
        total = 0
        for x in [1, 3, 5, 7, 9]:
            total += x
        return total
    rtype(dummyfn)

def test_recursive():
    def dummyfn(N):
        l = []
        while N > 0:
            l = [l]
            N -= 1
        return len(l)
    rtype(dummyfn, [int]) #.view()

def test_add():
    def dummyfn():
        l = [5]
        l += [6,7]
        return l + [8]
    rtype(dummyfn)

def test_slice():
    def dummyfn():
        l = [5, 6, 7, 8, 9]
        return l[:2], l[1:4], l[3:]
    rtype(dummyfn)

def test_set_del_item():
    def dummyfn():
        l = [5, 6, 7]
        l[1] = 55
        l[-1] = 66
        del l[0]
        del l[-1]
        del l[:]
    rtype(dummyfn)

def test_setslice():
    def dummyfn():
        l = [10, 9, 8, 7]
        l[:2] = [6, 5]
        return l[0], l[1], l[2], l[3]
    res = interpret(dummyfn, ())
    assert res.item0 == 6
    assert res.item1 == 5
    assert res.item2 == 8
    assert res.item3 == 7

def test_insert_pop():
    def dummyfn():
        l = [6, 7, 8]
        l.insert(0, 5)
        l.insert(1, 42)
        l.pop(2)
        l.pop(0)
        l.pop(-1)
        l.pop()
        return l[-1]
    res = interpret(dummyfn, ())#, view=True)
    assert res == 42

def test_reverse():
    def dummyfn():
        l = [5, 3, 2]
        l.reverse()
        return l[0]*100 + l[1]*10 + l[2]
    res = interpret(dummyfn, ())
    assert res == 235

def test_prebuilt_list():
    klist = ['a', 'd', 'z', 'k']
    def dummyfn(n):
        return klist[n]
    res = interpret(dummyfn, [0])
    assert res == 'a'
    res = interpret(dummyfn, [3])
    assert res == 'k'
    res = interpret(dummyfn, [-2])
    assert res == 'z'

def test_bound_list_method():
    klist = [1, 2, 3]
    # for testing constant methods without actually mutating the constant
    def dummyfn(n):
        klist.extend([])
    interpret(dummyfn, [7])

def test_list_is():
    def dummyfn():
        l1 = []
        return l1 is l1
    res = interpret(dummyfn, [])
    assert res is True
    def dummyfn():
        l2 = [1, 2]
        return l2 is l2
    res = interpret(dummyfn, [])
    assert res is True
    def dummyfn():
        l1 = [2]
        l2 = [1, 2]
        return l1 is l2
    res = interpret(dummyfn, [])
    assert res is False
    def dummyfn():
        l1 = [1, 2]
        l2 = [1, 2]
        return l1 is l2
    res = interpret(dummyfn, [])
    assert res is False

    def dummyfn():
        l1 = None
        l2 = [1, 2]
        return l1 is l2
    res = interpret(dummyfn, [])
    assert res is False

def test_list_compare():
    def fn(i, j, neg=False):
        s1 = [[1, 2, 3], [4, 5, 1], None]
        s2 = [[1, 2, 3], [4, 5, 1], [1], [1, 2], [4, 5, 1, 6],
              [7, 1, 1, 8, 9, 10], None]
        if neg: return s1[i] != s2[i]
        return s1[i] == s2[j]
    for i in range(3):
        for j in range(7):
            for case in False, True:
                res = interpret(fn, [i,j,case])
                assert res is fn(i, j, case)

def test_list_comparestr():
    def fn(i, j, neg=False):
        s1 = [["hell"], ["hello", "world"]]
        s1[0][0] += "o" # ensure no interning
        s2 = [["hello"], ["world"]]
        if neg: return s1[i] != s2[i]
        return s1[i] == s2[j]
    for i in range(2):
        for j in range(2):
            for case in False, True:
                res = interpret(fn, [i,j,case])
                assert res is fn(i, j, case)

class Foo: pass

class Bar(Foo): pass

def test_list_compareinst():
    def fn(i, j, neg=False):
        foo1 = Foo()
        foo2 = Foo()
        bar1 = Bar()
        s1 = [[foo1], [foo2], [bar1]]
        s2 = s1[:]
        if neg: return s1[i] != s2[i]
        return s1[i] == s2[j]
    for i in range(3):
        for j in range(3):
            for case in False, True:
                res = interpret(fn, [i, j, case])
                assert res is fn(i, j, case)

def test_list_contains():
    def fn(i, neg=False):
        foo1 = Foo()
        foo2 = Foo()
        bar1 = Bar()
        bar2 = Bar()
        lis = [foo1, foo2, bar1]
        args = lis + [bar2]
        if neg : return args[i] not in lis
        return args[i] in lis
    for i in range(4):
        for case in False, True:
            res = interpret(fn, [i, case])
            assert res is fn(i, case)

def test_list_index():
    def fn(i):
        foo1 = Foo()
        foo2 = Foo()
        bar1 = Bar()
        bar2 = Bar()
        lis = [foo1, foo2, bar1]
        args = lis + [bar2]
        return lis.index(args[i])
    for i in range(4):
        try:
            res = interpret(fn, [i])
        except Exception, e:
            res = find_exception(e)
        try:
            res2 = fn(i)
        except Exception, e:
            res2 = e.__class__
        assert res == res2

def test_list_str():
    def fn():
        return str([1,2,3])
    
    res = interpret(fn, [])
    assert ''.join(res.chars) == fn()

    def fn():
        return str([[1,2,3]])
    
    res = interpret(fn, [])
    assert ''.join(res.chars) == fn()

def test_list_or_None():
    empty_list = []
    nonempty_list = [1, 2]
    def fn(i):
        test = [None, empty_list, nonempty_list][i]
        if test:
            return 1
        else:
            return 0

    res = interpret(fn, [0])
    assert res == 0
    res = interpret(fn, [1])
    assert res == 0
    res = interpret(fn, [2])
    assert res == 1

def test_list_slice_minusone():
    def fn(i):
        lst = [i, i+1, i+2]
        lst2 = lst[:-1]
        return lst[-1] * lst2[-1]
    res = interpret(fn, [5])
    assert res == 42

def test_list_multiply():
    def fn(i):
        lst = [i] * i
        return len(lst)
    for arg in (1, 9, 0, -1, -27):
        res = interpret(fn, [arg])
        assert res == fn(arg)
    def fn(i):
        lst = [i, i + 1] * i
        return len(lst)
    for arg in (1, 9, 0, -1, -27):
        res = interpret(fn, [arg])
        assert res == fn(arg)

def test_indexerror():
    def fn(i):
        l = [5, 8, 3]
        try:
            del l[i]
        except IndexError:
            pass
        try:
            return l[2]    # implicit int->PyObj conversion here
        except IndexError:
            return "oups"
    res = interpret(fn, [6])
    assert res._obj.value == 3
    res = interpret(fn, [-2])
    assert res._obj.value == "oups"
