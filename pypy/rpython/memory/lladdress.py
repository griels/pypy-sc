import struct
from pypy.rpython import lltype
from pypy.rpython.memory.simulator import MemorySimulator
from pypy.rpython.rarithmetic import r_uint


class Address(object):
    def __new__(cls, intaddress=0):
        if intaddress == 0:
            null = cls.__dict__.get("NULL")
            if null is not None:
                return null
            cls.NULL = object.__new__(cls)
            return cls.NULL
        else:
            return object.__new__(cls)

    def __init__(self, intaddress=0):
        self.intaddress = intaddress

    def _getintattr(self): #needed to make _accessor easy
        return self.intaddress

    def __add__(self, offset):
        assert isinstance(offset, int)
        return Address(self.intaddress + offset)

    def __sub__(self, other):
        if isinstance(other, int):
            return Address(self.intaddress - other)
        else:
            return self.intaddress - other.intaddress

    def __cmp__(self, other):
        return cmp(self.intaddress, other.intaddress)

    def __repr__(self):
        return "<addr: %s>" % self.intaddress
class _accessor(object):
    def __init__(self, addr):
        self.intaddress = addr.intaddress
    def __getitem__(self, offset):
        result = simulator.getstruct(self.format,
                                     self.intaddress + offset * self.size)
        return self.convert_from(result[0])

    def __setitem__(self, offset, value):
        simulator.setstruct(self.format, self.intaddress + offset * self.size,
                            self.convert_to(value))
           
class _signed_accessor(_accessor):
    format = "i"
    size = struct.calcsize("i")
    convert_from = int
    convert_to = int

class _unsigned_accessor(_accessor):
    format = "I"
    size = struct.calcsize("I")
    convert_from = r_uint
    convert_to = long

class _char_accessor(_accessor):
    format = "c"
    size = struct.calcsize("c")
    convert_from = str
    convert_to = str

class _address_accessor(_accessor):
    format = "P"
    size = struct.calcsize("P")
    convert_from = Address
    convert_to = Address._getintattr

Address.signed = property(_signed_accessor)
Address.unsigned = property(_unsigned_accessor)
Address.char = property(_char_accessor)
Address.address = property(_address_accessor)


NULL = Address()
simulator = MemorySimulator()

def raw_malloc(size):
    return Address(simulator.malloc(size))

def raw_free(addr):
    simulator.free(addr.intaddress)

def raw_memcopy(addr1, addr2, size):
    pass


supported_access_types = {"signed":    lltype.Signed,
                          "unsigned":  lltype.Unsigned,
                          "char":      lltype.Char,
                          "address":   Address,
                          }
