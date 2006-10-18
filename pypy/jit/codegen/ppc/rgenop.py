from pypy.jit.codegen.model import AbstractRGenOp, CodeGenBlock, CodeGenerator
from pypy.jit.codegen.model import GenVar, GenConst
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.objectmodel import specialize

class VarLocation(object):
    pass

class RegisterLocation(VarLocation):
    def __init__(self, reg):
        self.reg = reg
    def load(self, builder):
        return self.reg
    def spill(self, builder):
        XXX
    def __repr__(self):
        return '$r%s'%(self.reg,)

class StackLocation(VarLocation):
    def __init__(self, offset):
        self.offset = offset
    def load(self, builder):
        XXX
    def spill(self, builder):
        XXX
    def __repr__(self):
        return 'stack+%s'%(self.offset,)

class Var(GenVar):

    def __init__(self, location):
        self.location = location

    def load(self, builder):
        return self.location.load(builder)

    def spill(self, builder):
        return self.location.spill(builder)

    def reg(self):
        assert isinstance(self.location, RegisterLocation)
        return self.location.reg

    def __repr__(self):
        return 'var@%r' % (self.location,)

class IntConst(GenConst):

    def __init__(self, value):
        self.value = value

    def load(self, builder):
        reg = builder.newvar().reg()
        builder.asm.load_word(reg, self.value)
        return reg

    @specialize.arg(1)
    def revealconst(self, T):
        if isinstance(T, lltype.Ptr):
            return lltype.cast_int_to_ptr(T, self.value)
        elif T is llmemory.Address:
            return llmemory.cast_int_to_adr(self.value)
        else:
            return lltype.cast_primitive(T, self.value)

    def __repr__(self):
        return "const=%r" % (self.value,)


from pypy.jit.codegen.ppc import codebuf_posix as memhandler
from ctypes import POINTER, cast, c_char, c_void_p, CFUNCTYPE, c_int

class CodeBlockOverflow(Exception):
    pass

from pypy.translator.asm.ppcgen.rassemblermaker import make_rassembler
from pypy.translator.asm.ppcgen.ppc_assembler import MyPPCAssembler

RPPCAssembler = make_rassembler(MyPPCAssembler)

def emit(self, value):
    self.mc.write(value)
RPPCAssembler.emit = emit

class MachineCodeBlock:

    def __init__(self, map_size):
        assert map_size % 4 == 0
        res = memhandler.alloc(map_size)
        self._data = cast(res, POINTER(c_int * (map_size / 4)))
        self._size = map_size/4
        self._pos = 0

    def write(self, data):
         p = self._pos
         if p >= self._size:
             raise CodeBlockOverflow
         self._data.contents[p] = data
         self._pos = p + 1

    def tell(self):
        baseaddr = cast(self._data, c_void_p).value
        return baseaddr + self._pos * 4

    def __del__(self):
        memhandler.free(cast(self._data, memhandler.PTR), self._size * 4)

##     def execute(self, arg1, arg2):
##         fnptr = cast(self._data, binaryfn)
##         return fnptr(arg1, arg2)

## binaryfn = CFUNCTYPE(c_int, c_int, c_int)    # for testing

class Block(CodeGenBlock):

    def __init__(self, startaddr, arg_locations):
        self.startaddr = startaddr
        self.arg_locations = arg_locations

class Builder(CodeGenerator):

    def __init__(self, rgenop, mc, stackdepth):
        self.rgenop = rgenop
        self.stackdepth = stackdepth
        self.asm = RPPCAssembler()
        self.asm.mc = mc
        self.curreg = 3

    def _write_prologue(self, sigtoken):
        numargs = sigtoken     # for now
        self.curreg += numargs
        #self.asm.trap()
        return [Var(RegisterLocation(pos)) for pos in range(3, 3+numargs)]

    def _close(self):
        self.rgenop.close_mc(self.asm.mc)
        self.asm.mc = None

    @specialize.arg(1)
    def genop2(self, opname, gv_arg1, gv_arg2):
        genmethod = getattr(self, 'op_' + opname)
        return genmethod(gv_arg1, gv_arg2)

    def finish_and_return(self, sigtoken, gv_returnvar):
        self.asm.mr(3, gv_returnvar.load(self))
        self.asm.blr()
        self._close()

    def enter_next_block(self, kinds, args_gv):
        arg_locations = []
        seen = {}
        for i in range(len(args_gv)):
            gv = args_gv[i]
            # turn constants into variables; also make copies of vars that
            # are duplicate in args_gv
            if not isinstance(gv, Var):
                gv = args_gv[i] = Var(RegisterLocation(gv.load(self)))
            elif gv.location in seen:
                if isinstance(gv.location, RegisterLocation):
                    new_gv = args_gv[i] = self.newvar()
                    assert isinstance(gv.location, RegisterLocation)
                    self.asm.mr(new_gv.reg(), gv.reg())
                    gv = new_gv
                else:
                    gv = args_gv[i] = Var(RegisterLocation(gv.load(self)))
            # remember the var's location
            arg_locations.append(gv.location)
            seen[gv.location] = None
        return Block(self.asm.mc.tell(), arg_locations)

    def newvar(self):
        d = self.curreg
        self.curreg += 1
        assert d < 12
        return Var(RegisterLocation(d))

    def new_and_load_2(self, gv_x, gv_y):
        gv_result = self.newvar()
        return (gv_result, gv_x.load(self), gv_y.load(self))

    def op_int_add(self, gv_x, gv_y):
        gv_result, r_x, r_y = self.new_and_load_2(gv_x, gv_y)
        self.asm.add(gv_result.reg(), r_x, r_y)
        return gv_result

    def op_int_sub(self, gv_x, gv_y):
        gv_result, r_x, r_y = self.new_and_load_2(gv_x, gv_y)
        self.asm.sub(gv_result.reg(), r_x, r_y)
        return gv_result

    def op_int_gt(self, gv_x, gv_y):
        gv_result, r_x, r_y = self.new_and_load_2(gv_x, gv_y)
        r_result = gv_result.reg()
        self.asm.cmpw(0, r_x, r_y)
        self.asm.mfcr(r_result)
        self.asm.extrwi(r_result, r_result, 1, 1)
        return gv_result

    def jump_if_false(self, gv_condition):
        targetbuilder = self._fork()
        gv = self.newvar()
        self.asm.load_word(gv.reg(), targetbuilder.asm.mc.tell())
        self.asm.mtctr(gv.reg())
        self.asm.cmpwi(0, gv_condition.load(self), 0)
        self.asm.beqctr()
        return targetbuilder

    def _fork(self):
        return self.rgenop.openbuilder(self.stackdepth)


class RPPCGenOp(AbstractRGenOp):
    from pypy.jit.codegen.i386.codebuf import MachineCodeBlock

    def __init__(self):
        self.mcs = []   # machine code blocks where no-one is currently writing


    def __init__(self):
        self.mcs = []   # machine code blocks where no-one is currently writing

    def open_mc(self):
        if self.mcs:
            # XXX think about inserting NOPS for alignment
            return self.mcs.pop()
        else:
            return MachineCodeBlock(65536)   # XXX supposed infinite for now

    def close_mc(self, mc):
        self.mcs.append(mc)

    @staticmethod
    @specialize.memo()
    def sigToken(FUNCTYPE):
        return len(FUNCTYPE.ARGS)     # for now

    @staticmethod
    @specialize.memo()
    def kindToken(T):
        return None     # for now

    def openbuilder(self, stackdepth):
        return Builder(self, self.open_mc(), stackdepth)

    def newgraph(self, sigtoken):
        numargs = sigtoken          # for now
        initialstackdepth = numargs+1
        builder = self.openbuilder(initialstackdepth)
        entrypoint = builder.asm.mc.tell()
        inputargs_gv = builder._write_prologue(sigtoken)
        return builder, entrypoint, inputargs_gv


    @staticmethod
    @specialize.genconst(0)
    def genconst(llvalue):
        T = lltype.typeOf(llvalue)
        if isinstance(T, lltype.Primitive):
            return IntConst(lltype.cast_primitive(lltype.Signed, llvalue))
##         elif T is llmemory.Address:
##             return AddrConst(llvalue)
##         elif isinstance(T, lltype.Ptr):
##             return AddrConst(llmemory.cast_ptr_to_adr(llvalue))
        else:
            assert 0, "XXX not implemented"

    def gencallableconst(self, sigtoken, name, entrypointaddr):
        return IntConst(entrypointaddr)
