import py

from pypy.rpython.memory import lladdress
from pypy.rpython import lltype

import struct

log = py.log.Producer("lltypesim")

primitive_to_fmt = {lltype.Signed:          "i",
                    lltype.Unsigned:        "I",
                    lltype.Char:            "c",
                    lltype.Bool:            "B",
                    }

#returns some sort of layout information that is useful for the simulatorptr
def get_layout(TYPE):
    layout = {}
    if isinstance(TYPE, lltype.Primitive):
        return primitive_to_fmt[TYPE]
    elif isinstance(TYPE, lltype.Ptr):
        return "P"
    elif isinstance(TYPE, lltype.Struct):
        curr = 0
        for name in TYPE._names:
            layout[name] = curr
            curr += get_fixed_size(TYPE._flds[name])
        layout["_size"] = curr
        return layout
    elif isinstance(TYPE, lltype.Array):
        return (get_fixed_size(lltype.Signed), get_fixed_size(TYPE.OF))
    elif isinstance(TYPE, lltype.OpaqueType):
        return "i"
    elif isinstance(TYPE, lltype.FuncType):
        return "i"
    elif isinstance(TYPE, lltype.PyObjectType):
        return "i"
    else:
        assert 0, "type %s not yet implemented" % (TYPE, )

def get_fixed_size(TYPE):
    if isinstance(TYPE, lltype.Primitive):
        if TYPE == lltype.Void:
            return 0
        return struct.calcsize(primitive_to_fmt[TYPE])
    elif isinstance(TYPE, lltype.Ptr):
        return struct.calcsize("P")
    elif isinstance(TYPE, lltype.Struct):
        return get_layout(TYPE)["_size"]
    elif isinstance(TYPE, lltype.Array):
        return get_fixed_size(lltype.Unsigned)
    elif isinstance(TYPE, lltype.OpaqueType):
        return get_fixed_size(lltype.Unsigned)
    elif isinstance(TYPE, lltype.FuncType):
        return get_fixed_size(lltype.Unsigned)
    elif isinstance(TYPE, lltype.PyObjectType):
        return get_fixed_size(lltype.Unsigned)
    assert 0, "not yet implemented"

def get_variable_size(TYPE):
    if isinstance(TYPE, lltype.Array):
        return get_fixed_size(TYPE.OF)
    elif isinstance(TYPE, lltype.Primitive):
        return 0
    elif isinstance(TYPE, lltype.Struct):
        if TYPE._arrayfld is not None:
            return get_variable_size(TYPE._flds[TYPE._arrayfld])
        else:
            return 0
    elif isinstance(TYPE, lltype.OpaqueType):
        return 0
    elif isinstance(TYPE, lltype.FuncType):
        return 0
    elif isinstance(TYPE, lltype.PyObjectType):
        return 0
    else:
        assert 0, "not yet implemented"

def get_total_size(TYPE, i=None):
    fixedsize = get_fixed_size(TYPE)
    varsize = get_variable_size(TYPE)
    if i is None:
        assert varsize == 0
        return fixedsize
    else:
        return fixedsize + i * varsize
    

def _expose(T, address):
    """XXX A nice docstring here"""
    if isinstance(T, (lltype.Struct, lltype.Array)):
        return simulatorptr(lltype.Ptr(T), address)
    elif T == lltype.Bool:
        return bool(address._load(primitive_to_fmt[T])[0])
    elif isinstance(T, lltype.Primitive):
        return address._load(primitive_to_fmt[T])[0]
    elif isinstance(T, lltype.Ptr):
        return simulatorptr(T, address.address[0])
    elif isinstance(T, lltype.PyObjectType):
        return simulatorptr(lltype.Ptr(T), address)
    else:
        assert 0, "not implemented yet"


# this class is intended to replace the _ptr class in lltype
# using the memory simulator
class simulatorptr(object):
    def __init__(self, TYPE, address):
        self.__dict__['_TYPE'] = TYPE
        self.__dict__['_T'] = TYPE.TO
        self.__dict__['_address'] = address
        self.__dict__['_layout'] = get_layout(TYPE.TO)

    def _zero_initialize(self, i=None):
        size = get_total_size(self._T, i)
        self._address._store("c" * size, *(["\x00"] * size))

    def _init_size(self, size):
        if isinstance(self._T, lltype.Array):
            self._address.signed[0] = size
        elif isinstance(self._T, lltype.Struct):
            if isinstance(self._T._flds[self._T._names[-1]], lltype.Array):
                addr = self._address + self._layout[self._T._arrayfld]
                addr.signed[0] = size
        else:
            assert size is None, "setting not implemented"

    def __getattr__(self, field_name):
        if isinstance(self._T, lltype.Struct):
            offset = self._layout[field_name]
            if field_name in self._T._flds:
                T = self._T._flds[field_name]
                base = self._layout[field_name]
                if isinstance(T, lltype.Primitive):
                    if T == lltype.Void:
                        return None
                    res = (self._address + offset)._load(primitive_to_fmt[T])[0]
                    if T == lltype.Bool:
                        res = bool(res)
                    return res
                elif isinstance(T, lltype.Ptr):
                    res = _expose(T.TO, (self._address + offset).address[0])
                    return res
                elif isinstance(T, lltype.ContainerType):
                    res = _expose(T, (self._address + offset))
                    return res
                else:
                    assert 0, "not implemented"
        raise AttributeError, ("%r instance has no field %r" % (self._T,
                                                                field_name))

    def __setattr__(self, field_name, value):
        if isinstance(self._T, lltype.Struct):
            if field_name in self._T._flds:
                T = self._T._flds[field_name]
                offset = self._layout[field_name]
                if isinstance(T, lltype.Primitive):
                    if T == lltype.Void:
                        return
                    (self._address + offset)._store(primitive_to_fmt[T], value)
                    return
                elif isinstance(T, lltype.Ptr):
                    assert value._TYPE == T
                    (self._address + offset).address[0] = value._address
                    return
                else:
                    assert 0, "not implemented"
        raise AttributeError, ("%r instance has no field %r" % (self._T,
                                                                field_name))

    def __getitem__(self, i):
        if isinstance(self._T, lltype.Array):
            if not (0 <= i < self._address.signed[0]):
                raise IndexError, "array index out of bounds"
            addr = self._address + self._layout[0] + i * self._layout[1]
            return _expose(self._T.OF, addr)
        raise TypeError("%r instance is not an array" % (self._T,))

    def __setitem__(self, i, value):
        if isinstance(self._T, lltype.Array):
            T1 = self._T.OF
            if isinstance(T1, lltype.ContainerType):
                s = "cannot directly assign to container array items"
                raise TypeError, s
            T2 = lltype.typeOf(value)
            if T2 != T1:
                raise TypeError("%r items:\n"
                                "expect %r\n"
                                "   got %r" % (self._T, T1, T2))
            if not (0 <= i < self._address.signed[0]):
                raise IndexError, "array index out of bounds"
            if isinstance(T2, lltype.Ptr):
                value = value._address.intaddress
            addr = self._address + self._layout[0] + i * self._layout[1]
            addr._store(get_layout(self._T.OF), value)
            return
        raise TypeError("%r instance is not an array" % (self._T,))

    def _getobj(self):
        assert isinstance(self._T, (lltype.FuncType, lltype.PyObjectType))
        return self._address.attached[0]
    _obj = property(_getobj)

    def __call__(self, *args):
        if isinstance(self._T, lltype.FuncType):
            if len(args) != len(self._T.ARGS):
                raise TypeError,"calling %r with wrong argument number: %r" % (self._T, args)
            for a, ARG in zip(args, self._T.ARGS):
                if lltype.typeOf(a) != ARG:
                    raise TypeError,"calling %r with wrong argument types: %r" % (self._T, args)
            callb = self._address.attached[0]._callable
            if callb is None:
                raise RuntimeError,"calling undefined function"
            return callb(*args)
        raise TypeError("%r instance is not a function" % (self._T,))


    def __len__(self):
        if isinstance(self._T, lltype.Array):
            return self._address.signed[0]
        raise TypeError("%r instance is not an array" % (self._T,))

    def __nonzero__(self):
        return self._address != lladdress.NULL

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if not isinstance(other, simulatorptr):
            raise TypeError("comparing pointer with %r object" % (
                type(other).__name__,))
        if self._TYPE != other._TYPE:
            raise TypeError("comparing %r and %r" % (self._TYPE, other._TYPE))
        return self._address == other._address

    def __repr__(self):
        return '<simulatorptr %s to %s>' % (self._TYPE.TO, self._address)


def cast_pointer(PTRTYPE, ptr):
    if not isinstance(ptr, simulatorptr) or not isinstance(PTRTYPE, lltype.Ptr):
        raise TypeError, "can only cast pointers to other pointers"
    CURTYPE = ptr._TYPE
    down_or_up = lltype.castable(PTRTYPE, CURTYPE)
    if down_or_up == 0:
        return ptr
    # XXX the lltype.cast_pointer does a lot of checks here:
    # I can't think of a way to do that with simulatorptr.
    # I'm not sure whether this is the right way to go...
    return simulatorptr(PTRTYPE, ptr._address)

# for now use the simulators raw_malloc
def malloc(T, n=None, immortal=False):
    fixedsize = get_fixed_size(T)
    varsize = get_variable_size(T)
    if n is None:
        if varsize:
            raise TypeError, "%r is variable-sized" % (T,)
        size = fixedsize
    else:
        size = fixedsize + n * varsize
    address = lladdress.raw_malloc(size)
    result = simulatorptr(lltype.Ptr(T), address)
    result._zero_initialize(n)
    result._init_size(n)
    return result

def nullptr(T):
    return simulatorptr(lltype.Ptr(T), lladdress.NULL)

#XXX unify attached objects with the address space as to samuele's suggestion
def functionptr(TYPE, name, **attrs):
    if not isinstance(TYPE, lltype.FuncType):
        raise TypeError, "functionptr() for FuncTypes only"
    try:
        hash(tuple(attrs.items()))
    except TypeError:
        raise TypeError("'%r' must be hashable"%attrs)
    addr = lladdress.raw_malloc(get_total_size(TYPE))
    addr.attached[0] = lltype._func(TYPE, _name=name, **attrs)
    return simulatorptr(lltype.Ptr(TYPE), addr)

def pyobjectptr(obj):
    addr = lladdress.raw_malloc(get_total_size(lltype.PyObject))
    addr.attached[0] = lltype._pyobject(obj)
    return simulatorptr(lltype.Ptr(lltype.PyObject), addr) 
