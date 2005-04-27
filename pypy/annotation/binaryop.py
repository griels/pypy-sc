"""
Binary operations between SomeValues.
"""

from pypy.annotation.pairtype import pair, pairtype
from pypy.annotation.model import SomeObject, SomeInteger, SomeBool
from pypy.annotation.model import SomeString, SomeChar, SomeList, SomeDict
from pypy.annotation.model import SomeTuple, SomeImpossibleValue
from pypy.annotation.model import SomeInstance, SomeBuiltin, SomeIterator
from pypy.annotation.model import SomePBC, SomeSlice, SomeFloat
from pypy.annotation.model import unionof, set, setunion, missing_operation
from pypy.annotation.bookkeeper import getbookkeeper
from pypy.annotation.classdef import isclassdef
from pypy.objspace.flow.model import Constant

# convenience only!
def immutablevalue(x):
    return getbookkeeper().immutablevalue(x)

# XXX unify this with ObjSpace.MethodTable
BINARY_OPERATIONS = set(['add', 'sub', 'mul', 'div', 'mod',
                         'truediv', 'floordiv', 'divmod', 'pow',
                         'and_', 'or_', 'xor',
                         'lshift', 'rshift',
                         'getitem', 'setitem',
                         'inplace_add', 'inplace_sub', 'inplace_mul',
                         'inplace_truediv', 'inplace_floordiv', 'inplace_div',
                         'inplace_mod', 'inplace_pow',
                         'inplace_lshift', 'inplace_rshift',
                         'inplace_and', 'inplace_or', 'inplace_xor',
                         'lt', 'le', 'eq', 'ne', 'gt', 'ge', 'is_', 'cmp',
                         'union', 'coerce',
                         ])

for opname in BINARY_OPERATIONS:
    missing_operation(pairtype(SomeObject, SomeObject), opname)

class __extend__(pairtype(SomeObject, SomeObject)):

    def union((obj1, obj2)):
        if obj1 == obj2:
            return obj1
        else:
            result = SomeObject()
            is_type_of1 = getattr(obj1, 'is_type_of', None)
            is_type_of2 = getattr(obj2, 'is_type_of', None)
            if is_type_of1 and is_type_of1 == is_type_of2:
                result.is_type_of = is_type_of1
            # try to preserve the origin of SomeObjects
            if obj1 == result:
                return obj1
            elif obj2 == result:
                return obj2
            else:
                return result

    # inplace_xxx ---> xxx by default
    def inplace_add((obj1, obj2)):      return pair(obj1, obj2).add()
    def inplace_sub((obj1, obj2)):      return pair(obj1, obj2).sub()
    def inplace_mul((obj1, obj2)):      return pair(obj1, obj2).mul()
    def inplace_truediv((obj1, obj2)):  return pair(obj1, obj2).truediv()
    def inplace_floordiv((obj1, obj2)): return pair(obj1, obj2).floordiv()
    def inplace_div((obj1, obj2)):      return pair(obj1, obj2).div()
    def inplace_mod((obj1, obj2)):      return pair(obj1, obj2).mod()
    def inplace_pow((obj1, obj2), obj3):return pair(obj1, obj2).pow(obj3)
    def inplace_lshift((obj1, obj2)):   return pair(obj1, obj2).lshift()
    def inplace_rshift((obj1, obj2)):   return pair(obj1, obj2).rshift()
    def inplace_and((obj1, obj2)):      return pair(obj1, obj2).and_()
    def inplace_or((obj1, obj2)):       return pair(obj1, obj2).or_()
    def inplace_xor((obj1, obj2)):      return pair(obj1, obj2).xor()

    def lt((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(obj1.const < obj2.const)
        else:
            return SomeBool()

    def le((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(obj1.const <= obj2.const)
        else:
            return SomeBool()

    def eq((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(obj1.const == obj2.const)
        else:
            return SomeBool()

    def ne((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(obj1.const != obj2.const)
        else:
            return SomeBool()

    def gt((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(obj1.const > obj2.const)
        else:
            return SomeBool()

    def ge((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(obj1.const >= obj2.const)
        else:
            return SomeBool()

    def cmp((obj1, obj2)):
        if obj1.is_constant() and obj2.is_constant():
            return immutablevalue(cmp(obj1.const, obj2.const))
        else:
            return SomeInteger()

    def is_((obj1, obj2)):
        # XXX assumption: for "X is Y" we for simplification 
        #     assume that X is possibly variable and Y constant 
        #     (and not the other way round) 
        r = SomeBool()
        if obj2.is_constant():
            if obj1.is_constant(): 
                r.const = obj1.const is obj2.const
            if obj2.const is None and not getattr(obj1, 'can_be_None', True):
                r.const = False
        elif obj1.is_constant():
            if obj1.const is None and not getattr(obj2, 'can_be_None', True):
                r.const = False
        # XXX HACK HACK HACK
        # XXX HACK HACK HACK
        # XXX HACK HACK HACK
        bk = getbookkeeper()
        if bk is not None: # for testing
            if hasattr(obj1,'is_type_of') and obj2.is_constant():
                r.knowntypedata = (obj1.is_type_of, bk.valueoftype(obj2.const))
                return r
            fn, block, i = bk.position_key
            annotator = bk.annotator
            op = block.operations[i]
            assert op.opname == "is_" 
            assert len(op.args) == 2
            assert annotator.binding(op.args[0]) == obj1 
            r.knowntypedata = ([op.args[0]], obj2)
        return r

    def divmod((obj1, obj2)):
        return SomeTuple([pair(obj1, obj2).div(), pair(obj1, obj2).mod()])

    def coerce((obj1, obj2)):
        return pair(obj1, obj2).union()   # reasonable enough

class __extend__(pairtype(SomeInteger, SomeInteger)):
    # unsignedness is considered a rare and contagious disease

    def union((int1, int2)):
        unsigned = int1.unsigned or int2.unsigned
        return SomeInteger(nonneg = unsigned or (int1.nonneg and int2.nonneg),
                           unsigned=unsigned)
                           

    add = mul = div = floordiv = mod = or_ = xor = union

    def truediv((int1, int2)):
        return SomeFloat()

    def sub((int1, int2)):
        return SomeInteger(unsigned = int1.unsigned or int2.unsigned)

    def and_((int1, int2)):
        unsigned = int1.unsigned or int2.unsigned
        return SomeInteger(nonneg = unsigned or int1.nonneg or int2.nonneg,
                           unsigned = unsigned)

    def lshift((int1, int2)):
        if int1.unsigned:
            return SomeInteger(unsigned=True)
        return SomeInteger()

    rshift = lshift

    def pow((int1, int2), obj3):
        if int1.unsigned or int2.unsigned or getattr(obj3, 'unsigned', False):
            return SomeInteger(unsigned=True)
        return SomeInteger()

class __extend__(pairtype(SomeBool, SomeBool)):

    def union((boo1, boo2)):
        s = SomeBool() 
        if getattr(boo1, 'const', -1) == getattr(boo2, 'const', -2): 
            s.const = boo1.const 
        if hasattr(boo1, 'knowntypedata') and \
           hasattr(boo2, 'knowntypedata') and \
           boo1.knowntypedata[0] == boo2.knowntypedata[0]: 
            s.knowntypedata = (
                boo1.knowntypedata[0], 
                unionof(boo1.knowntypedata[1], boo2.knowntypedata[1]))
        return s 

class __extend__(pairtype(SomeString, SomeString)):

    def union((str1, str2)):
        return SomeString(can_be_None=str1.can_be_None or str2.can_be_None)

    def add((str1, str2)):
        return SomeString()


class __extend__(pairtype(SomeString, SomeObject)):

    def mod((str, args)):
        return SomeString()


class __extend__(pairtype(SomeFloat, SomeFloat)):
    
    def union((flt1, flt2)):
        return SomeFloat()

    add = sub = mul = div = truediv = floordiv = mod = union

    def pow((flt1, flt2), obj3):
        return SomeFloat()


class __extend__(pairtype(SomeList, SomeList)):

    def union((lst1, lst2)):
        return SomeList(lst1.listdef.union(lst2.listdef))

    add = union


class __extend__(pairtype(SomeList, SomeObject)):

    def inplace_add((lst1, obj2)):
        s_iter = obj2.iter()
        pair(lst1, SomeInteger()).setitem(s_iter.next())
        return lst1

    def inplace_mul((lst1, obj2)):
        return lst1


class __extend__(pairtype(SomeTuple, SomeTuple)):

    def union((tup1, tup2)):
        if len(tup1.items) != len(tup2.items):
            return SomeObject()
        else:
            unions = [unionof(x,y) for x,y in zip(tup1.items, tup2.items)]
            return SomeTuple(items = unions)

    def add((tup1, tup2)):
        return SomeTuple(items = tup1.items + tup2.items)


class __extend__(pairtype(SomeDict, SomeDict)):

    def union((dic1, dic2)):
        return SomeDict(dic1.dictdef.union(dic2.dictdef))


class __extend__(pairtype(SomeDict, SomeObject)):

    def getitem((dic1, obj2)):
        return dic1.dictdef.read_value()

    def setitem((dic1, obj2), s_value):
        dic1.dictdef.generalize_key(obj2)
        dic1.dictdef.generalize_value(s_value)


class __extend__(pairtype(SomeSlice, SomeSlice)):

    def union((slic1, slic2)):
        return SomeSlice(unionof(slic1.start, slic2.start),
                         unionof(slic1.stop, slic2.stop),
                         unionof(slic1.step, slic2.step))


class __extend__(pairtype(SomeTuple, SomeInteger)):
    
    def getitem((tup1, int2)):
        if int2.is_constant():
            try:
                return tup1.items[int2.const]
            except IndexError:
                return SomeImpossibleValue()
        else:
            return unionof(*tup1.items)


class __extend__(pairtype(SomeList, SomeInteger)):
    
    def mul((lst1, int2)):
        return lst1

    def getitem((lst1, int2)):
        return lst1.listdef.read_item()

    def setitem((lst1, int2), s_value):
        lst1.listdef.generalize(s_value)


class __extend__(pairtype(SomeList, SomeSlice)):

    def getitem((lst, slic)):
        return lst


class __extend__(pairtype(SomeString, SomeSlice)):

    def getitem((str1, slic)):
        return SomeString()

class __extend__(pairtype(SomeString, SomeInteger)):

    def getitem((str1, int2)):
        return SomeChar()

    def mul((str1, int2)): # xxx do we want to support this
        return SomeString()

class __extend__(pairtype(SomeInteger, SomeString)):
    
    def mul((int1, str2)): # xxx do we want to support this
        return SomeString()

class __extend__(pairtype(SomeInteger, SomeList)):
    
    def mul((int1, lst2)):
        return lst2


class __extend__(pairtype(SomeInstance, SomeInstance)):

    def union((ins1, ins2)):
        basedef = ins1.classdef.commonbase(ins2.classdef)
        if basedef is None:
            # print warning?
            return SomeObject()
        return SomeInstance(basedef, can_be_None=ins1.can_be_None or ins2.can_be_None)

class __extend__(pairtype(SomeIterator, SomeIterator)):

    def union((iter1, iter2)):
        return SomeIterator(unionof(iter1.s_item, iter2.s_item))


class __extend__(pairtype(SomeBuiltin, SomeBuiltin)):

    def union((bltn1, bltn2)):
        if bltn1.analyser != bltn2.analyser:
            assert False, "merging incompatible builtins == BAD!"
            return SomeObject()
        else:
            s_self = unionof(bltn1.s_self, bltn2.s_self)
            return SomeBuiltin(bltn1.analyser, s_self)

class __extend__(pairtype(SomePBC, SomePBC)):
    def union((pbc1, pbc2)):       
        if len(pbc2.prebuiltinstances) > len(pbc1.prebuiltinstances):
            pbc1, pbc2 = pbc2, pbc1
        d = pbc1.prebuiltinstances.copy()
        for x, classdef in pbc2.prebuiltinstances.items():
            if x in d:
                if bool(isclassdef(classdef)) ^ bool(isclassdef(d[x])):
                    raise Exception(
                        "union failed for %r with classdefs %r and %r" % 
                        (x, classdef, d[x]))
                if isclassdef(classdef):
                    classdef2 = classdef
                    if classdef != d[x]:
                        classdef = classdef.commonbase(d[x])
                        for cand in classdef.getmro():
                            if x in cand.cls.__dict__.values():
                                break
                        else:
                            assert False, ("confused pbc union trying unwarranted"
                                           "moving up of method %s from pair %s %s" %
                                           (x, d[x], classdef2))
            d[x] = classdef
        result =  SomePBC(d)
        return result

class __extend__(pairtype(SomeImpossibleValue, SomeObject)):
    def union((imp1, obj2)):
        return obj2

class __extend__(pairtype(SomeObject, SomeImpossibleValue)):
    def union((obj1, imp2)):
        return obj1

class __extend__(pairtype(SomeInstance, SomePBC)):
    def union((ins, pbc)):
        if pbc.isNone():
            return SomeInstance(classdef=ins.classdef, can_be_None = True)
        classdef = ins.classdef.superdef_containing(pbc.knowntype)
        if classdef is None:
            # print warning?
            return SomeObject()
        return SomeInstance(classdef)

class __extend__(pairtype(SomePBC, SomeInstance)):
    def union((pbc, ins)):
        return pair(ins, pbc).union()

# let mix lists and None for now
class __extend__(pairtype(SomeList, SomePBC)):
    def union((lst, pbc)):
        if pbc.isNone():
            return lst
        return SomeObject()

class __extend__(pairtype(SomePBC, SomeList    )):
    def union((pbc, lst)):
        return pair(lst, pbc).union()

# mixing strings and None

class __extend__(pairtype(SomeString, SomePBC)):
    def union((s, pbc)):
        if pbc.isNone():
            return SomeString(can_be_None=True)
        return SomeObject()

class __extend__(pairtype(SomePBC, SomeString    )):
    def union((pbc, s)):
        return pair(s, pbc).union()
