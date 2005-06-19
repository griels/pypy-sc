import py
from pypy.translator.llvm2.log import log 

log = log.codewriter 

class CodeWriter(object): 
    def __init__(self): 
        self._lines = []

    def append(self, line): 
        self._lines.append(line) 
        log(line) 

    def indent(self, line): 
        self.append("        " + line) 

    def label(self, name):
        self.append("    %s:" % name)

    def structdef(self, name, typereprs):
        self.append("%s = type { %s }" %(name, ", ".join(typereprs)))

    def declare(self, decl):
        self.append("declare %s" %(decl,))

    def startimpl(self):
        self.append("")
        self.append("implementation")
        self.append("")

    def br_uncond(self, blockname): 
        self.indent("br label %%%s" %(blockname,))

    def br(self, switch, blockname_false, blockname_true):
        self.indent("br bool %s, label %%%s, label %%%s"
                    % (switch, blockname_true, blockname_false))

    def openfunc(self, decl): 
        self.append("%s {" % (decl,))

    def closefunc(self): 
        self.append("}") 

    def ret(self, type_, ref): 
        self.indent("ret %s %s" % (type_, ref)) 

    def phi(self, targetvar, type_, refs, blocknames): 
        assert targetvar.startswith('%')
        assert refs and len(refs) == len(blocknames), "phi node requires blocks" 
        mergelist = ", ".join(
            ["[%s, %%%s]" % item 
                for item in zip(refs, blocknames)])
        self.indent("%s = phi %s %s" %(targetvar, type_, mergelist))

    def binaryop(self, name, targetvar, type_, ref1, ref2):
        self.indent("%s = %s %s %s, %s" % (targetvar, name, type_, ref1, ref2))

    def call(self, targetvar, returntype, functionref, argrefs, argtypes):
        arglist = ["%s %s" % item for item in zip(argtypes, argrefs)]
        self.indent("%s = call %s %s(%s)" % (targetvar, returntype, functionref,
                                             ", ".join(arglist)))

    def cast(self, targetvar, fromtype, fromvar, targettype):
        self.indent("%(targetvar)s = cast %(fromtype)s "
                        "%(fromvar)s to %(targettype)s" % locals())

    def malloc(self, targetvar, type):
        self.indent("%(targetvar)s = malloc %(type)s" % locals())

    def getelementptr(self, targetvar, type, typevar, index):
        self.indent("%(targetvar)s = getelementptr "
                    "%(type)s %(typevar)s, int 0, uint %(index)s" % locals())

    def load(self, targetvar, targettype, ptr):
        self.indent("%(targetvar)s = load %(targettype)s* %(ptr)s" % locals())

    def store(self, valuetype, valuevar, ptr): 
        self.indent("store %(valuetype)s %(valuevar)s, "
                    "%(valuetype)s* %(ptr)s" % locals())

    def __str__(self): 
        return "\n".join(self._lines)
