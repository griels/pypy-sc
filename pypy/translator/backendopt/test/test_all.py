import py
from pypy.translator.backendopt.all import backend_optimizations
from pypy.translator.backendopt.test.test_malloc import check_malloc_removed
from pypy.translator.translator import Translator
from pypy.objspace.flow.model import Constant
from pypy.rpython.llinterp import LLInterpreter


class A:
    def __init__(self, x, y):
        self.bounds = (x, y)
    def mean(self, percentage=50):
        x, y = self.bounds
        total = x*percentage + y*(100-percentage)
        return total//100

def condition(n):
    return n >= 100

def firstthat(function, condition):
    for n in range(101):
        if condition(function(n)):
            return n
    else:
        return -1

def myfunction(n):
    a = A(117, n)
    return a.mean()

def big():
    """This example should be turned into a simple 'while' loop with no
    malloc nor direct_call by back-end optimizations, given a high enough
    inlining threshold.
    """
    return firstthat(myfunction, condition)


def test_big():
    assert big() == 83

    t = Translator(big)
    t.annotate([])
    t.specialize()
    backend_optimizations(t, inline_threshold=100, mallocs=True)

    graph = t.getflowgraph()
    check_malloc_removed(graph)

    interp = LLInterpreter(t.flowgraphs, t.rtyper)
    res = interp.eval_function(big, [])
    assert res == 83



def test_for_loop():
    def f(n):
        total = 0
        for i in range(n):
            total += i
        return total
    t = Translator(f)
    t.annotate([int])
    t.specialize()
    t.backend_optimizations(inline_threshold=1, mallocs=True)
    # this also checks that the BASE_INLINE_THRESHOLD is enough for 'for' loops

    graph = t.getflowgraph()
    check_malloc_removed(graph)

    interp = LLInterpreter(t.flowgraphs, t.rtyper)
    res = interp.eval_function(f, [11])
    assert res == 55


def test_list_comp():
    def f(n1, n2):
        c = [i for i in range(n2)]
        return 33
    t = Translator(f)
    t.annotate([int, int])
    t.specialize()
    t.backend_optimizations(inline_threshold=10, mallocs=True)

    graph = t.getflowgraph()
    check_malloc_removed(graph)

    interp = LLInterpreter(t.flowgraphs, t.rtyper)
    res = interp.eval_function(f, [11, 22])
    assert res == 33
