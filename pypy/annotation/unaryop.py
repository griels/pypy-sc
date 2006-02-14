"""
Unary operations on SomeValues.
"""

from pypy.annotation.model import \
     SomeObject, SomeInteger, SomeBool, SomeString, SomeChar, SomeList, \
     SomeDict, SomeUnicodeCodePoint, SomeTuple, SomeImpossibleValue, \
     SomeInstance, SomeBuiltin, SomeFloat, SomeIterator, SomePBC, \
     SomeExternalObject, SomeTypedAddressAccess, SomeAddress, \
     SomeCTypesObject,\
     unionof, set, missing_operation, add_knowntypedata
from pypy.annotation.bookkeeper import getbookkeeper
from pypy.annotation import builtin

from pypy.annotation.binaryop import _clone ## XXX where to put this?

# convenience only!
def immutablevalue(x):
    return getbookkeeper().immutablevalue(x)

UNARY_OPERATIONS = set(['len', 'is_true', 'getattr', 'setattr', 'delattr', 'hash',
                        'simple_call', 'call_args', 'str', 'repr',
                        'iter', 'next', 'invert', 'type', 'issubtype',
                        'pos', 'neg', 'nonzero', 'abs', 'hex', 'oct',
                        'ord', 'int', 'float', 'long', 'id',
                        'neg_ovf', 'abs_ovf'])

for opname in UNARY_OPERATIONS:
    missing_operation(SomeObject, opname)


class __extend__(SomeObject):

    def type(obj, *moreargs):
        if moreargs:
            raise Exception, 'type() called with more than one argument'
        if obj.is_constant():
            if isinstance(obj, SomeInstance):
                r = SomePBC([obj.classdef.classdesc])
            else:
                r = immutablevalue(obj.knowntype)
        else:
            r = SomeObject()
            r.knowntype = type
        bk = getbookkeeper()
        fn, block, i = bk.position_key
        annotator = bk.annotator
        op = block.operations[i]
        assert op.opname == "type"
        assert len(op.args) == 1
        assert annotator.binding(op.args[0]) == obj
        r.is_type_of = [op.args[0]]
        return r

    def issubtype(obj, s_cls):
        if hasattr(obj, 'is_type_of'):
            vars = obj.is_type_of
            annotator = getbookkeeper().annotator
            return builtin.builtin_isinstance(annotator.binding(vars[0]),
                                              s_cls, vars)
        if obj.is_constant() and s_cls.is_constant():
            return immutablevalue(issubclass(obj.const, s_cls.const))
        return SomeBool()

    def len(obj):
        return SomeInteger(nonneg=True)

    def is_true_behavior(obj):
        if obj.is_immutable_constant():
            return immutablevalue(bool(obj.const))
        else:
            s_len = obj.len()
            if s_len.is_constant():
                return immutablevalue(s_len.const > 0)
            else:
                return SomeBool()

    def is_true(s_obj):
        r = s_obj.is_true_behavior()
        assert isinstance(r, SomeBool)

        bk = getbookkeeper()
        knowntypedata = r.knowntypedata = {}
        fn, block, i = bk.position_key
        op = block.operations[i]
        assert op.opname == "is_true" or op.opname == "nonzero"
        assert len(op.args) == 1
        arg = op.args[0]
        s_nonnone_obj = s_obj
        if s_obj.can_be_none():
            s_nonnone_obj = s_obj.nonnoneify()
        add_knowntypedata(knowntypedata, True, [arg], s_nonnone_obj)
        return r
        

    def nonzero(obj):
        return obj.is_true()

    def hash(obj):
        raise TypeError, "hash() is not generally supported"

    def str(obj):
        getbookkeeper().count('str', obj)
        return SomeString()

    def repr(obj):
        getbookkeeper().count('repr', obj)
        return SomeString()

    def hex(obj):
        getbookkeeper().count('hex', obj)
        return SomeString()

    def oct(obj):
        getbookkeeper().count('oct', obj)
        return SomeString()

    def id(obj): # xxx
        return SomeInteger()

    def int(obj):
        return SomeInteger()

    def float(obj):
        return SomeFloat()

    def long(obj):
        return SomeObject()   # XXX

    def delattr(obj, s_attr):
        if obj.__class__ != SomeObject or obj.knowntype != object:
            getbookkeeper().warning(
                ("delattr on potentally non-SomeObjects is not RPythonic: delattr(%r,%r)" %
                 (obj, s_attr)))

    def find_method(obj, name):
        "Look for a special-case implementation for the named method."
        try:
            analyser = getattr(obj.__class__, 'method_' + name)
        except AttributeError:
            return None
        else:
            return SomeBuiltin(analyser, obj, name)

    def getattr(obj, s_attr):
        # get a SomeBuiltin if the SomeObject has
        # a corresponding method to handle it
        if s_attr.is_constant() and isinstance(s_attr.const, str):
            attr = s_attr.const
            s_method = obj.find_method(attr)
            if s_method is not None:
                return s_method
            # if the SomeObject is itself a constant, allow reading its attrs
            if obj.is_immutable_constant() and hasattr(obj.const, attr):
                return immutablevalue(getattr(obj.const, attr))
        else:
            getbookkeeper().warning('getattr(%r, %r) is not RPythonic enough' %
                                    (obj, s_attr))
        return SomeObject()
    getattr.can_only_throw = []

    def bind_callables_under(obj, classdef, name):
        return obj   # default unbound __get__ implementation

    def simple_call(obj, *args_s):
        return obj.call(getbookkeeper().build_args("simple_call", args_s))

    def call_args(obj, *args_s):
        return obj.call(getbookkeeper().build_args("call_args", args_s))

    def call(obj, args, implicit_init=False):
        #raise Exception, "cannot follow call_args%r" % ((obj, args),)
        getbookkeeper().warning("cannot follow call(%r, %r)" % (obj, args))
        return SomeObject()

    def op_contains(obj, s_element):
        return SomeBool()

class __extend__(SomeFloat):

    def pos(flt):
        return flt

    def neg(flt):
        return SomeFloat()

    abs = neg

    def is_true(self):
        if self.is_constant():
            return getbookkeeper().immutablevalue(bool(self.const))
        return SomeBool()

    def hash(flt):
        return SomeInteger()

class __extend__(SomeInteger):

    def invert(self):
        if self.unsigned:
            return SomeInteger(unsigned=True, size=self.size)
        return SomeInteger(size=self.size)

    invert.can_only_throw = []

    def pos(self):
        return self

    pos.can_only_throw = []
    int = pos

    # these are the only ones which can overflow:

    def neg(self):
        if self.unsigned:
            return SomeInteger(unsigned=True, size=self.size)
        return SomeInteger(size=self.size)

    neg.can_only_throw = []
    neg_ovf = _clone(neg, [OverflowError])

    def abs(self):
        if self.unsigned:
            return self
        return SomeInteger(nonneg=True, size=self.size)

    abs.can_only_throw = []
    abs_ovf = _clone(abs, [OverflowError])

class __extend__(SomeBool):
    def is_true(self):
        return self


class __extend__(SomeTuple):

    def len(tup):
        return immutablevalue(len(tup.items))

    def iter(tup):
        getbookkeeper().count("tuple_iter", tup)
        return SomeIterator(tup)
    iter.can_only_throw = []

    def getanyitem(tup):
        return unionof(*tup.items)


class __extend__(SomeList):

    def method_append(lst, s_value):
        lst.listdef.resize()
        lst.listdef.generalize(s_value)

    def method_extend(lst, s_iterable):
        lst.listdef.resize()
        if isinstance(s_iterable, SomeList):   # unify the two lists
            lst.listdef.agree(s_iterable.listdef)
        else:
            s_iter = s_iterable.iter()
            lst.method_append(s_iter.next())

    def method_reverse(lst):
        lst.listdef.mutate()

    def method_insert(lst, s_index, s_value):
        lst.method_append(s_value)

    def method_pop(lst, s_index=None):
        lst.listdef.resize()
        return lst.listdef.read_item()

    def method_index(lst, s_value):
        getbookkeeper().count("list_index")
        lst.listdef.generalize(s_value)
        return SomeInteger(nonneg=True)

    def len(lst):
        s_item = lst.listdef.read_item()
        if isinstance(s_item, SomeImpossibleValue):
            return immutablevalue(0)
        return SomeObject.len(lst)

    def iter(lst):
        return SomeIterator(lst)
    iter.can_only_throw = []

    def getanyitem(lst):
        return lst.listdef.read_item()

    def op_contains(lst, s_element):
        lst.listdef.generalize(s_element)
        return SomeBool()

class __extend__(SomeDict):

    def len(dct):
        s_key = dct.dictdef.read_key()
        s_value = dct.dictdef.read_value()
        if isinstance(s_key, SomeImpossibleValue) or isinstance(s_value, SomeImpossibleValue):
            return immutablevalue(0)
        return SomeObject.len(dct)

    def iter(dct):
        return SomeIterator(dct)
    iter.can_only_throw = []

    def getanyitem(dct, variant='keys'):
        if variant == 'keys':
            return dct.dictdef.read_key()
        elif variant == 'values':
            return dct.dictdef.read_value()
        elif variant == 'items':
            return SomeTuple((dct.dictdef.read_key(),
                              dct.dictdef.read_value()))
        else:
            raise ValueError

    def method_get(dct, key, dfl):
        dct.dictdef.generalize_key(key)
        dct.dictdef.generalize_value(dfl)
        return dct.dictdef.read_value()

    def method_copy(dct):
        return SomeDict(dct.dictdef)

    def method_update(dct1, dct2):
        dct1.dictdef.union(dct2.dictdef)

    def method_keys(dct):
        return getbookkeeper().newlist(dct.dictdef.read_key())

    def method_values(dct):
        return getbookkeeper().newlist(dct.dictdef.read_value())

    def method_items(dct):
        return getbookkeeper().newlist(SomeTuple((dct.dictdef.read_key(),
                                                  dct.dictdef.read_value())))

    def method_iterkeys(dct):
        return SomeIterator(dct, 'keys')

    def method_itervalues(dct):
        return SomeIterator(dct, 'values')

    def method_iteritems(dct):
        return SomeIterator(dct, 'items')

    def method_clear(dct):
        pass

    def op_contains(dct, s_element):
        dct.dictdef.generalize_key(s_element)
        return SomeBool()


class __extend__(SomeString):

    def method_startswith(str, frag):
        return SomeBool()

    def method_endswith(str, frag):
        return SomeBool()

    def method_find(str, frag, start=None, end=None):
        return SomeInteger()

    def method_rfind(str, frag, start=None, end=None):
        return SomeInteger()

    def method_strip(str, chr):
        return SomeString()

    def method_lstrip(str, chr):
        return SomeString()

    def method_rstrip(str, chr):
        return SomeString()

    def method_join(str, s_list):
        getbookkeeper().count("str_join", str)
        s_item = s_list.listdef.read_item()
        if s_item == SomeImpossibleValue():
            return immutablevalue("")
        return SomeString()

    def iter(str):
        return SomeIterator(str)
    iter.can_only_throw = []

    def getanyitem(str):
        return SomeChar()

    def ord(str):
        return SomeInteger(nonneg=True)

    def hash(str):
        return SomeInteger()

    def method_split(str, patt): # XXX
        getbookkeeper().count("str_split", str, patt)
        return getbookkeeper().newlist(SomeString())

    def method_replace(str, s1, s2):
        return SomeString()

    def method_lower(str):
        return SomeString()

    def method_upper(str):
        return SomeString()


class __extend__(SomeChar):

    def len(chr):
        return immutablevalue(1)

    def method_isspace(chr):
        return SomeBool()

    def method_isdigit(chr):
        return SomeBool()

    def method_isalpha(chr):
        return SomeBool()

    def method_isalnum(chr):
        return SomeBool()

    def method_islower(chr):
        return SomeBool()

    def method_isupper(chr):
        return SomeBool()

class __extend__(SomeUnicodeCodePoint):

    def ord(uchr):
        return SomeInteger(nonneg=True)


class __extend__(SomeIterator):

    def iter(itr):
        return itr
    iter.can_only_throw = []

    def next(itr):
        return itr.s_container.getanyitem(*itr.variant)


class __extend__(SomeInstance):

    def getattr(ins, s_attr):
        if s_attr.is_constant() and isinstance(s_attr.const, str):
            attr = s_attr.const
            attrdef = ins.classdef.find_attribute(attr)
            position = getbookkeeper().position_key
            attrdef.read_locations[position] = True
            s_result = attrdef.getvalue()
            # hack: if s_result is a set of methods, discard the ones
            #       that can't possibly apply to an instance of ins.classdef.
            # XXX do it more nicely
            if isinstance(s_result, SomePBC):
                s_result = ins.classdef.lookup_filter(s_result, attr)
            elif isinstance(s_result, SomeImpossibleValue):
                ins.classdef.check_missing_attribute_update(attr)
            return s_result
        return SomeObject()
    getattr.can_only_throw = []

    def setattr(ins, s_attr, s_value):
        if s_attr.is_constant() and isinstance(s_attr.const, str):
            attr = s_attr.const
            # find the (possibly parent) class where this attr is defined
            clsdef = ins.classdef.locate_attribute(attr)
            attrdef = clsdef.attrs[attr]
            attrdef.readonly = False

            # if the attrdef is new, this must fail
            if attrdef.getvalue().contains(s_value):
                return
            # create or update the attribute in clsdef
            clsdef.generalize_attr(attr, s_value)

    def hash(ins):
        getbookkeeper().needs_hash_support[ins.classdef] = True
        return SomeInteger()

    def is_true_behavior(ins):
        if ins.can_be_None:
            return SomeBool()
        else:
            return immutablevalue(True)


class __extend__(SomeBuiltin):
    def simple_call(bltn, *args):
        if bltn.s_self is not None:
            return bltn.analyser(bltn.s_self, *args)
        else:
            getbookkeeper().count(bltn.methodname.replace('.', '_'), *args)
            return bltn.analyser(*args)

    def call(bltn, args, implicit_init=False):
        args_s, kwds = args.unpack()
        # prefix keyword arguments with 's_'
        kwds_s = {}
        for key, s_value in kwds.items():
            kwds_s['s_'+key] = s_value
        if bltn.s_self is not None:
            return bltn.analyser(bltn.s_self, *args_s, **kwds_s)
        else:
            return bltn.analyser(*args_s, **kwds_s)


class __extend__(SomePBC):

    def getattr(pbc, s_attr):
        bookkeeper = getbookkeeper()
        return bookkeeper.pbc_getattr(pbc, s_attr)
    getattr.can_only_throw = []

    def setattr(pbc, s_attr, s_value):
        getbookkeeper().warning("setattr not wanted on %r" % (pbc,))

    def call(pbc, args):
        bookkeeper = getbookkeeper()
        return bookkeeper.pbc_call(pbc, args)

    def bind_callables_under(pbc, classdef, name):
        d = [desc.bind_under(classdef, name) for desc in pbc.descriptions]
        return SomePBC(d, can_be_None=pbc.can_be_None)

    def is_true_behavior(pbc):
        if pbc.isNone():
            return immutablevalue(False)
        elif pbc.can_be_None:
            return SomeBool()
        else:
            return immutablevalue(True)


class __extend__(SomeExternalObject):
    def find_method(obj, name):
        "Look for a special-case implementation for the named method."
        type_analyser = builtin.EXTERNAL_TYPE_ANALYZERS[obj.knowntype]
        if name in type_analyser:
            analyser = type_analyser[name]
            return SomeBuiltin(analyser, obj, name)
        return SomeObject.find_method(obj, name)


# annotation of low-level types
from pypy.annotation.model import SomePtr, SomeLLADTMeth 
from pypy.annotation.model import SomeOOInstance, SomeOOBoundMeth, SomeOOStaticMeth
from pypy.annotation.model import ll_to_annotation, annotation_to_lltype

class __extend__(SomePtr):

    def getattr(p, s_attr):
        assert s_attr.is_constant(), "getattr on ptr %r with non-constant field-name" % p.ll_ptrtype
        v = getattr(p.ll_ptrtype._example(), s_attr.const)
        return ll_to_annotation(v)
    getattr.can_only_throw = []

    def len(p):
        len(p.ll_ptrtype._example())   # just doing checking
        return SomeObject.len(p)

    def setattr(p, s_attr, s_value): # just doing checking
        assert s_attr.is_constant(), "setattr on ptr %r with non-constant field-name" % p.ll_ptrtype
        example = p.ll_ptrtype._example()
        if getattr(example, s_attr.const) is not None:  # ignore Void s_value
            v_lltype = annotation_to_lltype(s_value)
            setattr(example, s_attr.const, v_lltype._defl())

    def simple_call(p, *args_s):
        llargs = [annotation_to_lltype(arg_s)._defl() for arg_s in args_s]
        v = p.ll_ptrtype._example()(*llargs)
        return ll_to_annotation(v)

    def is_true(p):
        return SomeBool()

class __extend__(SomeLLADTMeth):

    def call(adtmeth, args):
        bookkeeper = getbookkeeper()
        s_func = bookkeeper.immutablevalue(adtmeth.func)
        return s_func.call(args.prepend(SomePtr(adtmeth.ll_ptrtype)))

from pypy.rpython.ootypesystem import ootype
class __extend__(SomeOOInstance):
    def getattr(r, s_attr):
        assert s_attr.is_constant(), "getattr on ref %r with non-constant field-name" % r.ootype
        v = getattr(r.ootype._example(), s_attr.const)
        if isinstance(v, ootype._bound_meth):
            return SomeOOBoundMeth(r.ootype, s_attr.const)
        return ll_to_annotation(v)

    def setattr(r, s_attr, s_value): 
        assert s_attr.is_constant(), "setattr on ref %r with non-constant field-name" % r.ootype
        v = annotation_to_lltype(s_value)
        setattr(r.ootype._example(), s_attr.const,
                v._example())

    def is_true(p):
        return SomeBool()

class __extend__(SomeOOBoundMeth):
    def simple_call(m, *args_s):
        llargs = [annotation_to_lltype(arg_s)._example() for arg_s in args_s]
        inst = m.ootype._example()
        v = getattr(inst, m.name)(*llargs)
        return ll_to_annotation(v)

class __extend__(SomeOOStaticMeth):
    def simple_call(m, *args_s):
        llargs = [annotation_to_lltype(arg_s)._example() for arg_s in args_s]
        smeth = m.method._example()
        v = smeth(*llargs)
        return ll_to_annotation(v)

class __extend__(SomeCTypesObject):
    def setattr(cto, s_attr, s_value):
        pass

    def getattr(cto, s_attr):
        if s_attr.is_constant() and isinstance(s_attr.const, str):
            attr = s_attr.const
            # We reactivate the old contents field hack
            if False:
                try:
                    atype = cto.knowntype._fields_def_[attr]
                except AttributeError:
                    # We are dereferencing a pointer by accessing its contents attribute
                    if s_attr.const == "contents":
                        return SomeCTypesObject(
                                cto.knowntype._type_, cto.MEMORYALIAS)
                    else:
                        raise AttributeError(
                                "%r object has no attribute %r" % (
                                    cto.knowntype, s_attr.const))
            else:
                atype = cto.knowntype._fields_def_[attr]
            try:
                return atype.annotator_type
            except AttributeError:
                return SomeCTypesObject(atype)
        else:
            return SomeObject()

#_________________________________________
# memory addresses

from pypy.rpython.memory import lladdress

class __extend__(SomeAddress):
    def getattr(s_addr, s_attr):
        assert s_attr.is_constant()
        assert isinstance(s_attr, SomeString)
        assert s_attr.const in lladdress.supported_access_types
        return SomeTypedAddressAccess(
            lladdress.supported_access_types[s_attr.const])
    getattr.can_only_throw = []
