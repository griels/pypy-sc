"""
Some simple classes that output LLVM-assembler.
"""

import autopath

import exceptions

from pypy.objspace.flow.model import Variable, Constant, SpaceOperation


class Function(object):
    def __init__(self, funcdef, startbb):
        self.funcdef = funcdef
        self.startbb = startbb
        self.blocks = {}

    def basic_block(self, block):
        assert block.label != self.startbb.label, "Block has same label as startblock!"
        self.blocks[block.label] = block

    def __str__(self):
        r = [self.funcdef, " {\n", str(self.startbb)]
        r += [str(bb) for bb in self.blocks.values()] + ["}\n\n"]
        return "".join(r)

class BasicBlock(object):
    def __init__(self, label):
        self.label = label
        self.instructions = []

    def instructions(self, instruction): #should not be used
        self.instructions.append(instruction)

    def select(self, l_arg, l_select, l_v1, l_v2):
        s = "%s = select bool %s, %s, %s"
        s = s % (l_arg.llvmname(), l_select.llvmname(), l_v1.typed_name(),
                 l_v2.typed_name())
        self.instructions.append(s)               

    def phi(self, l_arg, l_values, blocks):
        assert len(l_values) == len(blocks)
        vars_string = []
        fd = "" + "%s = phi %s " % (l_arg.llvmname(), l_arg.llvmtype())
        fd += ", ".join(["[%s, %s]" % (v.llvmname(), b)
               for v, b in zip(l_values, blocks)])
        self.instructions.append(fd)

    def spaceop(self, l_target, opname, l_args):
        if l_target.llvmtype() == "void":
            s = "call void %%std.%s(" % opname
        else:
            s = "%s = call %s %%std.%s(" % (l_target.llvmname(),
                                        l_target.llvmtype(), opname)
        self.instructions.append(s +
            ", ".join([a.typed_name() for a in l_args]) + ")")
        
    def call(self, l_target, l_func, l_args):
        s = "%s = call %s %s(" % (l_target.llvmname(), l_target.llvmtype(),
                                  l_func.llvmname())
        self.instructions.append(s + 
            ", ".join([a.typed_name() for a in l_args]) + ")")

    def ret(self, l_value):
        self.instructions.append("ret %s" % l_value.typed_name())

    def uncond_branch(self, block):
        self.instructions.append("br label " + block)

    def cond_branch(self, l_switch, blocktrue, blockfalse):
        s = "br %s, label %s, label %s" % (l_switch.typed_name(),
                                           blocktrue, blockfalse)
        self.instructions.append(s)


    def __str__(self):
        s = [self.label + ":\n"]
        for ins in self.instructions:
            s += ["\t%s\n" % ins]
        return "".join(s)

