import py
from pypy.translator.translator import TranslationContext, graphof
from pypy.jit.hintannotator import HintAnnotator
from pypy.jit.hintbookkeeper import HintBookkeeper
from pypy.jit.hintmodel import *
from pypy.jit.hinttimeshift import HintTimeshift
from pypy.jit import rtimeshift
from pypy.jit.test.test_llabstractinterp import annotation
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.objectmodel import hint
from pypy.rpython import rgenop
from pypy.annotation import model as annmodel
from pypy.rpython.llinterp import LLInterpreter
from pypy.objspace.flow.model import checkgraph
from pypy import conftest


def hannotate(func, values, policy=None):
    # build the normal ll graphs for ll_function
    t = TranslationContext()
    a = t.buildannotator()
    argtypes = [annotation(a, x) for x in values]
    a.build_types(func, argtypes)
    rtyper = t.buildrtyper()
    rtyper.specialize()
    graph1 = graphof(t, func)
    # build hint annotator types
    hannotator = HintAnnotator(policy=policy)
    hannotator.base_translator = t
    hs = hannotator.build_types(graph1, [SomeLLAbstractConstant(v.concretetype,
                                                                {OriginFlags(): True})
                                         for v in graph1.getargs()])
    if conftest.option.view:
        hannotator.translator.view()
    return hs, hannotator, rtyper

def timeshift(ll_function, values):
    hs, ha, rtyper = hannotate(ll_function, values)
    htshift = HintTimeshift(ha, rtyper)
    htshift.timeshift()
    t = rtyper.annotator.translator
    for graph in ha.translator.graphs:
        checkgraph(graph)
        t.graphs.append(graph)
    if conftest.option.view:
        t.view()
    # run the time-shifted graph-producing graphs
    graph1 = ha.translator.graphs[0]
    jitstate = rtimeshift.ll_setup_jitstate()
    graph1args = [jitstate]
    residual_graph_args = []
    assert len(graph1.getargs()) == 1 + len(values)
    for v, llvalue in zip(graph1.getargs()[1:], values):
        color = htshift.varcolor[v]
        if color == "green":
            graph1args.append(llvalue)
        elif color == "red":
            TYPE = htshift.varconcretetype[v]
            box = rtimeshift.ll_input_redbox(jitstate, TYPE)
            graph1args.append(box)
            residual_graph_args.append(llvalue)
        else:
            raise NotImplementedError(color)
    llinterp = LLInterpreter(rtyper)
    result1 = llinterp.eval_graph(graph1, graph1args)
    # now try to run the block produced by the jitstate
    color = htshift.varcolor[graph1.getreturnvar()]
    if color == "green":
        result_gvar = rgenop.genconst(jitstate.curblock, result1)
    elif color == "red":
        result_gvar = result1.genvar
    else:
        raise NotImplementedError(color)
    jitblock = rtimeshift.ll_close_jitstate(jitstate, result_gvar)
    return rgenop.runblock(jitblock, residual_graph_args,
                           viewbefore = conftest.option.view)

def test_simple_fixed():
    def ll_function(x, y):
        return hint(x + y, concrete=True)
    res = timeshift(ll_function, [5, 7])
    assert res == 12

def test_simple():
    def ll_function(x, y):
        return x + y
    res = timeshift(ll_function, [5, 7])
    assert res == 12
