import operator
from pypy.annotation.pairtype import pairtype
from pypy.annotation import model as annmodel
from pypy.objspace.flow.model import Constant
from pypy.rpython.error import TyperError
from pypy.rpython.rmodel import Repr, IntegerRepr, inputconst
from pypy.rpython.rmodel import IteratorRepr
from pypy.rpython.rmodel import externalvsinternal
from pypy.rpython.robject import PyObjRepr, pyobj_repr
from pypy.rpython.rtuple import AbstractTupleRepr
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
        _gen_hash_function_cache[key] = ll_hash
        return ll_hash


class TupleRepr(AbstractTupleRepr):

    def __init__(self, rtyper, items_r):
        AbstractTupleRepr.__init__(self, rtyper, items_r)
        fields = zip(self.fieldnames, self.lltypes)
        self.lowleveltype = Ptr(GcStruct('tuple%d' % len(self.items_r), *fields))

    def newtuple(cls, llops, r_tuple, items_v):
        # items_v should have the lowleveltype of the internal reprs
        if len(r_tuple.items_r) == 0:
            return inputconst(r_tuple, ())    # always the same empty tuple
        c1 = inputconst(Void, r_tuple.lowleveltype.TO)
        v_result = llops.genop('malloc', [c1], resulttype = r_tuple.lowleveltype)
        for i in range(len(r_tuple.items_r)):
            cname = inputconst(Void, r_tuple.fieldnames[i])
            llops.genop('setfield', [v_result, cname, items_v[i]])
        return v_result
    newtuple = classmethod(newtuple)

    def instantiate(self):
        return malloc(self.lowleveltype.TO)

    #def get_eqfunc(self):
    #    return inputconst(Void, self.item_repr.get_ll_eq_function())

    def get_ll_eq_function(self):
        return gen_eq_function(self.items_r)

    def get_ll_hash_function(self):
        return gen_hash_function(self.items_r)    

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


def rtype_newtuple(hop):
    return TupleRepr._rtype_newtuple(hop)

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
        return r_to.newtuple(llops, r_to, vlist)

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
