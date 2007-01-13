import py
from pypy.jit.codegen.ppc.rgenop import RPPCGenOp
from pypy.rpython.lltypesystem import lltype
from pypy.jit.codegen.test.rgenop_tests import AbstractRGenOpTests, FUNC, FUNC2
from ctypes import cast, c_int, c_void_p, CFUNCTYPE
from pypy.jit.codegen.ppc import instruction as insn

class FewRegisters(RPPCGenOp):
    freeregs = {
        insn.GP_REGISTER:insn.gprs[3:6],
        insn.FP_REGISTER:insn.fprs,
        insn.CR_FIELD:insn.crfs[:1],
        insn.CT_REGISTER:[insn.ctr]}

class TestRPPCGenop(AbstractRGenOpTests):
    RGenOp = RPPCGenOp

class TestRPPCGenopNoRegs(TestRPPCGenop):
    RGenOp = FewRegisters

    def compile(self, runner, argtypes):
        py.test.skip("Skip compiled tests w/ restricted register allocator")
