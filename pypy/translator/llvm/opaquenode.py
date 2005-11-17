from pypy.translator.llvm.node import LLVMNode, ConstantLLVMNode
from pypy.rpython.lltypesystem import lltype

class OpaqueTypeNode(LLVMNode):

    def __init__(self, db, opaquetype): 
        assert isinstance(opaquetype, lltype.OpaqueType)
        self.db = db
        self.opaquetype = opaquetype
        self.ref = "%%RPyOpaque_%s" % (opaquetype.tag)
        
    def __str__(self):
        return "<OpaqueNode %r>" %(self.ref,)

    # ______________________________________________________________________
    # main entry points from genllvm 

    def writedatatypedecl(self, codewriter):
        codewriter.append("%s = type opaque*" % self.ref)


class OpaqueNode(ConstantLLVMNode):
    def __init__(self, db, value):
        self.db = db
        self.value = value
        self.ref = "null"
    # ______________________________________________________________________
    # main entry points from genllvm 

    def writeglobalconstants(self, codewriter):
        # XXX Dummy - not sure what what we want
        pass
