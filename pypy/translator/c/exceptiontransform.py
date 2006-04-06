from pypy.translator.simplify import join_blocks, cleanup_graph
from pypy.translator.unsimplify import copyvar, split_block
from pypy.translator.backendopt import canraise, inline, support
from pypy.objspace.flow.model import Block, Constant, Variable, Link, \
    c_last_exception, SpaceOperation, checkgraph, FunctionGraph
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.memory.lladdress import NULL
from pypy.rpython.memory.gctransform import varoftype
from pypy.rpython import rclass
from pypy.rpython.rarithmetic import r_uint, r_longlong, r_ulonglong
from pypy.annotation import model as annmodel
from pypy.rpython.annlowlevel import MixLevelHelperAnnotator

PrimitiveErrorValue = {lltype.Signed: -1,
                       lltype.Unsigned: r_uint(-1),
                       lltype.SignedLongLong: r_longlong(-1),
                       lltype.UnsignedLongLong: r_ulonglong(-1),
                       lltype.Float: -1.0,
                       lltype.Char: chr(255),
                       lltype.UniChar: unichr(0xFFFF), # XXX is this always right?
                       lltype.Bool: True,
                       llmemory.Address: NULL,
                       lltype.Void: None}

def error_value(T):
    if isinstance(T, lltype.Primitive):
        return Constant(PrimitiveErrorValue[T], T)
    elif isinstance(T, lltype.Ptr):
        return Constant(lltype.nullptr(T.TO), T)
    assert 0, "not implemented yet"

class ExceptionTransformer(object):
    def __init__(self, translator):
        self.translator = translator
        self.raise_analyzer = canraise.RaiseAnalyzer(translator)
        edata = translator.rtyper.getexceptiondata()
        self.lltype_of_exception_value = edata.lltype_of_exception_value
        self.lltype_of_exception_type = edata.lltype_of_exception_type
        mixlevelannotator = MixLevelHelperAnnotator(translator.rtyper)
        l2a = annmodel.lltype_to_annotation

        class ExcData(object):
            pass
            #exc_type = lltype.nullptr(self.exc_data.lltype_of_exception_type.TO)
            #exc_value = lltype.nullptr(self.exc_data.lltype_of_exception_value.TO)

        exc_data = ExcData()
        null_type = lltype.nullptr(self.lltype_of_exception_type.TO)
        null_value = lltype.nullptr(self.lltype_of_exception_value.TO)
        
        def rpyexc_occured():
            return exc_data.exc_type is not null_type

        def rpyexc_fetch_type():
            return exc_data.exc_type

        def rpyexc_fetch_value():
            return exc_data.exc_value

        def rpyexc_clear():
            exc_data.exc_type = null_type
            exc_data.exc_value = null_value

        def rpyexc_raise(etype, evalue):
            # assert(!RPyExceptionOccurred());
            exc_data.exc_type = etype
            exc_data.exc_value = evalue
        
        RPYEXC_OCCURED_TYPE = lltype.FuncType([], lltype.Bool)
        rpyexc_occured_graph = mixlevelannotator.getgraph(
            rpyexc_occured, [], l2a(lltype.Bool))
        self.rpyexc_occured_ptr = Constant(lltype.functionptr(
            RPYEXC_OCCURED_TYPE, "RPyExceptionOccurred",
            graph=rpyexc_occured_graph),
            lltype.Ptr(RPYEXC_OCCURED_TYPE))
        
        RPYEXC_FETCH_TYPE_TYPE = lltype.FuncType([], self.lltype_of_exception_type)
        rpyexc_fetch_type_graph = mixlevelannotator.getgraph(
            rpyexc_fetch_type, [],
            l2a(self.lltype_of_exception_type))
        self.rpyexc_fetch_type_ptr = Constant(lltype.functionptr(
            RPYEXC_FETCH_TYPE_TYPE, "RPyFetchExceptionType",
            graph=rpyexc_fetch_type_graph),
            lltype.Ptr(RPYEXC_FETCH_TYPE_TYPE))
        
        RPYEXC_FETCH_VALUE_TYPE = lltype.FuncType([], self.lltype_of_exception_value)
        rpyexc_fetch_value_graph = mixlevelannotator.getgraph(
            rpyexc_fetch_value, [],
            l2a(self.lltype_of_exception_value))
        self.rpyexc_fetch_value_ptr = Constant(lltype.functionptr(
            RPYEXC_FETCH_VALUE_TYPE, "RPyFetchExceptionValue",
            graph=rpyexc_fetch_value_graph),
            lltype.Ptr(RPYEXC_FETCH_VALUE_TYPE))

        RPYEXC_CLEAR = lltype.FuncType([], lltype.Void)
        rpyexc_clear_graph = mixlevelannotator.getgraph(
            rpyexc_clear, [], l2a(lltype.Void))
        self.rpyexc_clear_ptr = Constant(lltype.functionptr(
            RPYEXC_CLEAR, "RPyClearException",
            graph=rpyexc_clear_graph),
            lltype.Ptr(RPYEXC_CLEAR))

        RPYEXC_RAISE = lltype.FuncType([self.lltype_of_exception_type,
                                        self.lltype_of_exception_value],
                                        lltype.Void)
        rpyexc_raise_graph = mixlevelannotator.getgraph(
            rpyexc_raise, [l2a(self.lltype_of_exception_type),
                           l2a(self.lltype_of_exception_value)],
            l2a(lltype.Void))
        self.rpyexc_raise_ptr = Constant(lltype.functionptr(
            RPYEXC_RAISE, "RPyRaiseException",
            graph=rpyexc_raise_graph),
            lltype.Ptr(RPYEXC_RAISE))

        mixlevelannotator.finish()
    
    def transform_completely(self):
        for graph in self.translator.graphs:
            self.create_exception_handling(graph)

    def create_exception_handling(self, graph):
        """After an exception in a direct_call (or indirect_call), that is not caught
        by an explicit
        except statement, we need to reraise the exception. So after this
        direct_call we need to test if an exception had occurred. If so, we return
        from the current graph with a special value (False/-1/-1.0/null).
        Because of the added exitswitch we need an additional block.
        """
        join_blocks(graph)
        for block in list(graph.iterblocks()): #collect the blocks before changing them
            self.transform_block(graph, block)
        self.transform_except_block(graph, graph.exceptblock)
        cleanup_graph(graph)

    def transform_block(self, graph, block):
        if block is graph.exceptblock:
            return
        elif block is graph.returnblock:
            return
        last_operation = len(block.operations) - 1
        if block.exitswitch == c_last_exception:
            need_exc_matching = True
            last_operation -= 1
        else:
            need_exc_matching = False
        lastblock = block
        for i in range(last_operation, -1, -1):
            op = block.operations[i]
            if not self.raise_analyzer.can_raise(op):
                continue

            afterblock = support.split_block_with_keepalive(
                self.translator, graph, block, i+1, False)
            if lastblock is block:
                lastblock = afterblock

            self.gen_exc_check(block, graph.returnblock)                

            #non-exception case
            block.exits[0].exitcase = block.exits[0].llexitcase = False
        if need_exc_matching:
            assert lastblock.exitswitch == c_last_exception
            if not self.raise_analyzer.can_raise(lastblock.operations[-1]):
                print "XXX: operation %s cannot raise, but has exception guarding in graph %s" % (lastblock.operations[-1], graph)
                lastblock.exitswitch = None
                lastblock.exits = [lastblock.exits[0]]
                lastblock.exits[0].exitcase = None
            else:
                self.insert_matching(lastblock, graph)

    def transform_except_block(self, graph, block):
        # attach an except block -- let's hope that nobody uses it
        graph.exceptblock = Block([Variable('etype'),   # exception class
                                   Variable('evalue')])  # exception value
        result = Variable()
        result.concretetype = lltype.Void
        block.operations = [SpaceOperation(
           "direct_call", [self.rpyexc_raise_ptr] + block.inputargs, result)]
        l = Link([error_value(graph.returnblock.inputargs[0].concretetype)], graph.returnblock)
        l.prevblock  = block
        block.exits = [l]

    def insert_matching(self, block, graph):
        proxygraph, op = self.create_proxy_graph(block.operations[-1])
        block.operations[-1] = op
        #non-exception case
        block.exits[0].exitcase = block.exits[0].llexitcase = None
        # use the dangerous second True flag :-)
        inliner = inline.OneShotInliner(self.translator, graph,
                                        inline_guarded_calls=True,
                                        inline_guarded_calls_no_matter_what=True,
                                        raise_analyzer=self.raise_analyzer)
        inliner.inline_once(block, len(block.operations)-1)
        #block.exits[0].exitcase = block.exits[0].llexitcase = False

    def create_proxy_graph(self, op):
        """ creates a graph which calls the original function, checks for
        raised exceptions, fetches and then raises them again. If this graph is
        inlined, the correct exception matching blocks are produced."""
        # XXX slightly annoying: construct a graph by hand
        # but better than the alternative
        result = copyvar(self.translator, op.result)
        opargs = []
        inputargs = []
        callargs = []
        ARGTYPES = []
        for var in op.args:
            if isinstance(var, Variable):
                v = Variable()
                v.concretetype = var.concretetype
                inputargs.append(v)
                opargs.append(v)
                callargs.append(var)
                ARGTYPES.append(var.concretetype)
            else:
                opargs.append(var)
        newop = SpaceOperation(op.opname, opargs, result)
        startblock = Block(inputargs)
        startblock.operations.append(newop) 
        newgraph = FunctionGraph("dummy_exc1", startblock)
        startblock.closeblock(Link([result], newgraph.returnblock))
        startblock.exits = list(startblock.exits)
        newgraph.returnblock.inputargs[0].concretetype = op.result.concretetype
        self.gen_exc_check(startblock, newgraph.returnblock)
        startblock.exits[0].exitcase = startblock.exits[0].llexitcase = False
        excblock = Block([])
        var_value = varoftype(self.lltype_of_exception_value)
        var_type = varoftype(self.lltype_of_exception_type)
        var_void = varoftype(lltype.Void)
        excblock.operations.append(SpaceOperation(
            "direct_call", [self.rpyexc_fetch_value_ptr], var_value))
        excblock.operations.append(SpaceOperation(
            "direct_call", [self.rpyexc_fetch_type_ptr], var_type))
        excblock.operations.append(SpaceOperation(
            "direct_call", [self.rpyexc_clear_ptr], var_void))
        newgraph.exceptblock.inputargs[0].concretetype = self.lltype_of_exception_type
        newgraph.exceptblock.inputargs[1].concretetype = self.lltype_of_exception_value
        excblock.closeblock(Link([var_type, var_value], newgraph.exceptblock))
        startblock.exits[True].target = excblock
        startblock.exits[True].args = []
        FUNCTYPE = lltype.FuncType(ARGTYPES, op.result.concretetype)
        fptr = Constant(lltype.functionptr(FUNCTYPE, "dummy_exc2", graph=newgraph),
                        lltype.Ptr(FUNCTYPE))
        return newgraph, SpaceOperation("direct_call", [fptr] + callargs, op.result) 

    def gen_exc_check(self, block, returnblock):
        var_exc_occured = Variable()
        var_exc_occured.concretetype = lltype.Bool
        
        block.operations.append(SpaceOperation("direct_call", [self.rpyexc_occured_ptr], var_exc_occured))
        block.exitswitch = var_exc_occured
        #exception occurred case
        l = Link([error_value(returnblock.inputargs[0].concretetype)], returnblock)
        l.prevblock  = block
        l.exitcase = l.llexitcase = True

        block.exits.append(l)

