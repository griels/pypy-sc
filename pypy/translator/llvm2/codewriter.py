import py
from itertools import count
from pypy.translator.llvm2.log import log 

log = log.codewriter 

DEFAULT_TAIL  = 'tail'      #or ''
DEFAULT_CCONV = 'fastcc'    #or 'ccc'

class CodeWriter(object): 
    def __init__(self, f, show_line_number=False): 
        self.f = f
        self.show_line_numbers = show_line_number
        self.n_lines = 0

    def append(self, line): 
        self.n_lines += 1
        if self.show_line_numbers:
            line = "%-75s; %d" % (line, self.n_lines)
        self.f.write(line + '\n')

    def comment(self, line, indent=True):
        line = ";; " + line
        if indent:
            self.indent(line)
        else:
            self.append(line)

    def newline(self):
        self.append("")

    def indent(self, line): 
        self.append("        " + line) 

    def label(self, name):
        self.newline()
        self.append("    %s:" % name)

    def globalinstance(self, name, typeandata):
        self.append("%s = internal global %s" % (name, typeandata))

    def structdef(self, name, typereprs):
        self.append("%s = type { %s }" %(name, ", ".join(typereprs)))

    def arraydef(self, name, lentype, typerepr):
        self.append("%s = type { %s, [0 x %s] }" % (name, lentype, typerepr))

    def funcdef(self, name, rettyperepr, argtypereprs):
        self.append("%s = type %s (%s)" % (name, rettyperepr,
                                           ", ".join(argtypereprs)))

    def declare(self, decl, cconv=DEFAULT_CCONV):
        self.append("declare %s %s" %(cconv, decl,))

    def startimpl(self):
        self.newline()
        self.append("implementation")
        self.newline()

    def br_uncond(self, blockname): 
        self.indent("br label %%%s" %(blockname,))

    def br(self, cond, blockname_false, blockname_true):
        self.indent("br bool %s, label %%%s, label %%%s"
                    % (cond, blockname_true, blockname_false))

    def switch(self, intty, cond, defaultdest, value_label):
        labels = ''
        for value, label in value_label:
            labels += ' %s %s, label %%%s' % (intty, value, label)
        self.indent("switch %s %s, label %%%s [%s ]"
                    % (intty, cond, defaultdest, labels))

    def openfunc(self, decl, is_entrynode=False, cconv=DEFAULT_CCONV): 
        self.malloc_count = count(0).next
        self.newline()
        if is_entrynode:
            linkage_type = ''
        else:
            linkage_type = 'internal '
        self.append("%s%s %s {" % (linkage_type, cconv, decl,))

    def closefunc(self): 
        self.append("}") 

    def ret(self, type_, ref): 
        self.indent("ret %s %s" % (type_, ref))

    def ret_void(self):
        self.indent("ret void")

    def unwind(self):
        self.indent("unwind")

    def phi(self, targetvar, type_, refs, blocknames): 
        assert targetvar.startswith('%')
        assert refs and len(refs) == len(blocknames), "phi node requires blocks" 
        mergelist = ", ".join(
            ["[%s, %%%s]" % item 
                for item in zip(refs, blocknames)])
        s = "%s = phi %s %s" % (targetvar, type_, mergelist)
        self.indent(s)

    def binaryop(self, name, targetvar, type_, ref1, ref2):
        self.indent("%s = %s %s %s, %s" % (targetvar, name, type_, ref1, ref2))

    def shiftop(self, name, targetvar, type_, ref1, ref2):
        self.indent("%s = %s %s %s, ubyte %s" % (targetvar, name, type_, ref1, ref2))

    #from: http://llvm.cs.uiuc.edu/docs/LangRef.html
    #The optional "tail" marker indicates whether the callee function accesses any
    # allocas or varargs in the caller. If the "tail" marker is present, the function
    # call is eligible for tail call optimization. Note that calls may be marked
    # "tail" even if they do not occur before a ret instruction. 
    def call(self, targetvar, returntype, functionref, argrefs, argtypes, tail=DEFAULT_TAIL, cconv=DEFAULT_CCONV):
        if cconv is not 'fastcc':
            tail = ''
        arglist = ["%s %s" % item for item in zip(argtypes, argrefs)]
        self.indent("%s = %s call %s %s %s(%s)" % (targetvar, tail, cconv, returntype, functionref,
                                             ", ".join(arglist)))

    def call_void(self, functionref, argrefs, argtypes, tail=DEFAULT_TAIL, cconv=DEFAULT_CCONV):
        if cconv is not 'fastcc':
            tail = ''
        arglist = ["%s %s" % item for item in zip(argtypes, argrefs)]
        self.indent("%s call %s void %s(%s)" % (tail, cconv, functionref, ", ".join(arglist)))

    def invoke(self, targetvar, returntype, functionref, argrefs, argtypes, label, except_label, cconv=DEFAULT_CCONV):
        arglist = ["%s %s" % item for item in zip(argtypes, argrefs)]
        self.indent("%s = invoke %s %s %s(%s) to label %%%s except label %%%s" % (targetvar, cconv, returntype, functionref,
                                             ", ".join(arglist), label, except_label))

    def invoke_void(self, functionref, argrefs, argtypes, label, except_label, cconv=DEFAULT_CCONV):
        arglist = ["%s %s" % item for item in zip(argtypes, argrefs)]
        self.indent("invoke %s void %s(%s) to label %%%s except label %%%s" % (cconv, functionref, ", ".join(arglist), label, except_label))

    def cast(self, targetvar, fromtype, fromvar, targettype):
        self.indent("%(targetvar)s = cast %(fromtype)s "
                        "%(fromvar)s to %(targettype)s" % locals())

    def malloc(self, targetvar, type_, size=1, atomic=False, cconv=DEFAULT_CCONV):
        n = self.malloc_count()
        if n:
            cnt = ".%d" % n
        else:
            cnt = ""
        postfix = ('', '_atomic')[atomic]
        self.indent("%%malloc.Size%(cnt)s = getelementptr %(type_)s* null, uint %(size)s" % locals())
        self.indent("%%malloc.SizeU%(cnt)s = cast %(type_)s* %%malloc.Size%(cnt)s to uint" % locals())
        self.indent("%%malloc.Ptr%(cnt)s = call %(cconv)s sbyte* %%gc_malloc%(postfix)s(uint %%malloc.SizeU%(cnt)s)" % locals())
        self.indent("%(targetvar)s = cast sbyte* %%malloc.Ptr%(cnt)s to %(type_)s*" % locals())

    def getelementptr(self, targetvar, type, typevar, *indices):
        res = "%(targetvar)s = getelementptr %(type)s %(typevar)s, int 0, " % locals()
        res += ", ".join(["%s %s" % (t, i) for t, i in indices])
        self.indent(res)

    def load(self, targetvar, targettype, ptr):
        self.indent("%(targetvar)s = load %(targettype)s* %(ptr)s" % locals())

    def store(self, valuetype, valuevar, ptr): 
        self.indent("store %(valuetype)s %(valuevar)s, "
                    "%(valuetype)s* %(ptr)s" % locals())

    def debugcomment(self, tempname, len, tmpname):
        res = "%s = tail call ccc int (sbyte*, ...)* %%printf("
        res += "sbyte* getelementptr ([%s x sbyte]* %s, int 0, int 0) )"
        res = res % (tmpname, len, tmpname)
        self.indent(res)
