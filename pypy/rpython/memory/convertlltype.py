import autopath
from pypy.rpython.memory import lladdress
from pypy.rpython.memory.lltypesimulation import simulatorptr, get_total_size
from pypy.rpython.memory.lltypesimulation import get_fixed_size
from pypy.rpython.memory.lltypesimulation import get_variable_size
from pypy.rpython.memory.lltypesimulation import primitive_to_fmt
from pypy.rpython.memory.lltypesimulation import get_layout
from pypy.objspace.flow.model import traverse, Link, Constant, Block
from pypy.objspace.flow.model import Constant
from pypy.rpython import lltype

import struct

class LLTypeConverter(object):
    def __init__(self, address):
        self.converted = {}
        self.curraddress = address

    def convert(self, val_or_ptr, inline_to_addr=None):
        TYPE = lltype.typeOf(val_or_ptr)
        if isinstance(TYPE, lltype.Primitive):
            if inline_to_addr is not None:
                inline_to_addr._store(primitive_to_fmt[TYPE], val_or_ptr)
            return val_or_ptr
        elif isinstance(TYPE, lltype.Array):
            return self.convert_array(val_or_ptr, inline_to_addr)
        elif isinstance(TYPE, lltype.Struct):
            return self.convert_struct(val_or_ptr, inline_to_addr)
        elif isinstance(TYPE, lltype.Ptr):
            return self.convert_pointer(val_or_ptr, inline_to_addr)
        elif isinstance(TYPE, lltype.OpaqueType):
            return self.convert_object(val_or_ptr, inline_to_addr)
        elif isinstance(TYPE, lltype.FuncType):
            return self.convert_object(val_or_ptr, inline_to_addr)
        elif isinstance(TYPE, lltype.PyObjectType):
            return self.convert_object(val_or_ptr, inline_to_addr)
        else:
            assert 0, "don't know about %s" % (val_or_ptr, )

    def convert_array(self, _array, inline_to_addr):
        if _array in self.converted:
            address = self.converted[_array]
            assert inline_to_addr is None or address == inline_to_addr
            return address
        TYPE = lltype.typeOf(_array)
        arraylength = len(_array.items)
        size = get_total_size(TYPE, arraylength)
        if inline_to_addr is not None:
            startaddr = inline_to_addr
        else:
            startaddr = self.curraddress
        self.converted[_array] = startaddr
        startaddr.signed[0] = arraylength
        curraddr = startaddr + get_fixed_size(TYPE)
        varsize = get_variable_size(TYPE)
        self.curraddress += size
        for item in _array.items:
            self.convert(item, curraddr)
            curraddr += varsize
        return startaddr

    def convert_struct(self, _struct, inline_to_addr):
        if _struct in self.converted:
            address = self.converted[_struct]
            assert inline_to_addr is None or address == inline_to_addr
            return address
        TYPE = lltype.typeOf(_struct)
        layout = get_layout(TYPE)
        if TYPE._arrayfld is not None:
            inlinedarraylength = len(getattr(_struct, TYPE._arrayfld).items)
            size = get_total_size(TYPE, inlinedarraylength)
        else:
            size = get_total_size(TYPE)
        if inline_to_addr is not None:
            startaddr = inline_to_addr
        else:
            startaddr = self.curraddress
        self.converted[_struct] = startaddr
        self.curraddress += size
        for name in TYPE._flds:
            addr = startaddr + layout[name]
            self.convert(getattr(_struct, name), addr)
        return startaddr

    def convert_pointer(self, _ptr, inline_to_addr):
        TYPE = lltype.typeOf(_ptr)
        if _ptr._obj is not None:
            addr = self.convert(_ptr._obj)
        else:
            addr = lladdress.NULL
        assert isinstance(addr, lladdress.Address)
        if inline_to_addr is not None:
            inline_to_addr.address[0] = addr
        return simulatorptr(TYPE, addr)

    def convert_object(self, _obj, inline_to_addr):
        if inline_to_addr is not None:
            inline_to_addr.attached[0] = _obj
            return inline_to_addr
        else:
            addr = self.curraddress
            addr.attached[0] = _obj
            self.curraddress += struct.calcsize("i")
            return addr

