from pypy.objspace.std.stdtypedef import *
from pypy.objspace.std.objecttype import object_typedef
from pypy.interpreter.error import OperationError

def descr__new__(space, w_inttype, w_value=None, w_base=None):
    from intobject import W_IntObject
    if w_base is None:
        w_base = space.w_None
    if w_value is None:
        w_obj = space.newint(0)
    elif w_base == space.w_None and not space.is_true(space.isinstance(w_value, space.w_str)):
            w_obj = space.int(w_value)
    else:
        if w_base == space.w_None:
            base = 0
        else:
            base = space.unwrap(w_base)
        # XXX write the logic for int("str", base)
        s = space.unwrap(w_value)
        try:
            value = int(s, base)
        except TypeError, e:
            raise OperationError(space.w_TypeError,
                         space.wrap(str(e)))
        except ValueError, e:
            raise OperationError(space.w_ValueError,
                         space.wrap(str(e)))
        except OverflowError, e:
            raise OperationError(space.w_OverflowError,
                         space.wrap(str(e)))
        w_obj = W_IntObject(space, value)
    return space.w_int.check_user_subclass(w_inttype, w_obj)

# ____________________________________________________________

int_typedef = StdTypeDef("int", [object_typedef],
    __new__ = newmethod(descr__new__),
    )
