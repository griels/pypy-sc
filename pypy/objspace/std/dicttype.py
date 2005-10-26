from pypy.objspace.std.stdtypedef import *
from pypy.objspace.std.register_all import register_all
from pypy.interpreter.error import OperationError

dict_copy       = StdObjspaceMultiMethod('copy',          1)
dict_items      = StdObjspaceMultiMethod('items',         1)
dict_keys       = StdObjspaceMultiMethod('keys',          1)
dict_values     = StdObjspaceMultiMethod('values',        1)
dict_has_key    = StdObjspaceMultiMethod('has_key',       2)
dict_clear      = StdObjspaceMultiMethod('clear',         1)
dict_get        = StdObjspaceMultiMethod('get',           3, defaults=(None,))
dict_pop        = StdObjspaceMultiMethod('pop',           2, w_varargs=True)
dict_popitem    = StdObjspaceMultiMethod('popitem',       1)
dict_setdefault = StdObjspaceMultiMethod('setdefault',    3, defaults=(None,))
dict_update     = StdObjspaceMultiMethod('update',        2, defaults=((),))
dict_iteritems  = StdObjspaceMultiMethod('iteritems',     1)
dict_iterkeys   = StdObjspaceMultiMethod('iterkeys',      1)
dict_itervalues = StdObjspaceMultiMethod('itervalues',    1)
dict_reversed   = StdObjspaceMultiMethod('__reversed__',      1)

def dict_reversed__ANY(space, w_dict):
    raise OperationError(space.w_TypeError, space.wrap('argument to reversed() must be a sequence'))

#dict_fromkeys   = MultiMethod('fromkeys',      2, varargs=True)
# This can return when multimethods have been fixed
#dict_str        = StdObjSpace.str

# default application-level implementations for some operations
# gateway is imported in the stdtypedef module
app = gateway.applevel('''

    def update(d, o):
        if hasattr(o, 'keys'):
            for k in o.keys():
                d[k] = o[k]
        else:
            for k,v in o:
                d[k] = v

    def popitem(d):
        k = d.keys()
        if not k:
            raise KeyError("popitem(): dictionary is empty")
        k = k[0]
        v = d[k]
        del d[k]
        return k, v

    def get(d, k, v=None):
        if k in d:
            return d[k]
        else:
            return v

    def setdefault(d, k, v=None):
        if k in d:
            return d[k]
        else:
            d[k] = v
            return v

    def pop(d, k, defaults):     # XXX defaults is actually *defaults
        if len(defaults) > 1:
            raise TypeError, "pop expected at most 2 arguments, got %d" % (
                1 + len(defaults))
        try:
            v = d[k]
            del d[k]
        except KeyError, e:
            if defaults:
                return defaults[0]
            else:
                raise e
        return v

    def iteritems(d):
        return iter(d.items())

    def iterkeys(d):
        return iter(d.keys())

    def itervalues(d):
        return iter(d.values())
''', filename=__file__)
#XXX what about dict.fromkeys()?

dict_update__ANY_ANY         = app.interphook("update")
dict_popitem__ANY            = app.interphook("popitem")
dict_get__ANY_ANY_ANY        = app.interphook("get")
dict_setdefault__ANY_ANY_ANY = app.interphook("setdefault")
dict_pop__ANY_ANY            = app.interphook("pop")
dict_iteritems__ANY          = app.interphook("iteritems")
dict_iterkeys__ANY           = app.interphook("iterkeys")
dict_itervalues__ANY         = app.interphook("itervalues")

register_all(vars(), globals())

# ____________________________________________________________

def descr__new__(space, w_dicttype, __args__):
    from pypy.objspace.std.dictobject import W_DictObject
    w_obj = space.allocate_instance(W_DictObject, w_dicttype)
    W_DictObject.__init__(w_obj, space)
    return w_obj

# ____________________________________________________________

dict_typedef = StdTypeDef("dict",
    __doc__ = '''dict() -> new empty dictionary.
dict(mapping) -> new dictionary initialized from a mapping object's
    (key, value) pairs.
dict(seq) -> new dictionary initialized as if via:
    d = {}
    for k, v in seq:
        d[k] = v
dict(**kwargs) -> new dictionary initialized with the name=value pairs
    in the keyword argument list.  For example:  dict(one=1, two=2)''',
    __new__ = newmethod(descr__new__,
                        unwrap_spec=[gateway.ObjSpace,gateway.W_Root,gateway.Arguments]),
    )
dict_typedef.registermethods(globals())


dictiter_typedef = StdTypeDef("dictionaryiterator",
    )
