from pypy.objspace.std.objspace import *


class W_TupleObject(object):
    def __init__(self, wrappeditems):
        self.wrappeditems = wrappeditems   # a list of wrapped values


def tuple_unwrap(space, w_tuple):
    items = [space.unwrap(w_item) for w_item in w_tuple.wrappeditems]
    return tuple(items)

StdObjSpace.unwrap.register(tuple_unwrap, W_TupleObject)
