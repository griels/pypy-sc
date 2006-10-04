from pypy.rpython.memory.gctransform2.transform import GCTransformer
from pypy.objspace.flow.model import c_last_exception, Variable
from pypy.rpython.memory.gctransform import var_needsgc, var_ispyobj
from pypy.translator.translator import TranslationContext, graphof
from pypy.translator.c.exceptiontransform import ExceptionTransformer
from pypy.rpython.lltypesystem import lltype
from pypy.objspace.flow.model import Variable
from pypy.annotation import model as annmodel
from pypy.rpython.extregistry import ExtRegistryEntry
from pypy import conftest

class _TestGCTransformer(GCTransformer):

    def push_alive_nopyobj(self, var, llops):
        llops.genop("gc_push_alive", [var])

    def pop_alive_nopyobj(self, var, llops):
        llops.genop("gc_pop_alive", [var])


def checkblock(block, is_borrowed):
    if block.operations == ():
        # a return/exception block -- don't want to think about them
        # (even though the test passes for somewhat accidental reasons)
        return
    if block.isstartblock:
        refs_in = 0
    else:
        refs_in = len([v for v in block.inputargs if isinstance(v, Variable)
                                                  and var_needsgc(v)
                                                  and not is_borrowed(v)])
    push_alives = len([op for op in block.operations
                       if op.opname == 'gc_push_alive'])
    pyobj_push_alives = len([op for op in block.operations
                             if op.opname == 'gc_push_alive_pyobj'])

    # implicit_pyobj_pushalives included calls to things that return pyobject*
    implicit_pyobj_pushalives = len([op for op in block.operations
                                     if var_ispyobj(op.result)
                                     and op.opname not in ('bare_getfield', 'bare_getarrayitem', 'same_as')])
    nonpyobj_gc_returning_calls = len([op for op in block.operations
                                       if op.opname in ('direct_call', 'indirect_call')
                                       and var_needsgc(op.result)
                                       and not var_ispyobj(op.result)])

    pop_alives = len([op for op in block.operations
                      if op.opname == 'gc_pop_alive'])
    pyobj_pop_alives = len([op for op in block.operations
                            if op.opname == 'gc_pop_alive_pyobj'])
    if pop_alives == len(block.operations):
        # it's a block we inserted
        return
    for link in block.exits:
        assert block.exitswitch is not c_last_exception
        refs_out = 0
        for v2 in link.target.inputargs:
            if var_needsgc(v2) and not is_borrowed(v2):
                refs_out += 1
        pyobj_pushes = pyobj_push_alives + implicit_pyobj_pushalives
        nonpyobj_pushes = push_alives + nonpyobj_gc_returning_calls
        assert refs_in + pyobj_pushes + nonpyobj_pushes == pop_alives + pyobj_pop_alives + refs_out

def rtype(func, inputtypes, specialize=True):
    t = TranslationContext()
    t.buildannotator().build_types(func, inputtypes)
    if specialize:
        t.buildrtyper().specialize()
    return t    

def rtype_and_transform(func, inputtypes, transformcls, specialize=True, check=True):
    t = rtype(func, inputtypes, specialize)
    transformer = transformcls(t)
    etrafo = ExceptionTransformer(t)
    etrafo.transform_completely()
    graphs_borrowed = {}
    for graph in t.graphs:
        graphs_borrowed[graph] = transformer.transform_graph(graph)
    if conftest.option.view:
        t.view()
    t.checkgraphs()
    if check:
        for graph, is_borrowed in graphs_borrowed.iteritems():
            for block in graph.iterblocks():
                checkblock(block, is_borrowed)
    return t, transformer

def getops(graph):
    ops = {}
    for block in graph.iterblocks():
        for op in block.operations:
            ops.setdefault(op.opname, []).append(op)
    return ops

def test_simple():
    def f():
        return 1
    rtype_and_transform(f, [], _TestGCTransformer)

def test_fairly_simple():
    class C:
        pass
    def f():
        c = C()
        c.x = 1
        return c.x
    t, transformer = rtype_and_transform(f, [], _TestGCTransformer)

def test_return_gcpointer():
    class C:
        pass
    def f():
        c = C()
        c.x = 1
        return c
    t, transformer = rtype_and_transform(f, [], _TestGCTransformer)
    
def test_call_function():
    class C:
        pass
    def f():
        c = C()
        c.x = 1
        return c
    def g():
        return f().x
    t, transformer = rtype_and_transform(g, [], _TestGCTransformer)
    ggraph = graphof(t, g)
    for i, op in enumerate(ggraph.startblock.operations):
        if op.opname == "direct_call":
            break
    else:
        assert False, "direct_call not found!"
    assert ggraph.startblock.operations[i + 1].opname != 'gc_push_alive'


def test_multiply_passed_var():
    S = lltype.GcStruct("S", ('x', lltype.Signed))
    def f(x):
        if x:
            a = lltype.malloc(S)
            a.x = 1
            b = a
        else:
            a = lltype.malloc(S)
            a.x = 1
            b = lltype.malloc(S)
            b.x = 2
        return a.x + b.x
    t, transformer = rtype_and_transform(f, [int], _TestGCTransformer)

def test_pyobj():
    def f(x):
        if x:
            a = 1
        else:
            a = "1"
        return int(a)
    t, transformer = rtype_and_transform(f, [int], _TestGCTransformer)
    fgraph = graphof(t, f)
    gcops = [op for op in fgraph.startblock.exits[0].target.operations
                 if op.opname.startswith("gc_")]
    for op in gcops:
        assert op.opname.endswith("_pyobj")

def test_call_return_pyobj():
    def g(factory):
        return factory()
    def f(factory):
        g(factory)
    t, transformer = rtype_and_transform(f, [object], _TestGCTransformer)
    fgraph = graphof(t, f)
    ops = getops(fgraph)
    calls = ops['direct_call']
    for call in calls:
        if call.result.concretetype is not lltype.Bool: #RPyExceptionOccurred()
            assert var_ispyobj(call.result)

def test_getfield_pyobj():
    class S:
        pass
    def f(thing):
        s = S()
        s.x = thing
        return s.x
    t, transformer = rtype_and_transform(f, [object], _TestGCTransformer)
    fgraph = graphof(t, f)
    pyobj_getfields = 0
    pyobj_setfields = 0
    for b in fgraph.iterblocks():
        for op in b.operations:
            if op.opname == 'bare_getfield' and var_ispyobj(op.result):
                pyobj_getfields += 1
            elif op.opname == 'bare_setfield' and var_ispyobj(op.args[2]):
                pyobj_setfields += 1
    # although there's only one explicit getfield in the code, a
    # setfield on a pyobj must get the old value out and decref it
    assert pyobj_getfields >= 2
    assert pyobj_setfields >= 1

def test_pass_gc_pointer():
    S = lltype.GcStruct("S", ('x', lltype.Signed))
    def f(s):
        s.x = 1
    def g():
        s = lltype.malloc(S)
        f(s)
        return s.x
    t, transformer = rtype_and_transform(g, [], _TestGCTransformer)

