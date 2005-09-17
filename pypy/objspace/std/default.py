"""Default implementation for some operation."""

from pypy.objspace.std.objspace import *


# The following default implementations are used before delegation is tried.
# 'id' is normally the address of the wrapper.

def id__ANY(space, w_obj):
    #print 'id:', w_obj
    from pypy.objspace.std import intobject
    return intobject.W_IntObject(space, id(w_obj))

# __init__ should succeed if called internally as a multimethod

def init__ANY(space, w_obj, __args__):
    pass

def typed_unwrap_error_msg(space, expected, w_obj):
    w = space.wrap
    type_name = space.str_w(space.getattr(space.type(w_obj),w("__name__")))
    return w("expected %s, got %s object" % (expected, type_name))

def int_w__ANY(space,w_obj):
    raise OperationError(space.w_TypeError,
                         typed_unwrap_error_msg(space, "integer", w_obj))

def str_w__ANY(space,w_obj):
    raise OperationError(space.w_TypeError,
                         typed_unwrap_error_msg(space, "string", w_obj))

def float_w__ANY(space,w_obj):
    raise OperationError(space.w_TypeError,
                         typed_unwrap_error_msg(space, "float", w_obj))

def uint_w__ANY(space,w_obj):
    raise OperationError(space.w_TypeError,
                         typed_unwrap_error_msg(space, "integer", w_obj))

register_all(vars())
