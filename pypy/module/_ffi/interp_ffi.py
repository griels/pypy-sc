
from pypy.interpreter.baseobjspace import W_Root, ObjSpace, Wrappable, \
     Arguments
from pypy.interpreter.error import OperationError, wrap_oserror
from pypy.interpreter.gateway import interp2app
from pypy.interpreter.typedef import TypeDef, GetSetProperty

from pypy.rlib.libffi import *
from pypy.rpython.lltypesystem import lltype, rffi
from pypy.rlib.unroll import unrolling_iterable

TYPEMAP = {
    # XXX A mess with unsigned/signed/normal chars :-/
    'c' : ffi_type_uchar,
    'b' : ffi_type_schar,
    'B' : ffi_type_uchar,
    'h' : ffi_type_sshort,
    'H' : ffi_type_ushort,
    'i' : ffi_type_sint,
    'I' : ffi_type_uint,
    'l' : ffi_type_slong,
    'L' : ffi_type_ulong,
    # XXX I'm not sure what is long long here, let's assume it's 64 bit :-/
    'q' : ffi_type_sint64,
    'Q' : ffi_type_uint64,
    'f' : ffi_type_float,
    'd' : ffi_type_double,
    's' : ffi_type_pointer,
    'p' : ffi_type_pointer,
    'P' : ffi_type_pointer,
}

LL_TYPEMAP = {
    'c' : rffi.CHAR,
    'b' : rffi.UCHAR,
    'B' : rffi.CHAR,
    'h' : rffi.SHORT,
    'H' : rffi.USHORT,
    'i' : rffi.INT,
    'I' : rffi.UINT,
    'l' : rffi.LONG,
    'L' : rffi.ULONG,
    'q' : rffi.LONGLONG,
    'Q' : rffi.ULONGLONG,
    'f' : rffi.FLOAT,
    'd' : rffi.DOUBLE,
    's' : rffi.CCHARP,
    'p' : rffi.CCHARP,
    'P' : rffi.VOIDP,    
}

class W_CDLL(Wrappable):
    def __init__(self, space, name):
        self.cdll = CDLL(name)
        self.name = name
        self.w_cache = space.newdict()
        self.space = space

    def get_type(self, key):
        space = self.space
        try:
            return TYPEMAP[key]
        except KeyError:
            raise OperationError(space.w_ValueError, space.wrap(
                "Uknown type letter %s" % key))

    def ptr(self, space, name, w_argtypes, restype):
        """ Get a pointer for function name with provided argtypes
        and restype
        """
        w = space.wrap
        w_argtypes = space.newtuple(space.unpackiterable(w_argtypes))
        w_key = space.newtuple([w(name), w_argtypes, w(restype)])
        try:
            return space.getitem(self.w_cache, w_key)
        except OperationError, e:
            if e.match(space, space.w_KeyError):
                pass
            else:
                raise
        argtypes_w = space.unpackiterable(w_argtypes)
        argtypes = [space.str_w(w_arg) for w_arg in argtypes_w]
        ffi_argtypes = [self.get_type(arg) for arg in argtypes]
        ffi_restype = self.get_type(restype)
        try:
            ptr = self.cdll.getpointer(name, ffi_argtypes, ffi_restype)
            w_funcptr = W_FuncPtr(ptr, argtypes, restype)
            space.setitem(self.w_cache, w_key, w_funcptr)
            return w_funcptr
        except KeyError:
            raise OperationError(space.w_AttributeError, space.wrap(
                "No symbol %s found in library %s" % (name, self.name)))
    ptr.unwrap_spec = ['self', ObjSpace, str, W_Root, str]

def descr_new_cdll(space, w_type, name):
    try:
        return space.wrap(W_CDLL(space, name))
    except OSError, e:
        raise wrap_oserror(space, e)
descr_new_cdll.unwrap_spec = [ObjSpace, W_Root, str]

W_CDLL.typedef = TypeDef(
    'CDLL',
    __new__     = interp2app(descr_new_cdll),
    ptr         = interp2app(W_CDLL.ptr),
    __doc__     = """ C Dynamically loaded library
use CDLL(libname) to create handle to C library (argument is processed the
same way as dlopen processes it). On such library call:
lib.ptr(func_name, argtype_list, restype)

where argtype_list is a list of single characters and restype is a single
character. Character meanings are more or less the same as in struct module,
except that s has trailing \x00 added, while p is considered a raw buffer.
"""
)

def pack_pointer(space, w_arg, ptr):
    arg = space.str_w(w_arg)
    ll_str = lltype.malloc(rffi.CCHARP.TO, len(arg), flavor='raw')
    for i in range(len(arg)):
        ll_str[i] = arg[i]
    ptr.push_arg(ll_str)
    return ll_str

def push_arg(space, ptr, argnum, argtype, w_arg, to_free, to_reconsider):
    w = space.wrap
    # XXX how to handle LONGLONG here?
    # they're probably long, so we'll not get them through int_w
    if argtype == "d" or argtype == "f":
        ptr.push_arg(space.float_w(w_arg))
    elif argtype == "s":
        ll_str = rffi.str2charp(space.str_w(w_arg))
        ptr.push_arg(ll_str)
        to_free.append(ll_str)
    elif argtype == "p":
        # check for NULL ptr
        if space.is_w(w_arg, space.w_None):
            ptr.push_arg(lltype.nullptr(rffi.VOIDP.TO))
        elif space.is_true(space.isinstance(w_arg, space.w_basestring)):
            to_free.append(pack_pointer(space, w_arg, ptr))
        else:
            mod = space.getbuiltinmodule('_ffi')
            w_StructureInstance = space.getattr(mod, w('StructureInstance'))
            if space.is_true(space.isinstance(w_arg, w_StructureInstance)):
                w_pack = space.getattr(w_arg, w('pack'))
                w_res = space.call(w_pack, space.newtuple([]))
                size = space.int_w(space.len(w_res))
                ll_ptr = pack_pointer(space, w_res, ptr)
                to_reconsider.append((argnum, ll_ptr, size))
            else:
                raise OperationError(space.w_TypeError, w(
                    "Expected structure, array or simple type"))
    elif argtype == "c" or argtype == "b" or argtype == "B":
        ptr.push_arg(space.str_w(w_arg))
    else:
        assert argtype in ["iIhHlLqQ"]
        ptr.push_arg(space.int_w(w_arg))

ll_typemap_iter = unrolling_iterable(LL_TYPEMAP.items())

def repack_struct(space, w_struct, value, size):
    w_unpack = space.getattr(w_struct, space.wrap('unpack'))
    # ARGH! too much copying!
    x = "".join([value[i] for i in range(size)])
    space.call(w_unpack, space.newtuple([space.wrap(x)]))

class W_FuncPtr(Wrappable):
    def __init__(self, ptr, argtypes, restype):
        self.ptr = ptr
        self.restype = restype
        self.argtypes = argtypes

    def call(self, space, arguments):
        args_w, kwds_w = arguments.unpack()
        # C has no keyword arguments
        if kwds_w:
            raise OperationError(space.w_TypeError, space.wrap(
                "Provided keyword arguments for C function call"))
        to_free = []
        to_reconsider = []
        i = 0
        for argtype, w_arg in zip(self.argtypes, args_w):
            push_arg(space, self.ptr, i, argtype, w_arg, to_free, to_reconsider)
            i += 1
        try:
            for c, ll_type in ll_typemap_iter:
                if self.restype == c:
                    if c == 's' or c == 'p':
                        return space.wrap(rffi.charp2str(self.ptr.call(rffi.CCHARP)))
                    elif c == 'P':
                        res = self.ptr.call(rffi.VOIDP)
                        return space.wrap(lltype.cast_ptr_to_int(res))
                    elif c == 'q' or c == 'Q' or c == 'L':
                        return space.newlong(self.ptr.call(ll_type))
                    else:
                        return space.wrap(self.ptr.call(ll_type))
        finally:
            for elem in to_free:
                lltype.free(elem, flavor='raw')
            for num, value, size in to_reconsider:
                repack_struct(space, args_w[num], value, size)
                lltype.free(value, flavor='raw')
    call.unwrap_spec = ['self', ObjSpace, Arguments]

W_FuncPtr.typedef = TypeDef(
    'FuncPtr',
    __call__ = interp2app(W_FuncPtr.call)
)
