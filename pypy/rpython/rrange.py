from pypy.annotation.pairtype import pairtype
from pypy.rpython.error import TyperError
from pypy.rpython.rmodel import Repr, IntegerRepr, IteratorRepr
from pypy.rpython.lltypesystem.lltype import Ptr, GcStruct, Signed, malloc, Void
from pypy.objspace.flow.model import Constant
from pypy.rpython.rlist import dum_nocheck, dum_checkidx

# ____________________________________________________________
#
#  Concrete implementation of RPython lists that are returned by range()
#  and never mutated afterwards:
#
#    struct range {
#        Signed start, stop;    // step is always constant
#    }
#
#    struct rangest {
#        Signed start, stop, step;    // rare case, for completeness
#    }

RANGE = GcStruct("range", ("start", Signed), ("stop", Signed))
RANGEITER = GcStruct("range", ("next", Signed), ("stop", Signed))

RANGEST = GcStruct("range", ("start", Signed), ("stop", Signed),("step", Signed))
RANGESTITER = GcStruct("range", ("next", Signed), ("stop", Signed), ("step", Signed))

class RangeRepr(Repr):
    def __init__(self, step):
        self.step = step
        if step != 0:
            self.lowleveltype = Ptr(RANGE)
        else:
            self.lowleveltype = Ptr(RANGEST)

    def _getstep(self, v_rng, hop):
        return hop.genop('getfield', [v_rng, hop.inputconst(Void, 'step')],
                         resulttype=Signed)

    def rtype_len(self, hop):
        v_rng, = hop.inputargs(self)
        if self.step != 0:
            cstep = hop.inputconst(Signed, self.step)
        else:
            cstep = self._getstep(v_rng, hop)
        return hop.gendirectcall(ll_rangelen, v_rng, cstep)

    def make_iterator_repr(self):
        return RangeIteratorRepr(self)

class __extend__(pairtype(RangeRepr, IntegerRepr)):

    def rtype_getitem((r_rng, r_int), hop):
        if hop.has_implicit_exception(IndexError):
            spec = dum_checkidx
        else:
            spec = dum_nocheck
        v_func = hop.inputconst(Void, spec)
        v_lst, v_index = hop.inputargs(r_rng, Signed)
        if r_rng.step != 0:
            cstep = hop.inputconst(Signed, r_rng.step)
        else:
            cstep = r_rng._getstep(v_lst, hop)
        if hop.args_s[1].nonneg:
            llfn = ll_rangeitem_nonneg
        else:
            llfn = ll_rangeitem
        hop.exception_is_here()
        return hop.gendirectcall(llfn, v_func, v_lst, v_index, cstep)

# ____________________________________________________________
#
#  Low-level methods.

def _ll_rangelen(start, stop, step):
    if step > 0:
        result = (stop - start + (step-1)) // step
    else:
        result = (start - stop - (step+1)) // (-step)
    if result < 0:
        result = 0
    return result

def ll_rangelen(l, step):
    return _ll_rangelen(l.start, l.stop, step)

def ll_rangeitem_nonneg(func, l, index, step):
    if func is dum_checkidx and index >= _ll_rangelen(l.start, l.stop, step):
        raise IndexError
    return l.start + index * step

def ll_rangeitem(func, l, index, step):
    if func is dum_checkidx:
        length = _ll_rangelen(l.start, l.stop, step)
        if index < 0:
            index += length
        if index < 0 or index >= length:
            raise IndexError
    else:
        if index < 0:
            length = _ll_rangelen(l.start, l.stop, step)
            index += length
    return l.start + index * step

# ____________________________________________________________
#
#  Irregular operations.

def ll_newrange(start, stop):
    l = malloc(RANGE)
    l.start = start
    l.stop = stop
    return l

def ll_newrangest(start, stop, step):
    if step == 0:
        raise ValueError
    l = malloc(RANGEST)
    l.start = start
    l.stop = stop
    l.step = step
    return l

def rtype_builtin_range(hop):
    vstep = hop.inputconst(Signed, 1)
    if hop.nb_args == 1:
        vstart = hop.inputconst(Signed, 0)
        vstop, = hop.inputargs(Signed)
    elif hop.nb_args == 2:
        vstart, vstop = hop.inputargs(Signed, Signed)
    else:
        vstart, vstop, vstep = hop.inputargs(Signed, Signed, Signed)
        if isinstance(vstep, Constant) and vstep.value == 0:
            # not really needed, annotator catches it. Just in case...
            raise TyperError("range cannot have a const step of zero")
    if isinstance(hop.r_result, RangeRepr):
        if hop.r_result.step != 0:
            return hop.gendirectcall(ll_newrange, vstart, vstop)
        else:
            return hop.gendirectcall(ll_newrangest, vstart, vstop, vstep)
    else:
        # cannot build a RANGE object, needs a real list
        r_list = hop.r_result
        cLIST = hop.inputconst(Void, r_list.lowleveltype.TO)
        return hop.gendirectcall(ll_range2list, cLIST, vstart, vstop, vstep)

rtype_builtin_xrange = rtype_builtin_range

def ll_range2list(LIST, start, stop, step):
    if step == 0:
        raise ValueError
    length = _ll_rangelen(start, stop, step)
    l = LIST.ll_newlist(length)
    idx = 0
    items = l.ll_items()
    while idx < length:
        items[idx] = start
        start += step
        idx += 1
    return l

# ____________________________________________________________
#
#  Iteration.

class RangeIteratorRepr(IteratorRepr):
    def __init__(self, r_rng):
        self.r_rng = r_rng
        if r_rng.step != 0:
            self.lowleveltype = Ptr(RANGEITER)
        else:
            self.lowleveltype = Ptr(RANGESTITER)

    def newiter(self, hop):
        v_rng, = hop.inputargs(self.r_rng)
        citerptr = hop.inputconst(Void, self.lowleveltype)
        return hop.gendirectcall(ll_rangeiter, citerptr, v_rng)

    def rtype_next(self, hop):
        v_iter, = hop.inputargs(self)
        args = hop.inputconst(Signed, self.r_rng.step),
        if self.r_rng.step > 0:
            llfn = ll_rangenext_up
        elif self.r_rng.step < 0:
            llfn = ll_rangenext_down
        else:
            llfn = ll_rangenext_updown
            args = ()
        hop.has_implicit_exception(StopIteration) # record that we know about it
        hop.exception_is_here()
        return hop.gendirectcall(llfn, v_iter, *args)

def ll_rangeiter(ITERPTR, rng):
    iter = malloc(ITERPTR.TO)
    iter.next = rng.start
    iter.stop = rng.stop
    if ITERPTR.TO is RANGESTITER:
        iter.step = rng.step
    return iter

def ll_rangenext_up(iter, step):
    next = iter.next
    if next >= iter.stop:
        raise StopIteration
    iter.next = next + step
    return next

def ll_rangenext_down(iter, step):
    next = iter.next
    if next <= iter.stop:
        raise StopIteration
    iter.next = next + step
    return next

def ll_rangenext_updown(iter):
    step = iter.step
    if step > 0:
        return ll_rangenext_up(iter, step)
    else:
        return ll_rangenext_down(iter, step)
