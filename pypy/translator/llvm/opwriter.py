from pypy.objspace.flow.model import Constant, Variable
from pypy.rpython.lltypesystem import lltype
from pypy.translator.llvm.log import log 
log = log.opwriter

def repr_if_variable(db, arg):
    if isinstance(arg, Variable):
        return db.repr_arg(arg)

class OpWriter(object):
    binary_operations = {'int_mul': 'mul',
                         'int_add': 'add',
                         'int_sub': 'sub',
                         'int_floordiv': 'div',
                         'int_mod': 'rem',
                         'int_and': 'and',
                         'int_or': 'or',
                         'int_xor': 'xor',
                         'int_lt': 'setlt',
                         'int_le': 'setle',
                         'int_eq': 'seteq',
                         'int_ne': 'setne',
                         'int_ge': 'setge',
                         'int_gt': 'setgt',

                         'llong_mul': 'mul',
                         'llong_add': 'add',
                         'llong_sub': 'sub',
                         'llong_floordiv': 'div',
                         'llong_mod': 'rem',
                         'llong_and': 'and',
                         'llong_or': 'or',
                         'llong_xor': 'xor',
                         'llong_lt': 'setlt',
                         'llong_le': 'setle',
                         'llong_eq': 'seteq',
                         'llong_ne': 'setne',
                         'llong_ge': 'setge',
                         'llong_gt': 'setgt',

                         'uint_mul': 'mul',
                         'uint_add': 'add',
                         'uint_sub': 'sub',
                         'uint_floordiv': 'div',
                         'uint_mod': 'rem',
                         'uint_and': 'and',
                         'uint_or': 'or',
                         'uint_xor': 'xor',
                         'uint_lt': 'setlt',
                         'uint_le': 'setle',
                         'uint_eq': 'seteq',
                         'uint_ne': 'setne',
                         'uint_ge': 'setge',
                         'uint_gt': 'setgt',

                         'unichar_lt': 'setlt',
                         'unichar_le': 'setle',
                         'unichar_eq': 'seteq',
                         'unichar_ne': 'setne',
                         'unichar_ge': 'setge',
                         'unichar_gt': 'setgt',

                         'float_mul': 'mul',
                         'float_add': 'add',
                         'float_sub': 'sub',
                         'float_truediv': 'div',
                         'float_lt': 'setlt',
                         'float_le': 'setle',
                         'float_eq': 'seteq',
                         'float_ne': 'setne',
                         'float_ge': 'setge',
                         'float_gt': 'setgt',

                         'ptr_eq': 'seteq',
                         'ptr_ne': 'setne',
                         }

    shift_operations  = {'int_lshift': 'shl',
                         'int_rshift': 'shr',

                         'uint_lshift': 'shl',
                         'uint_rshift': 'shr',
                         
                         'llong_lshift': 'shl',
                         'llong_rshift': 'shr',
                         }


    char_operations  = {'char_lt': 'setlt',
                        'char_le': 'setle',
                        'char_eq': 'seteq',
                        'char_ne': 'setne',
                        'char_ge': 'setge',
                        'char_gt': 'setgt'}

    def __init__(self, db, codewriter, node, block):
        self.db = db
        self.codewriter = codewriter
        self.node = node
        self.block = block

    def write_operation(self, op):
        invoke = op.opname.startswith('invoke:')
        if invoke:
            self.invoke(op)
        else:
            if op.opname in self.binary_operations:
                self.binaryop(op)
            elif op.opname in self.shift_operations:
                self.shiftop(op)
            elif op.opname in self.char_operations:
                self.char_binaryop(op)
            elif op.opname.startswith('cast_') or op.opname.startswith('truncate_'):
                if op.opname == 'cast_char_to_int':
                    self.cast_char_to_int(op)
                else:
                    self.cast_primitive(op)
            else:
                meth = getattr(self, op.opname, None)
                if not meth:
                    raise Exception, "operation %s not found" % op.opname
                meth(op)    

    def _generic_pow(self, op, onestr): 
        mult_type = self.db.repr_arg_type(op.args[0])
        mult_val = self.db.repr_arg(op.args[0])
        last_val = mult_val
        try:
            value = "NO VALUE"
            value = op.args[1].value
            operand = int(value)
        except Exception, exc:
            msg = 'XXX: Error: _generic_pow: Variable '\
                  '%s - failed to convert to int %s' % (value, str(exc))
            self.codewriter.comment(msg)
            raise Exception(msg)
        
        if operand < 1:
            res_val = onestr
        else:
            res_val = mult_val
            for ii in range(operand - 1):
                res_val = self.db.repr_tmpvar()
                self.codewriter.binaryop("mul", 
                                         res_val,
                                         mult_type,
                                         last_val,
                                         mult_val)
                last_val = res_val
        targetvar = self.db.repr_arg(op.result)
        self.codewriter.cast(targetvar, mult_type, res_val, mult_type)        

    def _skipped(self, op):
        self.codewriter.comment('***Skipping operation %s()' % (op.opname,))
    keepalive = _skipped

    def int_abs(self, op):
        functionref = '%pypyop_' + op.opname
        self.codewriter.call(self.db.repr_arg(op.result),
                             self.db.repr_arg_type(op.result),
                             functionref,
                             [self.db.repr_arg(op.args[0])],
                             [self.db.repr_arg_type(op.args[0])])
    float_abs = int_abs
    llong_abs = int_abs

    def int_pow(self, op):
        self._generic_pow(op, "1") 
    uint_pow = int_pow
    
    def float_pow(self, op):
        self._generic_pow(op, "1.0") 

    def _generic_neg(self, op, zerostr): 
        self.codewriter.binaryop("sub", 
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 zerostr, 
                                 self.db.repr_arg(op.args[0]),
                                 )
    def int_neg(self, op):
        self._generic_neg(op, "0")

    #this is really generated, don't know why
    # XXX rxe: Surely that cant be right?
    uint_neg = int_neg

    def float_neg(self, op):
        self._generic_neg(op, "0.0") 

    def bool_not(self, op):
        self.codewriter.binaryop("xor",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]), 
                                 "true")

    def int_invert(self, op):
        self.codewriter.binaryop("xor",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]), 
                                 -1)

    def uint_invert(self, op):
        self.codewriter.binaryop("xor",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]), 
                                 str((1L<<32) - 1))

    def binaryop(self, op):
        name = self.binary_operations[op.opname]
        assert len(op.args) == 2
        self.codewriter.binaryop(name,
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]),
                                 self.db.repr_arg(op.args[1]))

    def char_binaryop(self, op):
        name = self.char_operations[op.opname]
        assert len(op.args) == 2
        res = self.db.repr_arg(op.result)
        c1 = self.db.repr_tmpvar()
        c2 = self.db.repr_tmpvar()
        self.codewriter.cast(c1, "sbyte", self.db.repr_arg(op.args[0]), "ubyte")
        self.codewriter.cast(c2, "sbyte", self.db.repr_arg(op.args[1]), "ubyte")
        self.codewriter.binaryop(name, res, "ubyte", c1, c2)


    def shiftop(self, op):
        name = self.shift_operations[op.opname]
        assert len(op.args) == 2
        if isinstance(op.args[1], Constant):
            tmpvar = self.db.repr_arg(op.args[1])
        else:
            tmpvar = self.db.repr_tmpvar()
            self.codewriter.cast(tmpvar, self.db.repr_arg_type(op.args[1]), self.db.repr_arg(op.args[1]), 'ubyte')
        self.codewriter.shiftop(name,
                                self.db.repr_arg(op.result),
                                self.db.repr_arg_type(op.args[0]),
                                self.db.repr_arg(op.args[0]),
                                tmpvar)

    def cast_char_to_int(self, op):
        " works for all casts "
        assert len(op.args) == 1
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        fromvar = self.db.repr_arg(op.args[0])
        fromtype = self.db.repr_arg_type(op.args[0])
        intermediate = self.db.repr_tmpvar()
        self.codewriter.cast(intermediate, fromtype, fromvar, "ubyte")
        self.codewriter.cast(targetvar, "ubyte", intermediate, targettype)

    def cast_primitive(self, op):
        " works for all casts "
        assert len(op.args) == 1
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        fromvar = self.db.repr_arg(op.args[0])
        fromtype = self.db.repr_arg_type(op.args[0])
        self.codewriter.cast(targetvar, fromtype, fromvar, targettype)
    same_as = cast_primitive

    def int_is_true(self, op):
        self.codewriter.binaryop("setne",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]),
                                 "0")
    uint_is_true = int_is_true
    llong_is_true = int_is_true

    def float_is_true(self, op):
        self.codewriter.binaryop("setne",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]),
                                 "0.0")

    def ptr_nonzero(self, op):
        self.codewriter.binaryop("setne",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]),
                                 "null")

    def ptr_iszero(self, op):
        self.codewriter.binaryop("seteq",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg_type(op.args[0]),
                                 self.db.repr_arg(op.args[0]),
                                 "null")

    def direct_call(self, op):
        op_args = [arg for arg in op.args
                   if arg.concretetype is not lltype.Void]
        assert len(op_args) >= 1
        targetvar = self.db.repr_arg(op.result)
        returntype = self.db.repr_arg_type(op.result)
        functionref = self.db.repr_arg(op_args[0])
        argrefs = self.db.repr_arg_multi(op_args[1:])
        argtypes = self.db.repr_arg_type_multi(op_args[1:])
        if self.db.is_function_ptr(op.result):
            returntype = "%s (%s)*" % (returntype, ", ".join(argtypes))
        self.codewriter.call(targetvar, returntype,
                             functionref, argrefs, argtypes)

    def malloc_exception(self, op): 
        arg_type = op.args[0].value
        targetvar = self.db.repr_arg(op.result) 
        type_ = self.db.repr_type(arg_type)
        tmpvar1 = self.db.repr_tmpvar()
        tmpvar2 = self.db.repr_tmpvar()
        tmpvar3 = self.db.repr_tmpvar()

        ptr_type = type_ + '*'
        self.codewriter.raw_getelementptr(tmpvar1, ptr_type, "null", ("int", 1))
        self.codewriter.cast(tmpvar2, ptr_type, tmpvar1, 'uint')
        self.codewriter.call(tmpvar3, 'sbyte*', '%malloc_exception', [tmpvar2], ['uint'])
        self.codewriter.cast(targetvar, 'sbyte*', tmpvar3, type_+'*')

    def malloc(self, op): 
        arg_type = op.args[0].value
        targetvar = self.db.repr_arg(op.result) 
        type_ = self.db.repr_type(arg_type)
        gp = self.db.gcpolicy
        gp.malloc(self.codewriter, targetvar, type_,
                  atomic=arg_type._is_atomic())

    def malloc_varsize(self, op):
        arg_type = op.args[0].value
        if isinstance(arg_type, lltype.Array) and arg_type.OF is lltype.Void:
            # This is a backend decision to NOT represent a void array with
            # anything and save space - therefore not varsized anymore
            self.malloc(op)
            return
        
        targetvar = self.db.repr_arg(op.result)
        type_ = self.db.repr_type(arg_type) + "*"
        type_cons = self.db.repr_constructor(arg_type)
        argrefs = self.db.repr_arg_multi(op.args[1:])
        argtypes = self.db.repr_arg_type_multi(op.args[1:])
        self.codewriter.call(targetvar, type_, type_cons, argrefs, argtypes)

    def _getindexhelper(self, name, struct):
        assert name in list(struct._names)

        fieldnames = struct._names_without_voids()
        try:
            index = fieldnames.index(name)
        except ValueError:
            index = -1
        return index

    def getfield(self, op): 
        tmpvar = self.db.repr_tmpvar()
        struct, structtype = self.db.repr_argwithtype(op.args[0])
        index = self._getindexhelper(op.args[1].value, op.args[0].concretetype.TO)
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        if targettype != "void":
            assert index != -1
            self.codewriter.getelementptr(tmpvar, structtype, struct,
                                          ("uint", index))        
            self.codewriter.load(targetvar, targettype, tmpvar)
        else:
            self._skipped(op)
 
    def getsubstruct(self, op): 
        struct, structtype = self.db.repr_argwithtype(op.args[0])
        index = self._getindexhelper(op.args[1].value, op.args[0].concretetype.TO)
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        assert targettype != "void"
        self.codewriter.getelementptr(targetvar, structtype, 
                                      struct, ("uint", index))        
         
    def setfield(self, op): 
        tmpvar = self.db.repr_tmpvar()
        struct, structtype = self.db.repr_argwithtype(op.args[0])
        index = self._getindexhelper(op.args[1].value, op.args[0].concretetype.TO)
        valuevar, valuetype = self.db.repr_argwithtype(op.args[2])
        if valuetype != "void": 
            #Structure types require uint constants!
            #see: http://llvm.cs.uiuc.edu/docs/LangRef.html#i_getelementptr
            self.codewriter.getelementptr(tmpvar, structtype, struct,
                                          ("uint", index))
            self.codewriter.store(valuetype, valuevar, tmpvar) 
        else:
            self._skipped(op)
            
    def getarrayitem(self, op):        
        array, arraytype = self.db.repr_argwithtype(op.args[0])
        index = self.db.repr_arg(op.args[1])
        indextype = self.db.repr_arg_type(op.args[1])
        tmpvar = self.db.repr_tmpvar()
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        if targettype != "void":
            self.codewriter.getelementptr(tmpvar, arraytype, array,
                                          ("uint", 1), (indextype, index))
            self.codewriter.load(targetvar, targettype, tmpvar)
        else:
            self._skipped(op)

    def getarraysubstruct(self, op):        
        array, arraytype = self.db.repr_argwithtype(op.args[0])
        index = self.db.repr_arg(op.args[1])
        indextype = self.db.repr_arg_type(op.args[1])
        targetvar = self.db.repr_arg(op.result)
        self.codewriter.getelementptr(targetvar, arraytype, array,
                                      ("uint", 1), (indextype, index))

    def setarrayitem(self, op):
        array, arraytype = self.db.repr_argwithtype(op.args[0])
        index = self.db.repr_arg(op.args[1])
        indextype = self.db.repr_arg_type(op.args[1])

        tmpvar = self.db.repr_tmpvar()

        valuevar = self.db.repr_arg(op.args[2]) 
        valuetype = self.db.repr_arg_type(op.args[2])
        if valuetype != "void":
            self.codewriter.getelementptr(tmpvar, arraytype, array,
                                      ("uint", 1), (indextype, index))
            self.codewriter.store(valuetype, valuevar, tmpvar) 
        else:
            self._skipped(op)

    def getarraysize(self, op):
        array, arraytype = self.db.repr_argwithtype(op.args[0])
        tmpvar = self.db.repr_tmpvar()
        self.codewriter.getelementptr(tmpvar, arraytype, array, ("uint", 0))
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        self.codewriter.load(targetvar, targettype, tmpvar)

    def adr_delta(self, op):
        tmp = self.db.repr_tmpvar
        addr1, addr2 = tmp(), tmp()
        arg1, argtype1 = self.db.repr_argwithtype(op.args[0])
        arg2, argtype2 = self.db.repr_argwithtype(op.args[1])
        self.codewriter.cast(addr1, argtype1, arg1, "int")
        self.codewriter.cast(addr2, argtype2, arg2, "int")
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        self.codewriter.binaryop("sub",
                                 targetvar, targettype,
                                 addr1, addr2,)

    def _op_adr_generic(self, op, llvm_op):
        tmp = self.db.repr_tmpvar
        addr, res = tmp(), tmp()
        arg, argtype = self.db.repr_argwithtype(op.args[0])
        self.codewriter.cast(addr, argtype, arg, "int")
        arg2, argtype2 = self.db.repr_argwithtype(op.args[1])        
        self.codewriter.binaryop(llvm_op,
                                 res, "int",
                                 addr, arg2)
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        self.codewriter.cast(targetvar, "int", res, targettype)

    def adr_add(self, op):
        self._op_adr_generic(op, "add")

    def adr_sub(self, op):
        self._op_adr_generic(op, "sub")

    def _op_adr_comparison_generic(self, op, llvm_op):
        tmp = self.db.repr_tmpvar
        addr1, addr2 = tmp(), tmp()
        arg1, argtype1 = self.db.repr_argwithtype(op.args[0])
        arg2, argtype2 = self.db.repr_argwithtype(op.args[1])
        self.codewriter.cast(addr1, argtype1, arg1, "int")
        self.codewriter.cast(addr2, argtype2, arg2, "int")
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        assert targettype == "bool"
        self.codewriter.binaryop(llvm_op,
                                 targetvar, "int",
                                 addr1, addr2)

    def adr_eq(self, op):
        self._op_adr_comparison_generic(op, "seteq")

    def adr_ne(self, op):
        self._op_adr_comparison_generic(op, "setne")

    def adr_le(self, op):
        self._op_adr_comparison_generic(op, "setle")

    def adr_gt(self, op):
        self._op_adr_comparison_generic(op, "setgt")

    def adr_lt(self, op):
        self._op_adr_comparison_generic(op, "setlt")

    def adr_ge(self, op):
        self._op_adr_comparison_generic(op, "setge")

    def raw_malloc(self, op):
        # XXX ignore raise as not last op
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        argrefs = self.db.repr_arg_multi(op.args)
        argtypes = self.db.repr_arg_type_multi(op.args)
        self.codewriter.call(targetvar, targettype, "%raw_malloc",
                             argrefs, argtypes)
    def raw_free(self, op):
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        argrefs = self.db.repr_arg_multi(op.args)
        argtypes = self.db.repr_arg_type_multi(op.args)
        self.codewriter.call(targetvar, targettype, "%raw_free",
                             argrefs, argtypes)

    def raw_memcopy(self, op):
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)
        argrefs = self.db.repr_arg_multi(op.args)
        argtypes = self.db.repr_arg_type_multi(op.args)
        self.codewriter.call(targetvar, targettype, "%raw_memcopy",
                             argrefs, argtypes)

    def raw_store(self, op):
        tmp = self.db.repr_tmpvar

        (arg_addr, arg_dummy,
         arg_incr, arg_value) = self.db.repr_arg_multi(op.args)
        (argtype_addr, argtype_dummy,
         argtype_incr, argtype_value) = self.db.repr_arg_type_multi(op.args)

        cast_addr = tmp()
        addr_type = argtype_value + "*"

        # cast to the correct type before arithmetic/storing
        self.codewriter.cast(cast_addr, argtype_addr, arg_addr, addr_type)

        # pointer arithmetic
        if arg_incr:
            incr_addr = tmp()
            self.codewriter.raw_getelementptr(incr_addr,
                                              addr_type,
                                              cast_addr,
                                              ("int", arg_incr))
            cast_addr = incr_addr
        self.codewriter.store(argtype_value, arg_value, cast_addr)

        
    def raw_load(self, op):
        tmp = self.db.repr_tmpvar

        arg_addr, arg_dummy, arg_incr = self.db.repr_arg_multi(op.args)
        argtype_addr, argtype_dummy, argtype_incr = \
                                      self.db.repr_arg_type_multi(op.args)
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_arg_type(op.result)

        cast_addr = tmp()
        addr_type = targettype + "*"

        # cast to the correct type before arithmetic/loading
        self.codewriter.cast(cast_addr, argtype_addr, arg_addr, addr_type)
        # pointer arithmetic
        if arg_incr:
            incr_addr = tmp()
            self.codewriter.raw_getelementptr(incr_addr,
                                              addr_type,
                                              cast_addr,
                                              ("int", arg_incr))
            cast_addr = incr_addr

        self.codewriter.load(targetvar, targettype, cast_addr) 
        
    # ______________________________________________________________________
    # exception specific

    def last_exception_type_ptr(self, op):
        e = self.db.translator.rtyper.getexceptiondata()
        self.codewriter.load('%' + str(op.result),
                             self.db.repr_type(e.lltype_of_exception_type),
                             '%last_exception_type')

    def invoke(self, op):
        ep = self.db.exceptionpolicy

        op_args = [arg for arg in op.args
                   if arg.concretetype is not lltype.Void]

        if op.opname == 'invoke:direct_call':
            functionref = self.db.repr_arg(op_args[0])

        else:
            # operation - provided by genexterns 
            opname = op.opname.split(':', 1)[1]
            op_args = ['%pypyop_' + opname] + op_args
            functionref = op_args[0]
        
        assert len(op_args) >= 1
        
        # at least one label and one exception label
        assert len(self.block.exits) >= 2   

        link = self.block.exits[0]
        assert link.exitcase is None

        targetvar   = self.db.repr_arg(op.result)
        returntype  = self.db.repr_arg_type(op.result)
        argrefs     = self.db.repr_arg_multi(op_args[1:])
        argtypes    = self.db.repr_arg_type_multi(op_args[1:])

        none_label  = self.node.block_to_name[link.target]
        block_label = self.node.block_to_name[self.block]
        exc_label   = block_label + '_exception_handling'
        
        # use longhand form
        if self.db.is_function_ptr(op.result):
            returntype = "%s (%s)*" % (returntype, ", ".join(argtypes))

        ep.invoke(self.codewriter, targetvar, returntype, functionref,
                  argrefs, argtypes, none_label, exc_label)

        # write exception handling blocks
        
        e = self.db.translator.rtyper.getexceptiondata()
        ll_exception_match = self.db.repr_value(e.fn_exception_match._obj)        
        lltype_of_exception_type = self.db.repr_type(e.lltype_of_exception_type)
        lltype_of_exception_value = self.db.repr_type(e.lltype_of_exception_value)
        
        # start with the exception handling block
        # * load the last exception type
        # * check it with call to ll_exception_match()
        # * branch to to correct block?
        
        self.codewriter.label(exc_label)

        catch_all = False
        found_blocks_info = []
        last_exception_type = None

        # XXX tmp - debugging info 

        # block_label = "block28"
        # exc_label = "block28_exception_handling"
        # ll_exception_match = function for catching exception
        # lltype_of_exception_type, lltype_of_exception_value = generic
        # catch_all = ???
        # found_blocks_info = list of found block data to write those blocks 
        # last_exception_type = Load exception pointer once for handle and not found blocks

        # link = iteration thru rest of links in block 
        # etype = node for exception
        # current_exception_type = repr for node etype
        # target = label of the destination block 
        # exc_found_label = label of intermediate exc found block
        # last_exc_type_var = ????
        # last_exc_value_var = ???
        
        for link in self.block.exits[1:]:
            assert issubclass(link.exitcase, Exception)

            # information for found blocks
            target = self.node.block_to_name[link.target]
            exc_found_label = block_label + '_exception_found_branchto_' + target
            link_exc_type = repr_if_variable(self.db, link.last_exception)
            link_exc_value = repr_if_variable(self.db, link.last_exc_value)
            found_blocks_info.append((exc_found_label, target,
                                      link_exc_type, link_exc_value))

            # XXX fix database to handle this case
            etype = self.db.obj2node[link.llexitcase._obj]
            current_exception_type = etype.get_ref()
            not_this_exception_label = block_label + '_not_exception_' + etype.ref[1:]

            # catch specific exception (class) type

            # load pointer only once
            if not last_exception_type:
                last_exception_type = self.db.repr_tmpvar()
                self.codewriter.load(last_exception_type,
                                     lltype_of_exception_type,
                                     '%last_exception_type')
                self.codewriter.newline()

            ll_issubclass_cond = self.db.repr_tmpvar()

            self.codewriter.call(ll_issubclass_cond,
                                 'bool',
                                 ll_exception_match,
                                 [last_exception_type, current_exception_type],
                                 [lltype_of_exception_type, lltype_of_exception_type])

            self.codewriter.br(ll_issubclass_cond,
                               not_this_exception_label,
                               exc_found_label)

            self.codewriter.label(not_this_exception_label)

        if not catch_all:
            ep.reraise(self.node, self.codewriter)

        ep.fetch_exceptions(self.codewriter,
                            found_blocks_info,
                            lltype_of_exception_type,
                            lltype_of_exception_value)
