import operator
from pypy.annotation.pairtype import pairtype
from pypy.annotation import model as annmodel
from pypy.objspace.flow.model import Constant
from pypy.rpython.error import TyperError
from pypy.rpython.rmodel import Repr, IntegerRepr, inputconst
from pypy.rpython.rmodel import IteratorRepr
from pypy.rpython.rmodel import externalvsinternal
from pypy.rpython.robject import PyObjRepr, pyobj_repr
from pypy.rpython.lltypesystem.lltype import \
     Ptr, GcStruct, Void, Signed, malloc, typeOf, nullptr
from pypy.rpython.rarithmetic import intmask

# ____________________________________________________________
#
#  Concrete implementation of RPython tuples:
#
#    struct tuple {
#        type0 item0;
#        type1 item1;
#        type2 item2;
#        ...
#    }

class __extend__(annmodel.SomeTuple):
    def rtyper_makerepr(self, rtyper):
        return TupleRepr(rtyper, [rtyper.getrepr(s_item) for s_item in self.items])
    
    def rtyper_makekey_ex(self, rtyper):
        keys = [rtyper.makekey(s_item) for s_item in self.items]
        return tuple([self.__class__]+keys)

_gen_eq_function_cache = {}
_gen_hash_function_cache = {}

def gen_eq_function(items_r):
    eq_funcs = [r_item.get_ll_eq_function() or operator.eq for r_item in items_r]
    key = tuple(eq_funcs)
    try:
        return _gen_eq_function_cache[key]
    except KeyError:
        miniglobals = {}
        source = """
def ll_eq(t1, t2):
    %s
    return True
"""
        body = []
        for i, eq_func in enumerate(eq_funcs):
            miniglobals['eq%d' % i] = eq_func
            body.append("if not eq%d(t1.item%d, t2.item%d): return False" % (i, i, i))
        body = ('\n'+' '*4).join(body)
        source = source % body
        exec source in miniglobals
        ll_eq = miniglobals['ll_eq']
        _gen_eq_function_cache[key] = ll_eq
        return ll_eq

def gen_hash_function(items_r):
    # based on CPython
    hash_funcs = [r_item.get_ll_hash_function() for r_item in items_r]
    key = tuple(hash_funcs)
    try:
        return _gen_hash_function_cache[key]
    except KeyError:
        miniglobals = {}
        source = """
def ll_hash(t):
    retval = 0x345678
    %s
    return retval
"""
        body = []
        mult = 1000003
        for i, hash_func in enumerate(hash_funcs):
            miniglobals['hash%d' % i] = hash_func
            body.append("retval = (retval ^ hash%d(t.item%d)) * %d" %
                        (i, i, mult))
            mult = intmask(mult + 82520 + 2*len(items_r))
        body = ('\n'+' '*4).join(body)
        source = source % body
        exec source in miniglobals
        ll_hash = miniglobals['ll_hash']
        ll_hash.cache_in_dict = True
        _gen_hash_function_cache[key] = ll_hash
        return ll_hash



class TupleRepr(Repr):

    def __init__(self, rtyper, items_r):
        self.items_r = []
        self.external_items_r = []
        for item_r in items_r:
            external_repr, internal_repr = externalvsinternal(rtyper, item_r)
            self.items_r.append(internal_repr)
            self.external_items_r.append(external_repr)
        items_r = self.items_r
        self.fieldnames = ['item%d' % i for i in range(len(items_r))]
        self.lltypes = [r.lowleveltype for r in items_r]
        fields = zip(self.fieldnames, self.lltypes)
        self.lowleveltype = Ptr(GcStruct('tuple%d' % len(items_r), *fields))
        self.tuple_cache = {}

    def compact_repr(self):
        return "TupleR %s" % ' '.join([llt._short_name() for llt in self.lltypes])

    def convert_const(self, value):
        assert isinstance(value, tuple) and len(value) == len(self.items_r)
        key = tuple([Constant(item) for item in value])
        try:
            return self.tuple_cache[key]
        except KeyError:
            p = malloc(self.lowleveltype.TO)
            self.tuple_cache[key] = p
            for obj, r, name in zip(value, self.items_r, self.fieldnames):
                setattr(p, name, r.convert_const(obj))
            return p

    #def get_eqfunc(self):
    #    return inputconst(Void, self.item_repr.get_ll_eq_function())

    def get_ll_eq_function(self):
        return gen_eq_function(self.items_r)

    def get_ll_hash_function(self):
        return gen_hash_function(self.items_r)    

    def rtype_len(self, hop):
        return hop.inputconst(Signed, len(self.items_r))

    def rtype_bltn_list(self, hop):
        from pypy.rpython import rlist
        nitems = len(self.items_r)
        vtup = hop.inputarg(self, 0)
        LIST = hop.r_result.lowleveltype.TO
        cno = inputconst(Signed, nitems)
        vlist = hop.gendirectcall(LIST.ll_newlist, cno)
        v_func = hop.inputconst(Void, rlist.dum_nocheck)
        for index in range(nitems):
            name = self.fieldnames[index]
            ritem = self.items_r[index]
            cname = hop.inputconst(Void, name)
            vitem = hop.genop('getfield', [vtup, cname], resulttype = ritem)
            vitem = hop.llops.convertvar(vitem, ritem, hop.r_result.item_repr)
            cindex = inputconst(Signed, index)
            hop.gendirectcall(rlist.ll_setitem_nonneg, v_func, vlist, cindex, vitem)
        return vlist

    def make_iterator_repr(self):
        if len(self.items_r) == 1:
            return Length1TupleIteratorRepr(self)
        raise TyperError("can only iterate over tuples of length 1 for now")

    def getitem(self, llops, v_tuple, index): # ! returns internal repr lowleveltype
        name = self.fieldnames[index]
        llresult = self.lltypes[index]
        cname = inputconst(Void, name)
        return  llops.genop('getfield', [v_tuple, cname], resulttype = llresult)



class __extend__(pairtype(TupleRepr, Repr)): 
    def rtype_contains((r_tup, r_item), hop):
        s_tup = hop.args_s[0]
        if not s_tup.is_constant():
            raise TyperError("contains() on non-const tuple") 
        t = s_tup.const
        typ = type(t[0]) 
        for x in t[1:]: 
            if type(x) is not typ: 
                raise TyperError("contains() on mixed-type tuple "
                                 "constant %r" % (t,))
        d = {}
        for x in t: 
            d[x] = None 
        hop2 = hop.copy()
        _, _ = hop2.r_s_popfirstarg()
        v_dict = Constant(d)
        s_dict = hop.rtyper.annotator.bookkeeper.immutablevalue(d)
        hop2.v_s_insertfirstarg(v_dict, s_dict)
        return hop2.dispatch()
 
class __extend__(pairtype(TupleRepr, IntegerRepr)):

    def rtype_getitem((r_tup, r_int), hop):
        v_tuple, v_index = hop.inputargs(r_tup, Signed)
        if not isinstance(v_index, Constant):
            raise TyperError("non-constant tuple index")
        index = v_index.value
        v = r_tup.getitem(hop.llops, v_tuple, index)
        return hop.llops.convertvar(v, r_tup.items_r[index], r_tup.external_items_r[index])

class __extend__(pairtype(TupleRepr, TupleRepr)):
    
    def rtype_add((r_tup1, r_tup2), hop):
        v_tuple1, v_tuple2 = hop.inputargs(r_tup1, r_tup2)
        vlist = []
        for i in range(len(r_tup1.items_r)):
            vlist.append(r_tup1.getitem(hop.llops, v_tuple1, i))
        for i in range(len(r_tup2.items_r)):
            vlist.append(r_tup2.getitem(hop.llops, v_tuple2, i))
        return newtuple_cached(hop, vlist)
    rtype_inplace_add = rtype_add

    def convert_from_to((r_from, r_to), v, llops):
        if len(r_from.items_r) == len(r_to.items_r):
            if r_from.lowleveltype == r_to.lowleveltype:
                return v
            n = len(r_from.items_r)
            items_v = []
            for i in range(n):
                item_v = r_from.getitem(llops, v, i)
                item_v = llops.convertvar(item_v,
                                              r_from.items_r[i],
                                              r_to.items_r[i])
                items_v.append(item_v)
            return newtuple(llops, r_to, items_v)
        return NotImplemented
                
# ____________________________________________________________
#
#  Irregular operations.

def newtuple(llops, r_tuple, items_v): # items_v should have the lowleveltype of the internal reprs
    if len(r_tuple.items_r) == 0:
        return inputconst(r_tuple, ())    # always the same empty tuple
    c1 = inputconst(Void, r_tuple.lowleveltype.TO)
    v_result = llops.genop('malloc', [c1], resulttype = r_tuple.lowleveltype)
    for i in range(len(r_tuple.items_r)):
        cname = inputconst(Void, r_tuple.fieldnames[i])
        llops.genop('setfield', [v_result, cname, items_v[i]])
    return v_result

def newtuple_cached(hop, items_v):
    r_tuple = hop.r_result
    if hop.s_result.is_constant():
        return inputconst(r_tuple, hop.s_result.const)
    else:
        return newtuple(hop.llops, r_tuple, items_v)

def rtype_newtuple(hop):
    r_tuple = hop.r_result
    vlist = hop.inputargs(*r_tuple.items_r)
    return newtuple_cached(hop, vlist)

#
# _________________________ Conversions _________________________

class __extend__(pairtype(PyObjRepr, TupleRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        vlist = []
        for i in range(len(r_to.items_r)):
            ci = inputconst(Signed, i)
            v_item = llops.gencapicall('PyTuple_GetItem_WithIncref', [v, ci],
                                       resulttype = pyobj_repr)
            v_converted = llops.convertvar(v_item, pyobj_repr,
                                           r_to.items_r[i])
            vlist.append(v_converted)
        return newtuple(llops, r_to, vlist)

class __extend__(pairtype(TupleRepr, PyObjRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        ci = inputconst(Signed, len(r_from.items_r))
        v_result = llops.gencapicall('PyTuple_New', [ci],
                                     resulttype = pyobj_repr)
        for i in range(len(r_from.items_r)):
            cname = inputconst(Void, r_from.fieldnames[i])
            v_item = llops.genop('getfield', [v, cname],
                                 resulttype = r_from.items_r[i].lowleveltype)
            v_converted = llops.convertvar(v_item, r_from.items_r[i],
                                           pyobj_repr)
            ci = inputconst(Signed, i)
            llops.gencapicall('PyTuple_SetItem_WithIncref', [v_result, ci,
                                                             v_converted])
        return v_result

# ____________________________________________________________
#
#  Iteration.

class Length1TupleIteratorRepr(IteratorRepr):

    def __init__(self, r_tuple):
        self.r_tuple = r_tuple
        self.lowleveltype = Ptr(GcStruct('tuple1iter',
                                         ('tuple', r_tuple.lowleveltype)))

    def newiter(self, hop):
        v_tuple, = hop.inputargs(self.r_tuple)
        citerptr = hop.inputconst(Void, self.lowleveltype)
        return hop.gendirectcall(ll_tupleiter, citerptr, v_tuple)

    def rtype_next(self, hop):
        v_iter, = hop.inputargs(self)
        hop.has_implicit_exception(StopIteration) # record that we know about it
        hop.exception_is_here()
        v = hop.gendirectcall(ll_tuplenext, v_iter)
        return hop.llops.convertvar(v, self.r_tuple.items_r[0], self.r_tuple.external_items_r[0])

def ll_tupleiter(ITERPTR, tuple):
    iter = malloc(ITERPTR.TO)
    iter.tuple = tuple
    return iter

def ll_tuplenext(iter):
    # for iterating over length 1 tuples only!
    t = iter.tuple
    if t:
        iter.tuple = nullptr(typeOf(t).TO)
        return t.item0
    else:
        raise StopIteration
