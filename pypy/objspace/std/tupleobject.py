from pypy.objspace.std.objspace import *
from intobject import W_IntObject
from sliceobject import W_SliceObject


class W_TupleObject(W_Object):

    def __init__(w_self, space, wrappeditems):
        W_Object.__init__(w_self, space)
        w_self.wrappeditems = wrappeditems   # a list of wrapped values

    def __repr__(w_self):
        """ representation for debugging purposes """
        reprlist = [repr(w_item) for w_item in w_self.wrappeditems]
        return "%s(%s)" % (w_self.__class__.__name__, ', '.join(reprlist))


def tuple_unwrap(space, w_tuple):
    items = [space.unwrap(w_item) for w_item in w_tuple.wrappeditems]
    return tuple(items)

StdObjSpace.unwrap.register(tuple_unwrap, W_TupleObject)

def tuple_is_true(space, w_tuple):
    return not not w_tuple.wrappeditems

StdObjSpace.is_true.register(tuple_is_true, W_TupleObject)

def tuple_len(space, w_tuple):
    result = len(w_tuple.wrappeditems)
    return W_IntObject(space, result)

StdObjSpace.len.register(tuple_len, W_TupleObject)

def getitem_tuple_int(space, w_tuple, w_index):
    items = w_tuple.wrappeditems
    try:
        w_item = items[w_index.intval]
    except IndexError:
        raise OperationError(space.w_IndexError,
                             space.wrap("tuple index out of range"))
    return w_item

StdObjSpace.getitem.register(getitem_tuple_int, W_TupleObject, W_IntObject)

def getitem_tuple_slice(space, w_tuple, w_slice):
    items = w_tuple.wrappeditems
    w_length = space.wrap(len(items))
    w_start, w_stop, w_step, w_slicelength = w_slice.indices(space, w_length)
    start       = space.unwrap(w_start)
    step        = space.unwrap(w_step)
    slicelength = space.unwrap(w_slicelength)
    assert slicelength >= 0
    subitems = [None] * slicelength
    for i in range(slicelength):
        subitems[i] = items[start]
        start += step
    return W_TupleObject(space, subitems)

StdObjSpace.getitem.register(getitem_tuple_slice, W_TupleObject, W_SliceObject)

def tuple_iter(space, w_tuple):
    import iterobject
    return iterobject.W_SeqIterObject(space, w_tuple)

StdObjSpace.iter.register(tuple_iter, W_TupleObject)

def tuple_add(space, w_tuple1, w_tuple2):
    items1 = w_tuple1.wrappeditems
    items2 = w_tuple2.wrappeditems
    return W_TupleObject(space, items1 + items2)

StdObjSpace.add.register(tuple_add, W_TupleObject, W_TupleObject)

def tuple_int_mul(space, w_tuple, w_int):
    items = w_tuple.wrappeditems
    times = w_int.intval
    return W_TupleObject(space, items * times)

StdObjSpace.mul.register(tuple_int_mul, W_TupleObject, W_IntObject)

def int_tuple_mul(space, w_int, w_tuple):
    return tuple_int_mul(space, w_tuple, w_int)

StdObjSpace.mul.register(int_tuple_mul, W_IntObject, W_TupleObject)

def tuple_eq(space, w_tuple1, w_tuple2):
    items1 = w_tuple1.wrappeditems
    items2 = w_tuple2.wrappeditems
    if len(items1) != len(items2):
        return space.w_False
    for item1, item2 in zip(items1, items2):
        if not space.is_true(space.eq(item1, item2)):
            return space.w_False
    return space.w_True

StdObjSpace.eq.register(tuple_eq, W_TupleObject, W_TupleObject)
