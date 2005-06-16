from pypy.rpython.lltype import * 
from pypy.rpython.lltype import _ptr
from pypy.objspace.flow.model import Constant, last_exception
import py

class RPythonError(Exception):
    pass

class LLInterpreter(object): 
    """ low level interpreter working with concrete values. """ 
#    log = py.log.Producer('llinterp') 

    def __init__(self, flowgraphs, typer): 
        self.flowgraphs = flowgraphs 
        self.bindings = {}
        self.typer = typer

    # _______________________________________________________
    # variable setters/getters helpers 
    
    def fillvars(self, block, values): 
        vars = block.inputargs 
        assert len(vars) == len(values), (
                   "block %s received %d args, expected %d" % (
                    block, len(values), len(vars)))
        for var, val in zip(vars, values): 
            self.setvar(var, val) 
        
    def setvar(self, var, val): 
        # XXX assert that val "matches" lowlevel type 
        self.bindings[var] = val 

    def getval(self, varorconst): 
        try: 
            return varorconst.value
        except AttributeError: 
            return self.bindings[varorconst]

    # _______________________________________________________
    # other helpers 
    def getoperationhandler(self, opname): 
        try: 
            return getattr(self, 'op_' + opname) 
        except AttributeError: 
            g = globals()
            assert opname in g, (
                    "cannot handle operation %r yet" %(opname,))
            ophandler = g[opname]
            return ophandler

    # _______________________________________________________
    # evaling functions 

    def eval_function(self, func, args=()): 
        graph = self.flowgraphs[func]
        return self.eval_graph(graph,args)

    def eval_graph(self, graph, args=()): 
        nextblock = graph.startblock
        while 1: 
            self.fillvars(nextblock, args) 
            nextblock, args = self.eval_block(nextblock) 
            if nextblock is None: 
                return args 

    def eval_block(self, block): 
        """ return (nextblock, values) tuple. If nextblock 
            is None, values is the concrete return value. 
        """
        catch_exception = block.exitswitch == Constant(last_exception)
        e = None

        for op in block.operations:
            try:
                self.eval_operation(op)
            except RPythonError, e:
                assert catch_exception, 'exception received, but not expected'

        # determine nextblock and/or return value 
        if len(block.exits) == 0:
            # return block
            if len(block.inputargs) == 2:
                # exception
                etypevar, evaluevar = block.getvariables()
                etype = self.getval(etypevar)
                evalue = self.getval(evaluevar)
                # watch out, these are _ptr's
                raise RPythonError(etype, evalue)
            resultvar, = block.getvariables()
            result = self.getval(resultvar) 
#            self.log.operation("returning", result) 
            return None, result 
        elif block.exitswitch is None:
            # single-exit block
            assert len(block.exits) == 1
            link = block.exits[0]
        elif catch_exception:
            link = block.exits[0]
            if e:
                exdata = self.typer.getexceptiondata()
                cls, inst = e.args
                for link in block.exits[1:]:
                    assert issubclass(link.exitcase, Exception)
                    if exdata.ll_exception_match(cls, link.llexitcase):
                        self.setvar(link.last_exception, cls)
                        self.setvar(link.last_exc_value, inst)
                        return link.target, [cls, inst]
                else:
                    raise Exception, e # unhandled case, should not happen"
        else: 
            index = self.getval(block.exitswitch)
            link = block.exits[index]
        return link.target, [self.getval(x) for x in link.args]
    
    def eval_operation(self, operation): 
#        self.log.operation("considering", operation) 
        ophandler = self.getoperationhandler(operation.opname) 
        vals = [self.getval(x) for x in operation.args]
        # if these special cases pile up, do something better here
        if operation.opname == 'cast_pointer':
            vals.insert(0, operation.result.concretetype)
        retval = ophandler(*vals) 
        self.setvar(operation.result, retval)

    # __________________________________________________________
    # misc LL operation implementations 

    def op_same_as(self, x): 
        return x

    def op_setfield(self, obj, fieldname, fieldvalue): 
        # obj should be pointer 
        setattr(obj, fieldname, fieldvalue) # is that right?  -- yes
    
    def op_direct_call(self, f, *args):
        # XXX the logic should be:
        #       if f._obj has a graph attribute, interpret
        #       that graph without looking at _callable
        if hasattr(f._obj, 'graph'):
            return self.eval_graph(f._obj.graph, args)
        return self.eval_function(f._obj._callable, args)

    def op_malloc(self, obj):
        return malloc(obj)
    
    def op_getfield(self, obj, field):
        # assert: obj should be pointer
        result = getattr(obj, field)
        # check the difference between op_getfield and op_getsubstruct:
        # the former returns the real field, the latter a pointer to it
        assert typeOf(result) == getattr(typeOf(obj).TO, field)
        return result

    def op_getsubstruct(self, obj, field):
        # assert: obj should be pointer
        result = getattr(obj, field)
        # check the difference between op_getfield and op_getsubstruct:
        # the former returns the real field, the latter a pointer to it
        assert typeOf(result) == Ptr(getattr(typeOf(obj).TO, field))
        return result

    def op_malloc_varsize(self, obj, size):
        return malloc(obj, size)

    def op_getarraysubstruct(self, array, index):
        assert isinstance(array, _ptr)
        
        return array[index]
        # the diff between op_getarrayitem and op_getarraysubstruct
        # is the same as between op_getfield and op_getsubstruct

    def op_getarraysize(self,array):
        #print array,type(array),dir(array)
        return len(array)
    
    def op_cast_pointer(self, tp, obj):
        # well, actually this is what's now in the globals.
        return cast_pointer(tp, obj)
# __________________________________________________________
# primitive operations 
from pypy.objspace.flow.operation import FunctionByName 
opimpls = FunctionByName.copy()
opimpls['is_true'] = bool 

for typ in (float, int): 
    typname = typ.__name__
    for opname in ('add', 'sub', 'mul', 'div', 'gt', 'lt', 
                   'ge', 'ne', 'le', 'eq'): 
        assert opname in opimpls 
        exec py.code.Source("""
            def %(typname)s_%(opname)s(x, y): 
                assert isinstance(x, %(typname)s)
                assert isinstance(y, %(typname)s)
                func = opimpls[%(opname)r]
                return func(x, y) 
        """ % locals()).compile()
    for opname in 'is_true',: 
        assert opname in opimpls 
        exec py.code.Source("""
            def %(typname)s_%(opname)s(x): 
                assert isinstance(x, %(typname)s)
                func = opimpls[%(opname)r]
                return func(x) 
        """ % locals()).compile()

