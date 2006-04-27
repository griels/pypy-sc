from pypy.interpreter.error import OperationError
from pypy.interpreter.pyopcode import PyInterpFrame
from pypy.interpreter import function, pycode, pyframe
from pypy.interpreter.baseobjspace import Wrappable
from pypy.interpreter.mixedmodule import MixedModule

class Cell(Wrappable):
    "A simple container for a wrapped value."
    
    def __init__(self, w_value=None):
        self.w_value = w_value

    def clone(self):
        return self.__class__(self.w_value)

    def empty(self):
        return self.w_value is None

    def get(self):
        if self.w_value is None:
            raise ValueError, "get() from an empty cell"
        return self.w_value

    def set(self, w_value):
        self.w_value = w_value

    def delete(self):
        if self.w_value is None:
            raise ValueError, "delete() on an empty cell"
        self.w_value = None
  
    def descr__eq__(self, space, w_other):
        other = space.interpclass_w(w_other)
        if not isinstance(other, Cell):
            return space.w_False
        return space.eq(self.w_value, other.w_value)    
        
    def descr__reduce__(self, space):
        w_mod    = space.getbuiltinmodule('_pickle_support')
        mod      = space.interp_w(MixedModule, w_mod)
        cell_new = mod.get('cell_new')
        if self.w_value is None:    #when would this happen?
            return space.newtuple([cell_new, space.newtuple([])])
        return space.newtuple([cell_new, space.newtuple([]),
            space.newtuple([self.w_value])])

    def descr__setstate__(self, space, w_state):
        self.w_value = space.getitem(w_state, space.wrap(0))
        
    def __repr__(self):
        """ representation for debugging purposes """
        if self.w_value is None:
            content = ""
        else:
            content = repr(self.w_value)
        return "<%s(%s) at 0x%x>" % (self.__class__.__name__,
                                     content, id(self))


class PyNestedScopeFrame(PyInterpFrame):
    """This class enhances a standard frame with nested scope abilities,
    i.e. handling of cell/free variables."""

    # Cell Vars:
    #     my local variables that are exposed to my inner functions
    # Free Vars:
    #     variables coming from a parent function in which i'm nested
    # 'closure' is a list of Cell instances: the received free vars.

    def __init__(self, space, code, w_globals, closure):
        PyInterpFrame.__init__(self, space, code, w_globals, closure)
        ncellvars = len(code.co_cellvars)
        nfreevars = len(code.co_freevars)
        if closure is None:
            if nfreevars:
                raise OperationError(space.w_TypeError,
                                     space.wrap("directly executed code object "
                                                "may not contain free variables"))
            closure = []
        else:
            if len(closure) != nfreevars:
                raise ValueError("code object received a closure with "
                                 "an unexpected number of free variables")
        self.cells = [Cell() for i in range(ncellvars)] + closure

    def getclosure(self):
        ncellvars = len(self.pycode.co_cellvars)  # not part of the closure
        return self.cells[ncellvars:]

    def fast2locals(self):
        PyInterpFrame.fast2locals(self)
        # cellvars are values exported to inner scopes
        # freevars are values coming from outer scopes 
        freevarnames = self.pycode.co_cellvars + self.pycode.co_freevars
        for i in range(len(freevarnames)):
            name = freevarnames[i]
            cell = self.cells[i]
            try:
                w_value = cell.get()
            except ValueError:
                pass
            else:
                w_name = self.space.wrap(name)
                self.space.setitem(self.w_locals, w_name, w_value)

    def locals2fast(self):
        PyInterpFrame.locals2fast(self)
        freevarnames = self.pycode.co_cellvars + self.pycode.co_freevars
        for i in range(len(freevarnames)):
            name = freevarnames[i]
            cell = self.cells[i]
            w_name = self.space.wrap(name)
            try:
                w_value = self.space.getitem(self.w_locals, w_name)
            except OperationError, e:
                if not e.match(self.space, self.space.w_KeyError):
                    raise
            else:
                cell.set(w_value)

    def init_cells(self):
        args_to_copy = self.pycode._args_as_cellvars
        for i in range(len(args_to_copy)):
            argnum = args_to_copy[i]
            self.cells[i] = Cell(self.fastlocals_w[argnum])

    def getfreevarname(self, index):
        freevarnames = self.pycode.co_cellvars + self.pycode.co_freevars
        return freevarnames[index]

    def iscellvar(self, index):
        # is the variable given by index a cell or a free var?
        return index < len(self.pycode.co_cellvars)

    ### extra opcodes ###

    def LOAD_CLOSURE(f, varindex):
        # nested scopes: access the cell object
        cell = f.cells[varindex]
        w_value = f.space.wrap(cell)
        f.valuestack.push(w_value)

    def LOAD_DEREF(f, varindex):
        # nested scopes: access a variable through its cell object
        cell = f.cells[varindex]
        try:
            w_value = cell.get()
        except ValueError:
            varname = f.getfreevarname(varindex)
            if f.iscellvar(varindex):
                message = "local variable '%s' referenced before assignment"%varname
                w_exc_type = f.space.w_UnboundLocalError
            else:
                message = ("free variable '%s' referenced before assignment"
                           " in enclosing scope"%varname)
                w_exc_type = f.space.w_NameError
            raise OperationError(w_exc_type, f.space.wrap(message))
        else:
            f.valuestack.push(w_value)

    def STORE_DEREF(f, varindex):
        # nested scopes: access a variable through its cell object
        w_newvalue = f.valuestack.pop()
        #try:
        cell = f.cells[varindex]
        #except IndexError:
        #    import pdb; pdb.set_trace()
        #    raise
        cell.set(w_newvalue)

    def MAKE_CLOSURE(f, numdefaults):
        w_codeobj = f.valuestack.pop()
        codeobj = f.space.interp_w(pycode.PyCode, w_codeobj)
        if codeobj.magic >= 0xa0df281:    # CPython 2.5 AST branch merge
            w_freevarstuple = f.valuestack.pop()
            freevars = [f.space.interp_w(Cell, cell)
                        for cell in f.space.unpacktuple(w_freevarstuple)]
        else:
            nfreevars = len(codeobj.co_freevars)
            freevars = [f.space.interp_w(Cell, f.valuestack.pop())
                        for i in range(nfreevars)]
            freevars.reverse()
        defaultarguments = [f.valuestack.pop() for i in range(numdefaults)]
        defaultarguments.reverse()
        fn = function.Function(f.space, codeobj, f.w_globals,
                               defaultarguments, freevars)
        f.valuestack.push(f.space.wrap(fn))
