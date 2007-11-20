from pypy.translator.llvm.node import FuncNode
from pypy.rpython.lltypesystem import lltype

class ExternalFuncNode(FuncNode):
    def __init__(self, db, value):
        name = value._name
        self.db = db
        self.value = value
        self.name = "@" + name

    def external_c_source(self):
        # return a list of unique includes and sources in C
        c_includes = []
        c_sources = []

        if hasattr(self.value, 'includes'):
            c_includes = list(self.value.includes)

        if hasattr(self.value, 'sources'):
            c_sources = list(self.value.sources)

        return c_includes, c_sources

    def writeglobalconstants(self, codewriter):
        pass

    def getdecl_parts(self):
        T = self.value._TYPE
        rettype = self.db.repr_type(T.RESULT)
        argtypes = [self.db.repr_type(a) for a in T.ARGS if a is not lltype.Void]
        return rettype, argtypes

    def getdecl(self):
        rettype, argtypes = self.getdecl_parts()
        return "%s %s(%s)" % (rettype, self.ref, ", ".join(argtypes))

    def writedecl(self, codewriter):
        codewriter.declare(self.getdecl())

