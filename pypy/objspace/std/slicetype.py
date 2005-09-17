import sys
from pypy.interpreter import baseobjspace
from pypy.objspace.std.stdtypedef import *
from pypy.objspace.std.register_all import register_all
from pypy.interpreter.error import OperationError

slice_indices = MultiMethod('indices', 2)

def slice_indices__ANY_ANY(space, w_slice, w_length):
    length = space.int_w(w_length)
    start, stop, step = indices3(space, w_slice, length)
    return space.newtuple([space.wrap(start), space.wrap(stop),
                           space.wrap(step)])

# utility functions
def _Eval_SliceIndex(space, w_int):
    try:
        x = space.int_w(w_int)
    except OperationError, e:
        if not e.match(space, space.w_OverflowError):
            raise
        cmp = space.is_true(space.ge(w_int, space.wrap(0)))
        if cmp:
            x = sys.maxint
        else:
            x = -sys.maxint
    return x

def indices3(space, w_slice, length):
    if space.is_true(space.is_(w_slice.w_step, space.w_None)):
        step = 1
    else:
        step = _Eval_SliceIndex(space, w_slice.w_step)
        if step == 0:
            raise OperationError(space.w_ValueError,
                                 space.wrap("slice step cannot be zero"))
    if space.is_true(space.is_(w_slice.w_start, space.w_None)):
        if step < 0:
            start = length - 1
        else:
            start = 0
    else:
        start = _Eval_SliceIndex(space, w_slice.w_start)
        if start < 0:
            start += length
            if start < 0:
                if step < 0:
                    start = -1
                else:
                    start = 0
        elif start >= length:
            if step < 0:
                start = length - 1
            else:
                start = length
    if space.is_true(space.is_(w_slice.w_stop, space.w_None)):
        if step < 0:
            stop = -1
        else:
            stop = length
    else:
        stop = _Eval_SliceIndex(space, w_slice.w_stop)
        if stop < 0:
            stop += length
            if stop < 0:
                stop =-1
        elif stop > length:
            stop = length
    return start, stop, step

def indices4(space, w_slice, length):
    start, stop, step = indices3(space, w_slice, length)
    if (step < 0 and stop >= start) or (step > 0 and start >= stop):
        slicelength = 0
    elif step < 0:
        slicelength = (stop - start + 1) / step + 1
    else:
        slicelength = (stop - start - 1) / step + 1
    return start, stop, step, slicelength

def adapt_bound(space, w_index, w_size):
    if not (space.is_true(space.isinstance(w_index, space.w_int)) or
            space.is_true(space.isinstance(w_index, space.w_long))):
        raise OperationError(space.w_TypeError,
                             space.wrap("slice indices must be integers"))
    if space.is_true(space.lt(w_index, space.wrap(0))):
        w_index = space.add(w_index, w_size)
        if space.is_true(space.lt(w_index, space.wrap(0))):
            w_index = space.wrap(0)
    if space.is_true(space.gt(w_index, w_size)):
        w_index = w_size
    return w_index

register_all(vars(), globals())

# ____________________________________________________________

def descr__new__(space, w_slicetype, args_w):
    from pypy.objspace.std.sliceobject import W_SliceObject
    w_start = space.w_None
    w_stop = space.w_None
    w_step = space.w_None
    if len(args_w) == 1:
        w_stop, = args_w
    elif len(args_w) == 2:
        w_start, w_stop = args_w
    elif len(args_w) == 3:
        w_start, w_stop, w_step = args_w
    elif len(args_w) > 3:
        raise OperationError(space.w_TypeError,
                             space.wrap("slice() takes at most 3 arguments"))
    else:
        raise OperationError(space.w_TypeError,
                             space.wrap("slice() takes at least 1 argument"))
    w_obj = space.allocate_instance(W_SliceObject, w_slicetype)
    W_SliceObject.__init__(w_obj, space, w_start, w_stop, w_step)
    return w_obj
#
descr__new__.unwrap_spec = [baseobjspace.ObjSpace, baseobjspace.W_Root,
                            'args_w']

# ____________________________________________________________

def slicewprop(name):
    def fget(space, w_obj):
        from pypy.objspace.std.sliceobject import W_SliceObject
        if not isinstance(w_obj, W_SliceObject):
            raise OperationError(space.w_TypeError,
                                 space.wrap("descriptor is for 'slice'"))
        return getattr(w_obj, name)
    return GetSetProperty(fget)


slice_typedef = StdTypeDef("slice",
    __doc__ = '''slice([start,] stop[, step])

Create a slice object.  This is used for extended slicing (e.g. a[0:10:2]).''',
    __new__ = newmethod(descr__new__),
    start = slicewprop('w_start'),
    stop  = slicewprop('w_stop'),
    step  = slicewprop('w_step'),
    )
slice_typedef.registermethods(globals())
