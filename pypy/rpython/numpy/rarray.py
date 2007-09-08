from pypy.rpython.rmodel import Repr, FloatRepr, inputconst
from pypy.rpython.rrange import AbstractRangeRepr
from pypy.rpython.rint import IntegerRepr
from pypy.rpython.rlist import AbstractBaseListRepr
from pypy.rpython.rtuple import AbstractTupleRepr
from pypy.rpython.error import TyperError
from pypy.rpython.lltypesystem import lltype, llmemory, rtuple
from pypy.rpython.lltypesystem.rtupletype import TUPLE_TYPE
from pypy.rpython.rslice import AbstractSliceRepr
from pypy.rpython.lltypesystem.lltype import \
    GcArray, GcStruct, Number, Primitive, Signed, Ptr, Unsigned, Void, FixedSizeArray, Bool,\
    GcForwardReference, malloc, direct_arrayitems, direct_ptradd, nullptr
from pypy.rpython.lltypesystem.rffi import cast
from pypy.rpython.lltypesystem.rtuple import TupleRepr
from pypy.annotation.model import SomeObject, SomeInteger
from pypy.rpython.numpy.aarray import SomeArray
from pypy.annotation.pairtype import pairtype, pair
from pypy.rlib.unroll import unrolling_iterable
from pypy.annotation import listdef
from pypy.rpython.memory.lltypelayout import sizeof
from pypy.rlib.objectmodel import debug_assert

def gen_build_from_shape(ndim, zero=False):
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
        array.data = malloc(ARRAY.data.TO, itemsize, zero=zero)
        array.dataptr = direct_arrayitems(array.data)
        return array
    return ll_build_from_shape

def gen_build_alias_shape(ndim):
    unrolling_dims = unrolling_iterable(reversed(range(ndim)))
    def ll_build_alias_shape(ARRAY, ao, shape):
        array = ll_allocate(ARRAY, ndim)
        itemsize = 1
        for i in unrolling_dims:
            attr = 'item%d'%i
            size = getattr(shape, attr)
            array.shape[i] = size
            array.strides[i] = itemsize
            itemsize *= size
        array.data = ao.data
        array.dataptr = ao.dataptr
        return array
    return ll_build_alias_shape

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

NPY_INTP = Signed # XX index type (see Py_intptr_t)

def ARRAY_ITER(ARRAY, INDEXARRAY):
    ITER = Ptr(
        GcStruct("array_iter",
            ("nd_m1", Signed), # number of dimensions - 1 
            ("index", NPY_INTP),
            ("size", NPY_INTP),
            ("coordinates", INDEXARRAY), 
            ("dims_m1", INDEXARRAY), # array of dimensions - 1
            ("strides", INDEXARRAY),
            ("backstrides", INDEXARRAY),
            #("factors", INDEXARRAY),
            #("ao", ARRAY), # not needed..
            ("dataptr", ARRAY.TO.dataptr), # pointer to current item
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

    def ll_iter_reset(it, dataptr):
        it.index = 0
        it.dataptr = dataptr
        for i in unroll_ndim:
            it.coordinates[i] = 0
    ll_iter_reset._always_inline_ = True

    def ll_iter_new(ITER, ao, target_ao, iter_reset, iter_broadcast_to_shape):
        assert ao.dataptr
        # Suffix of ao.shape must match target_ao.shape
        # (suffix starts at the first non-1 entry in ao.shape.)
        # ao.shape must be no longer than target_ao.shape.
        debug_assert(ao.ndim <= ndim, "ao.ndim <= ndim")
        debug_assert(target_ao.ndim == ndim, "target_ao.ndim == ndim")
        # XX check suffix condition here... ?
        broadcast = ao.ndim < ndim
        i = 0
        while not broadcast and i < ao.ndim:
            if ao.shape[i] == 1 and target_ao.shape[i] > 1:
                broadcast = True
            i += 1
        if broadcast:
            return iter_broadcast_to_shape(ITER, ao, target_ao, iter_reset)
        it = malloc(ITER)
        it.nd_m1 = ndim - 1
        it.size = ll_mul_list(ao.shape, ndim)
        #it.factors[nd-1] = 1
        for i in unroll_ndim:
            it.dims_m1[i] = ao.shape[i]-1
            it.strides[i] = ao.strides[i]
            it.backstrides[i] = it.strides[i] * it.dims_m1[i]
            #if i > 0:
                #it.factors[nd-i-1] = it.factors[nd]*ao.shape[nd-i]
        iter_reset(it, ao.dataptr)
        return it
    ll_iter_new._always_inline_ = True

    def ll_iter_broadcast_to_shape(ITER, ao, target_ao, iter_reset):
        "iterate over <ao> but broadcast to the shape of <target_ao>"
        debug_assert(target_ao.ndim == ndim, "target_ao.ndim == ndim")
        delta = j = ndim - ao.ndim
        shape = target_ao.shape
        for i in range(ao.ndim):
            if ao.shape[i] != 1 and ao.shape[i] != shape[j]:
                raise Exception("array is not broadcastable to correct shape")
            j += 1
        it = malloc(ITER)
        it.size = ll_mul_list(target_ao.shape, ndim)
        it.nd_m1 = ndim - 1
        #it.factors[ndim-1] = 1
        for i in unroll_ndim:
            it.dims_m1[i] = shape[i]-1
            k = i - delta
            if k<0 or ao.shape[k] != shape[i]:
                #it.contiguous = False
                it.strides[i] = 0
            else:
                it.strides[i] = ao.strides[k]
            it.backstrides[i] = it.strides[i] * it.dims_m1[i]
            #if i > 0:
                #it.factors[ndim-i-1] = it.factors[nd-i]*shape[ndim-i]
        iter_reset(it, ao.dataptr)
        return it
    ll_iter_broadcast_to_shape._always_inline_ = True    
    
    # XXX
    # I think this is the only function that needs to be 
    # generated-per-ndim:
    def ll_iter_next(it):
        it.index += 1
        for i in unroll_ndim_rev:
            if it.coordinates[i] < it.dims_m1[i]:
                it.coordinates[i] += 1
                it.dataptr = direct_ptradd(it.dataptr, it.strides[i])
                break
            it.coordinates[i] = 0
            it.dataptr = direct_ptradd(it.dataptr, -it.backstrides[i])
    ll_iter_next._always_inline_ = True

    return ll_iter_new, ll_iter_reset, ll_iter_broadcast_to_shape, ll_iter_next

def ll_unary_op(p0, p1, op=lambda x:x):
    p0[0] = op(p1[0])

def ll_binary_op(p0, p1, p2, op=lambda x,y:x+y):
    p0[0] = op(p1[0], p2[0])


def ll_array_set(it0, it1, iter_next):
    if it0.size == 0:
        return # empty LHS..
    debug_assert(it0.size == it1.size, "it0.size == it1.size")
    while it0.index < it0.size:
        it0.dataptr[0] = it1.dataptr[0]
        iter_next(it0)
        iter_next(it1)

def ll_array_set1(value, it, iter_next):
    while it.index < it.size:
        it.dataptr[0] = value
        iter_next(it)

def ll_array_add(it0, it1, it2, iter_next):
    debug_assert(it0.size == it1.size, "it0.size == it1.size")
    debug_assert(it1.size == it2.size, "it0.size == it1.size")
    while it0.index < it0.size:
        it0.dataptr[0] = it1.dataptr[0] + it2.dataptr[0]
        iter_next(it0)
        iter_next(it1)
        iter_next(it2)

def dim_of_ITER(ITER):
    return ITER.TO.coordinates.length

def dim_of_ARRAY(ARRAY):
    return ARRAY.TO.shape.length

class ArrayIterRepr(Repr):
    def __init__(self, rtyper, s_iter):
        self.s_iter = s_iter
        self.lowleveltype = self.ITER

class ArrayRepr(Repr):
    def make_types(cls, ndim, ITEM):
        DATA_PTR = Ptr(FixedSizeArray(ITEM, 1))
        ITEMARRAY = GcArray(ITEM, hints={'nolength':True})
        INDEXARRAY = FixedSizeArray(NPY_INTP, ndim)
        STRUCT = GcStruct("array",
            ("data", Ptr(ITEMARRAY)), # pointer to raw data buffer 
            ("dataptr", DATA_PTR), # pointer to first element
            ("ndim", Signed), # number of dimensions
            ("shape", INDEXARRAY), # size in each dimension
            ("strides", INDEXARRAY), # elements to jump to get to the
                                     # next element in each dimension 
        )
        ARRAY = Ptr(STRUCT)
        return ARRAY, INDEXARRAY
    make_types = classmethod(make_types)

    def __init__(self, rtyper, s_array):
        self.s_array = s_array
        self.s_value = s_array.get_item_type()
        self.ndim = s_array.ndim
        self.r_item = rtyper.getrepr(self.s_value)
        self.ITEM = self.r_item.lowleveltype
        self.itemsize = sizeof(self.ITEM)
        self.ARRAY, self.INDEXARRAY = self.make_types(self.ndim, self.ITEM)
        self.lowleveltype = self.ARRAY
        self.ITER = ARRAY_ITER(self.ARRAY, self.INDEXARRAY)

    def build_from_array(self, hop, v_array):
        cARRAY = inputconst(lltype.Void, self.lowleveltype.TO) 
        return hop.llops.gendirectcall(ll_build_alias, cARRAY, v_array)

    def build_from_shape(self, hop, r_arg, v_arg, zero=False):
        cARRAY = inputconst(lltype.Void, self.lowleveltype.TO) 
        ndim = self.s_array.ndim
        if isinstance(r_arg, TupleRepr):
            r_tuple, v_tuple = r_arg, v_arg
            ll_build_from_shape = gen_build_from_shape(ndim, zero)
            c_ndim = inputconst(lltype.Signed, ndim)
            assert ndim == len(r_tuple.items_r)
            return hop.llops.gendirectcall(ll_build_from_shape, cARRAY, v_tuple)
        else:
            assert ndim == 1
            v_size = hop.inputarg(Signed, 0)
            _malloc = lambda tp, size: malloc(tp, size, zero=zero)
            cmalloc = inputconst(Void, _malloc)
            return hop.llops.gendirectcall(ll_build_from_size, cARRAY, v_size, cmalloc)

    def rtype_method_transpose(self, hop):
        [v_self] = hop.inputargs(self)
        cARRAY = hop.inputconst(Void, hop.r_result.ARRAY.TO)
        return hop.gendirectcall(ll_transpose, cARRAY, v_self)

    def rtype_method_reshape(self, hop):
        r_result = hop.r_result
        r_tuple = hop.args_r[1]
        if not isinstance(r_tuple, TupleRepr):
            raise TyperError()
        ndim = len(r_tuple.items_r)
        ll_build_alias_shape = gen_build_alias_shape(ndim)
        [v_array, v_tuple] = hop.inputargs(self, r_tuple)
        cARRAY = inputconst(lltype.Void, r_result.lowleveltype.TO) 
        return hop.llops.gendirectcall(ll_build_alias_shape, cARRAY, v_array, v_tuple)

    def get_ndim(self, hop, v_array):
        cname = inputconst(Void, 'ndim')
        return hop.llops.genop('getfield', [v_array, cname], resulttype=Signed)

    def get_shape(self, hop, v_array):
        TUPLE = TUPLE_TYPE([Signed]*self.ndim)
        cARRAY = inputconst(lltype.Void, self.lowleveltype.TO) 
        cTUPLE = inputconst(lltype.Void, TUPLE.TO)
        ll_get_shape = gen_get_shape(self.ndim)
        return hop.llops.gendirectcall(ll_get_shape, cARRAY, cTUPLE, v_array)

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
        key = self.__class__, self.typecode, self.ndim
        return key


class __extend__(pairtype(ArrayRepr, ArrayRepr)):
    def rtype_add((r_array1, r_array2), hop):
        v_array1, v_array2 = hop.inputargs(r_array1, r_array2)
        r_array0 = hop.r_result
        cARRAY = hop.inputconst(Void, r_array0.ARRAY.TO)
        # We build a contiguous "result" array
        # from the largest of the two args:
        v_bigarray = hop.gendirectcall(ll_find_largest, cARRAY, v_array1, v_array2)
        v_array0 = hop.gendirectcall(ll_build_like, cARRAY, v_bigarray)
        iter_new, iter_reset, iter_broadcast, iter_next = gen_iter_funcs(r_array0.ndim)
        cITER = hop.inputconst(Void, r_array0.ITER.TO)
        creset = hop.inputconst(Void, iter_reset)
        cbroadcast = hop.inputconst(Void, iter_broadcast)
        cnext = hop.inputconst(Void, iter_next)
        v_it0 = hop.gendirectcall(iter_new, cITER, v_array0, v_bigarray, creset, cbroadcast)
        v_it1 = hop.gendirectcall(iter_new, cITER, v_array1, v_bigarray, creset, cbroadcast)
        v_it2 = hop.gendirectcall(iter_new, cITER, v_array2, v_bigarray, creset, cbroadcast)
        return hop.gendirectcall(ll_array_add, v_it0, v_it1, v_it2, cnext)

class __extend__(pairtype(ArrayRepr, Repr)):
    def rtype_add((r_array, r_ob), hop):
        assert 0
        v_ob = hop.inputarg(r_ob, 1)
        if isinstance(r_ob.lowleveltype, Primitive):
            r_item, v_item = convert_scalar_to_array(r_array, v_ob, hop.llops)

class __extend__(pairtype(Repr, ArrayRepr)):
    def rtype_add((r_ob, r_array), hop):
        # XX ach! how to get this to work ??
        assert 0
        return pair(r_array, r_ob).rtype_add(hop)


        
def gen_getset_item(ndim):
    unrolling_dims = unrolling_iterable(range(ndim))
    def ll_get_item(ARRAY, ao, tpl):
        array = ll_allocate(ARRAY, ndim)
        idx = 0
        for i in unrolling_dims:
            idx += ao.strides[i] * getattr(tpl, 'item%d'%i)
        return ao.data[idx]

    def ll_set_item(ARRAY, ao, tpl, value):
        array = ll_allocate(ARRAY, ndim)
        idx = 0
        for i in unrolling_dims:
            idx += ao.strides[i] * getattr(tpl, 'item%d'%i)
        ao.data[idx] = value

    return ll_get_item, ll_set_item

def get_view_ndim(r_array, r_tuple): # XX method on the pair type ?
    ndim = len([r_item for r_item in r_tuple.items_r if isinstance(r_item, AbstractSliceRepr)])
    ndim += r_array.ndim - len(r_tuple.items_r)
    return ndim

def gen_get_view(r_array, r_tuple, hop): # XX method on the pair type ?
    ndim = get_view_ndim(r_array, r_tuple)
    unroll_r_tuple = unrolling_iterable(enumerate(r_tuple.items_r))
    rslice = hop.rtyper.type_system.rslice
    def ll_get_view(ARRAY, ao, tpl):
        array = ll_allocate(ARRAY, ndim)
        dataptr = direct_arrayitems(ao.data)
        src_i = 0
        tgt_i = 0
        for src_i, r_key in unroll_r_tuple:
            if isinstance(r_key, IntegerRepr):
                dataptr = direct_ptradd(dataptr, getattr(tpl, 'item%d'%src_i)*ao.strides[src_i])
            elif r_key == rslice.startonly_slice_repr:
                start = getattr(tpl, 'item%d'%src_i)
                size = ao.shape[src_i]
                if start > size:
                    start = size
                size -= start
                dataptr = direct_ptradd(dataptr, start*ao.strides[src_i])
                array.shape[tgt_i] = size
                array.strides[tgt_i] = ao.strides[src_i]
                tgt_i += 1
            elif r_key == rslice.startstop_slice_repr:
                start = getattr(tpl, 'item%d'%src_i).start
                stop = getattr(tpl, 'item%d'%src_i).stop
                size = ao.shape[src_i]
                if start > size:
                    start = size
                dataptr = direct_ptradd(dataptr, start*ao.strides[src_i])
                if stop < size:
                    size = stop
                size -= start
                if size < 0:
                    size = 0
                array.shape[tgt_i] = size
                array.strides[tgt_i] = ao.strides[src_i]
                tgt_i += 1
            else:
                assert 0
        src_i += 1
        # consume the rest of ndim as if we found more slices
        while tgt_i < ndim:
            array.shape[tgt_i] = ao.shape[src_i]
            array.strides[tgt_i] = ao.strides[src_i]
            tgt_i += 1
            src_i += 1
        debug_assert(tgt_i == ndim, "tgt_i == ndim")
        array.dataptr = dataptr
        array.data = ao.data # keep a ref
        return array
    return ll_get_view
            
def convert_int_to_tuple(r_int, v_int, llops):
    # int -> (int,)
    r_tuple = TupleRepr(llops.rtyper, [r_int]) # XX get this from rtyper cache ?
    v_tuple = rtuple.newtuple(llops, r_tuple, [v_int])
    return r_tuple, v_tuple

def convert_slice_to_tuple(r_slc, v_slc, llops):
    # slice -> (slice,)
    r_tuple = TupleRepr(llops.rtyper, [r_slc]) # XX get this from rtyper cache ?
    v_tuple = rtuple.newtuple(llops, r_tuple, [v_slc])
    return r_tuple, v_tuple

def convert_list_to_array(r_list, v_list, llops):
    # [...] -> array([...])
    from pypy.rpython.rmodel import inputconst
    ITEM = r_list.item_repr.lowleveltype
    ARRAY, _ = ArrayRepr.make_types(1, ITEM)
    cARRAY = inputconst(Void, ARRAY.TO)
    v_array = llops.gendirectcall(ll_build_from_list, cARRAY, v_list) # XX does a copy :P
    #v_array = llops.gendirectcall(ll_build_alias_to_list, cARRAY, v_list) # nice idea...
    return v_array

def convert_scalar_to_array(r_array, v_item, llops):
    # x -> array([x])
    s_array = r_array.s_array.get_one_dim()
    r_array = llops.rtyper.getrepr(s_array)
    from pypy.rpython.rmodel import inputconst
#    ARRAY, _ = ArrayRepr.make_types(1, ITEM)
    cARRAY = inputconst(Void, r_array.ARRAY.TO)
    cITEM = inputconst(Void, r_array.ITEM)
    v_casted = llops.genop("cast_primitive", [v_item], r_array.ITEM)
    v_array = llops.gendirectcall(ll_build_from_scalar, cARRAY, v_casted)
    return r_array, v_array

class __extend__(pairtype(ArrayRepr, Repr)):
    def rtype_getitem((r_array, r_key), hop):

        v_array, v_key = hop.inputargs(r_array, r_key)
        if isinstance(r_key, IntegerRepr):
            r_tuple, v_tuple = convert_int_to_tuple(r_key, v_key, hop.llops)
        elif isinstance(r_key, AbstractSliceRepr):
            r_tuple, v_tuple = convert_slice_to_tuple(r_key, v_key, hop.llops)
        elif isinstance(r_key, TupleRepr):
            r_tuple, v_tuple = r_key, v_key
        else:
            raise TyperError("bad key: %s"%r_key)

        ndim = get_view_ndim(r_array, r_tuple)
        if ndim == 0:
            # return a scalar
            cARRAY = hop.inputconst(Void, r_array.ARRAY.TO)
            get_item, set_item = gen_getset_item(r_array.ndim)
            return hop.gendirectcall(get_item, cARRAY, v_array, v_tuple)
        r_result = hop.r_result
        ARRAY = r_result.ARRAY
        assert dim_of_ARRAY(ARRAY) == ndim
        cARRAY = hop.inputconst(Void, ARRAY.TO)
        ll_get_view = gen_get_view(r_array, r_tuple, hop)
        return hop.gendirectcall(ll_get_view, cARRAY, v_array, v_tuple)

    def rtype_setitem((r_array, r_key), hop):
        r_item = hop.args_r[2]
        v_array, v_key, v_item = hop.inputargs(r_array, r_key, r_item)
        if isinstance(r_key, IntegerRepr):
            r_tuple, v_tuple = convert_int_to_tuple(r_key, v_key, hop.llops)
        elif isinstance(r_key, AbstractSliceRepr):
            r_tuple, v_tuple = convert_slice_to_tuple(r_key, v_key, hop.llops)
        elif isinstance(r_key, TupleRepr):
            r_tuple, v_tuple = r_key, v_key
        else:
            raise TyperError("bad key: %s"%r_key)
        ndim = get_view_ndim(r_array, r_tuple)
        assert len(r_tuple.items_r) <= r_array.ndim
        if ndim == 0:
            # Set from scalar
            assert isinstance(r_item, FloatRepr)
            cARRAY = hop.inputconst(Void, r_array.ARRAY.TO)
            get_item, set_item = gen_getset_item(r_array.ndim)
            return hop.gendirectcall(set_item, cARRAY, v_array, v_tuple, v_item)
        else:
            s_view = SomeArray(r_array.s_array.typecode, ndim)
            r_view = hop.rtyper.getrepr(s_view)
            cARRAY = hop.inputconst(Void, r_view.ARRAY.TO)
            get_view = gen_get_view(r_array, r_tuple, hop)
            v_view = hop.gendirectcall(get_view, cARRAY, v_array, v_tuple)
            iter_new, iter_reset, iter_broadcast, iter_next = gen_iter_funcs(ndim)        
            creset = hop.inputconst(Void, iter_reset)
            cbroadcast = hop.inputconst(Void, iter_broadcast)
            cnext = hop.inputconst(Void, iter_next)
            cITER = hop.inputconst(Void, r_view.ITER.TO)
            v_it0 = hop.gendirectcall(iter_new, cITER, v_view, v_view, creset, cbroadcast)
            if isinstance(r_item, ArrayRepr):
                source_ndim = r_item.ndim
            elif isinstance(r_item.lowleveltype, Primitive):
                # "broadcast" a scalar
                r_item, v_item = convert_scalar_to_array(r_view, v_item, hop.llops)
                source_ndim = 1
            elif isinstance(r_item, AbstractBaseListRepr):
                v_item = convert_list_to_array(r_item, v_item, hop.llops)
                source_ndim = 1
            else:
                raise TypeError("bad item: %s"%r_item)
            assert source_ndim <= ndim
            v_it1 = hop.gendirectcall(iter_new, cITER, v_item, v_view, creset, cbroadcast)
            return hop.gendirectcall(ll_array_set, v_it0, v_it1, cnext) 

class __extend__(pairtype(ArrayRepr, ArrayRepr)):
    def convert_from_to((r_array0, r_array1), v, llops):
        assert 0

class __extend__(pairtype(AbstractBaseListRepr, ArrayRepr)):
    def convert_from_to((r_lst, r_array), v, llops):
        if r_lst.listitem is None:
            return NotImplemented
        if r_lst.item_repr != r_array.r_item:
            assert 0, (r_lst, r_array.r_item)
            return NotImplemented
        cARRAY = inputconst(lltype.Void, r_array.lowleveltype.TO) 
        return llops.gendirectcall(ll_build_from_list, cARRAY, v)

class __extend__(pairtype(AbstractRangeRepr, ArrayRepr)):
    def convert_from_to((r_rng, r_array), v, llops):
        cARRAY = inputconst(lltype.Void, r_array.lowleveltype.TO) 
        return llops.gendirectcall(ll_build_from_list, cARRAY, v)

def ll_allocate(ARRAY, ndim):
    array = malloc(ARRAY)
    array.ndim = ndim
    array.data = nullptr(ARRAY.data.TO)
    array.dataptr = nullptr(ARRAY.dataptr.TO)
    return array

def ll_build_from_size(ARRAY, size, _malloc):
    array = ll_allocate(ARRAY, 1)
    array.shape[0] = size
    array.strides[0] = 1
    array.data = _malloc(ARRAY.data.TO, size)
    array.dataptr = direct_arrayitems(array.data)
    return array

def ll_build_from_list(ARRAY, lst):
    size = lst.ll_length()
    array = ll_allocate(ARRAY, 1)
    array.shape[0] = size
    array.strides[0] = 1
    array.data = malloc(ARRAY.data.TO, size)
    i = 0
    while i < size:
        array.data[i] = lst.ll_getitem_fast(i)
        i += 1
    array.dataptr = direct_arrayitems(array.data)
    return array

def ll_build_alias_to_list(ARRAY, lst):
    # This should only be used for temporary calculations
    size = lst.ll_length()
    array = ll_allocate(ARRAY, 1)
    array.shape[0] = size
    array.strides[0] = 1
    # Well.. this doesn't work (because array.data has nolength ?)
    array.data = lst.ll_items()
    array.dataptr = direct_arrayitems(array.data)
    return array

def ll_build_from_scalar(ARRAY, value):
    array = ll_allocate(ARRAY, 1)
    array.shape[0] = 1
    array.strides[0] = 1
    array.data = malloc(ARRAY.data.TO, 1)
    array.dataptr = direct_arrayitems(array.data)
    array.data[0] = value
    return array

def ll_build_alias(ARRAY, ao):
    array = ll_allocate(ARRAY, ao.ndim)
    array.data = ao.data # alias data
    for i in range(ao.ndim):
        array.shape[i] = ao.shape[i]
        array.strides[i] = ao.strides[i]
    array.dataptr = ao.dataptr
    return array

def ll_find_largest(ARRAY, array0, array1):
    sz0 = ll_mul_list(array0.shape, array0.ndim)
    sz1 = ll_mul_list(array1.shape, array1.ndim)
    # XXX 
    if sz0 > sz1:
        return array0
    return array1

def ll_build_like(ARRAY, ao):
    array = ll_allocate(ARRAY, ao.ndim)
    sz = ll_mul_list(ao.shape)
    array.data = malloc(ARRAY.data.TO, sz)
    array.dataptr = array.data
    itemsize = 1
    i = ao.ndim - 1
    while i >= 0:
        size = ao.shape[i]
        array.shape[i] = size
        array.strides[i] = itemsize
        itemsize *= size
        i -= 1
    return array

def ll_setitem1(array, index, item):
    array.data[index] = item

def ll_getitem1(array, index):
    return array.data[index]

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
    array.dataptr = direct_arrayitems(array.data)
    return array

def ll_transpose(ARRAY, ao):
    ndim = ao.ndim
    array = ll_allocate(ARRAY, ndim)
    array.data = ao.data # alias data
    for i in range(ndim):
        array.shape[i] = ao.shape[ndim-i-1]
        array.strides[i] = ao.strides[ndim-i-1]
    array.dataptr = ao.dataptr
    return array
    


