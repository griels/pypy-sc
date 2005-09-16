from pypy.objspace.flow.model import Variable, mkentrymap, flatten, Block
from pypy.tool.unionfind import UnionFind

def data_flow_families(graph):
    """Follow the flow of the data in the graph.  Returns a UnionFind grouping
    all the variables by families: each family contains exactly one variable
    where a value is stored into -- either by an operation or a merge -- and
    all following variables where the value is just passed unmerged into the
    next block.
    """
    entrymaplist = mkentrymap(graph).items()
    progress = True
    variable_families = UnionFind()

    # group variables by families; a family of variables will be identified.
    while progress:
        progress = False
        for block, links in entrymaplist:
            if block is graph.startblock:
                continue
            assert links
            for i in range(len(block.inputargs)):
                # list of possible vars that can arrive in i'th position
                v1 = block.inputargs[i]
                v1 = variable_families.find_rep(v1)
                inputs = {v1: True}
                key = []
                for link in links:
                    v = link.args[i]
                    if not isinstance(v, Variable):
                        break
                    v = variable_families.find_rep(v)
                    inputs[v] = True
                else:
                    if len(inputs) == 2:
                        variable_families.union(*inputs)
                        progress = True
    return variable_families

def SSI_to_SSA(graph):
    """Rename the variables in a flow graph as much as possible without
    violating the SSA rule.  'SSI' means that each Variable in a flow graph is
    defined only once in the whole graph; all our graphs are SSI.  This
    function does not break that rule, but changes the 'name' of some
    Variables to give them the same 'name' as other Variables.  The result
    looks like an SSA graph.  'SSA' means that each var name appears as the
    result of an operation only once in the whole graph, but it can be
    passed to other blocks across links.
    """
    variable_families = data_flow_families(graph)
    # rename variables to give them the name of their familiy representant
    for v in variable_families.keys():
        v1 = variable_families.find_rep(v)
        if v1 != v:
            v._name = v1.name

    # sanity-check that the same name is never used several times in a block
    variables_by_name = {}
    for block in flatten(graph):
        if not isinstance(block, Block):
            continue
        vars = [op.result for op in block.operations]
        for link in block.exits:
            vars += link.getextravars()
        assert len(dict.fromkeys([v.name for v in vars])) == len(vars), (
            "duplicate variable name in %r" % (block,))
        for v in vars:
            variables_by_name.setdefault(v.name, []).append(v)
    # sanity-check that variables with the same name have the same concretetype
    for vname, vlist in variables_by_name.items():
        vct = [getattr(v, 'concretetype', None) for v in vlist]
        assert vct == vct[:1] * len(vct), (
            "variables called %s have mixed concretetypes: %r" % (vname, vct))
