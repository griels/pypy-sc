import dis, pyframe, baseobjspace
from appfile import AppFile
from baseobjspace import OperationError, NoValue


# dynamically loaded application-space utilities
appfile = AppFile(__name__, ["interpreter"])


class unaryoperation:
    def __init__(self, operationname):
        self.operationname = operationname
    def __call__(self, f):
        operation = getattr(f.space, self.operationname)
        w_1 = f.valuestack.pop()
        w_result = operation(w_1)
        f.valuestack.push(w_result)

class binaryoperation:
    def __init__(self, operationname):
        self.operationname = operationname
    def __call__(self, f):
        operation = getattr(f.space, self.operationname)
        w_2 = f.valuestack.pop()
        w_1 = f.valuestack.pop()
        w_result = operation(w_1, w_2)
        f.valuestack.push(w_result)


################################################################
##  Implementation of the opcodes
##

def LOAD_FAST(f, varindex):
    varname = f.getlocalvarname(varindex)
    w_varname = f.space.wrap(varname)
    w_value = f.space.getitem(f.w_locals, w_varname)
    # XXX catch KeyError and make it a NameError
    f.valuestack.push(w_value)

def LOAD_CONST(f, constindex):
    w_const = f.getconstant(constindex)
    f.valuestack.push(w_const)

def STORE_FAST(f, varindex):
    varname = f.getlocalvarname(varindex)
    w_varname = f.space.wrap(varname)
    w_value = f.valuestack.pop()
    f.space.setitem(f.w_locals, w_varname, w_value)

def POP_TOP(f):
    f.valuestack.pop()

def ROT_TWO(f):
    w_1 = f.valuestack.pop()
    w_2 = f.valuestack.pop()
    f.valuestack.push(w_1)
    f.valuestack.push(w_2)

def ROT_THREE(f):
    w_1 = f.valuestack.pop()
    w_2 = f.valuestack.pop()
    w_3 = f.valuestack.pop()
    f.valuestack.push(w_1)
    f.valuestack.push(w_3)
    f.valuestack.push(w_2)

def ROT_FOUR(f):
    w_1 = f.valuestack.pop()
    w_2 = f.valuestack.pop()
    w_3 = f.valuestack.pop()
    w_4 = f.valuestack.pop()
    f.valuestack.push(w_1)
    f.valuestack.push(w_4)
    f.valuestack.push(w_3)
    f.valuestack.push(w_2)

def DUP_TOP(f):
    w_1 = f.valuestack.top()
    f.valuestack.push(w_1)

def DUP_TOPX(f, itemcount):
    assert 1 <= itemcount <= 5, "limitation of the current interpreter"
    for i in range(itemcount):
        w_1 = f.valuestack.top(itemcount-1)
        f.valuestack.push(w_1)

UNARY_POSITIVE = unaryoperation("pos")
UNARY_NEGATIVE = unaryoperation("neg")
UNARY_NOT      = unaryoperation("not_")
UNARY_CONVERT  = unaryoperation("repr")
UNARY_INVERT   = unaryoperation("invert")

def BINARY_POWER(f):
    w_2 = f.valuestack.pop()
    w_1 = f.valuestack.pop()
    w_result = f.space.pow(w_1, w_2, f.space.w_None)
    f.valuestack.push(w_result)

BINARY_MULTIPLY = binaryoperation("mul")
BINARY_TRUE_DIVIDE  = binaryoperation("truediv")
BINARY_FLOOR_DIVIDE = binaryoperation("floordiv")
BINARY_DIVIDE       = binaryoperation("div")
BINARY_MODULO       = binaryoperation("mod")
BINARY_ADD      = binaryoperation("add")
BINARY_SUBTRACT = binaryoperation("sub")
BINARY_SUBSCR   = binaryoperation("getitem")
BINARY_LSHIFT   = binaryoperation("lshift")
BINARY_RSHIFT   = binaryoperation("rshift")
BINARY_AND = binaryoperation("and_")
BINARY_XOR = binaryoperation("xor")
BINARY_OR  = binaryoperation("or_")

def INPLACE_POWER(f):
    w_2 = f.valuestack.pop()
    w_1 = f.valuestack.pop()
    w_result = f.space.inplace_pow(w_1, w_2, f.space.w_None)
    f.valuestack.push(w_result)

INPLACE_MULTIPLY = binaryoperation("inplace_mul")
INPLACE_TRUE_DIVIDE  = binaryoperation("inplace_truediv")
INPLACE_FLOOR_DIVIDE = binaryoperation("inplace_floordiv")
INPLACE_DIVIDE       = binaryoperation("inplace_div")
INPLACE_MODULO       = binaryoperation("inplace_mod")
INPLACE_ADD      = binaryoperation("inplace_add")
INPLACE_SUBTRACT = binaryoperation("inplace_sub")
INPLACE_LSHIFT   = binaryoperation("inplace_lshift")
INPLACE_RSHIFT   = binaryoperation("inplace_rshift")
INPLACE_AND = binaryoperation("inplace_and")
INPLACE_XOR = binaryoperation("inplace_xor")
INPLACE_OR  = binaryoperation("inplace_or")

def slice(f, w_start, w_end):
    w_slice = f.space.newslice(w_start, w_end, None)
    w_obj = f.valuestack.pop()
    w_result = f.space.getitem(w_obj, w_slice)
    f.push(w_result)

def SLICE_0(f):
    slice(f, None, None)

def SLICE_1(f):
    w_start = f.valuestack.pop()
    slice(f, w_start, None)

def SLICE_2(f):
    w_end = f.valuestack.pop()
    slice(f, None, w_end)

def SLICE_3(f):
    w_end = f.valuestack.pop()
    w_start = f.valuestack.pop()
    slice(f, w_start, w_end)

def storeslice(f, w_start, w_end):
    w_slice = f.space.newslice(w_start, w_end, None)
    w_obj = f.valuestack.pop()
    w_newvalue = f.valuestack.pop()
    f.space.setitem(w_obj, w_slice, w_newvalue)

def STORE_SLICE_0(f):
    storeslice(f, None, None)

def STORE_SLICE_1(f):
    w_start = f.valuestack.pop()
    storeslice(f, w_start, None)

def STORE_SLICE_2(f):
    w_end = f.valuestack.pop()
    storeslice(f, None, w_end)

def STORE_SLICE_3(f):
    w_end = f.valuestack.pop()
    w_start = f.valuestack.pop()
    storeslice(f, w_start, w_end)

def deleteslice(f, w_start, w_end):
    w_slice = f.space.newslice(w_start, w_end, None)
    w_obj = f.valuestack.pop()
    f.space.delitem(w_obj, w_slice)

def DELETE_SLICE_0(f):
    deleteslice(f, None, None)

def DELETE_SLICE_1(f):
    w_start = f.valuestack.pop()
    deleteslice(f, w_start, None)

def DELETE_SLICE_2(f):
    w_end = f.valuestack.pop()
    deleteslice(f, None, w_end)

def DELETE_SLICE_3(f):
    w_end = f.valuestack.pop()
    w_start = f.valuestack.pop()
    deleteslice(f, w_start, w_end)

def STORE_SUBSCR(f):
    "obj[subscr] = newvalue"
    w_subscr = f.valuestack.pop()
    w_obj = f.valuestack.pop()
    w_newvalue = f.valuestack.pop()
    f.space.setitem(w_obj, w_subscr, w_newvalue)

def DELETE_SUBSCR(f):
    "del obj[subscr]"
    w_subscr = f.valuestack.pop()
    w_obj = f.valuestack.pop()
    f.space.delitem(w_obj, w_subscr)

def PRINT_EXPR(f):
    w_expr = f.valuestack.pop()
    f.space.gethelper(appfile).call("print_expr", [w_expr])

def PRINT_ITEM_TO(f):
    w_stream = f.valuestack.pop()
    w_item = f.valuestack.pop()
    f.space.gethelper(appfile).call("print_item_to", [w_item, w_stream])

def PRINT_ITEM(f):
    w_item = f.valuestack.pop()
    f.space.gethelper(appfile).call("print_item", [w_item])

def PRINT_NEWLINE_TO(f):
    w_stream = f.valuestack.pop()
    f.space.gethelper(appfile).call("print_newline_to", [w_stream])

def PRINT_NEWLINE(f):
    f.space.gethelper(appfile).call("print_newline", [])

def BREAK_LOOP(f):
    raise pyframe.SBreakLoop

def CONTINUE_LOOP(f, startofloop):
    raise pyframe.SContinueLoop(startofloop)

def RAISE_VARARGS(f, nbargs):
    # we use the .app.py file to prepare the exception/value/traceback
    # but not to actually raise it, because we cannot use the 'raise'
    # statement to implement RAISE_VARARGS
    if nbargs == 0:
        w_resulttuple = f.space.gethelper(appfile).call("prepare_raise0")
    elif nbargs == 1:
        w_type = f.valuestack.pop()
        w_resulttuple = f.space.gethelper(appfile).call(
            "prepare_raise", [w_type, None, None])
    elif nbargs == 2:
        w_value = f.valuestack.pop()
        w_type  = f.valuestack.pop()
        w_resulttuple = f.space.gethelper(appfile).call(
            "prepare_raise", [w_type, w_value, None])
    elif nbargs == 3:
        w_traceback = f.valuestack.pop()
        w_value     = f.valuestack.pop()
        w_type      = f.valuestack.pop()
        w_resulttuple = f.space.gethelper(appfile).call(
            "prepare_raise", [w_type, w_value, w_traceback])
    else:
        raise pyframe.BytecodeCorruption, "bad RAISE_VARARGS oparg"
    w_type, w_value, w_traceback = pyframe.unpackiterable(
        f.space, w_resulttuple)
    raise OperationError(w_type, w_value, w_traceback)

def LOAD_LOCALS(f):
    f.valuestack.push(f.w_locals)

def RETURN_VALUE(f):
    w_returnvalue = f.valuestack.pop()
    raise pyframe.SReturnValue(w_returnvalue)

def YIELD_VALUE(f):
    w_yieldedvalue = f.valuestack.pop()
    raise pyframe.SYieldValue(w_yieldedvalue)
YIELD_STMT = YIELD_VALUE  # misnamed in dis.opname

def EXEC_STMT(f):
    w_locals  = f.valuestack.pop()
    w_globals = f.valuestack.pop()
    w_prog    = f.valuestack.pop()
    f.space.gethelper(appfile).call("exec_statement",
                                    [w_prog, w_globals, w_locals,
                                     f.w_builtins, f.w_globals, f.w_locals])

def POP_BLOCK(f):
    block = f.blockstack.pop()
    block.cleanup(f)  # the block knows how to clean up the value stack

def END_FINALLY(f):
    # unlike CPython, the information on what to do at the end
    # of a 'finally' is not stored in the value stack, but in
    # the block stack, in a new dedicated block type which knows
    # how to restore the environment (exception, break/continue...)
    # at the beginning of the 'finally'.
    block = f.blockstack.pop()
    block.cleanup(f)

def BUILD_CLASS(f):
    w_methodsdict = f.valuestack.pop()
    w_bases       = f.valuestack.pop()
    w_name        = f.valuestack.pop()
    w_newclass = f.space.gethelper(appfile).call(
        "build_class", [w_methodsdict, w_bases, w_name])
    f.push(w_newclass)

def STORE_NAME(f, varindex):
    varname = f.getname(varindex)
    w_varname = f.space.wrap(varname)
    w_newvalue = f.valuestack.pop()
    f.space.setitem(f.w_locals, w_varname, w_newvalue)

def DELETE_NAME(f, varindex):
    varname = f.getname(varindex)
    w_varname = f.space.wrap(varname)
    f.space.delitem(f.w_locals, w_varname)
    # XXX catch KeyError and make it a NameError

def UNPACK_SEQUENCE(f, itemcount):
    w_iterable = f.valuestack.pop()
    w_iterator = f.space.getiter(w_iterable)
    items = []
    for i in range(itemcount):
        try:
            w_item = f.space.iternext(w_iterator)
        except NoValue:
            if i == 1:
                plural = ""
            else:
                plural = "s"
            message = "need more than %d value%s to unpack" % (i, plural)
            w_exceptionclass = f.space.w_ValueError
            w_exceptionvalue = f.space.wrap(message)
            raise OperationError(w_exceptionclass, w_exceptionvalue)
        items.append(w_item)
    # check that we have exhausted the iterator now.
    try:
        f.space.iternext(w_iterator)
    except NoValue:
        pass
    else:
        w_exceptionclass = f.space.w_ValueError
        w_exceptionclass = f.space.wrap("too many values to unpack")
        raise OperationError(w_exceptionclass, w_exceptionvalue)
    items.reverse()
    for item in items:
        f.valuestack.push(item)

def STORE_ATTR(f, nameindex):
    "obj.attributename = newvalue"
    attributename = f.getname(nameindex)
    w_attributename = f.space.wrap(attributename)
    w_obj = f.valuestack.pop()
    w_newvalue = f.valuestack.pop()
    f.space.setattr(w_obj, w_attributename, w_newvalue)

def DELETE_ATTR(f, nameindex):
    "del obj.attributename"
    attributename = f.getname(nameindex)
    w_attributename = f.space.wrap(attributename)
    w_obj = f.valuestack.pop()
    f.space.delattr(w_obj, w_attributename)

def STORE_GLOBAL(f, nameindex):
    varname = f.getname(nameindex)
    w_varname = f.space.wrap(varname)
    w_newvalue = f.valuestack.pop()
    f.space.setitem(f.w_globals, w_varname, w_newvalue)

def DELETE_GLOBAL(f, nameindex):
    varname = f.getname(nameindex)
    w_varname = f.space.wrap(varname)
    f.space.delitem(f.w_globals, w_varname)

def LOAD_NAME(f, nameindex):
    varname = f.getname(nameindex)
    w_varname = f.space.wrap(varname)
    w_value = f.space.gethelper(appfile).call(
        "load_name", [w_varname, f.w_locals, f.w_globals, f.w_builtins])
    f.valuestack.push(w_value)

def LOAD_GLOBAL(f, nameindex):
    varname = f.getname(nameindex)
    w_varname = f.space.wrap(varname)
    try:
        w_value = f.space.getitem(f.w_globals, w_varname)
    except OperationError, e:
        # catch KeyErrors
        w_KeyError = f.space.w_KeyError
        w_match = f.space.compare(e.w_type, w_KeyError, "exc match")
        if not f.space.is_true(w_match):
            raise
        # we got a KeyError, now look in the built-ins
        try:
            w_value = f.space.getitem(f.w_builtins, w_varname)
        except OperationError, e:
            # catch KeyErrors again
            w_match = f.space.compare(e.w_type, w_KeyError, "exc match")
            if not f.space.is_true(w_match):
                raise
            message = "global name '%s' is not defined" % varname
            w_exc_type = f.space.w_NameError
            w_exc_value = f.space.wrap(message)
            raise OperationError(w_exc_type, w_exc_value)
    f.valuestack.push(w_value)

def DELETE_FAST(f, varindex):
    varname = f.getlocalvarname(varindex)
    w_varname = f.space.wrap(varname)
    f.space.delitem(f.w_locals, w_varname)
    # XXX catch KeyError and make it a NameError

def LOAD_CLOSURE(f, varindex):
    # nested scopes: access the cell object
    # XXX at some point implement an explicit traversal of
    #     syntactically nested frames?
    varname = f.getfreevarname(varindex)
    w_varname = f.space.wrap(varname)
    w_value = f.space.gethelper(appfile).call("load_closure",
                                              [f.w_locals, w_varname])
    f.valuestack.push(w_value)

def LOAD_DEREF(f, varindex):
    # nested scopes: access a variable through its cell object
    varname = f.getfreevarname(varindex)
    w_varname = f.space.wrap(varname)
    w_value = f.space.getitem(f.w_locals, w_varname)
    # XXX catch KeyError and make it a NameError
    f.valuestack.push(w_value)

def STORE_DEREF(f, varindex):
    # nested scopes: access a variable through its cell object
    varname = f.getfreevarname(varindex)
    w_varname = f.space.wrap(varname)
    w_newvalue = f.valuestack.pop()
    f.space.setitem(f.w_locals, w_varname, w_newvalue)

def BUILD_TUPLE(f, itemcount):
    items = [f.valuestack.pop() for i in range(itemcount)]
    items.reverse()
    w_tuple = f.space.newtuple(items)
    f.valuestack.push(w_tuple)

def BUILD_LIST(f, itemcount):
    items = [f.valuestack.pop() for i in range(itemcount)]
    items.reverse()
    w_list = f.space.newlist(items)
    f.valuestack.push(w_list)

def BUILD_MAP(f, zero):
    if zero != 0:
        raise pyframe.BytecodeCorruption
    w_dict = f.space.newdict([])
    f.valuestack.push(w_dict)

def LOAD_ATTR(f, nameindex):
    "obj.attributename"
    attributename = f.getname(nameindex)
    w_attributename = f.space.wrap(attributename)
    w_obj = f.valuestack.pop()
    w_value = f.space.getattr(w_obj, w_attributename)
    f.valuestack.push(w_value)

def COMPARE_OP(f, test):
    testnames = ["<", "<=", "==", "!=", ">", ">=",
                 "in", "not in", "is", "is not", "exc match"]
    testname = testnames[test]
    w_2 = f.valuestack.pop()
    w_1 = f.valuestack.pop()
    w_result = f.space.compare(w_1, w_2, testname)
    f.valuestack.push(w_result)

def IMPORT_NAME(f, nameindex):
    modulename = f.getname(nameindex)
    w_modulename = f.space.wrap(modulename)
    w_fromlist = f.valuestack.pop()
    w_obj = f.space.gethelper(appfile).call(
        "import_name", [f.w_builtins,
                        w_modulename, f.w_globals, f.w_locals, w_fromlist])
    f.valuestack.push(w_obj)

def IMPORT_STAR(f):
    w_module = f.valuestack.pop()
    f.space.gethelper(appfile).call("import_star", [w_module, f.w_locals])

def IMPORT_FROM(f, nameindex):
    name = f.getname(nameindex)
    w_name = f.space.wrap(name)
    w_module = f.valuestack.top()
    w_obj = f.space.gethelper(appfile).call("import_from", [w_module, w_name])
    f.valuestack.push(w_obj)

def JUMP_FORWARD(f, stepby):
    f.next_instr += stepby

def JUMP_IF_FALSE(f, stepby):
    w_cond = f.valuestack.top()
    if not f.space.is_true(w_cond):
        f.next_instr += stepby

def JUMP_IF_TRUE(f, stepby):
    w_cond = f.valuestack.top()
    if f.space.is_true(w_cond):
        f.next_instr += stepby

def JUMP_ABSOLUTE(f, jumpto):
    f.next_instr = jumpto

def GET_ITER(f):
    w_iterable = f.valuestack.pop()
    w_iterator = f.space.getiter(w_iterable)
    f.valuestack.push(w_iterator)

def FOR_ITER(f, jumpby):
    w_iterator = f.valuestack.top()
    try:
        w_nextitem = f.space.iternext(w_iterator)
    except NoValue:
        # iterator exhausted
        f.valuestack.pop()
        f.next_instr += jumpby
    else:
        f.valuestack.push(w_nextitem)

def FOR_LOOP(f, oparg):
    raise pyframe.BytecodeCorruption, "old opcode, no longer in use"

def SETUP_LOOP(f, offsettoend):
    block = pyframe.LoopBlock(f, f.next_instr + offsettoend)
    f.blockstack.push(block)

def SETUP_EXCEPT(f, offsettoend):
    block = pyframe.ExceptBlock(f, f.next_instr + offsettoend)
    f.blockstack.push(block)

def SETUP_FINALLY(f, offsettoend):
    block = pyframe.FinallyBlock(f, f.next_instr + offsettoend)
    f.blockstack.push(block)

def call_function_extra(f, oparg, with_varargs, with_varkw):
    n_arguments = oparg & 0xff
    n_keywords = (oparg>>8) & 0xff
    if with_varkw:
        w_varkw = f.valuestack.pop()
    if with_varargs:
        w_varargs = f.valuestack.pop()
    keywords = []
    for i in range(n_keywords):
        w_value = f.valuestack.pop()
        w_key   = f.valuestack.pop()
        keywords.append((w_value, w_key))
    arguments = [f.valuestack.pop() for i in range(n_arguments)]
    arguments.reverse()
    w_function  = f.valuestack.pop()
    w_arguments = f.space.newtuple(arguments)
    w_keywords  = f.space.newdict(keywords)
    if with_varargs:
        w_arguments = f.space.gethelper(appfile).call("concatenate_arguments",
                                                      [w_arguments, w_varargs])
    if with_varkw:
        w_keywords  = f.space.gethelper(appfile).call("concatenate_keywords",
                                                      [w_keywords,  w_varkw])
    w_result = f.space.call(w_function, w_arguments, w_keywords)
    f.valuestack.push(w_result)

def CALL_FUNCTION(f, oparg):
    call_function_extra(f, oparg, False, False)

def CALL_FUNCTION_VAR(f, oparg):
    call_function_extra(f, oparg, True,  False)

def CALL_FUNCTION_KW(f, oparg):
    call_function_extra(f, oparg, False, True)

def CALL_FUNCTION_VAR_KW(f, oparg):
    call_function_extra(f, oparg, True,  True)

def MAKE_FUNCTION(f, numdefaults):
    w_codeobj = f.valuestack.pop()
    defaultarguments = [f.valuestack.pop() for i in range(numdefaults)]
    defaultarguments.reverse()
    w_defaultarguments = f.space.newtuple(defaultarguments)
    w_func = f.space.newfunction(w_codeobj, f.w_globals, w_defaultarguments)
    f.valuestack.push(w_func)

def MAKE_CLOSURE(f, numdefaults):
    w_codeobj = f.valuestack.pop()
    codeobj = f.space.unwrap(w_codeobj)
    nfreevars = len(codeobj.co_freevars)
    freevars = [f.valuestack.pop() for i in range(nfreevars)]
    freevars.reverse()
    w_freevars = f.space.newtuple(freevars)
    defaultarguments = [f.valuestack.pop() for i in range(numdefaults)]
    defaultarguments.reverse()
    w_defaultarguments = f.space.newtuple(defaultarguments)
    w_func = f.space.newfunction(w_codeobj, f.w_globals, w_defaultarguments,
                                 w_freevars)
    f.valuestack.push(w_func)

def BUILD_SLICE(f, numargs):
    if numargs == 3:
        w_step = f.valuestack.pop()
    elif numargs == 2:
        w_step = None
    else:
        raise pyframe.BytecodeCorruption
    w_end   = f.valuestack.pop()
    w_start = f.valuestack.pop()
    w_slice = f.space.newslice(w_start, w_end, w_step)
    f.valuestack.push(w_slice)

def SET_LINENO(f, lineno):
    pass

def EXTENDED_ARG(f, oparg):
    opcode = f.nextop()
    oparg = oparg<<16 | f.nextarg()
    dispatch_arg(f, oparg)

def MISSING_OPCODE(f, oparg=None):
    raise pyframe.BytecodeCorruption, "unknown opcode"


################################################################

dispatch_table = []
for i in range(256):
    opname = dis.opname[i].replace('+', '_')
    fn = MISSING_OPCODE
    if opname in globals():
        fn = globals()[opname]
    elif not opname.startswith('<') and i>0:
        print "* Warning, missing opcode %s" % opname
    dispatch_table.append(fn)


def name(thing):
    try:
        return thing.operationname
    except AttributeError:
        return thing.__name__

def has_arg(opcode):
    return opcode >= dis.HAVE_ARGUMENT

def dispatch_noarg(f, opcode):
    try:
        fn = dispatch_table[opcode]
#        print name(fn)
    except KeyError:
        raise KeyError, "missing opcode %s" % dis.opname[opcode]
    fn(f)

def dispatch_arg(f, opcode, oparg):
    assert oparg >= 0
    try:
        fn = dispatch_table[opcode]
#        print name(fn)
    except KeyError:
        raise KeyError, "missing opcode %s" % dis.opname[opcode]
    fn(f, oparg)
