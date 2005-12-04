from pypy.rpython.l3interp import l3interp
from pypy.rpython.l3interp import model
from pypy.rpython.l3interp.model import Op
from pypy.translator.c.test.test_genc import compile
from pypy.translator.translator import TranslationContext
from pypy.annotation import policy

def translate(func, inputargs):
    t = TranslationContext()
    pol = policy.AnnotatorPolicy()
    pol.allow_someobjects = False
    t.buildannotator(policy=pol).build_types(func, inputargs)
    t.buildrtyper().specialize()

    from pypy.translator.tool.cbuild import skip_missing_compiler
    from pypy.translator.c import genc
    builder = genc.CExtModuleBuilder(t, func)
    builder.generate_source()
    skip_missing_compiler(builder.compile)
    builder.import_module()
    return builder.get_entry_point()


#----------------------------------------------------------------------
def eval_seven():
    #def f():
    #    return 3 + 4
    block = model.Block([Op.int_add, 0, 1,
                         Op.int_return, -1],
                        constants_int = [3, 4])
    graph = model.Graph("testgraph", block, 0, 0, 0)
    value = l3interp.l3interpret(graph, [], [], [])
    assert isinstance(value, l3interp.L3Integer)
    return value.intval
      
def test_very_simple():
    result = eval_seven()
    assert result == 7

def test_very_simple_translated():
    fn = translate(eval_seven, []) 
    assert fn() == 7

#----------------------------------------------------------------------
def eval_eight(number):
    #def f(x):
    #    return x + 4
    block = model.Block([Op.int_add, -1, 0,
                         Op.int_return, -1],
                        constants_int = [4])
    graph = model.Graph("testgraph", block, 1, 0, 0)
    value = l3interp.l3interpret(graph, [number], [], [])
    assert isinstance(value, l3interp.L3Integer)
    return value.intval

def test_simple():
    result = eval_eight(4)
    assert result == 8

def test_simple_translated():
    fn = translate(eval_eight, [int]) 
    assert fn(4) == 8 
#----------------------------------------------------------------------

def eval_branch(number):
    #def f(x):
    #    if x:
    #        return x
    #    return 1
    block1 = model.Block([Op.jump_cond, -1])
    block2 = model.Block([Op.int_return, -1])
    block3 = model.Block([Op.int_return, 0], constants_int=[1])
    block1.exit0 = model.Link(block3)
    block1.exit1 = model.Link(block2, targetregs_int=[-1])
    graph = model.Graph("testgraph", block1, 1, 0, 0)
    value = l3interp.l3interpret(graph, [number], [], [])
    assert isinstance(value, l3interp.L3Integer)
    return value.intval

def test_branch():
    result = eval_branch(4)
    assert result == 4
    result = eval_branch(0)
    assert result == 1

def test_branch_translated():
    fn = translate(eval_branch, [int]) 
    assert fn(4) == 4
    assert fn(0) == 1

#----------------------------------------------------------------------

def eval_call(number):
    #def g(x):
    #    return x + 1
    #def f(x):
    #    return g(x) + 2
    block = model.Block([Op.int_add, -1, 0,
                         Op.int_return, -1],
                        constants_int = [1])
    graph1 = model.Graph("g", block, 1, 0, 0)

    block = model.Block([Op.direct_call, 0, -1,
                         Op.int_add, -1, 0,
                         Op.int_return, -1],
                        constants_int = [2],
                        called_graphs = [graph1])
    graph2 = model.Graph("f", block, 1, 0, 0)

    value = l3interp.l3interpret(graph2, [number], [], [])
    assert isinstance(value, l3interp.L3Integer)
    return value.intval

def test_call():
    result = eval_call(4)
    assert result == 7
    result = eval_call(0)
    assert result == 3

def test_call_translated():
    fn = translate(eval_call, [int]) 
    assert fn(4) == 7 
    assert fn(0) == 3
