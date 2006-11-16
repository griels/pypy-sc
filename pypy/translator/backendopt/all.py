from pypy.translator.backendopt.raisingop2direct_call import raisingop2direct_call
from pypy.translator.backendopt import removenoops
from pypy.translator.backendopt import inline
from pypy.translator.backendopt.malloc import remove_simple_mallocs
from pypy.translator.backendopt.constfold import constant_fold_graph
from pypy.translator.backendopt.stat import print_statistics
from pypy.translator.backendopt.merge_if_blocks import merge_if_blocks
from pypy.translator import simplify
from pypy.translator.backendopt.escape import malloc_to_stack
from pypy.translator.backendopt.mallocprediction import clever_inlining_and_malloc_removal
from pypy.translator.backendopt.removeassert import remove_asserts
from pypy.translator.backendopt.support import log
from pypy.objspace.flow.model import checkgraph

def backend_optimizations(translator, graphs=None, **kwds):
    # sensible keywords are
    # raisingop2direct_call, inline_threshold, mallocs
    # merge_if_blocks, constfold, heap2stack
    # clever_malloc_removal, remove_asserts

    config = translator.config.translation.backendopt.copy()
    config.set(**kwds)

    if graphs is None:
        graphs = translator.graphs

    if config.print_statistics:
        print "before optimizations:"
        print_statistics(translator.graphs[0], translator, "per-graph.txt")

    if config.raisingop2direct_call:
        raisingop2direct_call(translator, graphs)

    # remove obvious no-ops
    for graph in graphs:
        removenoops.remove_same_as(graph)
        simplify.eliminate_empty_blocks(graph)
        simplify.transform_dead_op_vars(graph, translator)
        removenoops.remove_duplicate_casts(graph, translator)

    if config.print_statistics:
        print "after no-op removal:"
        print_statistics(translator.graphs[0], translator)

    if not config.clever_malloc_removal:
        if config.profile_based_inline:
            inline_malloc_removal_phase(config, translator, graphs,
                                        config.inline_threshold*.5) # xxx tune!
            inline.instrument_inline_candidates(graphs, config.inline_threshold)
            data = translator.driver_instrument_result(
                       config.profile_based_inline)
            import array, struct
            n = data.size()//struct.calcsize('L')
            data = data.open('rb')
            counters = array.array('L')
            counters.fromfile(data, n)
            data.close()
            def call_count_pred(label):
                if label >= n:
                    return False
                return counters[label] > 250 # xxx tune!
        else:
            call_count_pred = None
        inline_malloc_removal_phase(config, translator, graphs,
                                    config.inline_threshold,
                                    call_count_pred=call_count_pred)
    else:
        assert graphs is translator.graphs  # XXX for now
        clever_inlining_and_malloc_removal(translator)

        if config.print_statistics:
            print "after clever inlining and malloc removal"
            print_statistics(translator.graphs[0], translator)

    if config.constfold:
        for graph in graphs:
            constant_fold_graph(graph)

    if config.remove_asserts:
        remove_asserts(translator, graphs)

    if config.heap2stack:
        assert graphs is translator.graphs  # XXX for now
        malloc_to_stack(translator)

    if config.merge_if_blocks:
        for graph in graphs:
            merge_if_blocks(graph)

    if config.print_statistics:
        print "after if-to-switch:"
        print_statistics(translator.graphs[0], translator)

    for graph in graphs:
        checkgraph(graph)

def inline_malloc_removal_phase(config, translator, graphs, inline_threshold,
                                call_count_pred=None):

    log.inlining("phase with threshold factor: %s" % inline_threshold)

    # inline functions in each other
    if inline_threshold:
        callgraph = inline.inlinable_static_callers(graphs)
        inline.auto_inlining(translator, inline_threshold,
                             callgraph=callgraph,
                             call_count_pred=call_count_pred)
        for graph in graphs:
            removenoops.remove_superfluous_keep_alive(graph)
            removenoops.remove_duplicate_casts(graph, translator)

        if config.print_statistics:
            print "after inlining:"
            print_statistics(translator.graphs[0], translator)

    # vaporize mallocs
    if config.mallocs:
        tot = 0
        for graph in graphs:
            count = remove_simple_mallocs(graph)
            if count:
                # remove typical leftovers from malloc removal
                removenoops.remove_same_as(graph)
                simplify.eliminate_empty_blocks(graph)
                simplify.transform_dead_op_vars(graph, translator)
                tot += count
        log.malloc("removed %d simple mallocs in total" % tot)

        if config.print_statistics:
            print "after malloc removal:"
            print_statistics(translator.graphs[0], translator)    
