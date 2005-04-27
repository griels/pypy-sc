from pypy.objspace.std.stdtypedef import *
from pypy.objspace.std.strutil import string_to_w_long, ParseStringError
from pypy.interpreter.error import OperationError
from pypy.objspace.std.inttype import int_typedef
from pypy.interpreter.gateway import NoneNotWrapped

def descr__new__(space, w_longtype, w_value=0, w_base=NoneNotWrapped):
    from pypy.objspace.std.longobject import W_LongObject, args_from_long
    if w_base is None:
        # check for easy cases
        if isinstance(w_value, W_LongObject):
            pass
        elif space.is_true(space.isinstance(w_value, space.w_str)):
            try:
                w_value = string_to_w_long(space, space.str_w(w_value))
            except ParseStringError, e:
                raise OperationError(space.w_ValueError,
                                     space.wrap(e.msg))
        else:
            # otherwise, use the __long__() method
            w_obj = space.long(w_value)
            # 'long(x)' should return whatever x.__long__() returned
            if space.is_true(space.is_(w_longtype, space.w_long)):
                return w_obj
            if space.is_true(space.isinstance(w_obj, w_long)):
                w_value = w_obj
            elif space.is_true(space.isinstance(w_obj, w_int)):
                intval = space.int_w(w_obj)
                # xxx this logic needs to be put in 1 place                
                if intval < 0:
                    sign = -1
                elif intval > 0:
                    sign = 1
                else:
                    sign = 0
                w_value = W_LongObject(space, [r_uint(abs(intval))], sign) 
            else:
                raise OperationError(space.w_ValueError,
                                    space.wrap("value can't be converted to long"))
    else:
        base = space.int_w(w_base)

        if space.is_true(space.isinstance(w_value, space.w_unicode)):
            from pypy.objspace.std.unicodeobject import unicode_to_decimal_w
            s = unicode_to_decimal_w(space, w_value)
        else:
            try:
                s = space.str_w(w_value)
            except OperationError, e:
                raise OperationError(space.w_TypeError,
                                     space.wrap("long() can't convert non-string "
                                                "with explicit base"))
        try:
            w_value = string_to_w_long(space, s, base)
        except ParseStringError, e:
            raise OperationError(space.w_ValueError,
                                 space.wrap(e.msg))

    w_obj = space.allocate_instance(W_LongObject, w_longtype)
    w_obj.__init__(space, w_value.digits, w_value.sign)
    return w_obj

# ____________________________________________________________

long_typedef = StdTypeDef("long",
    __new__ = newmethod(descr__new__),
    )
