import autopath
from pypy.objspace.flow.model import *
from pypy.translator.annotation import Annotator

from pypy.translator.simplify import simplify_graph
from pypy.translator.peepfgt import register as fgt_register

# XXX For 2.2 the emitted code isn't quite right, because we cannot tell
# when we should write "0"/"1" or "nil"/"t".
if not isinstance(bool, type):
    class bool(int):
        pass

class Op:
    def __init__(self, gen, op):
        self.gen = gen
        self.str = gen.str
        self.op = op
        self.opname = op.opname
        self.args = op.args
        self.result = op.result
    def __call__(self):
        if self.opname in self.binary_ops:
            self.op_binary(self.opname)
        else:
            default = self.op_default
            meth = getattr(self, "op_" + self.opname, default)
            meth()
    def op_default(self):
        print ";", self.op
        print "; Op", self.opname, "is missing"
    binary_ops = {
        #"add": "+",
        "sub": "-",
        "inplace_add": "+", # weird, but it works
        "mod": "mod",
        "lt": "<",
        "le": "<=",
        "eq": "=",
        "gt": ">",
        "and_": "logand",
        "getitem": "elt",
    }
    def op_binary(self, op):
        s = self.str
        result, (arg1, arg2) = self.result, self.args
        cl_op = self.binary_ops[op]
        print "(setq", s(result), "(", cl_op, s(arg1), s(arg2), "))"
    def op_add(self):
        s = self.str
        result, (arg1, arg2) = self.result, self.args
        print "(setq", s(result)
        table = {
            (int, int): "(+ %s %s)",
            (str, str): "(concatenate 'string %s %s)",
        }
        self.gen.emit_typecase(table, arg1, arg2)
        print ")"
    def op_not_(self):
        s = self.str
        result, (arg1,) = self.result, self.args
        print "(setq", s(result), "(not"
        table = {
            (bool,): "(not %s)",
            (int,): "(zerop %s)",
        }
        self.gen.emit_typecase(table, arg1)
        print "))"
    def op_is_true(self):
        s = self.str
        result, (arg1,) = self.result, self.args
        print "(setq", s(result)
        table = {
            (bool,): "%s",
            (int,): "(not (zerop %s))",
        }
        self.gen.emit_typecase(table, arg1)
        print ")"
    def op_alloc_and_set(self):
        s = self.str
        result, (size, init) = self.result, self.args
        print "(setq", s(result), "(make-array", s(size), "))"
        print "(fill", s(result), s(init), ")"
    def op_setitem(self):
        s = self.str
        (array, index, element) = self.args
        print "(setf (elt", s(array), s(index), ")", s(element), ")"

class GenCL:
    def __init__(self, fun):
        simplify_graph(fun)
        self.fun = fun
        self.blockref = {}
        self.annotate([])
    def annotate(self, input_arg_types):
        ann = Annotator(self.fun)
        ann.build_types(input_arg_types)
        fgt_register(ann)
        ann.simplify()
        self.ann = ann
    def str(self, obj):
        if isinstance(obj, Variable):
            return obj.name
        elif isinstance(obj, Constant):
            return self.conv(obj.value)
        else:
            return "#<"
    def conv(self, val):
        if isinstance(val, bool): # should precedes int
            if val:
                return "t"
            else:
                return "nil"
        elif isinstance(val, int):
            return str(val)
        elif val is None:
            return "nil"
        elif isinstance(val, str):
            val.replace("\\", "\\\\")
            val.replace("\"", "\\\"")
            val = '"' + val + '"'
            return val
        else:
            return "#<"
    def emitcode(self):
        import sys
        from cStringIO import StringIO
        out = StringIO()
        sys.stdout = out
        self.emit()
        sys.stdout = sys.__stdout__
        return out.getvalue()
    def emit(self):
        self.emit_defun(self.fun)
    def emit_defun(self, fun):
        print "(defun", fun.name
        arglist = fun.getargs()
        print "(",
        for arg in arglist:
            print self.str(arg),
        print ")"
        print "(prog"
        blocklist = []
        def collect_block(node):
            if isinstance(node, Block):
                blocklist.append(node)
        traverse(collect_block, fun)
        varlist = {}
        for block in blocklist:
            tag = len(self.blockref)
            self.blockref[block] = tag
            for var in block.getvariables():
                varlist[var] = None
        varlist = varlist.keys()
        print "(",
        for var in varlist:
            if var in arglist:
                print "(", self.str(var), self.str(var), ")",
            else:
                print self.str(var),
        print ")"
        for block in blocklist:
            self.emit_block(block)
        print ")"
        print ")"
    def emit_block(self, block):
        self.cur_block = block
        tag = self.blockref[block]
        print "tag" + str(tag)
        for op in block.operations:
            emit_op = Op(self, op)
            emit_op()
        exits = block.exits
        if len(exits) == 1:
            self.emit_link(exits[0])
        elif len(exits) > 1:
            # only works in the current special case
            assert len(exits) == 2
            assert exits[0].exitcase == False
            assert exits[1].exitcase == True
            print "(if", self.str(block.exitswitch)
            print "(progn"
            self.emit_link(exits[1])
            print ") ; else"
            print "(progn"
            self.emit_link(exits[0])
            print "))"
        else:
            retval = self.str(block.inputargs[0])
            print "(return", retval, ")"
    def emit_jump(self, block):
        tag = self.blockref[block]
        print "(go", "tag" + str(tag), ")"
    def emit_link(self, link):
        source = link.args
        target = link.target.inputargs
        print "(psetq", # parallel assignment
        for item in zip(source, target):
            init, var = map(self.str, item)
            if var != init:
                print var, init,
        print ")"
        self.emit_jump(link.target)
    typemap = {
        bool: "boolean",
        int: "fixnum",
        type(''): "string", # hack, 'str' is in the namespace!
    }
    def emit_typecase(self, table, *args):
        argreprs = tuple(map(self.str, args))
        annset = self.ann.annotated[self.cur_block]
        argtypes = tuple(map(annset.get_type, args))
        if argtypes in table:
            trans = table[argtypes]
            print trans % argreprs
        else:
            print "(cond"
            for argtypes in table:
                print "((and",
                for tp, s in zip(argtypes, argreprs):
                    cl_tp = "'" + self.typemap[tp]
                    print "(typep", s, cl_tp, ")",
                print ")"
                trans = table[argtypes]
                print trans % argreprs,
                print ")"
            print ")"
