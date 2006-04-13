from pypy.annotation.pairtype import pairtype
from pypy.rpython.rlist import AbstractBaseListRepr, AbstractListRepr, \
        AbstractListIteratorRepr, rtype_newlist
from pypy.rpython.rmodel import Repr, IntegerRepr
from pypy.rpython.rmodel import inputconst, externalvsinternal
from pypy.rpython.lltypesystem.lltype import Signed, Void
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.ootypesystem.riterable import iterator_type
from pypy.rpython.ootypesystem.rslice import SliceRepr, \
     startstop_slice_repr, startonly_slice_repr, minusone_slice_repr


class BaseListRepr(AbstractBaseListRepr):

    def __init__(self, rtyper, item_repr, listitem=None):
        self.rtyper = rtyper
        if not isinstance(item_repr, Repr):  # not computed yet, done by setup()
            assert callable(item_repr)
            self._item_repr_computer = item_repr
            self.LIST = ootype.ForwardReference()
        else:
            self.LIST = ootype.List(item_repr.lowleveltype)
            self.external_item_repr, self.item_repr = \
                    externalvsinternal(rtyper, item_repr)
        self.lowleveltype = self.LIST
        self.listitem = listitem
        self.list_cache = {}
        self.ll_concat = ll_concat
        self.ll_extend = ll_extend
        self.ll_listslice_startonly = ll_listslice_startonly
        self.ll_listslice = ll_listslice
        self.ll_listslice_minusone = ll_listslice_minusone
        self.ll_listsetslice = ll_listsetslice        
        # setup() needs to be called to finish this initialization

    def _setup_repr(self):
        if 'item_repr' not in self.__dict__:
            self.external_item_repr, self.item_repr = \
                    externalvsinternal(self.rtyper, self._item_repr_computer())
        if isinstance(self.lowleveltype, ootype.ForwardReference):
            self.lowleveltype.become(ootype.List(self.item_repr.lowleveltype))

    def send_message(self, hop, message, can_raise=False, v_args=None):
        if v_args is None:
            v_args = hop.inputargs(self, *hop.args_r[1:])
        c_name = hop.inputconst(ootype.Void, message)
        if can_raise:
            hop.exception_is_here()
        return hop.genop("oosend", [c_name] + v_args,
                resulttype=hop.r_result.lowleveltype)

    def rtype_len(self, hop):
        return self.send_message(hop, "length")

    def rtype_method_append(self, hop):
        return self.send_message(hop, "append")

    def rtype_method_extend(self, hop):
        return self.send_message(hop, "extend")

    def make_iterator_repr(self):
        return ListIteratorRepr(self)

class ListRepr(AbstractListRepr, BaseListRepr):

    pass

FixedSizeListRepr = ListRepr

class __extend__(pairtype(BaseListRepr, IntegerRepr)):

    def rtype_getitem((r_list, r_int), hop):
        if hop.args_s[1].nonneg:
            return r_list.send_message(hop, "getitem_nonneg", can_raise=True)
        else:
            v_list, v_index = hop.inputargs(r_list, Signed)            
            hop.exception_is_here()
            v_res = hop.gendirectcall(ll_getitem, v_list, v_index)
            return r_list.recast(hop.llops, v_res)

    def rtype_setitem((r_list, r_int), hop):
        if hop.args_s[1].nonneg:
            return r_list.send_message(hop, "setitem_nonneg", can_raise=True)
        else:
            v_list, v_index, v_item = hop.inputargs(r_list, Signed, r_list.item_repr)
            hop.exception_is_here()
            return hop.gendirectcall(ll_setitem, v_list, v_index, v_item)


def newlist(llops, r_list, items_v):
    c_1ist = inputconst(ootype.Void, r_list.lowleveltype)
    v_result = llops.genop("new", [c_1ist], resulttype=r_list.lowleveltype)
    c_append = inputconst(ootype.Void, "append")
    # This is very inefficient for a large amount of initial items ...
    for v_item in items_v:
        llops.genop("oosend", [c_append, v_result, v_item],
                resulttype=ootype.Void)
    return v_result

# These helpers are sometimes trivial but help encapsulation

def ll_newlist(LIST):
    return ootype.new(LIST)

def ll_getitem(lst, index):
    if index < 0:
        index += lst.length()
    return lst.getitem_nonneg(index)

def ll_setitem(lst, index, item):
    if index < 0:
        index += lst.length()
    return lst.setitem_nonneg(index, item)

def ll_append(lst, item):
    lst.append(item)

def ll_extend(l1, l2):
    # This is a bit inefficient, could also add extend to the list interface
    len2 = l2.length()
    i = 0
    while i < len2:
        l1.append(l2.getitem_nonneg(i))
        i += 1

def ll_concat(RESLIST, l1, l2):
    len1 = l1.length()
    len2 = l2.length()
    l = ootype.new(RESLIST)
    i = 0
    while i < len1:
        l.append(l1.getitem_nonneg(i))
        i += 1
    i = 0
    while i < len2:
        l.append(l2.getitem_nonneg(i))
        i += 1
    return l

def ll_listslice_startonly(RESLIST, lst, start):
    len1 = lst.length()
    #newlength = len1 - start
    res = ootype.new(RESLIST) # TODO: pre-allocate newlength elements
    i = start
    while i < len1:
        res.append(lst.getitem_nonneg(i))
        i += 1
    return res

def ll_listslice(RESLIST, lst, slice):
    start = slice.start
    stop = slice.stop
    length = lst.length()
    if stop > length:
        stop = length
    #newlength = stop - start
    res = ootype.new(RESLIST) # TODO: pre-allocate newlength elements
    i = start
    while i < stop:
        res.append(lst.getitem_nonneg(i))
        i += 1
    return res

def ll_listslice_minusone(RESLIST, lst):
    newlength = lst.length() - 1
    #assert newlength >= 0 # TODO: asserts seems to have problems with ootypesystem
    res = ootype.new(RESLIST) # TODO: pre-allocate newlength elements
    i = 0
    while i < newlength:
        res.append(lst.getitem_nonneg(i))
        i += 1
    return res

def ll_listsetslice(l1, slice, l2):
    count = l2.length()
##    assert count == slice.stop - slice.start, (    # TODO: see above
##        "setslice cannot resize lists in RPython")
    # XXX but it should be easy enough to support, soon
    start = slice.start
    j = start
    i = 0
    while i < count:
        l1.setitem_nonneg(j, l2.getitem_nonneg(i))
        i += 1
        j += 1


# ____________________________________________________________
#
#  Iteration.

class ListIteratorRepr(AbstractListIteratorRepr):

    def __init__(self, r_list):
        self.r_list = r_list
        self.lowleveltype = iterator_type(r_list, r_list.item_repr)
        self.ll_listiter = ll_listiter
        self.ll_listnext = ll_listnext


def ll_listiter(ITER, lst):
    iter = ootype.new(ITER)
    iter.iterable = lst
    iter.index = 0
    return iter

def ll_listnext(iter):
    l = iter.iterable
    index = iter.index
    if index >= l.length():
        raise StopIteration
    iter.index = index + 1
    return l.getitem_nonneg(index)

