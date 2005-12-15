from pypy.translator.backendopt.merge_if_blocks import merge_if_blocks_once
from pypy.translator.translator import TranslationContext, graphof as tgraphof
from pypy.objspace.flow.model import flatten, Block
from pypy.translator.backendopt.removenoops import remove_same_as

def test_merge1():
    def merge1(n):
        n += 1
        if n == 1:
            return 1
        elif n == 2:
            return 2
        elif n == 3:
            return 3
        return 4
    t = TranslationContext()
    a = t.buildannotator()
    a.build_types(merge1, [int])
    rtyper = t.buildrtyper()
    rtyper.specialize()
    graph = tgraphof(t, merge1)
    assert len(list(graph.iterblocks())) == 4 #startblock, blocks, returnblock
    remove_same_as(graph)
    merge_if_blocks_once(graph)
    assert len(graph.startblock.exits) == 4
    assert len(list(graph.iterblocks())) == 2 #startblock, returnblock

def test_merge_passonvars():
    def merge(n, m):
        if n == 1:
            return m + 1
        elif n == 2:
            return m + 2
        elif n == 3:
            return m + 3
        return m + 4
    t = TranslationContext()
    a = t.buildannotator()
    a.build_types(merge, [int, int])
    rtyper = t.buildrtyper()
    rtyper.specialize()
    graph = tgraphof(t, merge)
    assert len(list(graph.iterblocks())) == 8
    remove_same_as(graph)
    merge_if_blocks_once(graph)
    assert len(graph.startblock.exits) == 4

