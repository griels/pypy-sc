import pypy.interpreter.appfile
from pypy.interpreter.baseobjspace import *
from multimethod import *


##################################################################

class StdObjSpace(ObjSpace):
    """The standard object space, implementing a general-purpose object
    library in Restricted Python."""

    PACKAGE_PATH = 'objspace.std'

    class AppFile(pypy.interpreter.appfile.AppFile):
        pass
    AppFile.LOCAL_PATH = [PACKAGE_PATH]

    def initialize(self):
        from noneobject    import W_NoneObject
        from boolobject    import W_BoolObject
        from cpythonobject import W_CPythonObject
        self.w_None  = W_NoneObject()
        self.w_False = W_BoolObject(False)
        self.w_True  = W_BoolObject(True)
        # hack in the exception classes
        import __builtin__, types
        for n, c in __builtin__.__dict__.iteritems():
            if isinstance(c, types.ClassType) and issubclass(c, Exception):
                w_c = W_CPythonObject(c)
                setattr(self, 'w_' + c.__name__, w_c)

    def wrap(self, x):
        "Wraps the Python value 'x' into one of the wrapper classes."
        if isinstance(x, int):
            import intobject
            return intobject.W_IntObject(x)
        if isinstance(x, str):
            import stringobject
            return stringobject.W_StringObject(x)
        if isinstance(x, float):
            import floatobject
            return floatobject.W_FloatObject(x)
        if isinstance(x, tuple):
            wrappeditems = [self.wrap(item) for item in x]
            import tupleobject
            return tupleobject.W_TupleObject(wrappeditems)
        raise TypeError, "don't know how to wrap instances of %s" % type(x)

    def newtuple(self, list_w):
        import tupleobject
        return tupleobject.W_TupleObject(list_w)

    def newlist(self, list_w):
        import listobject
        return listobject.W_ListObject(list_w)

    def newdict(self, list_pairs_w):
        import dictobject
        return dictobject.W_DictObject(list_pairs_w)

    def newslice(self, w_start, w_end, w_step):
        # w_step may be a real None
        import sliceobject
        return sliceobject.W_SliceObject(w_start, w_end, w_step)

    def newfunction(self, w_code, w_globals, w_defaultarguments, w_closure=None):
        import funcobject
        return funcobject.W_FuncObject(w_code, w_globals,
                                       w_defaultarguments, w_closure)

    def newbool(self, b):
        if b:
            return self.w_True
        else:
            return self.w_False

    # special multimethods
    unwrap  = MultiMethod('unwrap', 1)   # returns an unwrapped object
    hash    = MultiMethod('hash', 1)     # returns an unwrapped int
    is_true = MultiMethod('true?', 1)    # returns an unwrapped bool
    compare = MultiMethod('compare', 2)  # extra 3rd arg is a Python string

    # handling of the common fall-back cases
    def compare_any_any(self, w_1, w_2, operation):
        if operation == "is":
            return self.newbool(w_1 == w_2)
        elif operation == "is not":
            return self.newbool(w_1 != w_2)
        else:
            raise FailedToImplement(self.w_TypeError,
                                    "unknown comparison operator %r" % operation)
        
    compare.register(compare_any_any, W_ANY, W_ANY)


# add all regular multimethods to StdObjSpace
for _name, _symbol, _arity in ObjSpace.MethodTable:
    setattr(StdObjSpace, _name, MultiMethod(_symbol, _arity))
