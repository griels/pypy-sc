"""
Interp-level implementation of the basic space operations.
"""

from pypy.interpreter import gateway
from pypy.interpreter.error import OperationError 
NoneNotWrapped = gateway.NoneNotWrapped

def abs(space, w_val):
    "abs(number) -> number\n\nReturn the absolute value of the argument."
    return space.abs(w_val)

def chr(space, w_ascii):
    w_character = space.newstring([w_ascii])
    return w_character

def len(space, w_obj):
    "len(object) -> integer\n\nReturn the number of items of a sequence or mapping."
    return space.len(w_obj)

def delattr(space, w_object, w_name):
    space.delattr(w_object, w_name)
    return space.w_None

def getattr(space, w_object, w_name, w_defvalue=NoneNotWrapped):
    if space.is_true(space.isinstance(w_name, space.w_unicode)): # xxx collect this logic somewhere
        w_name = space.call_method(w_name, 'encode')
    try:
        return space.getattr(w_object, w_name)
    except OperationError, e:
        if e.match(space, space.w_AttributeError):
            if w_defvalue is not None:
                return w_defvalue
        raise

def hash(space, w_object):
    return space.hash(w_object)

def oct(space, w_val):
    # XXX does this need to be a space operation?
    return space.oct(w_val)

def hex(space, w_val):
    return space.hex(w_val)

def round(space, w_val, w_n=0):
    return space.round(w_val, w_n)

def id(space, w_object):
    return space.id(w_object)

def cmp(space, w_x, w_y):
    """return 0 when x == y, -1 when x < y and 1 when x > y """
    return space.cmp(w_x, w_y)

def coerce(space, w_x, w_y):
    """coerce(x, y) -> (x1, y1)

    Return a tuple consisting of the two numeric arguments converted to
    a common type, using the same rules as used by arithmetic operations.
    If coercion is not possible, raise TypeError."""
    return space.coerce(w_x, w_y)

def divmod(space, w_x, w_y):
    return space.divmod(w_x, w_y)

# semi-private: works only for new-style classes.
def _issubtype(space, w_cls1, w_cls2):
    return space.issubtype(w_cls1, w_cls2)


# ____________________________________________________________

app = gateway.applevel('''
    # App-level implementation of the iter(callable,sentinel) operation.

    def iter_generator(callable_, sentinel):
        while 1:
            result = callable_()
            if result == sentinel:
                return
            yield result

    def iter_sentinel(callable_, sentinel):
        if not callable(callable_):
            raise TypeError, 'iter(v, w): v must be callable'
        return iter_generator(callable_, sentinel)

''')
iter_sentinel = app.interphook("iter_sentinel")

def iter(space, w_collection_or_callable, w_sentinel=NoneNotWrapped):
    if w_sentinel is None:
        return space.iter(w_collection_or_callable)
    else:
        return iter_sentinel(space, w_collection_or_callable, w_sentinel)

def _seqiter(space, w_obj):
    return space.newseqiter(w_obj)

def ord(space, w_val):
    return space.ord(w_val)

def pow(space, w_base, w_exponent, w_modulus=None):
    return space.pow(w_base, w_exponent, w_modulus)

def repr(space, w_object):
    return space.repr(w_object)

def setattr(space, w_object, w_name, w_val):
    space.setattr(w_object, w_name, w_val)
    return space.w_None
