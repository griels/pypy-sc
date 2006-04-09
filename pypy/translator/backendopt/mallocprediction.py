from pypy.translator.backendopt.escape import AbstractDataFlowInterpreter
from pypy.translator.backendopt.malloc import remove_simple_mallocs
from pypy.translator.backendopt.inline import auto_inlining
from pypy.rpython.lltypesystem import lltype
from pypy.translator.simplify import get_graph

def find_malloc_creps(graph, adi, translator):
    # mapping from malloc creation point to graphs that it flows into
    malloc_creps = {}
    # find all mallocs that don't escape
    for block, op in graph.iterblockops():
        if op.opname == 'malloc':
            STRUCT = op.args[0].value
            # must not remove mallocs of structures that have a RTTI with a destructor
            try:
                destr_ptr = lltype.getRuntimeTypeInfo(
                    STRUCT)._obj.destructor_funcptr
                if destr_ptr:
                    continue
            except (ValueError, AttributeError), e:
                pass
            varstate = adi.getstate(op.result)
            assert len(varstate.creation_points) == 1
            crep = varstate.creation_points.keys()[0]
            if not crep.escapes:
                malloc_creps[crep] = {}
    return malloc_creps

def find_calls_where_creps_go(interesting_creps, graph, adi,
                              translator, seen):
    print "find_calls_where_creps_go", interesting_creps, graph.name
    print seen
    # drop creps that are merged with another creation point
    for block in graph.iterblocks():
        for var in block.getvariables():
            varstate = adi.getstate(var)
            if varstate is None:
                continue
            for crep in varstate.creation_points:
                if crep in interesting_creps:
                    if len(varstate.creation_points) != 1:
                        del interesting_creps[crep]
                        break
    
    # drop creps that are passed into an indirect_call
    for block, op in graph.iterblockops():
        if not interesting_creps:
            return
        if op.opname == "indirect_call":
            for var in op.args[:-1]:
                varstate = adi.getstate(var)
                for crep in varstate.creation_points:
                    if crep in interesting_creps:
                        del interesting_creps[crep]
        elif op.opname == "direct_call":
            print op, interesting_creps
            called_graph = get_graph(op.args[0], translator)
            if called_graph is None:
                del interesting_creps[crep]
                print "graph not found"
                continue
            interesting = {}
            for i, var in enumerate(op.args[1:]):
                print i, var,
                varstate = adi.getstate(var)
                if varstate is None:
                    print "no varstate"
                    continue
                if len(varstate.creation_points) == 1:
                    crep = varstate.creation_points.keys()[0]
                    if crep not in interesting_creps:
                        print "not interesting"
                        continue
                    if (called_graph, i) in seen:
                        seen[(called_graph, i)][graph] = True
                        print "seen already"
                    else:
                        print "taking", crep
                        seen[(called_graph, i)] = {graph: True}
                        arg = called_graph.startblock.inputargs[i]
                        argstate = adi.getstate(arg)
                        argcrep = [c for c in argstate.creation_points
                                    if c.creation_method == "arg"][0]
                        interesting[argcrep] = True
            print interesting
            if interesting:
                find_calls_where_creps_go(interesting, called_graph,
                                          adi, translator, seen)
    return interesting_creps

def find_malloc_removal_candidates(t):
    adi = AbstractDataFlowInterpreter(t)
    for graph in t.graphs:
        if graph.startblock not in adi.flown_blocks:
            adi.schedule_function(graph)
            adi.complete()
    caller_candidates = {}
    seen = {}
    for graph in t.graphs:
        creps = find_malloc_creps(graph, adi, t)
        print "malloc creps", creps
        if creps:
            find_calls_where_creps_go(creps, graph, adi, t, seen)
            if creps:
                caller_candidates[graph] = True
    callgraph = []
    for (called_graph, i), callers in seen.iteritems():
        for caller in callers:
            callgraph.append((caller, called_graph))
    return callgraph, caller_candidates

def inline_and_remove(t, threshold=1):
    callgraph, caller_candidates = find_malloc_removal_candidates(t)
    auto_inlining(t, threshold, callgraph)
    for graph in caller_candidates:
        remove_simple_mallocs(graph)
