import autopath
from pypy.translator.flowmodel import *

class Op:
    def __init__(self, gen, op):
        self.str = gen.str
        self.opname = op.opname
        self.args = op.args
        self.result = op.result
    def __call__(self):
        meth_name = "op_" + self.opname
        meth_default = self.op_default
        meth = getattr(self, meth_name, meth_default)
        meth()
    def op_default(self):
        print self.opname, "is missing"
    def op_mod(self):
        result, arg1, arg2 = map(self.str, (self.result,) + self.args)
        print "(setq", result, "(mod", arg1, arg2, "))"

class GenCL:
    def __init__(self, fun):
        self.fun = fun
        self.blockref = {}
    def str(self, obj):
        if isinstance(obj, Variable):
            return obj.pseudoname
    def emit(self):
        self.emit_defun(self.fun)
    def emit_defun(self, fun):
        print "(defun", fun.functionname, "(",
        for arg in fun.get_args():
            print self.str(arg),
        print ")"
        print "(block nil"
        self.emit_block(fun.startblock)
        print ")"
        print ")"
    def emit_block(self, block):
        print "(tagbody"
        nb = len(self.blockref)
        tag = self.blockref.setdefault(block, nb)
        if tag != nb:
            print "(go", "tag" + str(tag), ")"
            print ")" # close tagbody
            return
        print "tag" + str(tag)
        for op in block.operations:
            emit_op = Op(self, op)
            emit_op()
        self.dispatch_branch(block.branch)
        print ")"
    def dispatch_branch(self, branch):
        if isinstance(branch, Branch):
            self.emit_branch(branch)
        elif isinstance(branch, ConditionalBranch):
            self.emit_conditional_branch(branch)
        elif isinstance(branch, EndBranch):
            self.emit_end_branch(branch)
        else:
            print branch.__class__, "is missing"
    def emit_branch(self, branch):
        if branch.target.has_renaming:
            source = branch.args
            target = branch.target.input_args
            print "(psetq",   # parallel assignment
            for item in zip(source, target):
                init, var = map(self.str, item)
                print var, init,
            print ")"
        self.emit_block(branch.target)
    def emit_conditional_branch(self, branch):
        print "(if"
        self.emit_truth_test(branch.condition)
        self.emit_branch(branch.ifbranch)
        self.emit_branch(branch.elsebranch)
        print ")"
    def emit_end_branch(self, branch):
        retval = self.str(branch.returnvalue)
        print "(return", retval, ")"
    def emit_truth_test(self, obj):
        # XXX: Fix this
        print "(not (zerop", self.str(obj), "))"
