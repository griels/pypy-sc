from pypy.objspace.std.objspace import *
from pypy.objspace.std.intobject import W_IntObject
from pypy.objspace.std.sliceobject import W_SliceObject
from pypy.objspace.std.tupleobject import W_TupleObject

from pypy.objspace.std import slicetype
from pypy.interpreter import gateway
from pypy.objspace.std.restricted_int import r_int, r_uint


class W_ListObject(W_Object):
    from pypy.objspace.std.listtype import list_typedef as typedef
    
    def __init__(w_self, space, wrappeditems):
        W_Object.__init__(w_self, space)
        w_self.ob_item = []
        w_self.ob_size = 0
        newlen = len(wrappeditems)
        _list_resize(w_self, newlen)
        w_self.ob_size = newlen
        items = w_self.ob_item
        p = newlen
        while p:
            p -= 1
            items[p] = wrappeditems[p]

    def __repr__(w_self):
        """ representation for debugging purposes """
        reprlist = [repr(w_item) for w_item in w_self.ob_item[:w_self.ob_size]]
        return "%s(%s)" % (w_self.__class__.__name__, ', '.join(reprlist))

    def unwrap(w_list):
        space = w_list.space
        items = [space.unwrap(w_item) for w_item in w_list.ob_item[:w_list.ob_size]]# XXX generic mixed types unwrap
        return list(items)


registerimplementation(W_ListObject)


def init__List(space, w_list, __args__):
    w_iterable, = __args__.parse('list',
                               (['sequence'], None, None),   # signature
                               [W_ListObject(space, [])])    # default argument
    w_list.ob_size = 0  # XXX think about it later
	
    length = 0
    try:
        length = space.int_w(space.len(w_iterable))
        if length < 0:
            length = 8 
    except OperationError, e:
        pass # for now
    _list_resize(w_list, length)
    w_iterator = space.iter(w_iterable)
    while True:
        try:
            w_item = space.next(w_iterator)
        except OperationError, e:
            if not e.match(space, space.w_StopIteration):
                raise
            break  # done
        _ins1(w_list, w_list.ob_size, w_item)


def len__List(space, w_list):
    result = w_list.ob_size
    return W_IntObject(space, result)

def getitem__List_ANY(space, w_list, w_index):
    items = w_list.ob_item
    idx = space.int_w(w_index)
    if idx < 0:
        idx += w_list.ob_size
    if idx < 0 or idx >= w_list.ob_size:
        raise OperationError(space.w_IndexError,
                             space.wrap("list index out of range"))
    w_item = items[idx]
    return w_item

def getitem__List_Slice(space, w_list, w_slice):
    items = w_list.ob_item
    length = w_list.ob_size
    start, stop, step, slicelength = slicetype.indices4(space, w_slice, length)
    assert slicelength >= 0
    w_res = W_ListObject(space, [])
    _list_resize(w_res, slicelength)
    subitems = w_res.ob_item
    for i in range(slicelength):
        subitems[i] = items[start]
        start += step
    w_res.ob_size = slicelength
    return w_res

def contains__List_ANY(space, w_list, w_obj):
    items = w_list.ob_item
    for i in range(w_list.ob_size):
        if space.eq_w(items[i], w_obj):
            return space.w_True
    return space.w_False

def iter__List(space, w_list):
    from pypy.objspace.std import iterobject
    return iterobject.W_SeqIterObject(space, w_list)

def add__List_List(space, w_list1, w_list2):
    w_res = W_ListObject(space, [])
    newlen = w_list1.ob_size + w_list2.ob_size
    _list_resize(w_res, newlen)
    p = 0
    items = w_res.ob_item
    src = w_list1.ob_item
    for i in range(w_list1.ob_size):
        items[p] = src[i]
        p += 1
    src = w_list2.ob_item
    for i in range(w_list2.ob_size):
        items[p] = src[i]
        p += 1
    w_res.ob_size = p
    return w_res

def inplace_add__List_ANY(space, w_list1, w_iterable2):
    list_extend__List_ANY(space, w_list1, w_iterable2)
    return w_list1

def mul_list_times(space, w_list, times):
    w_res = W_ListObject(space, [])
    src = w_list.ob_item
    size = w_list.ob_size
    newlen = size * times  # XXX check overflow
    _list_resize(w_res, newlen)
    items = w_res.ob_item
    p = 0
    for _ in range(times):
        for i in range(size):
            items[p] = src[i]
            p += 1
    w_res.ob_size = p
    return w_res

def mul__List_ANY(space, w_list, w_times):
    return mul_list_times(space, w_list, space.int_w(w_times))

def mul__ANY_List(space, w_times, w_list):
    return mul_list_times(space, w_list, space.int_w(w_times))

def eq__List_List(space, w_list1, w_list2):
    items1 = w_list1.ob_item
    items2 = w_list2.ob_item
    if w_list1.ob_size != w_list2.ob_size:
        return space.w_False
    for i in range(w_list1.ob_size):
        if not space.is_true(space.eq(items1[i], items2[i])):
            return space.w_False
    return space.w_True

def _min(a, b):
    if a < b:
        return a
    return b

def lt__List_List(space, w_list1, w_list2):
    items1 = w_list1.ob_item
    items2 = w_list2.ob_item
    ncmp = _min(w_list1.ob_size, w_list2.ob_size)
    # Search for the first index where items are different
    for p in range(ncmp):
        if not space.is_true(space.eq(items1[p], items2[p])):
            return space.lt(items1[p], items2[p])
    # No more items to compare -- compare sizes
    return space.newbool(w_list1.ob_size < w_list2.ob_size)

def gt__List_List(space, w_list1, w_list2):
    items1 = w_list1.ob_item
    items2 = w_list2.ob_item
    ncmp = _min(w_list1.ob_size, w_list2.ob_size)
    # Search for the first index where items are different
    for p in range(ncmp):
        if not space.is_true(space.eq(items1[p], items2[p])):
            return space.gt(items1[p], items2[p])
    # No more items to compare -- compare sizes
    return space.newbool(w_list1.ob_size > w_list2.ob_size)

# upto here, lists are nearly identical to tuples, despite the
# fact that we now support over-allocation!

def delitem__List_ANY(space, w_list, w_idx):
    i = space.int_w(w_idx)
    if i < 0:
        i += w_list.ob_size
    if i < 0 or i >= w_list.ob_size:
        raise OperationError(space.w_IndexError,
                             space.wrap("list deletion index out of range"))
    _del_slice(w_list, i, i+1)
    return space.w_None

def delitem__List_Slice(space, w_list, w_slice):
    start, stop, step, slicelength = slicetype.indices4(space, w_slice, w_list.ob_size)
    if step == 1:
        return _setitem_slice_helper(space, w_list, w_slice, [], 0)

    # The current code starts from the top, to simplify
    # coding.  A later optimization could be to start from
    # the bottom, which would reduce the list motion.
    # A further later optimization would be to special-case
    # a step of -1, because this version will perform a LOT
    # of extra motion for this case.  Anybody with a real-life
    # use-case for this is welcome to write the special case.
    r = range(start, stop, step)
    if step > 0:
        r.reverse()
    for i in r:
        _del_slice(w_list, i, i+1)
    return space.w_None

def setitem__List_ANY_ANY(space, w_list, w_index, w_any):
    items = w_list.ob_item
    idx = space.int_w(w_index)
    if idx < 0:
        idx += w_list.ob_size
    if idx < 0 or idx >= w_list.ob_size:
        raise OperationError(space.w_IndexError,
                             space.wrap("list index out of range"))
    items[idx] = w_any
    return space.w_None

def setitem__List_Slice_List(space, w_list, w_slice, w_list2):
    return _setitem_slice_helper(space, w_list, w_slice, w_list2.ob_item, w_list2.ob_size)

def setitem__List_Slice_Tuple(space, w_list, w_slice, w_tuple):
    t = w_tuple.wrappeditems
    return _setitem_slice_helper(space, w_list, w_slice, t, len(t))

def setitem__List_Slice_ANY(space, w_list, w_slice, w_iterable):
##    if isinstance(w_iterable, W_ListObject):
##        return _setitem_slice_helper(space, w_list, w_slice,
##                                     w_iterable.ob_item, w_iterable.ob_size)
##    if isinstance(w_iterable, W_TupleObject):
##        t = w_iterable.wrappeditems
##    else:
    t = space.unpackiterable(w_iterable)
    return _setitem_slice_helper(space, w_list, w_slice, t, len(t))

def _setitem_slice_helper(space, w_list, w_slice, sequence2, len2):
    start, stop, step, slicelength = slicetype.indices4(space, w_slice, w_list.ob_size)
    assert slicelength >= 0

    if step == 1:  # Support list resizing for non-extended slices
        oldsize = w_list.ob_size
        delta = len2 - slicelength
        newsize = oldsize + delta
        _list_resize(w_list, newsize)
        w_list.ob_size = newsize
        r = range(stop+delta, newsize)
        if delta > 0:
            r.reverse()
        items = w_list.ob_item
        for i in r:
            items[i] = items[i-delta]
    elif len2 != slicelength:  # No resize for extended slices
        raise OperationError(space.w_ValueError, space.wrap("attempt to "
              "assign sequence of size %d to extended slice of size %d" %
              (len2,slicelength)))

    r = range(len2)
    items = w_list.ob_item
    if sequence2 is items:
        if step > 0:
            # Always copy starting from the right to avoid
            # having to make a shallow copy in the case where
            # the source and destination lists are the same list.
            r.reverse()
        else:
            # Make a shallow copy to more easily handle the reversal case
            sequence2 = list(sequence2)
    for i in r:
        items[start+i*step] = sequence2[i]
    return space.w_None

listrepr = gateway.appdef("""
    listrepr(currently_in_repr, l):
        'The app-level part of repr().'
        list_id = id(l)
        if list_id in currently_in_repr:
            return '[...]'
        currently_in_repr[list_id] = 1
        try:
            return "[" + ", ".join([repr(x) for x in l]) + ']'
        finally:
            try:
                del currently_in_repr[list_id]
            except:
                pass
""") 
        
def repr__List(space, w_list):
    if w_list.ob_size == 0:
        return space.wrap('[]')
    statedict = space.get_ec_state_dict()
    try:
        w_currently_in_repr = statedict['Py_Repr']
    except KeyError:
        w_currently_in_repr = statedict['Py_Repr'] = space.newdict(())

    return listrepr(space, w_currently_in_repr, w_list)

def hash__List(space,w_list):
    raise OperationError(space.w_TypeError,space.wrap("list objects are unhashable"))

# adapted C code
def _roundupsize(n):
    nbits = r_uint(0)
    n2 = n >> 5

##    /* Round up:
##     * If n <       256, to a multiple of        8.
##     * If n <      2048, to a multiple of       64.
##     * If n <     16384, to a multiple of      512.
##     * If n <    131072, to a multiple of     4096.
##     * If n <   1048576, to a multiple of    32768.
##     * If n <   8388608, to a multiple of   262144.
##     * If n <  67108864, to a multiple of  2097152.
##     * If n < 536870912, to a multiple of 16777216.
##     * ...
##     * If n < 2**(5+3*i), to a multiple of 2**(3*i).
##     *
##     * This over-allocates proportional to the list size, making room
##     * for additional growth.  The over-allocation is mild, but is
##     * enough to give linear-time amortized behavior over a long
##     * sequence of appends() in the presence of a poorly-performing
##     * system realloc() (which is a reality, e.g., across all flavors
##     * of Windows, with Win9x behavior being particularly bad -- and
##     * we've still got address space fragmentation problems on Win9x
##     * even with this scheme, although it requires much longer lists to
##     * provoke them than it used to).
##     */
    while 1:
        n2 >>= 3
        nbits += 3
        if not n2 :
            break
    return ((n >> nbits) + 1) << nbits

# before we have real arrays,
# we use lists, allocated to fixed size.
# XXX memory overflow is ignored here.
# See listobject.c for reference.

for_later = """
#define NRESIZE(var, type, nitems)              \
do {                                \
    size_t _new_size = _roundupsize(nitems);         \
    if (_new_size <= ((~(size_t)0) / sizeof(type)))     \
        PyMem_RESIZE(var, type, _new_size);     \
    else                            \
        var = NULL;                 \
} while (0)
"""

def _list_resize(w_list, newlen):
    if newlen > len(w_list.ob_item):
        true_size = _roundupsize(newlen)
        old_items = w_list.ob_item
        w_list.ob_item = items = [None] * true_size
        for p in range(len(old_items)):
            items[p] = old_items[p]

def _ins1(w_list, where, w_any):
    _list_resize(w_list, w_list.ob_size+1)
    size = w_list.ob_size
    items = w_list.ob_item
    if where < 0:
        where += size
    if where < 0:
        where = 0
    if (where > size):
        where = size
    for i in range(size, where, -1):
        items[i] = items[i-1]
    items[where] = w_any
    w_list.ob_size += 1

def list_insert__List_ANY_ANY(space, w_list, w_where, w_any):
    _ins1(w_list, space.int_w(w_where), w_any)
    return space.w_None

def list_append__List_ANY(space, w_list, w_any):
    _ins1(w_list, w_list.ob_size, w_any)
    return space.w_None

def list_extend__List_ANY(space, w_list, w_any):
    lis = space.unpackiterable(w_any)
    newlen = w_list.ob_size + len(lis)
    _list_resize(w_list, newlen)
    d = w_list.ob_size
    items = w_list.ob_item
    for i in range(len(lis)):
        items[d+i] = lis[i]
    w_list.ob_size = newlen
    return space.w_None

def _del_slice(w_list, ilow, ihigh):
    """ similar to the deletion part of list_ass_slice in CPython """
    if ilow < 0:
        ilow = 0
    elif ilow > w_list.ob_size:
        ilow = w_list.ob_size
    if ihigh < ilow:
        ihigh = ilow
    elif ihigh > w_list.ob_size:
        ihigh = w_list.ob_size
    items = w_list.ob_item
    d = ihigh-ilow
    # XXX this is done by CPython to hold the elements
    # to be deleted. I have no idea how to express
    # this here, but we need to be aware when we write
    # a compiler.
    # recycle = [items[i] for i in range(ilow, ihigh)]
    for i in range(ilow, w_list.ob_size - d):
        items[i] = items[i+d]
        items[i+d] = None
    w_list.ob_size -= d
    # set the unused items to None to make sure the objects are freed
    for i in range(w_list.ob_size, ilow+d):
        items[i] = None

# note that the default value will come back wrapped!!!
def list_pop__List_ANY(space, w_list, w_idx=-1):
    if w_list.ob_size == 0:
        raise OperationError(space.w_IndexError,
                             space.wrap("pop from empty list"))
    i = space.int_w(w_idx)
    if i < 0:
        i += w_list.ob_size
    if i < 0 or i >= w_list.ob_size:
        raise OperationError(space.w_IndexError,
                             space.wrap("pop index out of range"))
    w_res = w_list.ob_item[i]
    _del_slice(w_list, i, i+1)
    return w_res

def list_remove__List_ANY(space, w_list, w_any):
    eq = space.eq
    items = w_list.ob_item
    for i in range(w_list.ob_size):
        cmp = eq(items[i], w_any)
        if space.is_true(cmp):
            _del_slice(w_list, i, i+1)
            return space.w_None
    raise OperationError(space.w_ValueError,
                         space.wrap("list.remove(x): x not in list"))

def list_index__List_ANY_ANY_ANY(space, w_list, w_any, w_start, w_stop):
    eq = space.eq
    items = w_list.ob_item
    size = w_list.ob_size
    w_start = slicetype.adapt_bound(space, w_start, space.wrap(size))
    w_stop = slicetype.adapt_bound(space, w_stop, space.wrap(size))
    start = space.int_w(w_start)
    stop = space.int_w(w_stop)
    for i in range(start,stop):
        cmp = eq(items[i], w_any)
        if space.is_true(cmp):
            return space.wrap(i)
    raise OperationError(space.w_ValueError,
                         space.wrap("list.index(x): x not in list"))

def list_count__List_ANY(space, w_list, w_any):
    eq = space.eq
    items = w_list.ob_item
    count = r_int(0)
    for i in range(w_list.ob_size):
        cmp = eq(items[i], w_any)
        if space.is_true(cmp):
            count += 1
    return space.wrap(count)

# Reverse a slice of a list in place, from lo up to (exclusive) hi.
# (also used in sort, later)

def _reverse_slice(lis, lo, hi):
    hi -= 1
    while lo < hi:
        t = lis[lo]
        lis[lo] = lis[hi]
        lis[hi] = t
        lo += 1
        hi -= 1

def list_reverse__List(space, w_list):
    if w_list.ob_size > 1:
        _reverse_slice(w_list.ob_item, 0, w_list.ob_size)
    return space.w_None

    

# Python Quicksort Written by Magnus Lie Hetland
# http://www.hetland.org/python/quicksort.html

# NOTE:  we cannot yet detect that a user comparision
#        function modifies the list in-place.  The
#        CPython sort() should be studied to learn how
#        to implement this functionality.

def _partition(list, key_list, start, end, lt):
    pivot = list[end]
    key_pivot = key_list[end]                          # Partition around the last value
    bottom = start-1                           # Start outside the area to be partitioned
    top = end                                  # Ditto

    done = 0
    while not done:                            # Until all elements are partitioned...

        while not done:                        # Until we find an out of place element...
            bottom = bottom+1                  # ... move the bottom up.

            if bottom == top:                  # If we hit the top...
                done = 1                       # ... we are done.
                break

            if lt(key_pivot, key_list[bottom]):        # Is the bottom out of place?
                key_list[top] = key_list[bottom]
                list[top] = list[bottom]       # Then put it at the top...
                break                          # ... and start searching from the top.

        while not done:                        # Until we find an out of place element...
            top = top-1                        # ... move the top down.
            
            if top == bottom:                  # If we hit the bottom...
                done = 1                       # ... we are done.
                break

            if lt(key_list[top], key_pivot):           # Is the top out of place?
                key_list[bottom] = key_list[top]
                list[bottom] = list[top]       # Then put it at the bottom...
                break                          # ...and start searching from the bottom.

    key_list[top] = key_pivot
    list[top] = pivot                          # Put the pivot in its place.
    return top                                 # Return the split point


def _quicksort(list, key_list, start, end, lt):
    """list is the list to be sorted
    key_list is the list that will be used for comparisions
    """
    if start < end:                            # If there are two or more elements...
        split = _partition(list, key_list, start, end, lt)    # ... partition the sublist...
        _quicksort(list, key_list, start, split-1, lt)        # ... and sort both halves.
        _quicksort(list, key_list, split+1, end, lt)

class Comparer:
    """Just a dumb container class for a space and a w_cmp, because
    we can't use nested scopes for that in RPython.
    """
    def __init__(self, space, w_cmp):
        self.space = space
        self.w_cmp = w_cmp

    def simple_lt(self, a, b):
        space = self.space
        return space.is_true(space.lt(a, b))

    def complex_lt(self, a, b):
        space = self.space
        w_cmp = self.w_cmp
        w_result = space.call_function(w_cmp, a, b)
        try:
            result = space.int_w(w_result)
        except OperationError, e:
            if e.match(space, space.w_TypeError):
                raise OperationError(space.w_TypeError,
                    space.wrap("comparison function must return int"))
            raise
        return result < 0

def list_sort__List_ANY_ANY_ANY(space, w_list, w_cmp, w_key, w_reverse):
    comparer = Comparer(space, w_cmp)
    if w_cmp is space.w_None:
        lt = comparer.simple_lt
    else:
        lt = comparer.complex_lt
    # The key_list is the result of map(w_key, w_list), and will be
    # used for comparisons during the qsort
    if w_key is not space.w_None:
        key_list = [space.call_function(w_key, item)
                    for item in w_list.ob_item[:w_list.ob_size]]
    else:
        # If no key was specified, then comparison will be made on
        # the original list
        key_list = w_list.ob_item
    # XXX Basic quicksort implementation
    # XXX this is not stable !!
    _quicksort(w_list.ob_item, key_list, 0, w_list.ob_size-1, lt)
    # _quicksort(w_list.ob_item, 0, w_list.ob_size-1, lt)
    # reverse list if needed
    if space.is_true(w_reverse):
        list_reverse__List(space, w_list)
    return space.w_None


"""
static PyMethodDef list_methods[] = {
    {"append",  (PyCFunction)listappend,  METH_O, append_doc},
    {"insert",  (PyCFunction)listinsert,  METH_VARARGS, insert_doc},
    {"extend",      (PyCFunction)listextend,  METH_O, extend_doc},
    {"pop",     (PyCFunction)listpop,     METH_VARARGS, pop_doc},
    {"remove",  (PyCFunction)listremove,  METH_O, remove_doc},
    {"index",   (PyCFunction)listindex,   METH_O, index_doc},
    {"count",   (PyCFunction)listcount,   METH_O, count_doc},
    {"reverse", (PyCFunction)listreverse, METH_NOARGS, reverse_doc},
    {"sort",    (PyCFunction)listsort,    METH_VARARGS, sort_doc},
    {NULL,      NULL}       /* sentinel */
};
"""

from pypy.objspace.std import listtype
register_all(vars(), listtype)
