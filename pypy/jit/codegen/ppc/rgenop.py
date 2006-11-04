from pypy.jit.codegen.model import AbstractRGenOp, GenLabel, GenBuilder
from pypy.jit.codegen.model import GenVar, GenConst, CodeGenSwitch
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rlib.objectmodel import specialize, we_are_translated
from pypy.jit.codegen.ppc.conftest import option
from ctypes import POINTER, cast, c_void_p, c_int

from pypy.jit.codegen.ppc import codebuf
from pypy.jit.codegen.ppc.instruction import rSP, rFP, rSCRATCH, gprs
from pypy.jit.codegen.ppc import instruction as insn
from pypy.jit.codegen.ppc.regalloc import RegisterAllocation
from pypy.jit.codegen.ppc.emit_moves import emit_moves

from pypy.translator.asm.ppcgen.rassemblermaker import make_rassembler
from pypy.translator.asm.ppcgen.ppc_assembler import MyPPCAssembler

RPPCAssembler = make_rassembler(MyPPCAssembler)

def emit(self, value):
    self.mc.write(value)
RPPCAssembler.emit = emit

_var_index = [0]
class Var(GenVar):
    def __init__(self):
        self.__magic_index = _var_index[0]
        _var_index[0] += 1
    def load(self, builder):
        return self
    def __repr__(self):
        return "<Var %d>" % self.__magic_index

class IntConst(GenConst):

    def __init__(self, value):
        self.value = value

    @specialize.arg(1)
    def revealconst(self, T):
        if isinstance(T, lltype.Ptr):
            return lltype.cast_int_to_ptr(T, self.value)
        elif T is llmemory.Address:
            return llmemory.cast_int_to_adr(self.value)
        else:
            return lltype.cast_primitive(T, self.value)

    def load(self, builder):
        var = builder.newvar()
        builder.insns.append(
            insn.Insn_GPR__IMM(RPPCAssembler.load_word,
                          var, [self]))
        return var

    def load_now(self, asm, loc):
        if loc.is_register:
            asm.load_word(loc.number, self.value)
        else:
            asm.load_word(rSCRATCH, self.value)
            asm.stw(rSCRATCH, rFP, loc.offset)

class JumpPatchupGenerator(object):

    def __init__(self, asm, min_offset):
        self.asm = asm
        self.min_offset = min_offset

    def emit_move(self, tarloc, srcloc):
        if tarloc == srcloc: return
        if tarloc.is_register and srcloc.is_register:
            self.asm.mr(tarloc.number, srcloc.number)
        elif tarloc.is_register and not srcloc.is_register:
            self.asm.lwz(tarloc.number, rFP, srcloc.offset)
        elif not tarloc.is_register and srcloc.is_register:
            self.asm.stw(srcloc.number, rFP, tarloc.offset)
        elif not tarloc.is_register and not srcloc.is_register:
            self.asm.lwz(rSCRATCH, rFP, srcloc.offset)
            self.asm.stw(rSCRATCH, rFP, tarloc.offset)

    def create_fresh_location(self):
        r = self.min_offset
        self.min_offset -= 4
        return insn.stack_slot(r)

def prepare_for_jump(asm, min_offset, sourcevars, src2loc, target):

    tar2src = {}     # tar var -> src var
    tar2loc = {}

    # construct mapping of targets to sources; note that "target vars"
    # and "target locs" are the same thing right now
    targetlocs = target.arg_locations
    for i in range(len(targetlocs)):
        tloc = targetlocs[i]
        tar2loc[tloc] = tloc
        tar2src[tloc] = sourcevars[i]

    gen = JumpPatchupGenerator(asm, min_offset)
    emit_moves(gen, tar2src, tar2loc, src2loc)
    return gen.min_offset


class Label(GenLabel):

    def __init__(self, startaddr, arg_locations, min_stack_offset):
        self.startaddr = startaddr
        self.arg_locations = arg_locations
        self.min_stack_offset = min_stack_offset

## class FlexSwitch(CodeGenSwitch):

##     def __init__(self, rgenop):
##         self.rgenop = rgenop
##         self.default_case_addr = 0

##     def initialize(self, builder, gv_exitswitch):
##         self.switch_reg = gv_exitswitch.load(builder)
##         self.saved_state = builder._save_state()
##         self._reserve(mc)

##     def _reserve(self, mc):
##         RESERVED = 11 # enough for 5 cases and a default
##         pos = mc.tell()
##         for i in range(RESERVED):
##             mc.write(0)
##         self.nextfreepos = pos
##         self.endfreepos = pos + RESERVED * 4

##     def _reserve_more(self):
##         XXX
##         start = self.nextfreepos
##         end   = self.endfreepos
##         newmc = self.rgenop.open_mc()
##         self._reserve(newmc)
##         self.rgenop.close_mc(newmc)
##         fullmc = InMemoryCodeBuilder(start, end)
##         a = RPPCAssembler()
##         a.mc = newmc
##         fullmc.ba(rel32(self.nextfreepos))
##         fullmc.done()

##     def add_case(self, gv_case):
##     def add_default(self):

class Builder(GenBuilder):

    def __init__(self, rgenop, mc):
        self.rgenop = rgenop
        self.asm = RPPCAssembler()
        self.asm.mc = mc
        self.insns = []
        self.stack_adj_addr = 0
        self.initial_spill_offset = 0
        self.initial_var2loc = None
        self.fresh_from_jump = False

    def make_fresh_from_jump(self, initial_var2loc):
        self.fresh_from_jump = True
        self.initial_var2loc = initial_var2loc

    def _write_prologue(self, sigtoken):
        numargs = sigtoken     # for now
        if not we_are_translated() and option.trap:
            self.asm.trap()
        inputargs = [self.newvar() for i in range(numargs)]
        assert self.initial_var2loc is None
        self.initial_var2loc = {}
        for arg in inputargs:
            self.initial_var2loc[arg] = gprs[3+len(self.initial_var2loc)]
        self.initial_spill_offset = self._var_offset(0)

        # Emit standard prologue
        #   Minimum space = 24+params+lv+4*GPR+8*FPR
        #   GPR=19
        # Initially, we allocate only enough space for GPRs, and allow
        # each basic block to ensure it has enough space to continue.
        minspace = self._stack_size(0,self._var_offset(0))
        self.asm.mflr(rSCRATCH)
        self.asm.stw(rSCRATCH,rSP,8)
        self.asm.stmw(gprs[13].number,rSP,-(4*20))     # save all regs from 13-31 to stack
        self.asm.mr(rFP, rSP)              # set up our frame pointer
        self.asm.stwu(rSP,rSP,-minspace)

        return inputargs

    def _var_offset(self, v):
        """v represents an offset into the local variable area in bytes;
        this returns the offset relative to rFP"""
        return -(4*19+4+v)

    def _stack_size(self, param, lv):
        """ Returns the required stack size to store all data, assuming
        that there are 'param' bytes of parameters for callee functions and
        'lv' is the largest (wrt to abs() :) rFP-relative byte offset of
        any variable on the stack."""
        return ((24 + param - lv) & ~15)+16

    def _close(self):
        self.rgenop.close_mc(self.asm.mc)
        self.asm.mc = None

    @specialize.arg(1)
    def genop2(self, opname, gv_arg1, gv_arg2):
        genmethod = getattr(self, 'op_' + opname)
        return genmethod(gv_arg1, gv_arg2)

    def allocate_and_emit(self):
        assert self.initial_var2loc is not None
        allocator = RegisterAllocation(
            self.rgenop.MINUSERREG, self.initial_var2loc, self.initial_spill_offset)
        self.insns = allocator.allocate_for_insns(self.insns)
        if self.insns:
            self.patch_stack_adjustment(self._stack_size(0, allocator.spill_offset))
        for insn in self.insns:
            insn.emit(self.asm)
        return allocator

    def finish_and_return(self, sigtoken, gv_returnvar):
        gv_returnvar = gv_returnvar.load(self)
        self.insns.append(insn.Return(gv_returnvar))
        allocator = self.allocate_and_emit()

        # Emit standard epilogue:
        self.asm.lwz(rSP,rSP,0)      # restore old SP
        self.asm.lmw(gprs[13].number,rSP,-4*20)  # restore all GPRs
        self.asm.lwz(rSCRATCH,rSP,8) # load old Link Register and jump to it
        self.asm.mtlr(rSCRATCH)      #
        self.asm.blr()               #
        self._close()

    def finish_and_goto(self, outputargs_gv, target):
        allocator = self.allocate_and_emit()
        min_offset = min(allocator.spill_offset, target.min_stack_offset)
        min_offset = prepare_for_jump(
            self.asm, min_offset, outputargs_gv, allocator.var2loc, target)
        self.patch_stack_adjustment(self._stack_size(0, min_offset))
        self.asm.load_word(rSCRATCH, target.startaddr)
        self.asm.mtctr(rSCRATCH)
        self.asm.bctr()
        self._close()

    def emit_stack_adjustment(self):
        # the ABI requires that at all times that r1 is valid, in the
        # sense that it must point to the bottom of the stack and that
        # executing SP <- *(SP) repeatedly walks the stack.
        # this code satisfies this, although there is a 1-instruction
        # window where such walking would find a strange intermediate
        # "frame"
        # as we emit these instructions waaay before doing the
        # register allocation for this block we don't know how much
        # stack will be required, so we patch it later (see
        # patch_stack_adjustment below).
        self.stack_adj_addr = self.asm.mc.tell()
        self.asm.addi(rSCRATCH, rFP, 0) # this is the immediate that later gets patched
        self.asm.subx(rSCRATCH, rSCRATCH, rSP) # rSCRATCH should now be <= 0
        self.asm.beq(3) # if rSCRATCH == 0, there is no actual adjustment, so
                        # don't end up with the situation where *(rSP) == rSP
        self.asm.stwux(rSP, rSP, rSCRATCH)
        self.asm.stw(rFP, rSP, 0)
        # branch to "here"

    def patch_stack_adjustment(self, newsize):
        if self.stack_adj_addr == 0:
            return
        # we build an addi instruction by hand here
        opcode = 14 << 26
        rD = rSCRATCH << 21
        rA = rFP << 16
        # if we decided to use r0 as the frame pointer, this would
        # emit addi rFOO, r0, SIMM which would just load SIMM into
        # rFOO and be "unlikely" to work
        assert rA != 0
        SIMM = (-newsize) & 0xFFFF
        p_instruction = cast(c_void_p(self.stack_adj_addr), POINTER(c_int*1))
        p_instruction.contents[0] = opcode | rD | rA | SIMM

    def enter_next_block(self, kinds, args_gv):
        if self.fresh_from_jump:
            var2loc = self.initial_var2loc
            self.fresh_from_jump = False
        else:
            var2loc = self.allocate_and_emit().var2loc

        #print "enter_next_block:", args_gv, var2loc

        min_stack_offset = self._var_offset(0)
        usedregs = {}
        livevar2loc = {}
        for gv in args_gv:
            if isinstance(gv, Var):
                assert gv in var2loc
                loc = var2loc[gv]
                livevar2loc[gv] = loc
                if not loc.is_register:
                    min_stack_offset = min(min_stack_offset, loc.offset)
                else:
                    usedregs[loc] = None # XXX use this

        unusedregs = [loc for loc in gprs[self.rgenop.MINUSERREG:] if loc not in usedregs]
        arg_locations = []

        for i in range(len(args_gv)):
            gv = args_gv[i]
            if isinstance(gv, Var):
                arg_locations.append(livevar2loc[gv])
            else:
                if unusedregs:
                    loc = unusedregs.pop()
                else:
                    loc = insn.stack_slot(min_stack_offset)
                    min_stack_offset -= 4
                gv.load_now(self.asm, loc)
                args_gv[i] = gv = Var()
                livevar2loc[gv] = loc
                arg_locations.append(loc)

        #print livevar2loc

        self.insns = []
        self.initial_var2loc = livevar2loc
        self.initial_spill_offset = min_stack_offset
        target_addr = self.asm.mc.tell()
        self.emit_stack_adjustment()
        return Label(target_addr, arg_locations, min_stack_offset)

    def newvar(self):
        gv = Var()
        return gv

    def new_and_load_2(self, gv_x, gv_y):
        gv_result = self.newvar()
        return (gv_result, gv_x.load(self), gv_y.load(self))

    def new_and_load_1(self, gv_x):
        gv_result = self.newvar()
        return (gv_result, gv_x.load(self))

    def op_int_mul(self, gv_x, gv_y):
        gv_result, gv_x, gv_y = self.new_and_load_2(gv_x, gv_y)
        self.insns.append(
            insn.Insn_GPR__GPR_GPR(RPPCAssembler.mullw,
                                   gv_result, [gv_x, gv_y]))
        return gv_result

    def op_int_add(self, gv_x, gv_y):
        if isinstance(gv_y, IntConst) and abs(gv_y.value) < 2**16:
            gv_result = self.newvar()
            self.insns.append(
                insn.Insn_GPR__GPR_IMM(RPPCAssembler.addi,
                                       gv_result, [gv_x.load(self), gv_y]))
            return gv_result
        elif isinstance(gv_x, IntConst):
            return self.op_int_add(gv_y, gv_x)
        else:
            gv_result = self.newvar()
            self.insns.append(
                insn.Insn_GPR__GPR_GPR(RPPCAssembler.add,
                                       gv_result, [gv_x.load(self), gv_y.load(self)]))
            return gv_result

    def op_int_sub(self, gv_x, gv_y):
        gv_result, gv_x, gv_y = self.new_and_load_2(gv_x, gv_y)
        self.insns.append(
            insn.Insn_GPR__GPR_GPR(RPPCAssembler.sub,
                                   gv_result, [gv_x, gv_y]))
        return gv_result

    def op_int_floordiv(self, gv_x, gv_y):
        gv_result, gv_x, gv_y = self.new_and_load_2(gv_x, gv_y)
        self.insns.append(
            insn.Insn_GPR__GPR_GPR(RPPCAssembler.divw,
                                   gv_result, [gv_x.load(self), gv_y.load(self)]))
        return gv_result

    def _compare(self, op, gv_x, gv_y):
        assert op == 'gt'
        result = self.newvar()
        if isinstance(gv_y, IntConst) and abs(gv_y.value) < 2*16:
            gv_x = gv_x.load(self)
            self.insns.append(insn.CMPWI((1, 0), result, [gv_x, gv_y]))
        elif isinstance(gv_x, IntConst) and abs(gv_x.value) < 2*16:
            gv_y = gv_y.load(self)
            self.insns.append(insn.CMPWI((1, 1), result, [gv_y, gv_x]))
        else:
            self.insns.append(insn.CMPW((1, 0), result, [gv_x.load(self), gv_y.load(self)]))
        return result

    def op_int_gt(self, gv_x, gv_y):
        return self._compare('gt', gv_x, gv_y)

    def _jump(self, gv_condition, if_true):
        targetbuilder = self._fork()

        gv = self.newvar()
        self.insns.append(
            insn.Insn_GPR__IMM(RPPCAssembler.load_word,
                               gv, [IntConst(targetbuilder.asm.mc.tell())]))
        gv2 = self.newvar()
        self.insns.append(
            insn.MTCTR(gv2, [gv]))
        self.insns.append(
            insn.Jump(gv_condition, gv2, if_true))

        allocator = self.allocate_and_emit()
        self.make_fresh_from_jump(allocator.var2loc)
        targetbuilder.make_fresh_from_jump(allocator.var2loc)

        return targetbuilder

    def jump_if_false(self, gv_condition):
        return self._jump(gv_condition, False)

    def jump_if_true(self, gv_condition):
        return self._jump(gv_condition, True)

    def _fork(self):
        return self.rgenop.openbuilder()


class RPPCGenOp(AbstractRGenOp):

    # minimum register we will use for register allocation
    # we can artifically restrict it for testing purposes
    MINUSERREG = 3

    def __init__(self):
        self.mcs = []   # machine code blocks where no-one is currently writing

    def open_mc(self):
        if self.mcs:
            return self.mcs.pop()
        else:
            return codebuf.MachineCodeBlock(65536)   # XXX supposed infinite for now

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

    def openbuilder(self):
        return Builder(self, self.open_mc())

    def newgraph(self, sigtoken):
        numargs = sigtoken          # for now
        builder = self.openbuilder()
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
