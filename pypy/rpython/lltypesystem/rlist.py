from pypy.annotation.pairtype import pairtype, pair
from pypy.annotation import model as annmodel
from pypy.rpython.error import TyperError
from pypy.rpython.rmodel import Repr, IntegerRepr, inputconst
from pypy.rpython.rmodel import externalvsinternal
from pypy.rpython.rlist import AbstractBaseListRepr, AbstractListRepr, \
        AbstractFixedSizeListRepr, AbstractListIteratorRepr, rtype_newlist, \
        rtype_alloc_and_set, ll_setitem_nonneg
from pypy.rpython.rlist import dum_nocheck, dum_checkidx
from pypy.rpython.lltypesystem.rslice import SliceRepr
from pypy.rpython.lltypesystem.rslice import startstop_slice_repr, startonly_slice_repr
from pypy.rpython.lltypesystem.rslice import minusone_slice_repr
from pypy.rpython.lltypesystem.lltype import \
     GcForwardReference, Ptr, GcArray, GcStruct, \
     Void, Signed, malloc, typeOf, Primitive, \
     Bool, nullptr, typeMethod
from pypy.rpython.lltypesystem import rstr
from pypy.rpython import robject

# ____________________________________________________________
#
#  Concrete implementation of RPython lists:
#
#    struct list {
#        int length;
#        items_array *items;
#    }
#
#    'items' points to a C-like array in memory preceded by a 'length' header,
#    where each item contains a primitive value or pointer to the actual list
#    item.
#
#    or for fixed-size lists an array is directly used:
#
#    item_t list_items[]
#

class BaseListRepr(AbstractBaseListRepr):

    def __init__(self, rtyper, item_repr, listitem=None):
        self.rtyper = rtyper
        self.LIST = GcForwardReference()
        self.lowleveltype = Ptr(self.LIST)
        if not isinstance(item_repr, Repr):  # not computed yet, done by setup()
            assert callable(item_repr)
            self._item_repr_computer = item_repr
        else:
            self.external_item_repr, self.item_repr = externalvsinternal(rtyper, item_repr)
        self.listitem = listitem
        self.list_cache = {}
        # setup() needs to be called to finish this initialization
        self.list_builder = ListBuilder()

    def _setup_repr_final(self):
        self.list_builder.setup(self)

    def null_const(self):
        return nullptr(self.LIST)

    def get_eqfunc(self):
        return inputconst(Void, self.item_repr.get_ll_eq_function())

    def make_iterator_repr(self):
        return ListIteratorRepr(self)

    def ll_str(self, l):
        items = l.ll_items()
        length = l.ll_length()
        item_repr = self.item_repr

        temp = malloc(TEMP, length)
        i = 0
        while i < length:
            temp[i] = item_repr.ll_str(items[i])
            i += 1

        return rstr.ll_strconcat(
            rstr.list_str_open_bracket,
            rstr.ll_strconcat(rstr.ll_join(rstr.list_str_sep,
                                           length,
                                           temp),
                              rstr.list_str_close_bracket))

class ListBuilder(object):
    """Interface to allow lazy list building by the JIT."""
    # This should not keep a reference to the RTyper, even indirectly via
    # the list_repr.
        
    def setup(self, list_repr):
        # Precompute the c_newitem and c_setitem_nonneg function pointers,
        # needed below.
        if list_repr.rtyper is None:
            return     # only for test_rlist, which doesn't need this anyway
        
        LIST = list_repr.LIST
        LISTPTR = list_repr.lowleveltype
        ITEM = list_repr.item_repr.lowleveltype
        self.LIST = LIST
        self.LISTPTR = LISTPTR

        argtypes = [Signed]
        fnptr = list_repr.rtyper.annotate_helper_fn(LIST.ll_newlist, argtypes)
        self.newlist_ptr = fnptr

        bk = list_repr.rtyper.annotator.bookkeeper
        argtypes = [bk.immutablevalue(dum_nocheck), LISTPTR, Signed, ITEM]
        fnptr = list_repr.rtyper.annotate_helper_fn(ll_setitem_nonneg, argtypes)
        self.setitem_nonneg_ptr = fnptr
        #self.c_dum_nocheck = inputconst(Void, dum_nocheck)
        #self.c_LIST = inputconst(Void, self.LIST)

    def __call__(self, builder, items_v):
        """Make the operations that would build a list containing the
        provided items."""
        from pypy.rpython import rgenop
        c_newlist = builder.genconst(self.newlist_ptr)
        c_len  = builder.genconst(len(items_v))
        v_result = builder.genop('direct_call',
                                 [c_newlist, rgenop.placeholder(self.LIST), c_len],
                                 self.LISTPTR)
        c_setitem_nonneg = builder.genconst(self.setitem_nonneg_ptr)
        for i, v in enumerate(items_v):
            c_i = builder.genconst(i)
            builder.genop('direct_call', [c_setitem_nonneg,
                                          rgenop.placeholder(dum_nocheck),
                                          v_result, c_i, v],
                          Void)
        return v_result

    def __eq__(self, other):
        return self.LISTPTR == other.LISTPTR

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return 1 # bad but not used alone


class __extend__(pairtype(BaseListRepr, BaseListRepr)):
    def rtype_is_((r_lst1, r_lst2), hop):
        if r_lst1.lowleveltype != r_lst2.lowleveltype:
            # obscure logic, the is can be true only if both are None
            v_lst1, v_lst2 = hop.inputargs(r_lst1, r_lst2)
            return hop.gendirectcall(ll_both_none, v_lst1, v_lst2)

        return pairtype(Repr, Repr).rtype_is_(pair(r_lst1, r_lst2), hop)


class ListRepr(AbstractListRepr, BaseListRepr):

    def _setup_repr(self):
        if 'item_repr' not in self.__dict__:
            self.external_item_repr, self.item_repr = externalvsinternal(self.rtyper, self._item_repr_computer())
        if isinstance(self.LIST, GcForwardReference):
            ITEM = self.item_repr.lowleveltype
            ITEMARRAY = GcArray(ITEM)
            # XXX we might think of turning length stuff into Unsigned
            self.LIST.become(GcStruct("list", ("length", Signed),
                                              ("items", Ptr(ITEMARRAY)),
                                      adtmeths = {
                                          "ll_newlist": ll_newlist,
                                          "ll_length": ll_length,
                                          "ll_items": ll_items,
                                          "list_builder": self.list_builder,
                                          "ITEM": ITEM,
                                          "ll_getitem_fast": ll_getitem_fast,
                                          "ll_setitem_fast": ll_setitem_fast,
                                          "_ll_resize_ge": _ll_list_resize_ge,
                                          "_ll_resize_le": _ll_list_resize_le,
                                          "_ll_resize": _ll_list_resize,
                                      })
                             )

    def compact_repr(self):
        return 'ListR %s' % (self.item_repr.compact_repr(),)

    def prepare_const(self, n):
        result = malloc(self.LIST, immortal=True)
        result.length = n
        result.items = malloc(self.LIST.items.TO, n)
        return result


class FixedSizeListRepr(AbstractFixedSizeListRepr, BaseListRepr):

    def _setup_repr(self):
        if 'item_repr' not in self.__dict__:
            self.external_item_repr, self.item_repr = externalvsinternal(self.rtyper, self._item_repr_computer())
        if isinstance(self.LIST, GcForwardReference):
            ITEM = self.item_repr.lowleveltype
            ITEMARRAY = GcArray(ITEM,
                                adtmeths = {
                                     "ll_newlist": ll_fixed_newlist,
                                     "ll_length": ll_fixed_length,
                                     "ll_items": ll_fixed_items,
                                     "list_builder": self.list_builder,
                                     "ITEM": ITEM,
                                     "ll_getitem_fast": ll_fixed_getitem_fast,
                                     "ll_setitem_fast": ll_fixed_setitem_fast,
                                })

            self.LIST.become(ITEMARRAY)

    def compact_repr(self):
        return 'FixedSizeListR %s' % (self.item_repr.compact_repr(),)

    def prepare_const(self, n):
        result = malloc(self.LIST, n, immortal=True)
        return result


# ____________________________________________________________
#
#  Low-level methods.  These can be run for testing, but are meant to
#  be direct_call'ed from rtyped flow graphs, which means that they will
#  get flowed and annotated, mostly with SomePtr.

# adapted C code

def _ll_list_resize_really(l, newsize):
    """
    Ensure ob_item has room for at least newsize elements, and set
    ob_size to newsize.  If newsize > ob_size on entry, the content
    of the new slots at exit is undefined heap trash; it's the caller's
    responsiblity to overwrite them with sane values.
    The number of allocated elements may grow, shrink, or stay the same.
    Failure is impossible if newsize <= self.allocated on entry, although
    that partly relies on an assumption that the system realloc() never
    fails when passed a number of bytes <= the number of bytes last
    allocated (the C standard doesn't guarantee this, but it's hard to
    imagine a realloc implementation where it wouldn't be true).
    Note that self->ob_item may change, and even if newsize is less
    than ob_size on entry.
    """
    allocated = len(l.items)

    # This over-allocates proportional to the list size, making room
    # for additional growth.  The over-allocation is mild, but is
    # enough to give linear-time amortized behavior over a long
    # sequence of appends() in the presence of a poorly-performing
    # system realloc().
    # The growth pattern is:  0, 4, 8, 16, 25, 35, 46, 58, 72, 88, ...
    ## (newsize < 9 ? 3 : 6)
    if newsize < 9:
        some = 3
    else:
        some = 6
    new_allocated = (newsize >> 3) + some + newsize
    if newsize == 0:
        new_allocated = 0
    # XXX consider to have a real realloc
    items = l.items
    newitems = malloc(typeOf(l).TO.items.TO, new_allocated)
    if allocated < new_allocated:
        p = allocated - 1
    else:
        p = new_allocated - 1
    while p >= 0:
            newitems[p] = items[p]
            ITEM = typeOf(l).TO.ITEM
            if isinstance(ITEM, Ptr):
                items[p] = nullptr(ITEM.TO)
            p -= 1
    l.length = newsize
    l.items = newitems

# this common case was factored out of _ll_list_resize
# to see if inlining it gives some speed-up.

def _ll_list_resize(l, newsize):
    # Bypass realloc() when a previous overallocation is large enough
    # to accommodate the newsize.  If the newsize falls lower than half
    # the allocated size, then proceed with the realloc() to shrink the list.
    allocated = len(l.items)
    if allocated >= newsize and newsize >= ((allocated >> 1) - 5):
        l.length = newsize
    else:
        _ll_list_resize_really(l, newsize)

def _ll_list_resize_ge(l, newsize):
    if len(l.items) >= newsize:
        l.length = newsize
    else:
        _ll_list_resize_really(l, newsize)

def _ll_list_resize_le(l, newsize):
    if newsize >= (len(l.items) >> 1) - 5:
        l.length = newsize
    else:
        _ll_list_resize_really(l, newsize)



TEMP = GcArray(Ptr(rstr.STR))

def ll_both_none(lst1, lst2):
    return not lst1 and not lst2
        

# ____________________________________________________________
#
#  Accessor methods

def ll_newlist(LIST, length):
    l = malloc(LIST)
    l.length = length
    l.items = malloc(LIST.items.TO, length)
    return l
ll_newlist = typeMethod(ll_newlist)
ll_newlist.oopspec = 'newlist(length)'

def ll_length(l):
    return l.length

def ll_items(l):
    return l.items

def ll_getitem_fast(l, index):
    return l.ll_items()[index]

def ll_setitem_fast(l, index, item):
    l.ll_items()[index] = item

# fixed size versions

def ll_fixed_newlist(LIST, length):
    l = malloc(LIST, length)
    return l
ll_fixed_newlist = typeMethod(ll_fixed_newlist)
ll_fixed_newlist.oopspec = 'newlist(length)'

def ll_fixed_length(l):
    return len(l)

def ll_fixed_items(l):
    return l

def ll_fixed_getitem_fast(l, index):
    return l[index]

def ll_fixed_setitem_fast(l, index, item):
    l[index] = item

def newlist(llops, r_list, items_v):
    LIST = r_list.LIST
    cno = inputconst(Signed, len(items_v))
    v_result = llops.gendirectcall(LIST.ll_newlist, cno)
    v_func = inputconst(Void, dum_nocheck)
    for i, v_item in enumerate(items_v):
        ci = inputconst(Signed, i)
        llops.gendirectcall(ll_setitem_nonneg, v_func, v_result, ci, v_item)
    return v_result


# ____________________________________________________________
#
#  Iteration.

class ListIteratorRepr(AbstractListIteratorRepr):

    def __init__(self, r_list):
        self.r_list = r_list
        self.lowleveltype = Ptr(GcStruct('listiter',
                                         ('list', r_list.lowleveltype),
                                         ('index', Signed)))
        self.ll_listiter = ll_listiter
        self.ll_listnext = ll_listnext

def ll_listiter(ITERPTR, lst):
    iter = malloc(ITERPTR.TO)
    iter.list = lst
    iter.index = 0
    return iter

def ll_listnext(iter):
    l = iter.list
    index = iter.index
    if index >= l.ll_length():
        raise StopIteration
    iter.index = index + 1
    return l.ll_getitem_fast(index)
