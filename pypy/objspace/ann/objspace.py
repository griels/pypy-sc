import sys
import operator

import pypy
from pypy.interpreter.baseobjspace \
     import ObjSpace, OperationError, NoValue, PyPyError
from pypy.interpreter.pycode import PyByteCode
from pypy.interpreter.extmodule import PyBuiltinCode
from pypy.objspace.ann.cloningcontext import CloningExecutionContext
from pypy.objspace.ann.cloningcontext import HelperExecutionContext
from pypy.objspace.ann.cloningcontext import IndeterminateCondition

from pypy.objspace.ann.wrapper import *



class AnnException(Exception):
    pass

class UnwrapException(AnnException):
    pass


class AnnotationObjSpace(ObjSpace):

    def initialize(self):
        self.bytecodecache = {}
        self.wrappercache = {}
        self.w_None = self.wrapboot(None)
        self.w_True = self.wrapboot(True)
        self.w_False = self.wrapboot(False)
        self.w_NotImplemented = self.wrapboot(NotImplemented)
        self.w_Ellipsis = self.wrapboot(Ellipsis)
        import __builtin__, types
        for n, c in __builtin__.__dict__.iteritems():
            if isinstance(c, types.TypeType) or isinstance(c, types.ClassType):
                setattr(self, 'w_'+n, self.wrap(c))
        self.make_builtins()
        self.make_sys()

    # Service methods whose interface is in the abstract base class

    def wrapboot(self, obj):
        # Wrapper around wrap() to initialize the wrappercache
        w_obj = self.wrap(obj)
        self.wrappercache[obj] = (obj, w_obj)
        return w_obj

    def wrap(self, obj):
        if isinstance(obj, W_Object):
            raise TypeError("already wrapped: " + repr(obj))
        try:
            if obj in self.wrappercache:
                key, w_obj = self.wrappercache[obj]
                if obj is key:
                    return w_obj
        except (TypeError, AttributeError):
            # This can happen when obj is not hashable, for instance
            # XXX What about other errors???
            pass
        return W_Constant(obj)

    def unwrap(self, w_obj):
        if isinstance(w_obj, W_Object):
            return w_obj.unwrap()
        else:
            raise TypeError("not wrapped: " + repr(w_obj))

    def reraise(self):
        t, v = sys.exc_info()[:2]
        raise OperationError(self.wrap(t), self.wrap(v))

    def is_true(self, w_obj):
        if w_obj.force is not None:
            force = w_obj.force
            w_obj.force = None
            return force # Forced by cloning machinery
        if isinstance(w_obj, W_KnownKeysContainer):
            return bool(len(w_obj))
        try:
            obj = self.unwrap(w_obj)
        except UnwrapException:
            pass
        else:
            return bool(obj)
        # It's indeterminate!!!
        # Raise an exception that will clone the interpreter.
        raise IndeterminateCondition(w_obj)

    def createexecutioncontext(self):
        return CloningExecutionContext(self)

    def gethelperspace(self):
        return HelperObjSpace()

    # Specialized creators whose interface is in the abstract base class
    
    def newtuple(self, args_w):
        for w_arg in args_w:
            if not isinstance(w_arg, W_Constant):
                return W_KnownKeysContainer(args_w)
        return self.wrap(tuple(map(self.unwrap, args_w)))

    def newdict(self, items_w):
        d = {}
        for w_key, w_value in items_w:
            try:
                key = self.unwrap(w_key)
                value = self.unwrap(w_value)
            except UnwrapException:
                break
            else:
                d[key] = value
        else:
            # All keys and values were unwrappable
            return self.wrap(d)
        # It's not quite constant.
        # Maybe the keys are constant?
        values_w = {}
        for w_key, w_value in items_w:
            try:
                key = self.unwrap(w_key)
            except UnwrapException:
                break
            else:
                values_w[key] = w_value
        else:
            return W_KnownKeysContainer(values_w)
        return W_Anything()

    def newmodule(self, w_name):
        return W_Module(w_name, self.w_None)

    def newfunction(self, code, w_globals, w_defaults, w_closure=None):
        if isinstance(code, PyBuiltinCode):
            return W_BuiltinFunction(code, w_defaults)
        if isinstance(code, PyByteCode):
            return W_PythonFunction(code, w_globals, w_defaults, w_closure)
        return W_Anything()

    def newlist(self, list_w):
        unwrappedlist = []
        try:
            for w_obj in list_w:
                obj = self.unwrap(w_obj)
                unwrappedlist.append(obj)
        except UnwrapException:
            return W_Anything()
        else:
            return self.wrap(unwrappedlist)

    def newstring(self, listofwrappedints):
        unwrappedints = []
        try:
            for w_i in listofwrappedints:
                i = self.unwrap(w_i)
                unwrappedints.append(i)
        except UnwrapException:
            return W_Anything()
        else:
            try:
                result = "".join(map(chr, unwrappedints))
            except:
                self.reraise()
            else:
                return self.wrap(result)

    def newslice(self, w_start, w_stop, w_end=None):
        try:
            if w_start is None:
                start = None
            else:
                start = self.unwrap(w_start)
            if w_stop is None:
                stop = None
            else:
                stop = self.unwrap(w_stop)
            if w_end is None:
                end = None
            else:
                end = self.unwrap(w_end)
        except UnwrapException:
            return W_Anything() # W_Slice()???
        else:
            return self.wrap(slice(start, stop, end))

    # Methods implementing Python operations
    # (Many missing ones are added by make_op() below)

    def str(self, w_left):
        if isinstance(w_left, W_Constant):
            try:
                result = str(w_left.value)
            except:
                self.reraise()
            else:
                return self.wrap(result)
        else:
            return W_Anything()

    def is_(self, w_left, w_right):
        if w_left is w_right:
            return self.w_True
        if isinstance(w_left, W_Constant) and isinstance(w_right, W_Constant):
            # XXX Is this really correct?
            if w_left.value is w_right.value:
                return self.w_True
            else:
                return self.w_False
        return W_Integer()

    def add(self, w_left, w_right):
        try:
            left = self.unwrap(w_left)
            right = self.unwrap(w_right)
        except UnwrapException:
            pass
        else:
            try:
                result = left + right
            except:
                self.reraise()
            else:
                return self.wrap(result)
        if is_int(w_left) and is_int(w_right):
            return W_Integer()
        else:
            return W_Anything()

    inplace_add = add # XXX Not quite right!

    def sub(self, w_left, w_right):
        try:
            left = self.unwrap(w_left)
            right = self.unwrap(w_right)
        except UnwrapException:
            pass
        else:
            try:
                result = left - right
            except:
                self.reraise()
            else:
                return self.wrap(result)
        if is_int(w_left) and is_int(w_right):
            return W_Integer()
        else:
            return W_Anything()

    def mul(self, w_left, w_right):
        try:
            left = self.unwrap(w_left)
            right = self.unwrap(w_right)
        except UnwrapException:
            pass
        else:
            try:
                result = left * right
            except:
                self.reraise()
            else:
                return self.wrap(result)
        if is_int(w_left) and is_int(w_right):
            return W_Integer()
        else:
            return W_Anything()

    def iter(self, w_iterable):
        # XXX Should return an actual iterable, so that
        # (1) if a true constant, a loop using next() will work correctly
        #     (e.g. unpackiterable())
        # (2) otherwise, we can at least unify the result types for next()
        if isinstance(w_iterable, W_Constant):
            value = w_iterable.value
            if isinstance(value, list):
                return W_ConstantIterator(value)
            try:
                it = iter(value)
            except:
                self.reraise()
        return W_Anything()

    def next(self, w_iterator):
        if w_iterator.force is not None:
            force = w_iterator.force
            w_iterator.force = None
            if force:
                return W_Anything()
            else:
                raise NoValue
        if isinstance(w_iterator, W_ConstantIterator):
            try:
                value = w_iterator.next()
            except StopIteration:
                raise NoValue
            else:
                return self.wrap(value)
        raise IndeterminateCondition(w_iterator)

    def call(self, w_func, w_args, w_kwds):
        # XXX Need to move this (or most of it) into the W_*Function classes
        w_closure = None
        if isinstance(w_func, W_BuiltinFunction):
            bytecode = w_func.code
            w_defaults = w_func.w_defaults
            w_globals = self.w_None
        elif isinstance(w_func, W_PythonFunction):
            bytecode = w_func.code
            w_defaults = w_func.w_defaults
            w_closure = w_func.w_closure
            w_globals = w_func.w_globals
        else:
            try:
                func = self.unwrap(w_func)
            except UnwrapException:
                return W_Anything()
            try:
                code = func.func_code
            except AttributeError:
                # Hmmm...  A built-in funtion?  Call it if constant args.
                try:
                    args = self.unwrap(w_args)
                    kwds = self.unwrap(w_kwds)
                except UnwrapException:
                    return W_Anything()
                else:
                    try:
                        result = func(*args, **kwds)
                    except:
                        self.reraise()
                    else:
                        w_result = self.wrap(result)
                        return w_result
            bytecode = self.bytecodecache.get(code)
            if bytecode is None:
                bytecode = PyByteCode()
                bytecode._from_code(code)
                self.bytecodecache[code] = bytecode
            w_defaults = self.wrap(func.func_defaults)
            w_globals = self.wrap(func.func_globals)
        if w_closure is None:
            w_closure = self.wrap(())
        w_locals = bytecode.build_arguments(self, w_args, w_kwds,
                                            w_defaults, w_closure)
        w_result = bytecode.eval_code(self, w_globals, w_locals)
        return w_result

    def getattr(self, w_obj, w_name):
        if isinstance(w_obj, W_Module) and isinstance(w_name, W_Constant):
            name = self.unwrap(w_name)
            try:
                return w_obj.getattr(name)
            except KeyError:
                raise OperationError(self.wrap(AttributeError),
                                     self.wrap(AttributeError(name)))
        try:
            obj = self.unwrap(w_obj)
            name = self.unwrap(w_name)
        except UnwrapException:
            return W_Anything()
        else:
            try:
                result = getattr(obj, name)
            except:
                return self.reraise()
            else:
                return self.wrap(result)

    def setattr(self, w_obj, w_name, w_value):
        if isinstance(w_obj, W_Module) and isinstance(w_name, W_Constant):
            name = self.unwrap(w_name)
            w_obj.setattr(name, w_value)
            return
        # Space setattr shouldn't return anything, so no w_None here

    def setitem(self, w_obj, w_key, w_value):
        if isinstance(w_key, W_Constant):
            key = self.unwrap(w_key)
            if isinstance(w_obj, W_KnownKeysContainer):
                try:
                    w_obj[key] = w_value
                except:
                    self.reraise()
                return
            elif (isinstance(w_obj, W_Constant) and
                  isinstance(w_value, W_Constant)):
                try:
                    w_obj[key] = self.unwrap(w_value)
                except:
                    self.reraise()
                return
        # XXX What if isinstance(w_obj, W_Constant) ???
        # XXX Otherwise, how to record the side effect?

    def len(self, w_obj):
        if isinstance(w_obj, W_KnownKeysContainer):
            return self.wrap(len(w_obj))
        try:
            obj = self.unwrap(w_obj)
        except UnwrapException:
            return W_Anything()
        else:
            try:
                result = len(obj)
            except:
                self.reraise()
            else:
                return self.wrap(result)

    def getitem(self, w_obj, w_key):
        try:
            key = self.unwrap(w_key)
        except UnwrapException:
            return W_Anything()
        try:
            obj = self.unwrap(w_obj)
        except UnwrapException:
            if isinstance(w_obj, W_KnownKeysContainer):
                try:
                    return w_obj[key]
                except:
                    return self.reraise()
            else:
                return W_Anything()
        try:
            result = obj[key]
        except:
            self.reraise()
        else:
            return self.wrap(result)

class HelperObjSpace(AnnotationObjSpace):

    def __init__(self):
        self.ec = None
        AnnotationObjSpace.__init__(self)

    def getexecutioncontext(self):
        if self.ec is None:
            self.ec = self.createexecutioncontext()
        return self.ec

    def createexecutioncontext(self):
        return HelperExecutionContext(self)

def make_op(name, symbol, arity, specialnames):

    if hasattr(AnnotationObjSpace, name):
        return # Shouldn't do it

    op = getattr(operator, name, None)
    if not op:
        return # Can't do it

    def generic_operator(self, *args_w):
        assert len(args_w) == arity, name+" got the wrong number of arguments"
        args = []
        for w_arg in args_w:
            try:
                arg = self.unwrap(w_arg)
            except UnwrapException:
                break
            else:
                args.append(arg)
        else:
            # All arguments are constants: call the operator now
            try:
                result = op(*args)
            except:
                self.reraise()
            else:
                return self.wrap(result)

        return W_Anything()

    setattr(AnnotationObjSpace, name, generic_operator)

for line in ObjSpace.MethodTable:
    make_op(*line)

call_level = 0
