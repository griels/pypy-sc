from pypy.objspace.flow.model import summary
from pypy.translator.backendopt.removeassert import remove_asserts
from pypy.translator.backendopt.constfold import constant_fold_graph
from pypy.translator.backendopt.test import test_constfold
from pypy.translator.backendopt.test.test_constfold import check_graph


def get_graph(fn, signature):
    graph, t = test_constfold.get_graph(fn, signature)
    constant_fold_graph(graph)
    return graph, t

def contains_raise(graph):
    for link in graph.iterlinks():
        if link.target is graph.exceptblock:
            return True
    else:
        return False

def check(fn, args, expected_result):
    signature = [int] * len(args)   # for now
    graph, t = get_graph(fn, signature)
    remove_asserts(t, [graph])
    assert not contains_raise(graph)
    check_graph(graph, args, expected_result, t)


def test_simple():
    def fn(n):
        assert n >= 1
        return n-1
    check(fn, [125], 124)

def test_and():
    def fn(n):
        assert n >= 1 and n < 10
        return n-1
    check(fn, [1], 0)

def test_or():
    def fn(n):
        assert n >= 1 or n % 2 == 0
        return n-1
    check(fn, [-120], -121)

def test_isinstance():
    class A:
        pass
    class B(A):
        pass
    def g(n):
        if n > 10:
            return A()
        else:
            b = B()
            b.value = 321
            return b
    def fn(n):
        x = g(n)
        assert isinstance(x, B)
        return x.value
    check(fn, [5], 321)
