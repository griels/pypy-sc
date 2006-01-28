from pypy.annotation import model as annmodel
from pypy.annotation.pairtype import pair, pairtype
from pypy.jit.hintbookkeeper import getbookkeeper
from pypy.rpython.lltypesystem import lltype

UNARY_OPERATIONS = "same_as hint".split()

BINARY_OPERATIONS = "int_add int_sub".split()

class OriginTreeNode(object):

    fixed = False

    def __init__(self, origins=None):
        if origins is None:
            origins = {}
        self.origins = origins

    def merge(self, nodes):
        self.origins.update(nodes)

    def visit(self, seen=None):
        if seen is None:
            seen = {}
        yield self
        for o in self.origins:
            if o not in seen:
                seen[o] = True
                for o1 in o.visit(seen):
                    yield o1
                    
class SomeLLAbstractValue(annmodel.SomeObject):

    def __init__(self, T):
        self.concretetype = T

class SomeLLAbstractVariable(SomeLLAbstractValue):
    pass

class SomeLLAbstractConstant(SomeLLAbstractValue):

    def __init__(self, T, origins):
        SomeLLAbstractValue.__init__(self, T)
        self.origins = origins

class SomeLLConcreteValue(SomeLLAbstractValue):
    pass

# ____________________________________________________________
# operations

class __extend__(SomeLLAbstractValue):

    def same_as(hs_v1):
        return hs_v1

class __extend__(SomeLLAbstractConstant):

    def hint(hs_c1, hs_flags):
        assert hs_flags.const['concrete']
        for o in hs_c1.origins:
            for o1 in o.visit():
                o1.fixed = True
        return SomeLLConcreteValue(hs_c1.concretetype)

class __extend__(pairtype(SomeLLAbstractConstant, SomeLLAbstractConstant)):

    def int_add((hs_c1, hs_c2)):
        origin = getbookkeeper().myorigin()
        origin.merge(hs_c1.origins)
        origin.merge(hs_c2.origins)
        return SomeLLAbstractConstant(lltype.Signed, {origin: True})

    int_sub = int_add

    def union((hs_c1, hs_c2)):
        assert hs_c1.concretetype == hs_c2.concretetype
        origins = annmodel.setunion(hs_c1.origins, hs_c2.origins)
        return SomeLLAbstractConstant(hs_c1.concretetype, origins)
