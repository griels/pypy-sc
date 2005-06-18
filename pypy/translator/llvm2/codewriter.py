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
        self.append("   " + line) 

    def label(self, name): 
        self.append("%s:" % name)

    def declare(self, decl): 
        self.append("declare %s" %(decl,))

    def br_uncond(self, blockname): 
        self.indent("br label %%%s" %(blockname,))

    def openfunc(self, decl): 
        self.append("%s {" % (decl,))

    def closefunc(self): 
        self.append("}") 

    def ret(self, type_, ref): 
        self.indent("ret %s %s" % (type_, ref)) 

    def phi(self, targetvar, type_, refs, blocknames): 
        assert targetvar.startswith('%')
        mergelist = ", ".join(
            ["[%s, %%%s]" % item 
                for item in zip(refs, blocknames)])
        self.indent("%s = phi %s %s" %(targetvar, type_, mergelist))

    def __str__(self): 
        return "\n".join(self._lines)
