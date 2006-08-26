import mmap
from pypy.module.mmap import interp_mmap
from ctypes import *
from ri386 import AbstractCodeBuilder

libcmmap   = interp_mmap.libc.mmap
libcmunmap = interp_mmap.libc.munmap
libcmemcpy = interp_mmap.libc.memcpy

binaryfn = CFUNCTYPE(c_int, c_int, c_int)


class CodeBlockOverflow(Exception):
    pass

class MachineCodeBlock(AbstractCodeBuilder):

    def __init__(self, map_size):
        flags = mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS
        prot = mmap.PROT_EXEC | mmap.PROT_READ | mmap.PROT_WRITE
        res = libcmmap(c_void_p(), map_size, prot, flags, -1, 0)
        if not res:
            raise MemoryError
        self._data = cast(res, POINTER(c_char * map_size))
        self._size = map_size
        self._pos = 0

    def write(self, data):
         p = self._pos
         if p + len(data) > self._size:
             raise CodeBlockOverflow
         for c in data:
             self._data.contents[p] = c
             p += 1
         self._pos = p

    def tell(self):
        baseaddr = cast(self._data, c_void_p).value
        return baseaddr + self._pos

    def __del__(self):
        libcmunmap(cast(self._data, c_void_p), self._size)

    def execute(self, arg1, arg2):
        fnptr = cast(self._data, binaryfn)
        return fnptr(arg1, arg2)

from pypy.rpython.lltypesystem import lltype

BUF = lltype.GcArray(lltype.Char)

class LLTypeMachineCodeBlock(AbstractCodeBuilder):

    def __init__(self, map_size):
        self._size = map_size
        self._pos = 0
        self._data = lltype.malloc(BUF, map_size)

    def write(self, data):
        p = self._pos
        if p + len(data) > self._size:
            raise CodeBlockOverflow
        for c in data:
            self._data[p] = c
            p += 1
        self._pos = p

    def tell(self):
        return self._pos
