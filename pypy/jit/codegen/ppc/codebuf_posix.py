import pypy.rpython.rctypes.implementation  # register rctypes types
from pypy.rpython.rctypes.tool import ctypes_platform
from pypy.rpython.rctypes.tool.libc import libc
from ctypes import POINTER, c_char, c_int

class CConfig:
    _includes_ = ("sys/types.h", "sys/mman.h")
    size_t = ctypes_platform.SimpleType("size_t", c_int)
    off_t = ctypes_platform.SimpleType("off_t", c_int)

    MAP_PRIVATE   = ctypes_platform.DefinedConstantInteger("MAP_PRIVATE")
    MAP_ANON      = ctypes_platform.DefinedConstantInteger("MAP_ANON")
    MAP_ANONYMOUS = ctypes_platform.DefinedConstantInteger("MAP_ANONYMOUS")
    PROT_READ     = ctypes_platform.DefinedConstantInteger("PROT_READ")
    PROT_WRITE    = ctypes_platform.DefinedConstantInteger("PROT_WRITE")
    PROT_EXEC     = ctypes_platform.DefinedConstantInteger("PROT_EXEC")

globals().update(ctypes_platform.configure(CConfig))
if MAP_ANONYMOUS is None:
    MAP_ANONYMOUS = MAP_ANON
    assert MAP_ANONYMOUS is not None
del MAP_ANON

# ____________________________________________________________

PTR = POINTER(c_char)    # cannot use c_void_p as return value of functions :-(

mmap_ = libc.mmap
mmap_.argtypes = [PTR, size_t, c_int, c_int, c_int, off_t]
mmap_.restype = PTR
mmap_.includes = ("sys/mman.h",)
munmap_ = libc.munmap
munmap_.argtypes = [PTR, size_t]
munmap_.restype = c_int
munmap_.includes = ("sys/mman.h",)

def alloc(map_size):
    flags = MAP_PRIVATE | MAP_ANONYMOUS
    prot = PROT_EXEC | PROT_READ | PROT_WRITE
    res = mmap_(PTR(), map_size, prot, flags, -1, 0)
    if not res:
        raise MemoryError
    return res

free = munmap_
