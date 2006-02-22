# functions to query information out of the translator and annotator from the debug prompt of translate
import types
import re

import pypy.annotation.model as annmodel
import pypy.objspace.flow.model as flowmodel

# query used for sanity checks by translate

def short_binding(annotator, var):
    try:
        binding = annotator.binding(var)
    except KeyError:
        return "?"
    if binding.is_constant():
        return 'const %s' % binding.__class__.__name__
    else:
        return binding.__class__.__name__

def graph_sig(t, g):
    ann = t.annotator
    hbinding = lambda v: short_binding(ann, v)
    return "%s -> %s" % (
        ', '.join(map(hbinding, g.getargs())),
        hbinding(g.getreturnvar()))
    
class Found(Exception):
    pass

def polluted_qgen(translator):
    """list functions with still real SomeObject variables"""
    annotator = translator.annotator
    def visit(block):
        if isinstance(block, flowmodel.Block):
            for v in block.getvariables():
                s = annotator.binding(v, extquery=True)
                if s and s.__class__ == annmodel.SomeObject and s.knowntype != type:
                    raise Found
    for g in translator.graphs:
        try:
            flowmodel.traverse(visit, g)
        except Found:
            line = "%s: %s" % (g, graph_sig(translator, g))
            yield line

def check_exceptblocks_qgen(translator):
    annotator = translator.annotator
    for graph in translator.graphs:
        et, ev = graph.exceptblock.inputargs
        s_et = annotator.binding(et, extquery=True)
        s_ev = annotator.binding(ev, extquery=True)
        if s_et:
            if s_et.knowntype == type:
                if s_et.__class__ == annmodel.SomeObject:
                    if hasattr(s_et, 'is_type_of') and  s_et.is_type_of == [ev]:
                        continue
                else:
                    if s_et.__class__ == annmodel.SomePBC:
                        continue
            yield "%s exceptblock is not completely sane" % graph.name

def check_methods_qgen(translator):
    from pypy.annotation.description import FunctionDesc, MethodDesc
    def ismeth(s_val):
        if not isinstance(s_val, annmodel.SomePBC):
            return False
        if s_val.isNone():
            return False
        return s_val.getKind() is MethodDesc
    bk = translator.annotator.bookkeeper
    classdefs = bk.classdefs
    withmeths = []
    for clsdef in classdefs:
        meths = []
        for attr in clsdef.attrs.values():
            if ismeth(attr.s_value):
                meths.append(attr)
        if meths:
            withmeths.append((clsdef, meths))
    for clsdef, meths in withmeths:
        n = 0
        subclasses = []
        for clsdef1 in classdefs:
            if clsdef1.issubclass(clsdef):
                subclasses.append(clsdef1)
        for meth in meths:
            name = meth.name
            funcs = dict.fromkeys([desc.funcdesc
                                   for desc in meth.s_value.descriptions])
            for subcls in subclasses:
                if not subcls.classdesc.find_source_for(name):
                    continue
                c = subcls.classdesc.read_attribute(name)
                if isinstance(c, flowmodel.Constant):
                    if not isinstance(c.value, (types.FunctionType,
                                                types.MethodType)):
                        continue
                    c = bk.getdesc(c.value)
                if isinstance(c, FunctionDesc):
                    if c not in funcs:
                        yield "lost method: %s %s %s %s" % (name, subcls.name, clsdef.name, subcls.attrs.keys() )

def qoutput(queryg, write=None):
    if write is None:
        def write(s):
            print s
    c = 0
    for bit in queryg:
        write(bit)
        c += 1
    return c

def polluted(translator):
    c = qoutput(polluted_qgen(translator))
    print c

def sanity_check_methods(translator):
    lost = qoutput(check_methods_qgen(translator))
    print lost
