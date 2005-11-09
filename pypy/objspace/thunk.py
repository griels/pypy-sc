"""Example usage:

    $ py.py -o thunk
    >>> def f():
    ...     print 'computing...'
    ...     return 6*7
    ...
    >>> x = thunk(f)
    >>> x
    computing...
    42
    >>> x
    42
    >>> y = thunk(f)
    >>> type(y)
    computing...
    <pypy type 'int'>
"""

from pypy.objspace.proxy import patch_space_in_place
from pypy.interpreter import gateway, baseobjspace, argument
from pypy.interpreter.error import OperationError

# __________________________________________________________________________

# 'w_obj.w_thunkalias' points to another object that 'w_obj' has turned into
baseobjspace.W_Root.w_thunkalias = None

class W_Thunk(baseobjspace.W_Root, object):
    def __init__(w_self, w_callable, args):
        w_self.w_callable = w_callable
        w_self.args = args
        w_self.w_thunkalias = w_self   # special marker for not-computed-yet


def _force_thunk(space, w_self):
    if not isinstance(w_self, W_Thunk):
        raise OperationError(space.w_RuntimeError,
                             space.wrap("cyclic thunk chain"))
    w_callable = w_self.w_callable
    args       = w_self.args
    if w_callable is None or args is None:
        raise OperationError(space.w_RuntimeError,
                             space.wrap("thunk is already being computed"))
    w_self.w_callable = None
    w_self.args       = None
    w_alias = space.call_args(w_callable, args)
    # XXX detect circular w_alias result
    w_self.w_thunkalias = w_alias
    return w_alias

def force(space, w_obj):
    while True:
        w_alias = w_obj.w_thunkalias
        if w_alias is None:
            return w_obj
        if w_alias is w_obj:  # detect the special marker for not-computed-yet
            w_alias = _force_thunk(space, w_alias)
        w_obj = w_alias

def thunk(w_callable, __args__):
    return W_Thunk(w_callable, __args__)
app_thunk = gateway.interp2app(thunk, unwrap_spec=[baseobjspace.W_Root,
                                                   argument.Arguments])

def is_thunk(space, w_obj):
    return space.newbool(w_obj.w_thunkalias is w_obj)
app_is_thunk = gateway.interp2app(is_thunk)

def become(space, w_target, w_source):
    w_target = force(space, w_target)
    w_target.w_thunkalias = w_source
    return space.w_None
app_become = gateway.interp2app(become)

# __________________________________________________________________________

nb_forcing_args = {}

def setup():
    nb_forcing_args.update({
        'setattr': 2,   # instead of 3
        'setitem': 2,   # instead of 3
        'get': 2,       # instead of 3
        # ---- irregular operations ----
        'wrap': 0,
        'str_w': 1,
        'int_w': 1,
        'float_w': 1,
        'uint_w': 1,
        'interpclass_w': 1,
        'unwrap': 1,
        'is_true': 1,
        'is_w': 2,
        'newtuple': 0,
        'newlist': 0,
        'newstring': 0,
        'newunicode': 0,
        'newdict': 0,
        'newslice': 0,
        'call_args': 1,
        'marshal_w': 1,
        'log': 1,
        })
    for opname, _, arity, _ in baseobjspace.ObjSpace.MethodTable:
        nb_forcing_args.setdefault(opname, arity)
    for opname in baseobjspace.ObjSpace.IrregularOpTable:
        assert opname in nb_forcing_args, "missing %r" % opname

setup()
del setup

# __________________________________________________________________________

def proxymaker(space, opname, parentfn):
    nb_args = nb_forcing_args[opname]
    if nb_args == 0:
        proxy = None
    elif nb_args == 1:
        def proxy(w1, *extra):
            w1 = force(space, w1)
            return parentfn(w1, *extra)
    elif nb_args == 2:
        def proxy(w1, w2, *extra):
            w1 = force(space, w1)
            w2 = force(space, w2)
            return parentfn(w1, w2, *extra)
    elif nb_args == 3:
        def proxy(w1, w2, w3, *extra):
            w1 = force(space, w1)
            w2 = force(space, w2)
            w3 = force(space, w3)
            return parentfn(w1, w2, w3, *extra)
    else:
        raise NotImplementedError("operation %r has arity %d" %
                                  (opname, nb_args))
    return proxy

def Space(*args, **kwds):
    # for now, always make up a wrapped StdObjSpace
    from pypy.objspace import std
    space = std.Space(*args, **kwds)
    patch_space_in_place(space, 'thunk', proxymaker)
    space.setitem(space.builtin.w_dict, space.wrap('thunk'),
                  space.wrap(app_thunk))
    space.setitem(space.builtin.w_dict, space.wrap('is_thunk'),
                  space.wrap(app_is_thunk))
    space.setitem(space.builtin.w_dict, space.wrap('become'),
                 space.wrap(app_become))
    return space
