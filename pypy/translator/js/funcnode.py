import py
import sys
from pypy.objspace.flow.model import Block, Constant, Variable, Link
from pypy.objspace.flow.model import flatten, mkentrymap, traverse, last_exception
from pypy.rpython.lltypesystem import lltype
from pypy.translator.js.node import Node
from pypy.translator.js.opwriter import OpWriter
from pypy.translator.js.log import log 
log = log.funcnode


class FuncNode(Node):
    def __init__(self, db, value):
        self.db = db
        self.value = value
        self.ref   = db.namespace.uniquename(value.graph.name)
        self.graph = value.graph

    def __str__(self):
        return "<FuncNode %r>" %(self.ref,)
    
    def setup(self):
        #log("setup", self)
        def visit(node):
            if isinstance(node, Link):
                map(self.db.prepare_arg, node.args)
            elif isinstance(node, Block):
                block = node
                map(self.db.prepare_arg, block.inputargs)
                for op in block.operations:
                    map(self.db.prepare_arg, op.args)
                    self.db.prepare_arg(op.result)
                    if block.exitswitch != Constant(last_exception):
                        continue
                    for link in block.exits[1:]:
                        self.db.prepare_constant(lltype.typeOf(link.llexitcase),
                                                 link.llexitcase)
                                            
        assert self.graph, "cannot traverse"
        traverse(visit, self.graph)

    def write_implementation(self, codewriter):
        graph = self.graph
        log.writeimplemention(graph.name)
        blocks = [x for x in flatten(graph) if isinstance(x, Block)]
        self.blockindex= {}
        for i, block in enumerate(blocks):
            self.blockindex[block] = i
        codewriter.openfunc(self.getdecl(), self, blocks)
        for block in blocks:
            codewriter.openblock(self.blockindex[block])
            for name in 'startblock returnblock exceptblock'.split():
                if block is getattr(graph, name):
                    getattr(self, 'write_' + name)(codewriter, block)
                    break
            else:
                self.write_block(codewriter, block)
            codewriter.closeblock()
        codewriter.closefunc()

    # ______________________________________________________________________
    # writing helpers for entry points

    def getdecl(self):
        startblock = self.graph.startblock
        returnblock = self.graph.returnblock
        startblock_inputargs = [a for a in startblock.inputargs
                                if a.concretetype is not lltype.Void]

        inputargs = self.db.repr_arg_multi(startblock_inputargs)
        return self.ref + "(%s)" % ", ".join(inputargs)

    def write_block(self, codewriter, block):
        self.write_block_operations(codewriter, block)
        self.write_block_branches(codewriter, block)

    def write_block_branches(self, codewriter, block):
        if block.exitswitch == Constant(last_exception):
            return
        if len(block.exits) == 1:
            codewriter.br_uncond(self.blockindex[block.exits[0].target], block.exits[0])
        elif len(block.exits) == 2:
            cond = self.db.repr_arg(block.exitswitch)
            codewriter.br(cond,
                          self.blockindex[block.exits[0].target], block.exits[0],
                          self.blockindex[block.exits[1].target], block.exits[1])

    def write_block_operations(self, codewriter, block):
        opwriter = OpWriter(self.db, codewriter, self, block)
        if block.exitswitch == Constant(last_exception):
            last_op_index = len(block.operations) - 1
        else:
            last_op_index = None
        for op_index, op in enumerate(block.operations):
            if op_index == last_op_index:
                #could raise an exception and should therefor have a function
                #implementation that can be invoked by the outputed code.
                invoke_prefix = 'invoke:'
                assert not op.opname.startswith(invoke_prefix)
                op.opname = invoke_prefix + op.opname
            opwriter.write_operation(op)

    def write_startblock(self, codewriter, block):
        self.write_block_operations(codewriter, block)
        self.write_block_branches(codewriter, block)

    def write_returnblock(self, codewriter, block):
        assert len(block.inputargs) == 1
        codewriter.ret( self.db.repr_arg(block.inputargs[0]) )

    def write_exceptblock(self, codewriter, block):
        assert len(block.inputargs) == 2
        codewriter.throw( str(block.inputargs[1]) )
        codewriter.skip_closeblock()


class ExternalFuncNode(Node):
    def __init__(self, db, value):
        self.db = db
        self.value = value
        self.ref   = db.namespace.uniquename(value.graph.name)
        self.graph = value.graph
