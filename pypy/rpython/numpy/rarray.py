from pypy.rpython.rmodel import Repr, inputconst
from pypy.rpython.rrange import AbstractRangeRepr
from pypy.rpython.rint import IntegerRepr
from pypy.rpython.rlist import AbstractBaseListRepr
from pypy.rpython.rtuple import AbstractTupleRepr
from pypy.rpython.error import TyperError
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.lltypesystem.rtupletype import TUPLE_TYPE
from pypy.rpython.rslice import AbstractSliceRepr
from pypy.rpython.lltypesystem.lltype import \
    GcArray, GcStruct, Signed, Ptr, Unsigned, Void, FixedSizeArray, Bool,\
    malloc, direct_arrayitems, direct_ptradd
from pypy.rpython.lltypesystem.rtuple import TupleRepr
from pypy.annotation.model import SomeObject, SomeInteger
from pypy.rpython.numpy.aarray import SomeArray
from pypy.annotation.pairtype import pairtype, pair
from pypy.rlib.unroll import unrolling_iterable
from pypy.annotation import listdef
from pypy.rpython.memory.lltypelayout import sizeof

def gen_build_from_shape(ndim):
    unrolling_dims = unrolling_iterable(reversed(range(ndim)))
    def ll_build_from_shape(ARRAY, shape):
        array = ll_allocate(ARRAY, ndim)
        itemsize = 1
        for i in unrolling_dims:
            attr = 'item%d'%i
            size = getattr(shape, attr)
            array.shape[i] = size
            array.strides[i] = itemsize
            itemsize *= size
        array.data = malloc(ARRAY.data.TO, itemsize)
        return array
    return ll_build_from_shape

def gen_get_shape(ndim):
    unrolling_dims = unrolling_iterable(range(ndim))
    def ll_get_shape(ARRAY, TUPLE, array):
        shape = malloc(TUPLE)
        for i in unrolling_dims:
            size = array.shape[i]
            attr = 'item%d'%i
            setattr(shape, attr, size)
        return shape
    return ll_get_shape

NPY_INTP = Signed # index type (see Py_intptr_t)
def ARRAY_ITER(ARRAY, INDEXARRAY):
    ITER = Ptr(
        GcStruct("array_iter",
            ("nd_m1", Signed), # number of dimensions - 1 
            ("index", NPY_INTP),
            ("size", NPY_INTP),
            ("coordinates", INDEXARRAY), 
            ("dims_m1", INDEXARRAY),
            ("strides", INDEXARRAY),
            ("backstrides", INDEXARRAY),
            #("factors", INDEXARRAY),
            ("ao", ARRAY),
            ("dataptr", Ptr(FixedSizeArray(ARRAY.TO.data.TO.OF, 1))), # pointer to current item
            #("contiguous", Bool),
        ))
    return ITER

def ll_mul_list(items, n):
    result = 1
    while n:
        result *= items[n-1]
        n -= 1
    return result

def gen_iter_funcs(ndim):
    unroll_ndim = unrolling_iterable(range(ndim))
    unroll_ndim_rev = unrolling_iterable(reversed(range(ndim)))

    def ll_iter_reset(it):
        it.index = 0
        it.dataptr = direct_arrayitems(it.ao.data)
        for i in unroll_ndim:
            it.coordinates[i] = 0

    def ll_iter_new(ITER, ao):
        it = malloc(ITER)
        it.nd_m1 = ndim - 1
        it.size = ll_mul_list(ao.shape, ndim)
        it.ao = ao
        #it.factors[nd-1] = 1
        for i in unroll_ndim:
            it.dims_m1[i] = ao.shape[i]-1
            it.strides[i] = ao.strides[i]
            it.backstrides[i] = it.strides[i] * it.dims_m1[i]
            #if i > 0:
                #it.factors[nd-i-1] = it.factors[nd]*ao.shape[nd-i]
    #    ll_iter_reset(it)
        it.index = 0
        it.dataptr = direct_arrayitems(it.ao.data)
        for i in unroll_ndim:
            it.coordinates[i] = 0
        return it
    ll_iter_new._always_inline_ = True
    
    def ll_iter_next(it):
        it.index += 1
        for i in unroll_ndim_rev:
            if it.coordinates[i] < it.dims_m1[i]:
                it.coordinates[i] += 1
                it.dataptr = direct_ptradd(it.dataptr, it.strides[i])
                break
            it.coordinates[i] = 0
            it.dataptr = direct_ptradd(it.dataptr, -it.backstrides[i])
            i -= 1
    ll_iter_next._always_inline_ = True

    return ll_iter_new, ll_iter_next

def ll_setitem_from_array(iter_new0, iter_next0, ITER0, array0, 
                          slice, 
                          iter_new1, iter_next1, ITER1, array1):
    it0 = iter_new0(ITER0, array0)
    it1 = iter_new1(ITER1, array1)
    while it0.index < it0.size:
        it0.dataptr[0] = it1.dataptr[0]
        iter_next0(it0)
        iter_next1(it1)

class ArrayRepr(Repr):
    def __init__(self, rtyper, s_array):
        self.s_array = s_array
        self.s_value = s_array.get_item_type()
        self.ndim = s_array.ndim
        self.item_repr = rtyper.getrepr(self.s_value)
        self.ITEM = self.item_repr.lowleveltype
        ITEMARRAY = GcArray(self.ITEM, hints={'nolength':True})
        self.INDEXARRAY = FixedSizeArray(NPY_INTP, self.ndim)
        self.itemsize = sizeof(self.ITEM)
        self.ARRAY = Ptr(
            GcStruct("array",
                ("data", Ptr(ITEMARRAY)), # pointer to raw data buffer 
                ("ndim", Signed), # number of dimensions (do we need this ?)
                ("shape", self.INDEXARRAY), # size in each dimension
                ("strides", self.INDEXARRAY), # elements to jump to get to the
                                                 # next element in each dimension 
            ))
        self.lowleveltype = self.ARRAY
        self.ITER = ARRAY_ITER(self.ARRAY, self.INDEXARRAY)

    def build_from_array(self, llops, v_array):
        cARRAY = inputconst(lltype.Void, self.lowleveltype.TO) 
        return llops.gendirectcall(ll_build_alias, cARRAY, v_array)

    def build_from_shape(self, llops, r_tuple, v_tuple):
        cARRAY = inputconst(lltype.Void, self.lowleveltype.TO) 
        cTUPLE = inputconst(lltype.Void, r_tuple.lowleveltype.TO)
        ndim = self.s_array.ndim
        ll_build_from_shape = gen_build_from_shape(ndim)
        c_ndim = inputconst(lltype.Signed, ndim)
        assert ndim == len(r_tuple.items_r)
        rval = llops.gendirectcall(ll_build_from_shape, cARRAY, v_tuple)
        return rval

    def rtype_method_transpose(self, hop):
        [v_self] = hop.inputargs(self)
        cARRAY = hop.inputconst(Void, hop.r_result.ARRAY.TO)
        return hop.gendirectcall(ll_transpose, cARRAY, v_self)

    def get_ndim(self, hop, v_array):
        cname = inputconst(Void, 'ndim')
        return hop.llops.genop('getfield', [v_array, cname], resulttype=Signed)

    def get_shape(self, hop, v_array):
        cname = inputconst(Void, 'shape')
        TUPLE = TUPLE_TYPE([Signed]*self.ndim)
        cARRAY = inputconst(lltype.Void, self.lowleveltype.TO) 
        cTUPLE = inputconst(lltype.Void, TUPLE.TO)
        ll_get_shape = gen_get_shape(self.ndim)
        return hop.llops.gendirectcall(ll_get_shape, cARRAY, cTUPLE, v_array)
        return llops.genop('getfield', [v_array, cname], resulttype=TUPLE)

    def rtype_getattr(self, hop):
        s_attr = hop.args_s[1]
        if s_attr.is_constant() and isinstance(s_attr.const, str):
            attr = s_attr.const
            s_obj = hop.args_s[0]
            v_array, vattr = hop.inputargs(self, Void)
            getter = getattr(self, 'get_'+attr, None)
            if getter:
                return getter(hop, v_array)
        return Repr.rtype_getattr(self, hop)


class __extend__(SomeArray):
    def rtyper_makerepr(self, rtyper):
        return ArrayRepr(rtyper, self)

    def rtyper_makekey(self):
        return self.__class__, self.typecode, self.ndim


class __extend__(pairtype(ArrayRepr, ArrayRepr)):
    def rtype_add((r_arr1, r_arr2), hop):
        v_arr1, v_arr2 = hop.inputargs(r_arr1, r_arr2)
        cARRAY = hop.inputconst(Void, hop.r_result.ARRAY.TO)
        return hop.gendirectcall(ll_add, cARRAY, v_arr1, v_arr2)


class __extend__(pairtype(ArrayRepr, IntegerRepr)):
    def rtype_setitem((r_arr, r_int), hop):
        v_array, v_index, v_item = hop.inputargs(r_arr, Signed, r_arr.item_repr)
        return hop.gendirectcall(ll_setitem, v_array, v_index, v_item)

    def rtype_getitem((r_arr, r_int), hop):
        v_array, v_index = hop.inputargs(r_arr, Signed)
        return hop.gendirectcall(ll_getitem, v_array, v_index)

#class __extend__(pairtype(ArrayRepr, AbstractTupleRepr)):
#    def rtype_setitem((r_arr, r_tpl), hop):
#        v_array, v_tuple, v_item = hop.inputargs(r_arr, r_tpl, r_arr)
#        return hop.gendirectcall(ll_setitem_from_array, v_array, v_tuple, v_item)
#
#    def rtype_getitem((r_arr, r_tpl), hop):
#        return NotImplemented


class __extend__(pairtype(ArrayRepr, AbstractSliceRepr)):
    def rtype_setitem((r_arr, r_slc), hop):
        r_item = hop.args_r[2]
        v_array, v_slc, v_item = hop.inputargs(r_arr, r_slc, r_item)
        cITER0 = hop.inputconst(Void, r_arr.ITER.TO)
        cITER1 = hop.inputconst(Void, r_item.ITER.TO)
        iter_new0, iter_next0 = gen_iter_funcs(r_arr.ndim)        
        iter_new1, iter_next1 = gen_iter_funcs(r_item.ndim)        
        cnew0 = hop.inputconst(Void, iter_new0)
        cnext0 = hop.inputconst(Void, iter_next0)
        cnew1 = hop.inputconst(Void, iter_new1)
        cnext1 = hop.inputconst(Void, iter_next1)
#        return hop.gendirectcall(ll_setitem_from_array, cnext, cITER0, v_array, v_slc, cITER1, v_item)
        return hop.gendirectcall(ll_setitem_from_array,
            cnew0, cnext0, cITER0, v_array, v_slc, cnew1, cnext1, cITER1, v_item)
        

#class __extend__(pairtype(ArrayRepr, AbstractSliceRepr)):
#    # promote and delegate  XX doesn't work
#    def rtype_setitem((r_arr, r_slc), hop):
#        r_tpl = TupleRepr(hop.rtyper, [r_slc])
#        return pair(r_arr, r_tpl).rtype_setitem(hop)
#
#    def rtype_getitem((r_arr, r_slc), hop):
#        r_tpl = TupleRepr(hop.rtyper, [r_slc])
#        return pair(r_arr, r_tpl).rtype_getitem(hop)

class __extend__(pairtype(AbstractBaseListRepr, ArrayRepr)):
    def convert_from_to((r_lst, r_arr), v, llops):
        if r_lst.listitem is None:
            return NotImplemented
        if r_lst.item_repr != r_arr.item_repr:
            assert 0, (r_lst, r_arr.item_repr)
            return NotImplemented
        cARRAY = inputconst(lltype.Void, r_arr.lowleveltype.TO) 
        return llops.gendirectcall(ll_build_from_list, cARRAY, v)

class __extend__(pairtype(AbstractRangeRepr, ArrayRepr)):
    def convert_from_to((r_rng, r_arr), v, llops):
        cARRAY = inputconst(lltype.Void, r_arr.lowleveltype.TO) 
        return llops.gendirectcall(ll_build_from_list, cARRAY, v)

def ll_allocate(ARRAY, ndim):
    array = malloc(ARRAY)
    array.ndim = ndim
    #array.shape = malloc(ARRAY.shape.TO, array.ndim)
    #array.strides = malloc(ARRAY.strides.TO, array.ndim)
    return array

def ll_build_from_list(ARRAY, lst):
    size = lst.ll_length()
    array = ll_allocate(ARRAY, 1)
    for i in range(array.ndim):
        array.shape[i] = size
        array.strides[i] = 1
    data = array.data = malloc(ARRAY.data.TO, size)
    i = 0
    while i < size:
        data[i] = lst.ll_getitem_fast(i)
        i += 1
    return array

def ll_build_alias(ARRAY, array):
    new_array = ll_allocate(ARRAY, array.ndim)
    new_array.data = array.data # alias data
    for i in range(array.ndim):
        new_array.shape[i] = array.shape[i]
        new_array.strides[i] = array.strides[i]
    return new_array

def ll_setitem(l, index, item):
    l.data[index] = item

def ll_getitem(l, index):
    return l.data[index]

def ll_add(ARRAY, a1, a2):
    size = a1.shape[0]
    if size != a2.shape[0]:
        raise ValueError
    array = malloc(ARRAY)
    array.data = malloc(ARRAY.data.TO, size)
    i = 0
    while i < size:
        array.data[i] = a1.data[i] + a2.data[i]
        i += 1
    return array

def ll_transpose(ARRAY, a1):
    a2 = ll_build_alias(ARRAY, a1)
    # XX do something to a2
    return a2
    


