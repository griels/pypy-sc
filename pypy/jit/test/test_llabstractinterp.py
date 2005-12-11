from pypy.translator.translator import TranslationContext
from pypy.rpython.annlowlevel import annotate_lowlevel_helper
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.llinterp import LLInterpreter
from pypy.rpython import rstr
from pypy.annotation import model as annmodel
from pypy.jit.llabstractinterp import LLAbstractInterp


def annotation(a, x):
    T = lltype.typeOf(x)
    if T == lltype.Ptr(rstr.STR):
        t = str
    else:
        t = annmodel.lltype_to_annotation(T)
    return a.typeannotation(t)

_lastinterpreted = []
def get_and_residualize_graph(ll_function, argvalues, arghints):
    key = ll_function, tuple(arghints), tuple([argvalues[n] for n in arghints])
    for key1, value1 in _lastinterpreted:    # 'key' is not hashable
        if key1 == key:
            return value1
    if len(_lastinterpreted) >= 3:
        del _lastinterpreted[0]
    # build the normal ll graphs for ll_function
    t = TranslationContext()
    a = t.buildannotator()
    argtypes = [annotation(a, value) for value in argvalues]
    graph1 = annotate_lowlevel_helper(a, ll_function, argtypes)
    rtyper = t.buildrtyper()
    rtyper.specialize()
    # build the residual ll graphs by propagating the hints
    interp = LLAbstractInterp()
    hints = {}
    for hint in arghints:
        hints[graph1.getargs()[hint]] = argvalues[hint]
    graph2 = interp.eval(graph1, hints)
    # cache and return the original and the residual ll graph
    result = t, interp, graph1, graph2
    _lastinterpreted.append((key, result))
    return result

def abstrinterp(ll_function, argvalues, arghints):
    t, interp, graph1, graph2 = get_and_residualize_graph(
        ll_function, argvalues, arghints)
    argvalues2 = [argvalues[n] for n in range(len(argvalues))
                               if n not in arghints]
    rtyper = t.rtyper
    # check the result by running it
    llinterp = LLInterpreter(rtyper)
    result1 = llinterp.eval_graph(graph1, argvalues)
    result2 = llinterp.eval_graph(graph2, argvalues2)
    assert result1 == result2
    # return a summary of the instructions left in graph2
    insns = {}
    for copygraph in interp.itercopygraphs():
        for block in copygraph.iterblocks():
            for op in block.operations:
                insns[op.opname] = insns.get(op.opname, 0) + 1
    return graph2, insns


def test_simple():
    def ll_function(x, y):
        return x + y

    graph2, insns = abstrinterp(ll_function, [6, 42], [1])
    # check that the result is "lambda x: x+42"
    assert len(graph2.startblock.operations) == 1
    assert len(graph2.getargs()) == 1
    op = graph2.startblock.operations[0]
    assert op.opname == 'int_add'
    assert op.args[0] is graph2.getargs()[0]
    assert op.args[0].concretetype == lltype.Signed
    assert op.args[1].value == 42
    assert op.args[1].concretetype == lltype.Signed
    assert len(graph2.startblock.exits) == 1
    assert insns == {'int_add': 1}

def test_simple2():
    def ll_function(x, y):
        return x + y
    graph2, insns = abstrinterp(ll_function, [6, 42], [0, 1])
    assert not insns

def test_constantbranch():
    def ll_function(x, y):
        if x:
            y += 1
        y += 2
        return y
    graph2, insns = abstrinterp(ll_function, [6, 42], [0])
    assert insns == {'int_add': 2}

def test_constantbranch_two_constants():
    def ll_function(x, y):
        if x:
            y += 1
        y += 2
        return y
    graph2, insns = abstrinterp(ll_function, [6, 42], [0, 1])
    assert not insns

def test_branch():
    def ll_function(x, y):
        if x:
            y += 1
        y += 2
        return y
    graph2, insns = abstrinterp(ll_function, [6, 42], [])
    assert insns == {'int_is_true': 1, 'int_add': 2}
    graph2, insns = abstrinterp(ll_function, [0, 42], [])
    assert insns == {'int_is_true': 1, 'int_add': 2}

def test_unrolling_loop():
    def ll_function(x, y):
        while x > 0:
            y += x
            x -= 1
        return y
    graph2, insns = abstrinterp(ll_function, [6, 42], [0])
    assert insns == {'int_add': 6}

def test_loop():
    def ll_function(x, y):
        while x > 0:
            y += x
            x -= 1
        return y
    graph2, insns = abstrinterp(ll_function, [6, 42], [])
    assert insns == {'int_gt': 1, 'int_add': 1, 'int_sub': 1}

def test_loop2():
    def ll_function(x, y):
        while x > 0:
            y += x
            x -= 1
        return y
    graph2, insns = abstrinterp(ll_function, [6, 42], [1])
    assert insns == {'int_gt': 2, 'int_add': 2, 'int_sub': 2}

def test_not_merging():
    def ll_function(x, y, z):
        if x:
            a = y + z
        else:
            a = y - z
        a += x
        return a
    graph2, insns = abstrinterp(ll_function, [3, 4, 5], [1, 2])
    assert insns == {'int_is_true': 1, 'int_add': 2}

def test_simple_call():
    def ll2(x, y):
        return x + (y + 42)
    def ll1(x, y, z):
        return ll2(x, y - z)
    graph2, insns = abstrinterp(ll1, [3, 4, 5], [1, 2])
    assert insns == {'direct_call': 1, 'int_add': 1}

def test_simple_struct():
    S = lltype.GcStruct('helloworld', ('hello', lltype.Signed),
                                      ('world', lltype.Signed),
                        hints={'immutable': True})
    s = lltype.malloc(S)
    s.hello = 6
    s.world = 7
    def ll_function(s):
        return s.hello * s.world
    graph2, insns = abstrinterp(ll_function, [s], [0])
    assert insns == {}

def test_simple_array():
    A = lltype.Array(lltype.Char,
                     hints={'immutable': True})
    S = lltype.GcStruct('str', ('chars', A))
    s = lltype.malloc(S, 11)
    for i, c in enumerate("hello world"):
        s.chars[i] = c
    def ll_function(s, i, total):
        while i < len(s.chars):
            total += ord(s.chars[i])
            i += 1
        return total
    graph2, insns = abstrinterp(ll_function, [s, 0, 0], [0, 1, 2])
    assert insns == {}

def test_recursive_call():
    def ll_factorial(k):
        if k <= 1:
            return 1
        else:
            return ll_factorial(k-1) * k
    def ll_function(k):
        # indirection needed, because the hint is not about *all* calls to
        # ll_factorial()
        return ll_factorial(k)
    graph2, insns = abstrinterp(ll_function, [7], [0])
    # the direct_calls are messy to count, with calls to ll_stack_check
    assert insns.keys() == ['direct_call']

def test_simple_malloc_removal():
    S = lltype.GcStruct('S', ('n', lltype.Signed))
    def ll_function(k):
        s = lltype.malloc(S)
        s.n = k
        l = s.n
        return l+1
    graph2, insns = abstrinterp(ll_function, [7], [0])
    assert insns == {}

def test_inlined_substructure():
    S = lltype.Struct('S', ('n', lltype.Signed))
    T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))
    def ll_function(k):
        t = lltype.malloc(T)
        t.s.n = k
        l = t.s.n
        return l
    graph2, insns = abstrinterp(ll_function, [7], [0])
    assert insns == {}

def test_merge_with_inlined_substructure():
    S = lltype.Struct('S', ('n1', lltype.Signed), ('n2', lltype.Signed))
    T = lltype.GcStruct('T', ('s', S), ('n', lltype.Float))
    def ll_function(k, flag):
        if flag:
            t = lltype.malloc(T)
            t.s.n1 = k
            t.s.n2 = flag
        else:
            t = lltype.malloc(T)
            t.s.n1 = 14 - k
            t.s.n2 = flag + 42
        # 't.s.n1' should always be 7 here, so the two branches should merge
        n1 = t.s.n1
        n2 = t.s.n2
        return n1 * n2
    graph2, insns = abstrinterp(ll_function, [7, 1], [0])
    assert insns == {'int_is_true': 1, 'int_add': 1, 'int_mul': 1}

def test_dont_merge_forced_and_not_forced():
    S = lltype.GcStruct('S', ('n', lltype.Signed))
    def ll_do_nothing(s):
        s.n = 2
    def ll_function(flag):
        s = lltype.malloc(S)
        s.n = 12
        t = s.n
        if flag:
            ll_do_nothing(s)
        return t + s.n
    graph2, insns = abstrinterp(ll_function, [0], [])
    # XXX fragile test: at the moment, the two branches of the 'if' are not
    # being merged at all because 's' was forced in one case only.
    assert insns == {'direct_call': 1, 'int_is_true': 1, 'int_add': 2,
                     'malloc': 1, 'setfield': 2, 'getfield': 1}

def test_unique_virtualptrs():
    S = lltype.GcStruct('S', ('n', lltype.Signed))
    def ll_do_nothing(s):
        s.n = 2
    def ll_function(flag, flag2):
        s = lltype.malloc(S)
        s.n = 12
        if flag2:   # flag2 should always be 0
            t = lltype.nullptr(S)
        else:
            t = s
        if flag:
            ll_do_nothing(s)
        return s.n * t.n
    graph2, insns = abstrinterp(ll_function, [1, 0], [])
