import py
from pypy.objspace.flow.model import Constant
from pypy.rpython.lltypesystem import lltype
from pypy.translator.js.log import log 
log = log.opwriter

class OpWriter(object):
    binary_operations = {'int_mul': '*',
                         'int_add': '+',
                         'int_sub': '-',
                         'int_floordiv': '/',
                         'int_mod': '%',
                         'int_and': '&',
                         'int_or': '|',
                         'int_xor': '^',
                         'int_lshift': '<<',
                         'int_rshift': '>>',
                         'int_lt': '<',
                         'int_le': '<=',
                         'int_eq': '==',
                         'int_ne': '!=',
                         'int_ge': '>=',
                         'int_gt': '>',

                         'uint_mul': '*',
                         'uint_add': '+',
                         'uint_sub': '-',
                         'uint_floordiv': '/',
                         'uint_mod': '%',
                         'uint_and': '&',
                         'uint_or': '|',
                         'uint_xor': '^',
                         'uint_lshift': '<<',
                         'uint_rshift': '>>',
                         'uint_lt': '<',
                         'uint_le': '<=',
                         'uint_eq': '==',
                         'uint_ne': '!=',
                         'uint_ge': '>=',
                         'uint_gt': '>',

                         'unichar_lt': '<',
                         'unichar_le': '<=',
                         'unichar_eq': '==',
                         'unichar_ne': '!=',
                         'unichar_ge': '>=',
                         'unichar_gt': '>',

                         'float_mul': '*',
                         'float_add': '+',
                         'float_sub': '-',
                         'float_truediv': '/',
                         'float_mod': '%',
                         'float_lt': '<',
                         'float_le': '<=',
                         'float_eq': '==',
                         'float_ne': '!=',
                         'float_ge': '>=',
                         'float_gt': '>',

                         'ptr_eq': '==',
                         'ptr_ne': '!=',
                         }

    char_operations  = {'char_lt': '<',
                        'char_le': '<=',
                        'char_eq': '==',
                        'char_ne': '!=',
                        'char_ge': '>=',
                        'char_gt': '>'}

    def __init__(self, db, codewriter, node, block):
        self.db = db
        self.codewriter = codewriter
        self.node = node
        self.block = block

    def write_operation(self, op):
        #log(str(op))
        #self.codewriter.comment(str(op))

        if op.opname.startswith('llong_'):
            op.opname = 'int_' + op.opname[6:]
        elif op.opname.startswith('ullong_'):
            op.opname = 'uint_' + op.opname[7:]

        invoke = op.opname.startswith('invoke:')
        if invoke:
            self.invoke(op)
        else:
            if op.opname in self.binary_operations:
                self.binaryop(op)
            elif op.opname in self.char_operations:
                self.char_binaryop(op)
            elif op.opname.startswith('cast_'):
                if op.opname == 'cast_char_to_int':
                    self.cast_char_to_int(op)
                else:
                    self.cast_primitive(op)
            else:
                meth = getattr(self, op.opname, None)
                if not meth:
                    raise Exception, "operation %s not found" % op.opname
                    return
                meth(op)

    def _generic_pow(self, op, onestr): 
        targetvar = self.db.repr_arg(op.result)
        mult_val  = self.db.repr_arg(op.args[0])
        value     = op.args[1].value
        self.codewriter.append('%s = Math.pow(%s, %s)' % (targetvar, mult_val, value))

    def _skipped(self, op):
            self.codewriter.comment('Skipping operation %s()' % op.opname)
            pass
    keepalive = _skipped 
    
    def int_abs(self, op):
        #ExternalFuncNode.used_external_functions[functionref] = True
        self.codewriter.call(self.db.repr_arg(op.result),
                             'Math.abs',
                             [self.db.repr_arg(op.args[0])])
    float_abs = int_abs

    def int_pow(self, op):
        self._generic_pow(op, "1") 
    uint_pow = int_pow
    
    def float_pow(self, op):
        self._generic_pow(op, "1.0") 

    def _generic_neg(self, op): 
        self.codewriter.neg(self.db.repr_arg(op.result),
                            self.db.repr_arg(op.args[0]))
    int_neg   = _generic_neg
    uint_neg  = _generic_neg
    float_neg = _generic_neg

    def bool_not(self, op):
        self.codewriter.binaryop('^',
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]), 
                                 "true")

    def int_invert(self, op):
        self.codewriter.binaryop('^',
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]), 
                                 -1)

    def uint_invert(self, op):
        self.codewriter.binaryop('^',
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]), 
                                 str((1L<<32) - 1))

    def binaryop(self, op):
        name = self.binary_operations[op.opname]
        assert len(op.args) == 2
        targetvar = self.db.repr_arg(op.result)
        self.codewriter.binaryop(name,
                                 targetvar,
                                 self.db.repr_arg(op.args[0]),
                                 self.db.repr_arg(op.args[1]))
        if op.opname.endswith('int_floordiv'):
            self.codewriter.append('%s = Math.floor(%s)' % (targetvar, targetvar))

    def char_binaryop(self, op):
        name = self.char_operations[op.opname]
        assert len(op.args) == 2
        res = self.db.repr_arg(op.result)
        c1 = self.db.repr_arg(op.args[0])
        c2 = self.db.repr_arg(op.args[1])
        self.codewriter.binaryop(name, res, c1, c2)

    def cast_char_to_int(self, op):
        " works for all casts "
        assert len(op.args) == 1
        targetvar  = self.db.repr_arg(op.result)
        targettype = self.db.repr_concretetype(op.result.concretetype)
        fromvar  = self.db.repr_arg(op.args[0])
        fromtype = self.db.repr_concretetype(op.args[0].concretetype)
        if True:
            intermediate = self.db.repr_arg(op.args[0])
        else:
            intermediate = self.db.repr_tmpvar()
        self.codewriter.cast(intermediate, fromtype, fromvar, "ubyte")
        self.codewriter.cast(targetvar, "ubyte", intermediate, targettype)

    def cast_primitive(self, op):
        " works for all casts "
        assert len(op.args) == 1
        targetvar = self.db.repr_arg(op.result)
        targettype = self.db.repr_concretetype(op.result.concretetype)
        fromvar = self.db.repr_arg(op.args[0])
        fromtype = self.db.repr_concretetype(op.args[0].concretetype)
        if op.opname not in ('cast_pointer',):
            self.codewriter.comment('next line=%s, from %s to %s' % (op.opname, fromtype, targettype))
        self.codewriter.cast(targetvar, fromtype, fromvar, targettype)
    same_as = cast_primitive

    def int_is_true(self, op):
        self.codewriter.binaryop("!=",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]),
                                 "0")
    uint_is_true = int_is_true

    def float_is_true(self, op):
        self.codewriter.binaryop("!=",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]),
                                 "0.0")

    def ptr_nonzero(self, op):
        self.codewriter.binaryop("!=",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]),
                                 "null")

    def ptr_iszero(self, op):
        self.codewriter.binaryop("==",
                                 self.db.repr_arg(op.result),
                                 self.db.repr_arg(op.args[0]),
                                 "null")

    def direct_call(self, op):
        op_args = [arg for arg in op.args
                   if arg.concretetype is not lltype.Void]
        assert len(op_args) >= 1
        targetvar = self.db.repr_arg(op.result)
        functionref = self.db.repr_arg(op_args[0])
        argrefs = self.db.repr_arg_multi(op_args[1:])
        self.codewriter.call(targetvar, functionref, argrefs)
    indirect_call = direct_call

    def invoke(self, op):
        op_args = [arg for arg in op.args
                   if arg.concretetype is not lltype.Void]

        if op.opname in ('invoke:direct_call', 'invoke:indirect_call'):
            functionref = self.db.repr_arg(op_args[0])
        else:   #operation
            opname = op.opname.split(':',1)[1]
            op_args = [opname] + op_args
            functionref = op_args[0]
            self.codewriter.comment("XXX: Error: exception raising operation %s" % functionref)

        assert len(op_args) >= 1
        # at least one label and one exception label
        assert len(self.block.exits) >= 2   

        link = self.block.exits[0]
        assert link.exitcase is None

        targetvar  = self.db.repr_arg(op.result)
        argrefs    = self.db.repr_arg_multi(op_args[1:])
        none_label = self.node.blockindex[link.target]
        no_exception = (none_label, link)

        exceptions = []
        for exit in self.block.exits[1:]:
            assert issubclass(exit.exitcase, Exception)
            exception_match  = self.db.translator.rtyper.getexceptiondata().fn_exception_match._obj._name
            exception_node   = self.db.obj2node[exit.llexitcase._obj] #.ref #get _ref()
            exception_target = self.node.blockindex[exit.target]
            exception        = (exception_match, exception_node, exception_target, exit)
            exceptions.append(exception)

        self.codewriter.call(targetvar, functionref, argrefs, no_exception, exceptions)

    def _type_repr(self, t):
        if t is lltype.Void:
            return 'undefined'
        elif t is lltype.Bool:
            return 'false'
        elif t is lltype.Char:
            return 'String.fromCharCode(0)'
        elif t is lltype.Float:
            return '0.0'
        elif isinstance(t, lltype.Array):
            if t.OF is lltype.Char:
                return '""'
            else:
                return '[%s]' % self._type_repr(t.OF)
        elif isinstance(t, lltype.Struct):
            return '{%s}' % self._structtype_repr(t)
        else:   #XXX 'null' for Ptr's? or recurse into Ptr.TO?
            return '0'

    def _structtype_repr(self, arg_type):
        type_ = ''
        for n, name in enumerate(arg_type._names_without_voids()):
            if n > 0:
                type_ += ', '
            type_ += self.db.namespace.ensure_non_reserved(name) + ':' + self._type_repr(arg_type._flds[name])
        return type_

    def malloc(self, op): 
        arg_type  = op.args[0].value
        targetvar = self.db.repr_arg(op.result)
        if isinstance(arg_type, lltype.Array):
            assert len(op.args) == 2
            n_items = self.db.repr_arg(op.args[1])
            r       = self._type_repr(arg_type.OF)
            self.codewriter.malloc(targetvar, '[];')
            if n_items != '0':
                self.codewriter.append('for (var t=%s-1;t >= 0;t--) %s[t] = %s' % (n_items, targetvar, r))
        else:
            assert isinstance(arg_type, lltype.Struct)
            #XXX op.args is not 1 in case of a varsize struct (ll_join* does this with a rpystring).
            #    At the moment the varsize array at the end of the struct (if I understand correctly)
            #    gets a length of zero instead of length op.args[1]
            #    This could be a problem in cases like test_typed.py -k test_str_join , but javascript
            #    mostly does the right array resizing later on when we need it!
            #assert len(op.args) == 1
            self.codewriter.malloc(targetvar, '{%s};' % self._structtype_repr(arg_type))
    malloc_varsize = malloc

    def _getindexhelper(self, name, struct):
        assert name in list(struct._names)

        fieldnames = struct._names_without_voids()
        try:
            index = fieldnames.index(name)
        except ValueError:
            index = -1
        return index

    def getfield(self, op): 
        struct = self.db.repr_arg(op.args[0])
        targetvar = self.db.repr_arg(op.result)
        targettype = 'undefined' #self.db.repr_arg_type(op.result)
        if targettype != "void" and \
            not targetvar.startswith('etype_'):
            f = self.db.namespace.ensure_non_reserved(op.args[1].value)
            self.codewriter.append('%s = %s.%s' % (targetvar, struct, f)) #XXX move to codewriter
        else:
            self.codewriter.comment('getfield')
            self._skipped(op)
 
    def getsubstruct(self, op): 
        struct = self.db.repr_arg(op.args[0])
        #index = self._getindexhelper(op.args[1].value, op.args[0].concretetype.TO)
        targetvar = self.db.repr_arg(op.result)
        #targettype = self.db.repr_arg_type(op.result)
        #assert targettype != "void"
        f = self.db.namespace.ensure_non_reserved(op.args[1].value)
        self.codewriter.append('%s = %s.%s' % (targetvar, struct, f)) #XXX move to codewriter
        #self.codewriter.getelementptr(targetvar, structtype, struct, ("uint", index))        
         
    def setfield(self, op): 
        struct   = self.db.repr_arg(op.args[0])
        valuevar = self.db.repr_arg(op.args[2])
        valuetype = 'undefined'  #XXX how to get to this when no longer keep track of type
        if valuetype != "void":
            f = self.db.namespace.ensure_non_reserved(op.args[1].value)
            self.codewriter.append('%s.%s = %s' % (struct, f, valuevar)) #XXX move to codewriter
        else:
            self.codewriter.comment('setfield')
            self._skipped(op)

    def getarrayitem(self, op):        
        array = self.db.repr_arg(op.args[0])
        index = self.db.repr_arg(op.args[1])
        #indextype = self.db.repr_arg_type(op.args[1])
        targetvar = self.db.repr_arg(op.result)
        targettype = 'undefined' #self.db.repr_arg_type(op.result)
        if targettype != "void":
            #tmpvar = self.db.repr_tmpvar()
            #self.codewriter.getelementptr(tmpvar, arraytype, array,
            #                              ("uint", 1), (indextype, index))
            #self.codewriter.load(targetvar, targettype, tmpvar)
            self.codewriter.load(targetvar, array, (index,))
        else:
            self.codewriter.comment('getarrayitem')
            self._skipped(op)

    def getarraysubstruct(self, op):        
        array = self.db.repr_arg(op.args[0])
        arraytype = ''
        index = self.db.repr_arg(op.args[1])
        indextype = '' #self.db.repr_arg_type(op.args[1])
        targetvar = self.db.repr_arg(op.result)
        self.codewriter.getelementptr(targetvar, arraytype, array,
                                      ("uint", 1), (indextype, index))

    def setarrayitem(self, op):
        array = self.db.repr_arg(op.args[0])
        index = self.db.repr_arg(op.args[1])
        #indextype = self.db.repr_arg_type(op.args[1])
        valuevar = self.db.repr_arg(op.args[2]) 
        valuetype = 'undefined' #self.db.repr_arg_type(op.args[2])
        if valuetype != "void":
            #tmpvar = self.db.repr_tmpvar()
            #self.codewriter.getelementptr(tmpvar, arraytype, array,
            #                          ("uint", 1), (indextype, index))
            #self.codewriter.store(valuetype, valuevar, tmpvar) 
            self.codewriter.store(array, (index,), valuevar)
        else:
            self.codewriter.comment('setarrayitem')
            self._skipped(op)

    def getarraysize(self, op):
        array = self.db.repr_arg(op.args[0])
        #tmpvar = self.db.repr_tmpvar()
        #self.codewriter.getelementptr(tmpvar, arraytype, array, ("uint", 0))
        targetvar = self.db.repr_arg(op.result)
        #targettype = self.db.repr_arg_type(op.result)
        #self.codewriter.load(targetvar, targettype, tmpvar)
        self.codewriter.append('%s = %s.length' % (targetvar, array)) #XXX move to codewriter

    #Stackless
    def yield_current_frame_to_caller(self, op):
        '''special handling of this operation: call stack_unwind() to force the
        current frame to be saved into the heap, but don't propagate the
        unwind -- instead, capture it and return it normally'''
        targetvar = self.db.repr_arg(op.result)
        self.codewriter.call(targetvar, "ll_stack_unwind", specialreturnvalue="slp_return_current_frame_to_caller()")
