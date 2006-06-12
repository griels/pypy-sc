from pypy.objspace.cpy.capi import *
from pypy.objspace.cpy.refcount import Py_Incref
from pypy.interpreter import baseobjspace
from pypy.interpreter.error import OperationError
from pypy.interpreter.function import Function
from pypy.interpreter.typedef import GetSetProperty
from pypy.rpython.rarithmetic import r_uint


class CPyObjSpace(baseobjspace.ObjSpace):
    from pypy.objspace.cpy.ctypes_base import W_Object

    def initialize(self):
        self.options.geninterp = False
        self.w_int   = W_Object(int)
        self.w_tuple = W_Object(tuple)
        self.w_str   = W_Object(str)
        self.w_unicode = W_Object(unicode)
        self.w_None  = W_Object(None)
        self.w_False = W_Object(False)
        self.w_True  = W_Object(True)
        self.w_type  = W_Object(type)
        self.w_Exception     = W_Object(Exception)
        self.w_StopIteration = W_Object(StopIteration)
        self.w_TypeError     = W_Object(TypeError)
        self.w_KeyError      = W_Object(KeyError)
        self.wrap_cache = {}

    def _freeze_(self):
        return True

    def getbuiltinmodule(self, name):
        return PyImport_ImportModule(name)

    def wrap(self, x):
        if isinstance(x, baseobjspace.Wrappable):
            x = x.__spacebind__(self)
            # special cases
            if isinstance(x, Function):
                from pypy.objspace.cpy.function import FunctionCache
                return self.fromcache(FunctionCache).getorbuild(x)
            if isinstance(x, GetSetProperty):
                from pypy.objspace.cpy.property import PropertyCache
                return self.fromcache(PropertyCache).getorbuild(x)
            # normal case
            from pypy.objspace.cpy.typedef import rpython2cpython
            return rpython2cpython(self, x)
        if x is None:
            return self.w_None
        if isinstance(x, int):
            return PyInt_FromLong(x)
        if isinstance(x, str):
            return PyString_FromStringAndSize(x, len(x))
        if isinstance(x, float): 
            return PyFloat_FromDouble(x)
        if isinstance(x, r_uint):
            return PyLong_FromUnsignedLong(x)
        # if we arrive here during RTyping, then the problem is *not* the %r
        # in the format string, but it's that someone is calling space.wrap()
        # on a strange object.
        raise TypeError("wrap(%r)" % (x,))
    wrap._annspecialcase_ = "specialize:wrap"

    def unwrap(self, w_obj):
        assert isinstance(w_obj, W_Object)
        return w_obj.value

    def interpclass_w(self, w_obj):
        "NOT_RPYTHON."
        from pypy.objspace.cpy.typedef import cpython2rpython_raw
        return cpython2rpython_raw(self, w_obj)

    def interp_w(self, RequiredClass, w_obj, can_be_None=False):
        """
	 Unwrap w_obj, checking that it is an instance of the required internal
	 interpreter class (a subclass of Wrappable).
	"""
	if can_be_None and self.is_w(w_obj, self.w_None):
	    return None
        from pypy.objspace.cpy.typedef import cpython2rpython
        return cpython2rpython(self, RequiredClass, w_obj)
    interp_w._annspecialcase_ = 'specialize:arg(1)'

    # __________ operations with a direct CPython equivalent __________

    getattr = staticmethod(PyObject_GetAttr)
    getitem = staticmethod(PyObject_GetItem)
    setitem = staticmethod(PyObject_SetItem)
    int_w   = staticmethod(PyInt_AsLong)
    uint_w  = staticmethod(PyInt_AsUnsignedLongMask)
    float_w = staticmethod(PyFloat_AsDouble)
    iter    = staticmethod(PyObject_GetIter)
    type    = staticmethod(PyObject_Type)
    str     = staticmethod(PyObject_Str)
    repr    = staticmethod(PyObject_Repr)

    add     = staticmethod(PyNumber_Add)
    sub     = staticmethod(PyNumber_Subtract)

    def len(self, w_obj):
        return self.wrap(PyObject_Size(w_obj))

    def str_w(self, w_obj):
        # XXX inefficient
        p = PyString_AsString(w_obj)
        length = PyString_Size(w_obj)
        buf = create_string_buffer(length)
        for i in range(length):
            buf[i] = p[i]
        return buf.raw

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

    def newstring(self, bytes_w):
        length = len(bytes_w)
        buf = ctypes.create_string_buffer(length)
        for i in range(length):
            buf[i] = chr(self.int_w(bytes_w[i]))
        return PyString_FromStringAndSize(buf, length)

    def newunicode(self, codes):
        # XXX inefficient
        lst = [PyUnicode_FromOrdinal(code) for code in codes]
        w_lst = self.newlist(lst)
        w_emptyunicode = PyUnicode_FromUnicode(None, 0)
        return self.call_method(w_emptyunicode, 'join', w_lst)

    def newint(self, intval):
        return PyInt_FromLong(intval)

    def newdict(self, items_w):
        w_dict = PyDict_New()
        for w_key, w_value in items_w:
            PyDict_SetItem(w_dict, w_key, w_value)
        return w_dict

    def newlist(self, items_w):
        n = len(items_w)
        w_list = PyList_New(n)
        for i in range(n):
            w_item = items_w[i]
            Py_Incref(w_item)
            PyList_SetItem(w_list, i, w_item)
        return w_list

    def newtuple(self, items_w):
        # XXX not very efficient, but PyTuple_SetItem complains if the
        # refcount of the tuple is not exactly 1
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

    def is_true(self, w_obj):
        return PyObject_IsTrue(w_obj) != 0

    def issubtype(self, w_type1, w_type2):
        if PyType_IsSubtype(w_type1, w_type2):
            return self.w_True
        else:
            return self.w_False

    def ord(self, w_obj):
        w_type = self.type(w_obj)
        if self.is_true(self.issubtype(w_type, self.w_str)):
            length = PyObject_Size(w_obj)
            if length == 1:
                s = self.str_w(w_obj)
                return self.wrap(ord(s[0]))
            errtype = 'string of length %d' % length
        elif self.is_true(self.issubtype(w_type, self.w_unicode)):
            length = PyObject_Size(w_obj)
            if length == 1:
                p = PyUnicode_AsUnicode(w_obj)
                return self.wrap(p[0])
            errtype = 'unicode string of length %d' % length
        else:
            errtype = self.str_w(self.getattr(w_type, self.wrap('__name__')))
        msg = 'expected a character, but %s found' % errtype
        raise OperationError(self.w_TypeError, self.wrap(msg))

    def exec_(self, statement, w_globals, w_locals, hidden_applevel=False):
        "NOT_RPYTHON"
        from types import CodeType
        if not isinstance(statement, (str, CodeType)):
            raise TypeError("CPyObjSpace.exec_(): only for CPython code objs")
        exec statement in w_globals.value, w_locals.value
