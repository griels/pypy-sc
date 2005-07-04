import py
from pypy.rpython import lltype
from pypy.translator.llvm2.log import log
from pypy.translator.llvm2.node import LLVMNode
import itertools  
log = log.structnode

count = itertools.count().next 

class ArrayTypeNode(LLVMNode):
    _issetup = False
    def __init__(self, db, array):
        self.db = db
        assert isinstance(array, lltype.Array)
        self.array = array
        c = count()
        ref_template = "%%array.%s." + str(c)
        ref_template = '"%s"' % ref_template
        arrayname = str(self.array.OF)            
        self.ref = ref_template % arrayname
        constructor_ref = "%%new.array.%s" % c
        self.constructor_ref = '"%s"' % constructor_ref
        self.constructor_decl = "%s * %s(int %%len)" % \
                                (self.ref, self.constructor_ref)

    def __str__(self):
        return "<ArrayTypeNode %r>" % self.ref
        
    def writedecl(self, codewriter): 
        # declaration for constructor
        codewriter.declare(self.constructor_decl)

    def writeimpl(self, codewriter):
        """ this function generates a LLVM function like the following:
        %array = type { int, [0 x double] }
        %array *%NewArray(int %len) {
           ;; Get the offset of the 'len' element of the array from the null
           ;; pointer.
           %size = getelementptr %array* null, int 0, uint 1, %int %len
           %usize = cast double* %size to uint
           %ptr = malloc sbyte, uint %usize
           %result = cast sbyte* %ptr to %array*
           %arraylength = getelementptr %array* %result, int 0, uint 0
           store int %len, int* %arraylength 
           ret %array* %result
        }"""
        log.writeimpl(self.ref)
        codewriter.openfunc(self.constructor_decl)
        indices = [("uint", 1), ("int", "%len")]
        codewriter.getelementptr("%size", self.ref + "*",
                                 "null", *indices)
        fromtype = self.db.repr_arg_type(self.array.OF) 
        codewriter.cast("%usize", fromtype + "*", "%size", "uint")
        codewriter.malloc("%ptr", "sbyte", "%usize", atomic=False)
        codewriter.cast("%result", "sbyte*", "%ptr", self.ref+"*")
        codewriter.getelementptr("%arraylength", self.ref+"*", "%result", ("uint", 0))
        codewriter.store("int", "%len", "%arraylength")
        codewriter.ret(self.ref+"*", "%result")
        codewriter.closefunc()

    def setup(self):
        self.db.prepare_repr_arg_type(self.array.OF)
        self._issetup = True

    # ______________________________________________________________________
    # entry points from genllvm
    #
    def writedatatypedecl(self, codewriter):
        codewriter.arraydef(self.ref, self.db.repr_arg_type(self.array.OF))

# Each ArrayNode is a global constant.  This needs to have a specific type of
# a certain type.

class ArrayNode(LLVMNode):

    _issetup = False 
    array_counter = 0

    def __init__(self, db, value):
        self.db = db
        name = "%s.%s" % (value._TYPE.OF, ArrayNode.array_counter)
        self.ref = "%%stinstance.%s" % name
        self.dataref = self.ref + ".tmp" 
        self.value = value
        ArrayNode.array_counter += 1

    def __str__(self):
        return "<ArrayNode %r>" %(self.ref,)

    def setup(self):
        T = self.value._TYPE.OF
        for item in self.value.items:
            if not isinstance(T, lltype.Primitive):
                value = getattr(self.value, name)
                # Create a dummy constant hack XXX
                c = Constant(value, T)
                self.db.prepare_arg(c)

        self._issetup = True

    def get_values(self):
        res = []

        T = self.value._TYPE.OF
        typval = self.db.repr_arg_type(self.value._TYPE.OF)
        for value in self.value.items:
            if not isinstance(T, lltype.Primitive):
                # Create a dummy constant hack XXX
                value = self.db.repr_arg(Constant(value, T))
            else:
                value = repr(value)
            res.append((typval, value))

        return ", ".join(["%s %s" % (t, v) for t, v in res])

    def writeglobalconstants(self, codewriter):
        lenitems = len(self.value.items)
        lenstr = ".%s" % lenitems
        codewriter.globalinstance(self.ref,
                                  self.db.repr_arg_type(self.value._TYPE),
                                  "null")
        #codewriter.globalinstance(self.dataref,
        #                          self.db.repr_arg_type(self.value._TYPE),
        #                          self.get_values())
