class ExceptionPolicy:
    RINGBUGGER_SIZE          = 8192
    RINGBUFFER_ENTRY_MAXSIZE = 16
    RINGBUGGER_OVERSIZE      = RINGBUGGER_SIZE + RINGBUFFER_ENTRY_MAXSIZE
    RINGBUFFER_LLVMCODE      = '''
internal fastcc sbyte* %%malloc_exception(uint %%nbytes) {
    %%cond = setle uint %%nbytes, %d
    br bool %%cond, label %%then, label %%else

then:
    %%tmp.3 = load uint* %%exception_ringbuffer_index
    %%tmp.4 = getelementptr [%d x sbyte]* %%exception_ringbuffer, int 0, uint %%tmp.3
    %%tmp.6 = add uint %%tmp.3, %%nbytes
    %%tmp.7 = and uint %%tmp.6, %d
    store uint %%tmp.7, uint* %%exception_ringbuffer_index
    ret sbyte* %%tmp.4

else:
    %%tmp.8  = call ccc sbyte* %%GC_malloc(uint %%nbytes)
    ret sbyte* %%tmp.8
}
''' % (RINGBUFFER_ENTRY_MAXSIZE, RINGBUGGER_OVERSIZE, RINGBUGGER_SIZE-1)

    def __init__(self):
        raise Exception, 'ExceptionPolicy should not be used directly'

    def transform(self, translator, graph=None):
        return

    def _noresult(self, returntype):
        r = returntype.strip()
        if r == 'void':
            return 'void'
        elif r == 'bool':
            return 'bool false'
        elif r in 'float double'.split():
            return r + ' 0.0'
        elif r in 'ubyte sbyte ushort short uint int ulong long'.split():
            return r + ' 0'
        return r + ' null'

    def _nonoderesult(self, node):
        decl = node.getdecl()
        returntype, name = decl.split(' ', 1)
        noresult = self._noresult(returntype)
        return noresult

    def new(exceptionpolicy=None):  #factory
        exceptionpolicy = exceptionpolicy or 'explicit'
        if exceptionpolicy == 'invokeunwind':
            from pypy.translator.js.exception import InvokeUnwindExceptionPolicy
            exceptionpolicy = InvokeUnwindExceptionPolicy()
        elif exceptionpolicy == 'explicit':
            from pypy.translator.js.exception import ExplicitExceptionPolicy
            exceptionpolicy = ExplicitExceptionPolicy()
        elif exceptionpolicy == 'none':
            from pypy.translator.js.exception import NoneExceptionPolicy
            exceptionpolicy = NoneExceptionPolicy()
        else:
            raise Exception, 'unknown exceptionpolicy: ' + str(exceptionpolicy)
        return exceptionpolicy
    new = staticmethod(new)


class NoneExceptionPolicy(ExceptionPolicy): #XXX untested
    def __init__(self):
        pass


class InvokeUnwindExceptionPolicy(ExceptionPolicy):  #uses issubclass() and llvm invoke&unwind
    def __init__(self):
        pass

    def llvmcode(self, entrynode):
        returntype, entrypointname =  entrynode.getdecl().split('%', 1)
        noresult = self._noresult(returntype)
        return '''
ccc %(returntype)s%%__entrypoint__%(entrypointname)s {
    %%result = invoke %(returntype)s%%%(entrypointname)s to label %%no_exception except label %%exception

no_exception:
    store %%RPYTHON_EXCEPTION_VTABLE* null, %%RPYTHON_EXCEPTION_VTABLE** %%last_exception_type
    ret %(returntype)s %%result

exception:
    ret %(noresult)s
}

ccc int %%__entrypoint__raised_LLVMException() {
    %%tmp    = load %%RPYTHON_EXCEPTION_VTABLE** %%last_exception_type
    %%result = cast %%RPYTHON_EXCEPTION_VTABLE* %%tmp to int
    ret int %%result
}

internal fastcc void %%unwind() {
    unwind
}
''' % locals() + self.RINGBUFFER_LLVMCODE

    def invoke(self, codewriter, targetvar, returntype, functionref, args, label, except_label):
        labels = 'to label %%%s except label %%%s' % (label, except_label)
        if returntype == 'void':
            codewriter.llvm('invoke void %s(%s) %s' % (functionref, args, labels))
        else:
            codewriter.llvm('%s = invoke %s %s(%s) %s' % (targetvar, returntype, functionref, args, labels))

    def _is_raise_new_exception(self, db, graph, block):
        from pypy.objspace.flow.model import mkentrymap
        is_raise_new = False
        entrylinks = mkentrymap(graph)[block]
        entrylinks = [x for x in entrylinks if x.prevblock is not None]
        inputargs = db.repr_arg_multi(block.inputargs)
        for i, arg in enumerate(inputargs):
            names = db.repr_arg_multi([link.args[i] for link in entrylinks])
            for name in names:  #These tests-by-name are a bit yikes, but I don't see a better way right now
                if not name.startswith('%last_exception_') and not name.startswith('%last_exc_value_'):
                    is_raise_new = True
        return is_raise_new

    def write_exceptblock(self, funcnode, codewriter, block):
        assert len(block.inputargs) == 2

        db    = funcnode.db
        graph = funcnode.graph

        if self._is_raise_new_exception(db, graph, block):
            funcnode.write_block_phi_nodes(codewriter, block)

            inputargs     = db.repr_arg_multi(block.inputargs)
            inputargtypes = db.repr_arg_type_multi(block.inputargs)

            codewriter.store(inputargtypes[0], inputargs[0], '%last_exception_type')
            codewriter.store(inputargtypes[1], inputargs[1], '%last_exception_value')
        else:
            codewriter.comment('reraise last exception')
            #Reraising last_exception.
            #Which is already stored in the global variables.
            #So nothing needs to happen here!

        codewriter.llvm('unwind')

    def fetch_exceptions(self, codewriter, exc_found_labels, lltype_of_exception_type, lltype_of_exception_value):
        for label, target, last_exc_type_var, last_exc_value_var in exc_found_labels:
            codewriter.label(label)
            if last_exc_type_var:    
                codewriter.load(last_exc_type_var, lltype_of_exception_type, '%last_exception_type')
            if last_exc_value_var:   
                codewriter.load(last_exc_value_var, lltype_of_exception_value, '%last_exception_value')
            codewriter.br_uncond(target)

    def reraise(self, funcnode, codewriter):
        codewriter.comment('reraise when exception is not caught')
        codewriter.llvm('unwind')

    def llc_options(self):
        return '-enable-correct-eh-support'


class ExplicitExceptionPolicy(ExceptionPolicy):    #uses issubclass() and last_exception tests after each call
    def __init__(self):
        self.invoke_count = 0

    def llvmcode(self, entrynode):
        returntype, entrypointname = entrynode.getdecl().split('%', 1)
        noresult = self._noresult(returntype)
        return '''
ccc %(returntype)s%%__entrypoint__%(entrypointname)s {
    store %%RPYTHON_EXCEPTION_VTABLE* null, %%RPYTHON_EXCEPTION_VTABLE** %%last_exception_type
    %%result = call %(returntype)s%%%(entrypointname)s
    %%tmp    = load %%RPYTHON_EXCEPTION_VTABLE** %%last_exception_type
    %%exc    = seteq %%RPYTHON_EXCEPTION_VTABLE* %%tmp, null
    br bool %%exc, label %%no_exception, label %%exception

no_exception:
    ret %(returntype)s %%result

exception:
    ret %(noresult)s
}

ccc int %%__entrypoint__raised_LLVMException() {
    %%tmp    = load %%RPYTHON_EXCEPTION_VTABLE** %%last_exception_type
    %%result = cast %%RPYTHON_EXCEPTION_VTABLE* %%tmp to int
    ret int %%result
}

internal fastcc void %%unwind() {
    ret void
}
''' % locals() + self.RINGBUFFER_LLVMCODE

    def transform(self, translator, graph=None):
        from pypy.translator.llvm.backendopt.exception import create_exception_handling
        if graph:
            create_exception_handling(translator, graph)
        else:
            for graph in translator.flowgraphs.itervalues():
                create_exception_handling(translator, graph)
            #translator.view()

    def invoke(self, codewriter, targetvar, returntype, functionref, args, label, except_label):
        if returntype == 'void':
            if functionref != '%keepalive': #XXX I think keepalive should not be the last operation here!
                codewriter.append('call void %s(%s)' % (functionref, args))
        else:
            codewriter.llvm('%s = call %s %s(%s)' % (targetvar, returntype, functionref, args))
        tmp = '%%invoke.tmp.%d' % self.invoke_count
        exc = '%%invoke.exc.%d' % self.invoke_count
        self.invoke_count += 1
        codewriter.llvm('%(tmp)s = load %%RPYTHON_EXCEPTION_VTABLE** %%last_exception_type' % locals())
        codewriter.llvm('%(exc)s = seteq %%RPYTHON_EXCEPTION_VTABLE* %(tmp)s, null'         % locals())
        codewriter.llvm('br bool %(exc)s, label %%%(label)s, label %%%(except_label)s'      % locals())

    def write_exceptblock(self, funcnode, codewriter, block):
        assert len(block.inputargs) == 2

        noresult = self._nonoderesult(funcnode)

        funcnode.write_block_phi_nodes(codewriter, block)

        inputargs     = funcnode.db.repr_arg_multi(block.inputargs)
        inputargtypes = funcnode.db.repr_arg_type_multi(block.inputargs)

        codewriter.store(inputargtypes[0], inputargs[0], '%last_exception_type')
        codewriter.store(inputargtypes[1], inputargs[1], '%last_exception_value')
        codewriter.llvm('ret ' + noresult)

    def fetch_exceptions(self, codewriter, exc_found_labels, lltype_of_exception_type, lltype_of_exception_value):
        for label, target, last_exc_type_var, last_exc_value_var in exc_found_labels:
            codewriter.label(label)
            if last_exc_type_var:    
                codewriter.load(last_exc_type_var, lltype_of_exception_type, '%last_exception_type')
            if last_exc_value_var:   
                codewriter.load(last_exc_value_var, lltype_of_exception_value, '%last_exception_value')
            codewriter.store(lltype_of_exception_type , 'null', '%last_exception_type')
            codewriter.store(lltype_of_exception_value, 'null', '%last_exception_value')
            codewriter.br_uncond(target)

    def reraise(self, funcnode, codewriter):
        noresult = self._nonoderesult(funcnode)
        codewriter.llvm('ret ' + noresult)

    def llc_options(self):
        return ''
