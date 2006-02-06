from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.objspace.flow.model import SpaceOperation, Variable, Constant, \
     c_last_exception, FunctionGraph, Block, Link, checkgraph
from pypy.translator.unsimplify import insert_empty_block
from pypy.rpython import rmodel
from pypy.rpython.memory import gc
import sets

"""
thought experiments

'setfield' obj field value ->
  a1 <- 'cast_ptr_to_adr' obj
  a2 <- 'cast_ptr_to_adr' value
  'direct_call' write_barrier a1, offset(TYPE(obj), field), a2

operations that need hooks:

setfield, setarrayitem, direct_call, indirect_call, malloc, getfield,
getarrayitem, getsubstruct?

push_alive, pop_alive,

"""

EXCEPTION_RAISING_OPS = ['direct_call', 'indirect_call']

def var_needsgc(var):
    if hasattr(var, 'concretetype'):
        vartype = var.concretetype
        return isinstance(vartype, lltype.Ptr) and vartype._needsgc()
    else:
        # assume PyObjPtr
        return True

def var_ispyobj(var):
    if hasattr(var, 'concretetype'):
        if isinstance(var.concretetype, lltype.Ptr):
            return var.concretetype.TO is lltype.PyObject
        else:
            return False
    else:
        # assume PyObjPtr
        return True
    

class GCTransformer:
    def __init__(self):
        self.seen_graphs = {}

    def transform(self, graphs):
        for graph in graphs:
            self.transform_graph(graph)

    def transform_graph(self, graph):
        if graph in self.seen_graphs:
            return
        self.seen_graphs[graph] = True
        self.links_to_split = {} # link -> vars to pop_alive across the link

        newops = []
        for var in graph.startblock.inputargs:
            if var_needsgc(var):
                newops.extend(self.push_alive(var))
        graph.startblock.operations[0:0] = newops
        
        for block in graph.iterblocks():
            self.transform_block(block)
        for link, livecounts in self.links_to_split.iteritems():
            newops = []
            for var, livecount in livecounts.iteritems():
                for i in range(livecount):
                    newops.extend(self.pop_alive(var))
                for i in range(-livecount):
                    newops.extend(self.push_alive(var))
            if newops:
                if len(link.prevblock.exits) == 1:
                    link.prevblock.operations.extend(newops)
                else:
                    insert_empty_block(None, link, newops)

    def transform_block(self, block):
        newops = []
        livevars = [var for var in block.inputargs if var_needsgc(var)]
        for op in block.operations:
            newops.extend(self.replacement_operations(op))
            # XXX for now we assume that everything can raise
            if 1 or op.opname in EXCEPTION_RAISING_OPS:
                cleanup_on_exception = []
                for var in livevars:
                    cleanup_on_exception.extend(self.pop_alive(var))
                op.cleanup = cleanup_on_exception
            if var_needsgc(op.result):
                if op.opname not in ('direct_call', 'indirect_call') and not var_ispyobj(op.result):
                    newops.extend(self.push_alive(op.result))
                livevars.append(op.result)
        if len(block.exits) == 0:
            # everything is fine already for returnblocks and exceptblocks
            pass
        else:
            if block.exitswitch is c_last_exception:
                # if we're in a try block, the last operation must
                # remain the last operation, so don't add a pop_alive
                # to the block, even if the variable dies in all
                # linked blocks.
                deadinallexits = sets.Set([])
            else:
                deadinallexits = sets.Set(livevars)
                for link in block.exits:
                    deadinallexits.difference_update(sets.Set(link.args))
            for var in deadinallexits:
                newops.extend(self.pop_alive(var))
            for link in block.exits:
                livecounts = dict.fromkeys(sets.Set(livevars) - deadinallexits, 1)
                if (block.exitswitch is c_last_exception and
                    link.exitcase is not None):
                    if livevars and livevars[-1] is block.operations[-1].result:
                        # if the last operation in the block raised an
                        # exception, it can't have returned anything that
                        # might need pop_aliving.
                        del livecounts[livevars[-1]]
                    for v in link.last_exception, link.last_exc_value:
                        if var_needsgc(v):
                            livecounts[v] = 1
                for v in link.args:
                    if v in livecounts:
                        livecounts[v] -= 1
                    elif var_needsgc(v):
                        assert isinstance(v, Constant)
                        livecounts[v] = -1
                self.links_to_split[link] = livecounts
        if newops:
            block.operations = newops

    def replacement_operations(self, op):
        m = getattr(self, 'replace_' + op.opname, None)
        if m:
            return m(op)
        else:
            return [op]

    def replace_setfield(self, op):
        if not var_needsgc(op.args[2]):
            return [op]
        oldval = Variable()
        oldval.concretetype = op.args[2].concretetype
        getoldvalop = SpaceOperation("getfield", [op.args[0], op.args[1]], oldval)
        result = [getoldvalop]
        result.extend(self.pop_alive(oldval))
        result.extend(self.push_alive(op.args[2]))
        result.append(op)
        return result

    def replace_setarrayitem(self, op):
        if not var_needsgc(op.args[2]):
            return [op]
        oldval = Variable()
        oldval.concretetype = op.args[2].concretetype
        getoldvalop = SpaceOperation("getarrayitem",
                                     [op.args[0], op.args[1]], oldval)
        result = [getoldvalop]
        result.extend(self.pop_alive(oldval))
        result.extend(self.push_alive(op.args[2]))
        result.append(op)
        return result

    def push_alive(self, var):
        if var_ispyobj(var):
            return self.push_alive_pyobj(var)
        else:
            return self.push_alive_nopyobj(var)

    def push_alive_nopyobj(self, var):
        result = Variable()
        result.concretetype = lltype.Void
        return [SpaceOperation("gc_push_alive", [var], result)]

    def push_alive_pyobj(self, var):
        result = Variable()
        result.concretetype = lltype.Void
        return [SpaceOperation("gc_push_alive_pyobj", [var], result)]

    def pop_alive(self, var):
        if var_ispyobj(var):
            return self.pop_alive_pyobj(var)
        else:
            return self.pop_alive_nopyobj(var)

    def pop_alive_nopyobj(self, var):
        result = Variable()
        result.concretetype = lltype.Void
        return [SpaceOperation("gc_pop_alive", [var], result)]

    def pop_alive_pyobj(self, var):
        result = Variable()
        result.concretetype = lltype.Void
        return [SpaceOperation("gc_pop_alive_pyobj", [var], result)]

    def free(self, var):
        result = Variable()
        result.concretetype = lltype.Void
        return [SpaceOperation("gc_free", [var], result)]        
    

    # ----------------------------------------------------------------

    def _static_deallocator_body_for_type(self, v, TYPE, depth=1):
        if isinstance(TYPE, lltype.Array):
            
            inner = list(self._static_deallocator_body_for_type('v_%i'%depth, TYPE.OF, depth+1))
            if inner:
                yield '    '*depth + 'i_%d = 0'%(depth,)
                yield '    '*depth + 'l_%d = len(%s)'%(depth, v)
                yield '    '*depth + 'while i_%d < l_%d:'%(depth, depth)
                yield '    '*depth + '    v_%d = %s[i_%d]'%(depth, v, depth)
                for line in inner:
                    yield line
                yield '    '*depth + '    i_%d += 1'%(depth,)
        elif isinstance(TYPE, lltype.Struct):
            for name in TYPE._names:
                inner = list(self._static_deallocator_body_for_type(
                    v + '_' + name, TYPE._flds[name], depth))
                if inner:
                    yield '    '*depth + v + '_' + name + ' = ' + v + '.' + name
                    for line in inner:
                        yield line
        elif isinstance(TYPE, lltype.Ptr):
            yield '    '*depth + 'pop_alive(%s)'%v

    def static_deallocation_graph_for_type(self, translator, TYPE, var):
        def compute_pop_alive_ll_ops(hop):
            hop.llops.extend(self.pop_alive(hop.args_v[1]))
            return hop.inputconst(hop.r_result.lowleveltype, hop.s_result.const)
        def pop_alive(var):
            pass
        pop_alive.compute_ll_ops = compute_pop_alive_ll_ops
        pop_alive.llresult = lltype.Void
        def compute_destroy_ll_ops(hop):
            hop.llops.extend(self.free(hop.args_v[1]))
            return hop.inputconst(hop.r_result.lowleveltype, hop.s_result.const)
        def destroy(var):
            pass
        destroy.compute_ll_ops = compute_destroy_ll_ops
        destroy.llresult = lltype.Void

        destrptr = None
        
        if isinstance(TYPE, lltype.Struct):
            rtti = None
            try:
                rtti = lltype.getRuntimeTypeInfo(TYPE)
            except ValueError:
                pass
            if rtti is not None:
                if hasattr(rtti._obj, 'destructor_funcptr'):
                    destrptr = rtti._obj.destructor_funcptr

        assert destrptr is None

        body = '\n'.join(self._static_deallocator_body_for_type('v', TYPE))
        
        src = 'def deallocator(v):\n' + body + '\n    destroy(v)\n'
        d = {'pop_alive':pop_alive,
             'destroy':destroy}
        print
        print src
        print
        exec src in d
        this = d['deallocator']
        g = translator.rtyper.annotate_helper(this, [lltype.Ptr(TYPE)])
        translator.rtyper.specialize_more_blocks()
        opcount = 0
        for block in g.iterblocks():
            opcount += len(block.operations)
        if opcount == 0:
            return None
        else:
            return g

class RefcountingGCTransformer(GCTransformer):
    gc_header_offset = gc.GCHeaderOffset(lltype.Struct("header", ("refcount", lltype.Signed)))
    def push_alive_nopyobj(self, var):
        adr1 = varoftype(llmemory.Address)
        result = [SpaceOperation("cast_ptr_to_adr", [var], adr1)]
        adr2 = varoftype(llmemory.Address)
        offset = rmodel.inputconst(lltype.Signed, self.gc_header_offset)
        result.append(SpaceOperation("adr_sub", [adr1, offset], adr2))
        zero = rmodel.inputconst(lltype.Signed, 0)
        intconst = rmodel.inputconst(lltype.Void, int)
        refcount = varoftype(lltype.Signed)
        result.append(SpaceOperation("raw_load", [adr2, intconst, zero], refcount))
        newrefcount = varoftype(lltype.Signed)
        result.append(SpaceOperation("int_add",
                                     [refcount, rmodel.inputconst(lltype.Signed, 1)],
                                     newrefcount))
        result.append(SpaceOperation("raw_store",
                                     [adr2, intconst, zero, newrefcount],
                                     varoftype(lltype.Void)))
        return result

def varoftype(concretetype):
    var = Variable()
    var.concretetype = concretetype
    return var
