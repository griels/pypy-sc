import py
import sys
from pypy.objspace.flow.model import Block, Constant, Variable, Link
from pypy.objspace.flow.model import flatten, mkentrymap, traverse, last_exception
from pypy.rpython import lltype
from pypy.translator.js.node import LLVMNode, ConstantLLVMNode
from pypy.translator.js.opwriter import OpWriter
#from pypy.translator.js.backendopt.removeexcmallocs import remove_exception_mallocs
#from pypy.translator.js.backendopt.mergemallocs import merge_mallocs
from pypy.translator.unsimplify import remove_double_links
from pypy.translator.js.log import log 
log = log.funcnode

class FuncTypeNode(LLVMNode):
    __slots__ = "db type_ ref".split()
    
    def __init__(self, db, type_):
        self.db = db
        assert isinstance(type_, lltype.FuncType)
        self.type_ = type_
        self.ref = self.make_ref('%functiontype', '')

    def __str__(self):
        return "<FuncTypeNode %r>" % self.ref

    def setup(self):
        self.db.prepare_type(self.type_.RESULT)
        self.db.prepare_type_multi(self.type_._trueargs())

    def writedatatypedecl(self, codewriter):
        returntype = self.db.repr_type(self.type_.RESULT)
        inputargtypes = [self.db.repr_type(a) for a in self.type_._trueargs()]
        codewriter.funcdef(self.ref, returntype, inputargtypes)

class FuncNode(ConstantLLVMNode):
    __slots__ = "db value ref graph blockindex".split()

    def __init__(self, db, value):
        self.db = db
        self.value = value
        self.ref   = self.make_ref('pypy_', value.graph.name)
        self.graph = value.graph

        self.db.genllvm.exceptionpolicy.transform(self.db.translator, self.graph)
        #remove_exception_mallocs(self.db.translator, self.graph, self.ref)
        #merge_mallocs(self.db.translator, self.graph, self.ref)

        remove_double_links(self.db.translator, self.graph)

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

    # ______________________________________________________________________
    # main entry points from genllvm 
    def writedecl(self, codewriter): 
        codewriter.declare(self.getdecl())

    def writeimpl(self, codewriter):
        graph = self.graph
        log.writeimpl(graph.name)
        nextblock = graph.startblock
        args = graph.startblock.inputargs 
        blocks = [x for x in flatten(graph) if isinstance(x, Block)]
        self.blockindex= {}
        for i, block in enumerate(blocks):
            self.blockindex[block] = i
        codewriter.openfunc(self, blocks)
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

    def writecomments(self, codewriter):
        """ write operations strings for debugging purposes. """ 
        blocks = [x for x in flatten(self.graph) if isinstance(x, Block)]
        for block in blocks:
            for op in block.operations:
                strop = str(op) + "\n\x00"
                l = len(strop)
                if strop.find("direct_call") == -1:
                    continue
                tempname = self.db.add_op2comment(l, op)
                printables = dict([(ord(i), None) for i in
                                   ("0123456789abcdefghijklmnopqrstuvwxyz" +
                                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
                                    "!#$%&()*+,-./:;<=>?@[\\]^_`{|}~ '")])
                s = []
                for c in strop:
                    if ord(c) in printables:
                        s.append(c)
                    else:
                        s.append("\\%02x" % ord(c))
                r = 'c"%s"' % "".join(s)
                typeandata = '[%s x sbyte] %s' % (l, r)
                codewriter.globalinstance(tempname, typeandata)

    def writeglobalconstants(self, codewriter):
        pass
    
    # ______________________________________________________________________
    # writing helpers for entry points

    def getdecl(self):
        startblock = self.graph.startblock
        returnblock = self.graph.returnblock
        startblock_inputargs = [a for a in startblock.inputargs
                                if a.concretetype is not lltype.Void]

        inputargs = self.db.repr_arg_multi(startblock_inputargs)
        inputargtypes = self.db.repr_arg_type_multi(startblock_inputargs)
        returntype = self.db.repr_arg_type(self.graph.returnblock.inputargs[0])
        #result = "%s %s" % (returntype, self.ref)
        #args = ["%s %s" % item for item in zip(inputargtypes, inputargs)]
        #result += "(%s)" % ", ".join(args)
        return self.ref + "(%s)" % ", ".join(inputargs)

    def write_block(self, codewriter, block):
        self.write_block_phi_nodes(codewriter, block)
        self.write_block_operations(codewriter, block)
        self.write_block_branches(codewriter, block)

    def get_phi_data(self, block):
        data = []
        entrylinks = mkentrymap(self.graph)[block]
        entrylinks = [x for x in entrylinks if x.prevblock is not None]
        inputargs = self.db.repr_arg_multi(block.inputargs)
        inputargtypes = self.db.repr_arg_type_multi(block.inputargs)
        for i, (arg, type_) in enumerate(zip(inputargs, inputargtypes)):
            names = self.db.repr_arg_multi([link.args[i] for link in entrylinks])
            blocknames = [self.blockindex[link.prevblock] for link in entrylinks]
            for i, link in enumerate(entrylinks):   #XXX refactor into a transformation
                if link.prevblock.exitswitch == Constant(last_exception) and \
                   link.prevblock.exits[0].target != block:
                    blocknames[i] += '_exception_found_branchto_' + self.blockindex[block]
            data.append( (arg, type_, names, blocknames) )
        return data

    def write_block_phi_nodes(self, codewriter, block):
        for arg, type_, names, blocknames in self.get_phi_data(block):
            if type_ != "void":
                codewriter.phi(arg, type_, names, blocknames)

    def write_block_branches(self, codewriter, block):
        #assert len(block.exits) <= 2    #more exits are possible (esp. in combination with exceptions)
        if block.exitswitch == Constant(last_exception):
            #codewriter.comment('FuncNode(ConstantLLVMNode) *last_exception* write_block_branches @%s@' % str(block.exits))
            return
        if len(block.exits) == 1:
            codewriter.br_uncond(self.blockindex[block.exits[0].target])
        elif len(block.exits) == 2:
            cond = self.db.repr_arg(block.exitswitch)
            codewriter.br(cond, self.blockindex[block.exits[0].target],
                          self.blockindex[block.exits[1].target])

    def write_block_operations(self, codewriter, block):
        opwriter = OpWriter(self.db, codewriter, self, block)
        if block.exitswitch == Constant(last_exception):
            last_op_index = len(block.operations) - 1
        else:
            last_op_index = None
        for op_index, op in enumerate(block.operations):
            if False:   # print out debug string
                codewriter.newline()
                codewriter.comment("** %s **" % str(op))
                info = self.db.get_op2comment(op)
                if info is not None:
                    lenofopstr, opstrname = info
                    codewriter.debugcomment(self.db.repr_tmpvar(),
                                            lenofopstr,
                                            opstrname)
            if op_index == last_op_index:
                #could raise an exception and should therefor have a function
                #implementation that can be invoked by the llvm-code.
                invoke_prefix = 'invoke:'
                assert not op.opname.startswith(invoke_prefix)
                op.opname = invoke_prefix + op.opname
            opwriter.write_operation(op)

    def write_startblock(self, codewriter, block):
        self.write_block_operations(codewriter, block)
        self.write_block_branches(codewriter, block)

    def write_returnblock(self, codewriter, block):
        assert len(block.inputargs) == 1
        self.write_block_phi_nodes(codewriter, block)
        inputargtype = self.db.repr_arg_type(block.inputargs[0])
        inputarg = self.db.repr_arg(block.inputargs[0])
        codewriter.ret(inputargtype, inputarg)

    def write_exceptblock(self, codewriter, block):
        self.db.genllvm.exceptionpolicy.write_exceptblock(self, codewriter, block)
