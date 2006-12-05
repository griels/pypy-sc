import os
from ctypes import POINTER, cast, c_char, c_void_p, CFUNCTYPE, c_int
from ri386 import I386CodeBuilder

# ____________________________________________________________


modname = 'pypy.jit.codegen.i386.codebuf_' + os.name
memhandler = __import__(modname, globals(), locals(), ['__doc__'])

PTR = memhandler.PTR


class CodeBlockOverflow(Exception):
    pass

class InMemoryCodeBuilder(I386CodeBuilder):
    _last_dump_start = 0

    def __init__(self, start, end):
        map_size = end - start
        res = c_void_p(start)
        data = cast(res, POINTER(c_char * map_size))
        self._init(data, map_size)

    def _init(self, data, map_size):
        self._data = data
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

    def execute(self, arg1, arg2):
        # XXX old testing stuff
        fnptr = cast(self._data, binaryfn)
        return fnptr(arg1, arg2)

    def done(self):
        # normally, no special action is needed here
        if machine_code_dumper.enabled:
            machine_code_dumper.dump(self)


class MachineCodeDumper:
    enabled = True
    log_fd = -1

    def dump(self, cb):
        if self.log_fd < 0:
            # check the environment for a file name
            from pypy.rlib.ros import getenv
            s = getenv('PYPYJITLOG')
            if not s:
                self.enabled = False
                return
            try:
                flags = os.O_WRONLY|os.O_CREAT|os.O_TRUNC
                self.log_fd = os.open(s, flags, 0666)
            except OSError:
                os.write(2, "could not create log file\n")
                self.enabled = False
                return
        self.dump_range(cb, cb._last_dump_start, cb._pos)
        cb._last_dump_start = cb._pos

    def dump_range(self, cb, start, end):
        HEX = '0123456789ABCDEF'
        dump = []
        for p in range(start, end):
            o = ord(cb._data.contents[p])
            dump.append(HEX[o >> 4])
            dump.append(HEX[o & 15])
            if (p & 3) == 3:
                dump.append(':')
        line = 'CODE_DUMP @%x +%d  %s\n' % (cb.tell() - cb._pos,
                                            start, ''.join(dump))
        os.write(self.log_fd, line)

machine_code_dumper = MachineCodeDumper()


class MachineCodeBlock(InMemoryCodeBuilder):

    def __init__(self, map_size):
        res = memhandler.alloc(map_size)
        data = cast(res, POINTER(c_char * map_size))
        self._init(data, map_size)

    def __del__(self):
        memhandler.free(cast(self._data, PTR), self._size)

binaryfn = CFUNCTYPE(c_int, c_int, c_int)    # for testing

# ____________________________________________________________

from pypy.rpython.lltypesystem import lltype

BUF = lltype.GcArray(lltype.Char)

class LLTypeMachineCodeBlock(I386CodeBuilder):
    # for testing only

    class State:
        pass
    state = State()
    state.base = 1

    def __init__(self, map_size):
        self._size = map_size
        self._pos = 0
        self._data = lltype.malloc(BUF, map_size)
        self._base = LLTypeMachineCodeBlock.state.base
        LLTypeMachineCodeBlock.state.base += 2 * map_size

    def write(self, data):
        p = self._pos
        if p + len(data) > self._size:
            raise CodeBlockOverflow
        for c in data:
            self._data[p] = c
            p += 1
        self._pos = p

    def tell(self):
        return self._base + 2 * self._pos

    def done(self):
        pass
