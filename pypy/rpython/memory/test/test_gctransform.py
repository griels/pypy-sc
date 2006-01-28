from pypy.rpython.memory import gctransform
from pypy.rpython.memory.gctransform import var_needsgc, var_ispyobj
from pypy.translator.translator import TranslationContext, graphof
from pypy.rpython.lltypesystem import lltype
from pypy.objspace.flow.model import Variable

def checkblock(block):
    if block.operations == ():
        # a return/exception block -- don't want to think about them
        # (even though the test passes for somewhat accidental reasons)
        return
    if block.isstartblock:
        refs_in = 0
    else:
        refs_in = len([v for v in block.inputargs if var_needsgc(v)])
    push_alives = len([op for op in block.operations
                       if op.opname.startswith('gc_push_alive')]) + \
                  len([op for op in block.operations
                       if var_ispyobj(op.result) and 'direct_call' not in op.opname])
    
    pop_alives = len([op for op in block.operations
                      if op.opname.startswith('gc_pop_alive')])
    calls = len([op for op in block.operations
                 if 'direct_call' in op.opname and var_needsgc(op.result)])
    if pop_alives == len(block.operations):
        # it's a block we inserted
        return
    for link in block.exits:
        refs_out = len([v for v in link.args
                        if isinstance(v, Variable) and var_needsgc(v)])
        assert refs_in + push_alives + calls == pop_alives + refs_out
    

def rtype_and_transform(func, inputtypes, transformcls, specialize=True):
    t = TranslationContext()
    t.buildannotator().build_types(func, inputtypes)
    if specialize:
        t.buildrtyper().specialize(t)
    transformer = transformcls()
    transformer.transform(t.graphs)
    t.checkgraphs()
    for graph in t.graphs:
        for block in graph.iterblocks():
            print graph, block, block.isstartblock
            checkblock(block)
    return t

def test_simple():
    def f():
        return 1
    rtype_and_transform(f, [], gctransform.GCTransformer)

def test_fairly_simple():
    class C:
        pass
    def f():
        c = C()
        c.x = 1
        return c.x
    t = rtype_and_transform(f, [], gctransform.GCTransformer)

def test_return_gcpointer():
    class C:
        pass
    def f():
        c = C()
        c.x = 1
        return c
    t = rtype_and_transform(f, [], gctransform.GCTransformer)
    
def test_call_function():
    class C:
        pass
    def f():
        c = C()
        c.x = 1
        return c
    def g():
        return f().x
    t = rtype_and_transform(g, [], gctransform.GCTransformer)
    ggraph = graphof(t, g)
    for i, op in enumerate(ggraph.startblock.operations):
        if op.opname == "direct_call":
            break
    else:
        assert False, "direct_call not found!"
    assert ggraph.startblock.operations[i + 1].opname != 'gc_push_alive'

def test_multiple_exits():
    S = lltype.GcStruct("S", ('x', lltype.Signed))
    T = lltype.GcStruct("T", ('y', lltype.Signed))
    def f(n):
        c = lltype.malloc(S)
        d = lltype.malloc(T)
        e = lltype.malloc(T)
        if n:
            x = d
        else:
            x = e
        return x
    t = rtype_and_transform(f, [int], gctransform.GCTransformer)
    fgraph = graphof(t, f)
    from pypy.translator.backendopt.ssa import SSI_to_SSA
    SSI_to_SSA(fgraph) # *cough*
    #t.view()
    pop_alive_count = 0
    for i, op in enumerate(fgraph.startblock.operations):
        if op.opname == "gc_pop_alive":
            var, = op.args
            assert var.concretetype == lltype.Ptr(S)
            pop_alive_count += 1
    
    assert pop_alive_count == 1, "gc_pop_alive not found!"
    for link in fgraph.startblock.exits:
        assert len(link.args) == 2
        ops = link.target.operations
        assert len(ops) == 1
        assert ops[0].opname == 'gc_pop_alive'
        assert len(ops[0].args) == len(link.target.exits) == \
               len(link.target.exits[0].args) == 1
        dyingname = ops[0].args[0].name
        passedname = link.target.exits[0].args[0].name
        assert dyingname != passedname
    
def test_cleanup_vars_on_call():
    S = lltype.GcStruct("S", ('x', lltype.Signed))
    def f():
        return lltype.malloc(S)
    def g():
        s1 = f()
        s2 = f()
        s3 = f()
        return s1
    t = rtype_and_transform(g, [], gctransform.GCTransformer)
    ggraph = graphof(t, g)
    direct_calls = [op for op in ggraph.startblock.operations if op.opname == "direct_call"]
    assert len(direct_calls) == 3
    assert direct_calls[1].cleanup[0].args[0] == direct_calls[0].result
    assert [op.args[0] for op in direct_calls[2].cleanup] == \
           [direct_calls[0].result, direct_calls[1].result]

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
    t = rtype_and_transform(f, [int], gctransform.GCTransformer)

def test_pyobj():
    def f(x):
        if x:
            a = 1
        else:
            a = "1"
        return int(a)
    t = rtype_and_transform(f, [int], gctransform.GCTransformer)
    fgraph = graphof(t, f)
    gcops = [op for op in fgraph.startblock.exits[0].target.operations
                 if op.opname.startswith("gc_")]
    for op in gcops:
        assert op.opname.endswith("_pyobj")

def test_pass_gc_pointer():
    S = lltype.GcStruct("S", ('x', lltype.Signed))
    def f(s):
        s.x = 1
    def g():
        s = lltype.malloc(S)
        f(s)
        return s.x
    t = rtype_and_transform(g, [], gctransform.GCTransformer)
        
def test_noconcretetype():
    def f():
        return [1][0]
    t = rtype_and_transform(f, [], gctransform.GCTransformer, specialize=False)
    fgraph = graphof(t, f)
    push_count = 0
    pop_count = 0
    for op in fgraph.startblock.operations:
        if op.opname == 'gc_push_alive_pyobj':
            push_count += 1
        elif op.opname == 'gc_pop_alive_pyobj':
            pop_count += 1
    assert push_count == 0 and pop_count == 1
    
