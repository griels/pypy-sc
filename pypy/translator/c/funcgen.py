from __future__ import generators
from pypy.translator.c.support import USESLOTS # set to False if necessary while refactoring
from pypy.translator.c.support import cdecl, ErrorValue
from pypy.translator.c.support import llvalue_from_constant, gen_assignments
from pypy.objspace.flow.model import Variable, Constant, Block
from pypy.objspace.flow.model import traverse, last_exception
from pypy.rpython.lltypesystem.lltype import \
     Ptr, PyObject, Void, Bool, pyobjectptr, Struct, Array


PyObjPtr = Ptr(PyObject)
LOCALVAR = 'l_%s'

class FunctionCodeGenerator(object):
    """
    Collects information about a function which we have to generate
    from a flow graph.
    """

    if USESLOTS:
        __slots__ = """graph db gcpolicy
                       cpython_exc
                       more_ll_values
                       vars
                       lltypes
                       functionname
                       currentblock""".split()

    def __init__(self, graph, db, cpython_exc=False, functionname=None):
        self.graph = graph
        self.db = db
        self.gcpolicy = db.gcpolicy
        self.cpython_exc = cpython_exc
        self.functionname = functionname
        #
        # collect all variables and constants used in the body,
        # and get their types now
        #
        # NOTE: cannot use dictionaries with Constants as keys, because
        #       Constants may hash and compare equal but have different lltypes
        mix = [self.graph.getreturnvar()]
        self.more_ll_values = []
        for block in graph.iterblocks():
            mix.extend(block.inputargs)
            for op in block.operations:
                mix.extend(op.args)
                mix.append(op.result)
            for link in block.exits:
                mix.extend(link.getextravars())
                mix.extend(link.args)
                if hasattr(link, 'llexitcase'):
                    self.more_ll_values.append(link.llexitcase)
                elif link.exitcase is not None:
                    mix.append(Constant(link.exitcase))

        uniquemix = []
        seen = {}
        for v in mix:
            if id(v) not in seen:
                uniquemix.append(v)
                seen[id(v)] = True
            T = getattr(v, 'concretetype', PyObjPtr)
            db.gettype(T)  # force the type to be considered by the database
        self.vars = uniquemix
        self.lltypes = None

    def implementation_begin(self):
        db = self.db
        lltypes = {}
        for v in self.vars:
            T = getattr(v, 'concretetype', PyObjPtr)
            typename = db.gettype(T)
            lltypes[id(v)] = T, typename
        self.lltypes = lltypes

    def implementation_end(self):
        self.lltypes = None

    def argnames(self):
        return [LOCALVAR % v.name for v in self.graph.getargs()]

    def allvariables(self):
        return [v for v in self.vars if isinstance(v, Variable)]

    def allconstants(self):
        return [c for c in self.vars if isinstance(c, Constant)]

    def allconstantvalues(self):
        for c in self.vars:
            if isinstance(c, Constant):
                yield llvalue_from_constant(c)
        for llvalue in self.more_ll_values:
            yield llvalue

    def lltypemap(self, v):
        T, typename = self.lltypes[id(v)]
        return T

    def lltypename(self, v):
        T, typename = self.lltypes[id(v)]
        return typename

    def expr(self, v, special_case_void=True):
        if isinstance(v, Variable):
            if self.lltypemap(v) is Void and special_case_void:
                return '/* nothing */'
            else:
                return LOCALVAR % v.name
        elif isinstance(v, Constant):
            value = llvalue_from_constant(v)
            if value is None and not special_case_void:
                return 'nothing'
            else:
                return self.db.get(value)
        else:
            raise TypeError, "expr(%r)" % (v,)

    def error_return_value(self):
        returnlltype = self.lltypemap(self.graph.getreturnvar())
        return self.db.get(ErrorValue(returnlltype))

    def return_with_error(self):
        if self.cpython_exc:
            lltype_of_exception_value = self.db.get_lltype_of_exception_value()
            exc_value_typename = self.db.gettype(lltype_of_exception_value)
            assert self.lltypemap(self.graph.getreturnvar()) == PyObjPtr
            yield '{'
            yield '\t%s;' % cdecl(exc_value_typename, 'vanishing_exc_value')
            yield '\tRPyConvertExceptionToCPython(vanishing_exc_value);'
            yield '\t%s' % self.pop_alive_expr('vanishing_exc_value', lltype_of_exception_value)
            yield '}'
        yield 'return %s; ' % self.error_return_value()

    # ____________________________________________________________

    def cfunction_declarations(self):
        # declare the local variables, excluding the function arguments
        seen = {}
        for a in self.graph.getargs():
            seen[a.name] = True

        result_by_name = []
        for v in self.allvariables():
            name = v.name
            if name not in seen:
                seen[name] = True
                result = cdecl(self.lltypename(v), LOCALVAR % name) + ';'
                if self.lltypemap(v) is Void:
                    result = '/*%s*/' % result
                result_by_name.append((v._name, result))
        result_by_name.sort()
        return [result for name, result in result_by_name]

    # ____________________________________________________________

    def cfunction_body(self):
        graph = self.graph

        blocknum = {}
        allblocks = []

        # match the subsequent pop_alive for each input argument
        for a in self.graph.getargs():
            line = self.push_alive(a)
            if line:
                yield line

        def gen_link(link, linklocalvars=None):
            "Generate the code to jump across the given Link."
            is_alive = {}
            linklocalvars = linklocalvars or {}
            for v in to_release:
                linklocalvars[v] = self.expr(v)
            is_alive_and_dies = linklocalvars.copy()
            assignments = []
            multiple_times_alive = []
            for a1, a2 in zip(link.args, link.target.inputargs):
                a2type, a2typename = self.lltypes[id(a2)]
                if a2type is Void:
                    continue
                if a1 in linklocalvars:
                    src = linklocalvars[a1]
                else:
                    src = self.expr(a1)
                dest = LOCALVAR % a2.name
                assignments.append((a2typename, dest, src))
                if a1 in is_alive_and_dies:
                    del is_alive_and_dies[a1]
                else:
                    #assert self.lltypemap(a1) == self.lltypemap(a2)
                    multiple_times_alive.append(a2)
            # warning, the order below is delicate to get right:
            # 1. forget the old variables that are not passed over
            for v in is_alive_and_dies:
                line = self.pop_alive(v, linklocalvars[v])
                if line:
                    yield line
            # 2. perform the assignments with collision-avoidance
            for line in gen_assignments(assignments):
                yield line
            # 3. keep alive the new variables if needed
            for a2 in multiple_times_alive:
                line = self.push_alive(a2)
                if line:
                    yield line
            yield 'goto block%d;' % blocknum[link.target]

        # collect all blocks
        def visit(block):
            if isinstance(block, Block):
                allblocks.append(block)
                blocknum[block] = len(blocknum)
        traverse(visit, graph)

        assert graph.startblock is allblocks[0]

        # generate the body of each block
        push_alive_op_result = self.gcpolicy.push_alive_op_result
        for block in allblocks:
            self.currentblock = block
            myblocknum = blocknum[block]
            yield ''
            yield 'block%d:' % myblocknum
            to_release = list(block.inputargs)
            reachable_err = -1   # the number of the first reachable err label
            for op in block.operations:
                err   = 'err%d_%d' % (myblocknum, len(to_release))
                macro = 'OP_%s' % op.opname.upper()
                meth  = getattr(self, macro, None)
                if meth:
                    line = meth(op, err)
                else:
                    lst = [self.expr(v) for v in op.args]
                    lst.append(self.expr(op.result))
                    lst.append(err)
                    line = '%s(%s);' % (macro, ', '.join(lst))
                if '\n' in line:
                    for subline in line.split('\n'):
                        yield subline
                else:
                    yield line
                if line.find(err) >= 0:
                    reachable_err = len(to_release)
                to_release.append(op.result)

                T = self.lltypemap(op.result)
                if T is not Void:
                    res = LOCALVAR % op.result.name
                    line = push_alive_op_result(op.opname, res, T)
                    if line:
                        yield line

            fallthrough = False
            if len(block.exits) == 0:
                if len(block.inputargs) == 2:   # exc_cls, exc_value
                    # exceptional return block
                    exc_cls   = self.expr(block.inputargs[0])
                    exc_value = self.expr(block.inputargs[1])
                    yield 'RPyRaiseException(%s, %s);' % (exc_cls, exc_value)
                    for line in self.return_with_error():
                        yield line 
                else:
                    # regular return block
                    retval = self.expr(block.inputargs[0])
                    yield 'return %s;' % retval
                continue
            elif block.exitswitch is None:
                # single-exit block
                assert len(block.exits) == 1
                for op in gen_link(block.exits[0]):
                    yield op
                yield ''
            elif block.exitswitch == Constant(last_exception):
                # block catching the exceptions raised by its last operation
                # we handle the non-exceptional case first
                link = block.exits[0]
                assert link.exitcase is None
                for op in gen_link(link):
                    yield op
                # we must catch the exception raised by the last operation,
                # which goes to the last err%d_%d label written above.
                yield ''
                to_release.pop()  # skip default error handling for this label
                yield 'err%d_%d:' % (myblocknum, len(to_release))
                reachable_err = len(to_release)   # XXX assert they are == ?
                yield ''
                for link in block.exits[1:]:
                    assert issubclass(link.exitcase, Exception)
                    try:
                        etype = link.llexitcase
                    except AttributeError:
                        etype = pyobjectptr(link.exitcase)
                        T1 = PyObjPtr
                        T2 = PyObjPtr
                    else:
                        assert hasattr(link.last_exception, 'concretetype')
                        assert hasattr(link.last_exc_value, 'concretetype')
                        T1 = link.last_exception.concretetype
                        T2 = link.last_exc_value.concretetype
                    typ1 = self.db.gettype(T1)
                    typ2 = self.db.gettype(T2)
                    yield 'if (RPyMatchException(%s)) {' % (self.db.get(etype),)
                    yield '\t%s;' % cdecl(typ1, 'exc_cls')
                    yield '\t%s;' % cdecl(typ2, 'exc_value')
                    yield '\tRPyFetchException(exc_cls, exc_value, %s);' % (
                        cdecl(typ2, ''))
                    d = {}
                    if isinstance(link.last_exception, Variable):
                        d[link.last_exception] = 'exc_cls'
                    else:
                        yield '\t' + self.pop_alive_expr('exc_cls', T1)
                    if isinstance(link.last_exc_value, Variable):
                        d[link.last_exc_value] = 'exc_value'
                    else:
                        yield '\t' + self.pop_alive_expr('exc_value', T2)
                    for op in gen_link(link, d):
                        yield '\t' + op
                    yield '}'
                fallthrough = True
            else:
                # block ending in a switch on a value
                TYPE = self.lltypemap(block.exitswitch)
                for link in block.exits[:-1]:
                    assert link.exitcase in (False, True)
                    expr = self.expr(block.exitswitch)
                    if TYPE == Bool:
                        if not link.exitcase:
                            expr = '!' + expr
                    elif TYPE == PyObjPtr:
                        yield 'assert(%s == Py_True || %s == Py_False);' % (
                            expr, expr)
                        if link.exitcase:
                            expr = '%s == Py_True' % expr
                        else:
                            expr = '%s == Py_False' % expr
                    else:
                        raise TypeError("switches can only be on Bool or "
                                        "PyObjPtr.  Got %r" % (TYPE,))
                    yield 'if (%s) {' % expr
                    for op in gen_link(link):
                        yield '\t' + op
                    yield '}'
                link = block.exits[-1]
                assert link.exitcase in (False, True)
                #yield 'assert(%s == %s);' % (self.expr(block.exitswitch),
                #                       self.genc.nameofvalue(link.exitcase, ct))
                for op in gen_link(block.exits[-1]):
                    yield op
                yield ''

            for i in range(reachable_err, -1, -1):
                if not fallthrough:
                    yield 'err%d_%d:' % (myblocknum, i)
                else:
                    fallthrough = False    # this label was already generated
                if i == 0:
                    for line in self.return_with_error():
                        yield line
                else:
                    yield self.pop_alive(to_release[i-1])

    # ____________________________________________________________

    # the C preprocessor cannot handle operations taking a variable number
    # of arguments, so here are Python methods that do it
    
    def OP_NEWLIST(self, op, err):
        args = [self.expr(v) for v in op.args]
        r = self.expr(op.result)
        if len(args) == 0:
            return 'OP_NEWLIST0(%s, %s);' % (r, err)
        else:
            args.insert(0, '%d' % len(args))
            return 'OP_NEWLIST((%s), %s, %s);' % (', '.join(args), r, err)

    def OP_NEWDICT(self, op, err):
        args = [self.expr(v) for v in op.args]
        r = self.expr(op.result)
        if len(args) == 0:
            return 'OP_NEWDICT0(%s, %s);' % (r, err)
        else:
            assert len(args) % 2 == 0
            args.insert(0, '%d' % (len(args)//2))
            return 'OP_NEWDICT((%s), %s, %s);' % (', '.join(args), r, err)

    def OP_NEWTUPLE(self, op, err):
        args = [self.expr(v) for v in op.args]
        r = self.expr(op.result)
        args.insert(0, '%d' % len(args))
        return 'OP_NEWTUPLE((%s), %s, %s);' % (', '.join(args), r, err)

    def OP_SIMPLE_CALL(self, op, err):
        args = [self.expr(v) for v in op.args]
        r = self.expr(op.result)
        args.append('NULL')
        return 'OP_SIMPLE_CALL((%s), %s, %s);' % (', '.join(args), r, err)

    def OP_CALL_ARGS(self, op, err):
        args = [self.expr(v) for v in op.args]
        r = self.expr(op.result)
        return 'OP_CALL_ARGS((%s), %s, %s);' % (', '.join(args), r, err)

    def OP_DIRECT_CALL(self, op, err):
        # skip 'void' arguments
        args = [self.expr(v) for v in op.args if self.lltypemap(v) is not Void]
        line = '%s(%s);' % (args[0], ', '.join(args[1:]))
        if self.lltypemap(op.result) is not Void:
            # skip assignment of 'void' return value
            r = self.expr(op.result)
            line = '%s = %s' % (r, line)
        line = '%s\n%s' % (line, self.check_directcall_result(op, err))
        return line

    def check_directcall_result(self, op, err):
        return 'if (RPyExceptionOccurred())\n\tFAIL(%s);' % err

    # low-level operations
    def generic_get(self, op, sourceexpr):
        T = self.lltypemap(op.result)
        newvalue = self.expr(op.result, special_case_void=False)
        result = ['%s = %s;' % (newvalue, sourceexpr)]
        # need to adjust the refcount of the result only for PyObjects
        if T == PyObjPtr:
            result.append(self.pyobj_incref_expr(newvalue, T))
        result = '\n'.join(result)
        if T is Void:
            result = '/* %s */' % result
        return result

    def generic_set(self, op, targetexpr):
        newvalue = self.expr(op.args[2], special_case_void=False)
        result = ['%s = %s;' % (targetexpr, newvalue)]
        # insert write barrier
        T = self.lltypemap(op.args[2])
        self.gcpolicy.write_barrier(result, newvalue, T, targetexpr)
        result = '\n'.join(result)
        if T is Void:
            result = '/* %s */' % result
        return result

    def OP_GETFIELD(self, op, err, ampersand=''):
        assert isinstance(op.args[1], Constant)
        STRUCT = self.lltypemap(op.args[0]).TO
        structdef = self.db.gettypedefnode(STRUCT)
        fieldname = structdef.c_struct_field_name(op.args[1].value)
        return self.generic_get(op, '%s%s->%s' % (ampersand,
                                                  self.expr(op.args[0]),
                                                  fieldname))

    def OP_SETFIELD(self, op, err):
        assert isinstance(op.args[1], Constant)
        STRUCT = self.lltypemap(op.args[0]).TO
        structdef = self.db.gettypedefnode(STRUCT)
        fieldname = structdef.c_struct_field_name(op.args[1].value)
        return self.generic_set(op, '%s->%s' % (self.expr(op.args[0]),
                                                fieldname))

    def OP_GETSUBSTRUCT(self, op, err):
        return self.OP_GETFIELD(op, err, ampersand='&')

    def OP_GETARRAYSIZE(self, op, err):
        return '%s = %s->length;' % (self.expr(op.result),
                                     self.expr(op.args[0]))

    def OP_GETARRAYITEM(self, op, err):
        return self.generic_get(op, '%s->items[%s]' % (self.expr(op.args[0]),
                                                       self.expr(op.args[1])))

    def OP_SETARRAYITEM(self, op, err):
        return self.generic_set(op, '%s->items[%s]' % (self.expr(op.args[0]),
                                                       self.expr(op.args[1])))

    def OP_GETARRAYSUBSTRUCT(self, op, err):
        return '%s = %s->items + %s;' % (self.expr(op.result),
                                         self.expr(op.args[0]),
                                         self.expr(op.args[1]))

    def OP_PTR_NONZERO(self, op, err):
        return '%s = (%s != NULL);' % (self.expr(op.result),
                                       self.expr(op.args[0]))
    def OP_PTR_ISZERO(self, op, err):
        return '%s = (%s == NULL);' % (self.expr(op.result),
                                       self.expr(op.args[0]))
    
    def OP_PTR_EQ(self, op, err):
        return '%s = (%s == %s);' % (self.expr(op.result),
                                     self.expr(op.args[0]),
                                     self.expr(op.args[1]))

    def OP_PTR_NE(self, op, err):
        return '%s = (%s != %s);' % (self.expr(op.result),
                                     self.expr(op.args[0]),
                                     self.expr(op.args[1]))

    def OP_MALLOC(self, op, err):
        TYPE = self.lltypemap(op.result).TO
        typename = self.db.gettype(TYPE)
        eresult = self.expr(op.result)
        esize = 'sizeof(%s)' % cdecl(typename, '')

        return self.gcpolicy.zero_malloc(TYPE, esize, eresult, err)

    def OP_MALLOC_VARSIZE(self, op, err):
        TYPE = self.lltypemap(op.result).TO
        typename = self.db.gettype(TYPE)
        lenfld = 'length'
        nodedef = self.db.gettypedefnode(TYPE)
        if isinstance(TYPE, Struct):
            arfld = TYPE._arrayfld
            lenfld = "%s.length" % nodedef.c_struct_field_name(arfld)
            VARPART = TYPE._flds[TYPE._arrayfld]
        else:
            VARPART = TYPE
        assert isinstance(VARPART, Array)
        itemtypename = self.db.gettype(VARPART.OF)
        elength = self.expr(op.args[1])
        eresult = self.expr(op.result)
        if VARPART.OF is Void:    # strange
            esize = 'sizeof(%s)' % (cdecl(typename, ''),)
            result = ''
        else:
            itemtype = cdecl(itemtypename, '')
            result = 'OP_MAX_VARSIZE(%s, %s, %s);\n' % (
                elength,
                itemtype,
                err)
            esize = 'sizeof(%s)-sizeof(%s)+%s*sizeof(%s)' % (
                cdecl(typename, ''),
                itemtype,
                elength,
                itemtype)
        result += self.gcpolicy.zero_malloc(TYPE, esize, eresult, err)
        result += '\n%s->%s = %s;' % (eresult, lenfld, elength)
        return result

    def OP_CAST_POINTER(self, op, err):
        TYPE = self.lltypemap(op.result)
        typename = self.db.gettype(TYPE)
        result = []
        result.append('%s = (%s)%s;' % (self.expr(op.result),
                                        cdecl(typename, ''),
                                        self.expr(op.args[0])))

        if TYPE == PyObjPtr:
            result.append(self.pyobj_incref(op.result))
        return '\t'.join(result)

    def OP_CAST_INT_TO_PTR(self, op, err):
        TYPE = self.lltypemap(op.result)
        typename = self.db.gettype(TYPE)
        return "%s = (%s)%s;" % (self.expr(op.result), cdecl(typename, ""), 
                                 self.expr(op.args[0]))

    def OP_SAME_AS(self, op, err):
        result = []
        TYPE = self.lltypemap(op.result)
        assert self.lltypemap(op.args[0]) == TYPE
        if TYPE is not Void:
            result.append('%s = %s;' % (self.expr(op.result),
                                        self.expr(op.args[0])))
            if TYPE == PyObjPtr:
                result.append(self.pyobj_incref(op.result))
        return '\t'.join(result)

    def OP_KEEPALIVE(self, op, err): # xxx what should be the sematics consequences of this
        return "/* kept alive: %s */ ;" % self.expr(op.args[0], special_case_void=False)

    #address operations
    def OP_RAW_STORE(self, op, err):
       addr = self.expr(op.args[0])
       TYPE = op.args[1].value
       offset = self.expr(op.args[2])
       value = self.expr(op.args[3])
       typename = self.db.gettype(TYPE).replace("@", "*") #XXX help! is this the way to do it?
       return "*(((%(typename)s) %(addr)s ) + %(offset)s) = %(value)s;" % locals()

    def OP_RAW_LOAD(self, op, err):
        addr = self.expr(op.args[0])
        TYPE = op.args[1].value
        offset = self.expr(op.args[2])
        result = self.expr(op.result)
        typename = self.db.gettype(TYPE).replace("@", "*") #XXX see above
        return "%(result)s = *(((%(typename)s) %(addr)s ) + %(offset)s);" % locals()

    def pyobj_incref(self, v):
        T = self.lltypemap(v)
        return self.pyobj_incref_expr(LOCALVAR % v.name, T)

    def pyobj_incref_expr(self, expr, T):
        return self.gcpolicy.pyobj_incref(expr, T)

    def pyobj_decref_expr(self, expr, T):
        return self.gcpolicy.pyobj_decref(expr, T)
            
    def push_alive(self, v):
        T = self.lltypemap(v)
        return self.gcpolicy.push_alive(LOCALVAR % v.name, T)

    def pop_alive(self, v, expr=None):
        T = self.lltypemap(v)
        return self.gcpolicy.pop_alive(expr or (LOCALVAR % v.name), T)

    def pop_alive_expr(self, expr, T):
        return self.gcpolicy.pop_alive(expr, T)


assert not USESLOTS or '__dict__' not in dir(FunctionCodeGenerator)
