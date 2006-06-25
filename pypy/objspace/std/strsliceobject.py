from pypy.objspace.std.objspace import *
from pypy.objspace.std.stringobject import W_StringObject
from pypy.objspace.std.unicodeobject import delegate_String2Unicode


class W_StringSliceObject(W_Object):
    from pypy.objspace.std.stringtype import str_typedef as typedef

    def __init__(w_self, str, start, stop):
        w_self.str = str
        w_self.start = start
        w_self.stop = stop

    def force(w_self):
        str = w_self.str[w_self.start:w_self.stop]
        w_self.str = str
        w_self.start = 0
        w_self.stop = len(str)
        return str

    def __repr__(w_self):
        """ representation for debugging purposes """
        return "%s(%r[%d:%d])" % (w_self.__class__.__name__,
                                  w_self.str, w_self.start, w_self.stop)


registerimplementation(W_StringSliceObject)


def delegate_slice2str(space, w_strslice):
    return W_StringObject(w_strslice.force())

def delegate_slice2unicode(space, w_strslice):
    w_str = W_StringObject(w_strslice.force())
    return delegate_String2Unicode(space, w_str)

# ____________________________________________________________

def contains__StringSlice_String(space, w_self, w_sub):
    sub = w_sub._value
    return space.newbool(w_self.str.find(sub, w_self.start, w_self.stop) >= 0)


def _convert_idx_params(space, w_self, w_sub, w_start, w_end):
    length = w_self.stop - w_self.start
    sub = w_sub._value
    w_start = slicetype.adapt_bound(space, w_start, space.wrap(length))
    w_end = slicetype.adapt_bound(space, w_end, space.wrap(length))

    start = space.int_w(w_start)
    end = space.int_w(w_end)
    assert start >= 0
    assert end >= 0

    return (w_self.str, sub, w_self.start + start, end)


def str_find__StringSlice_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.find(sub, start, end)
    return space.wrap(res)

def str_rfind__StringSlice_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.rfind(sub, start, end)
    return space.wrap(res)

def str_index__StringSlice_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.find(sub, start, end)
    if res < 0:
        raise OperationError(space.w_ValueError,
                             space.wrap("substring not found in string.index"))

    return space.wrap(res)


def str_rindex__StringSlice_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.rfind(sub, start, end)
    if res < 0:
        raise OperationError(space.w_ValueError,
                             space.wrap("substring not found in string.rindex"))

    return space.wrap(res)


def str_w__StringSlice(space, w_str):
    return w_str.force()


def getitem__StringSlice_ANY(space, w_str, w_index):
    ival = space.int_w(w_index)
    slen = w_str.stop - w_str.start
    if ival < 0:
        ival += slen
    if ival < 0 or ival >= slen:
        exc = space.call_function(space.w_IndexError,
                                  space.wrap("string index out of range"))
        raise OperationError(space.w_IndexError, exc)
    return W_StringObject(w_str.str[w_str.start + ival])

def getitem__StringSlice_Slice(space, w_str, w_slice):
    w = space.wrap
    length = w_str.stop - w_str.start
    start, stop, step, sl = w_slice.indices4(space, length)
    if sl == 0:
        str = ""
    else:
        s = w_str.str
        start = w_str.start + start
        if step == 1:
            stop = w_str.start + stop
            assert start >= 0 and stop >= 0
            return W_StringSliceObject(s, start, stop)
        else:
            str = "".join([s[start + i*step] for i in range(sl)])
    return W_StringObject(str)

def len__StringSlice(space, w_str):
    return space.wrap(w_str.stop - w_str.start)


def str__StringSlice(space, w_str):
    if type(w_str) is W_StringSliceObject:
        return w_str
    return W_StringSliceObject(w_str.str, w_str.start, w_str.stop)
