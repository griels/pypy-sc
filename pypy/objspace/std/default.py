"""Default implementation for some operation."""

from pypy.objspace.std.objspace import *


# These are operations that must fall back to some default behavior that
# should not appear in the explicit object.__xxx__ methods.


# 'eq' falls back to 'is'

def default_eq(space, w_a, w_b):
    return space.is_(w_a, w_b)

StdObjSpace.eq.register(default_eq, W_ANY, W_ANY)


# 'ne' -> 'eq', 'le/gt/ge' -> 'lt'

def default_ne(space, w_a, w_b):
    return space.not_(space.eq(w_a, w_b))
def default_le(space, w_a, w_b):
    return space.not_(space.lt(w_b, w_a))
def default_gt(space, w_a, w_b):
    return space.lt(w_b, w_a)
def default_ge(space, w_a, w_b):
    return space.not_(space.lt(w_a, w_b))

StdObjSpace.ne.register(default_ne, W_ANY, W_ANY)
StdObjSpace.le.register(default_le, W_ANY, W_ANY)
StdObjSpace.gt.register(default_gt, W_ANY, W_ANY)
StdObjSpace.ge.register(default_ge, W_ANY, W_ANY)


# 'id' falls back to the address of the wrapper

def default_id(space, w_obj):
    import intobject
    return intobject.W_IntObject(space, id(w_obj))

StdObjSpace.id.register(default_id, W_ANY)


# this 'not' implementation should be fine for most cases

def default_not(space, w_obj):
    return space.newbool(not space.is_true(w_obj))

StdObjSpace.not_.register(default_not, W_ANY)


# everything is True unless otherwise specified

def default_is_true(space, w_obj):
    return True

StdObjSpace.is_true.register(default_is_true, W_ANY)


# in-place operators fall back to their non-in-place counterpart

for _name, _symbol, _arity, _specialnames in ObjSpace.MethodTable:
    if _name.startswith('inplace_'):
        def default_inplace(space, w_1, w_2, baseop=_name[8:]):
            op = getattr(space, baseop)
            return op(w_1, w_2)
        getattr(StdObjSpace, _name).register(default_inplace, W_ANY, W_ANY)


# 'contains' falls back to iteration

def default_contains(space, w_iterable, w_lookfor):
    w_iter = space.iter(w_iterable)
    while 1:
        try:
            w_next = space.next(w_iter)
        except NoValue:
            return space.w_False
        if space.is_true(space.eq(w_next, w_lookfor)):
            return space.w_True

StdObjSpace.contains.register(default_contains, W_ANY, W_ANY)


# '__get__(descr, inst, cls)' returns 'descr' by default

def default_get(space, w_descr, w_inst, w_cls):
    return w_descr

StdObjSpace.get.register(default_get, W_ANY, W_ANY, W_ANY)
