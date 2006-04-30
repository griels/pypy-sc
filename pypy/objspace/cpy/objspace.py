from pypy.objspace.cpy.capi import *
from pypy.annotation.pairtype import pair
from pypy.interpreter import baseobjspace
from pypy.interpreter.error import OperationError


class CPyObjSpace(baseobjspace.ObjSpace):
    from pypy.objspace.cpy.ctypes_base import W_Object

    def initialize(self):
        self.options.geninterp = True
        self.w_int   = W_Object(int)
        self.w_None  = W_Object(None)
        self.w_False = W_Object(False)
        self.w_True  = W_Object(True)
        self.w_type  = W_Object(type)
        self.w_Exception     = W_Object(Exception)
        self.w_StopIteration = W_Object(StopIteration)
        self.w_TypeError     = W_Object(TypeError)
        self.wrap_cache = {}
        self.rev_wrap_cache = {}

    def _freeze_(self):
        return True

    def getbuiltinmodule(self, name):
        return PyImport_ImportModule(name)

    def wrap(self, x):
        if isinstance(x, baseobjspace.Wrappable):
            x = x.__spacebind__(self)
            if isinstance(x, baseobjspace.Wrappable):
                try:
                    return self.wrap_cache[x]
                except KeyError:
                    import pypy.objspace.cpy.wrappable
                    result = pair(self, x).wrap()
                    self.wrap_cache[x] = result
                    self.rev_wrap_cache[id(result)] = result, x
                    return result
        if x is None:
            return self.w_None
        if isinstance(x, int):
            return PyInt_FromLong(x)
        if isinstance(x, str):
            return PyString_FromStringAndSize(x, len(x))
        raise TypeError("wrap(%r)" % (x,))
    wrap._annspecialcase_ = "specialize:wrap"

    def unwrap(self, w_obj):
        assert isinstance(w_obj, W_Object)
        return w_obj.value

    def finditem(self, w_obj, w_key):
        try:
            return self.getitem(w_obj, w_key)
        except KeyError:   # XXX think about OperationError
            return None

    def interpclass_w(self, w_obj):
        try:
            return self.rev_wrap_cache[id(w_obj)][1]
        except KeyError:
            return None

    # __________ operations with a direct CPython equivalent __________

    getattr = staticmethod(PyObject_GetAttr)
    getitem = staticmethod(PyObject_GetItem)
    setitem = staticmethod(PyObject_SetItem)
    int_w   = staticmethod(PyInt_AsLong)
    str_w   = staticmethod(PyString_AsString)
    iter    = staticmethod(PyObject_GetIter)

    add     = staticmethod(PyNumber_Add)
    sub     = staticmethod(PyNumber_Subtract)

    def call_function(self, w_callable, *args_w):
        args_w += (None,)
        return PyObject_CallFunctionObjArgs(w_callable, *args_w)

    def call_args(self, w_callable, args):
        args_w, kwds_w = args.unpack()
        w_args = self.newtuple(args_w)
        w_kwds = self.newdict([(self.wrap(key), w_value)
                               for key, w_value in kwds_w.items()])
        return PyObject_Call(w_callable, w_args, w_kwds)

    def new_interned_str(self, s):
        w_s = self.wrap(s)
        PyString_InternInPlace(byref(w_s))
        return w_s

    def newint(self, intval):
        return PyInt_FromLong(intval)

    def newdict(self, items_w):
        w_dict = PyDict_New()
        for w_key, w_value in items_w:
            PyDict_SetItem(w_dict, w_key, w_value)
        return w_dict

    def newlist(self, items_w):
        w_list = PyList_New(0)
        for w_item in items_w:
            # XXX inefficient but:
            #       PyList_SetItem steals a ref so it's harder to use
            #       PySequence_SetItem crashes if it replaces a NULL item
            PyList_Append(w_list, w_item)
        return w_list

    def newtuple(self, items_w):
        # XXX not very efficient, but PyTuple_SetItem steals a ref
        w_list = self.newlist(items_w)
        return PySequence_Tuple(w_list)

    def lt(self, w1, w2): return PyObject_RichCompare(w1, w2, Py_LT)
    def le(self, w1, w2): return PyObject_RichCompare(w1, w2, Py_LE)
    def eq(self, w1, w2): return PyObject_RichCompare(w1, w2, Py_EQ)
    def ne(self, w1, w2): return PyObject_RichCompare(w1, w2, Py_NE)
    def gt(self, w1, w2): return PyObject_RichCompare(w1, w2, Py_GT)
    def ge(self, w1, w2): return PyObject_RichCompare(w1, w2, Py_GE)

    def lt_w(self, w1, w2): return PyObject_RichCompareBool(w1, w2, Py_LT) != 0
    def le_w(self, w1, w2): return PyObject_RichCompareBool(w1, w2, Py_LE) != 0
    def eq_w(self, w1, w2): return PyObject_RichCompareBool(w1, w2, Py_EQ) != 0
    def ne_w(self, w1, w2): return PyObject_RichCompareBool(w1, w2, Py_NE) != 0
    def gt_w(self, w1, w2): return PyObject_RichCompareBool(w1, w2, Py_GT) != 0
    def ge_w(self, w1, w2): return PyObject_RichCompareBool(w1, w2, Py_GE) != 0

    def is_w(self, w1, w2):
        return w1.value is w2.value   # XXX any idea not involving SomeObjects?
    is_w.allow_someobjects = True

    def is_(self, w1, w2):
        return self.newbool(self.is_w(w1, w2))

    def next(self, w_obj):
        w_res = PyIter_Next(w_obj)
        if not w_res:
            raise OperationError(self.w_StopIteration, self.w_None)
        return w_res
