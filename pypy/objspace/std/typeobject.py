from pypy.objspace.std.objspace import *
from pypy.interpreter.typedef import attrproperty_w

class W_TypeObject(W_Object):
    from pypy.objspace.std.typetype import type_typedef as typedef

    def __init__(w_self, space, name, bases_w, dict_w, overridetypedef=None):
        W_Object.__init__(w_self, space)
        w_self.name = name
        w_self.bases_w = bases_w
        w_self.dict_w = dict_w
        w_self.needs_new_dict = False
        if overridetypedef is not None:
            w_self.instancetypedef = overridetypedef
        else:
            # find the most specific typedef
            longest_mro = [space.object_typedef]
            for w_base in bases_w:
                mro = w_base.instancetypedef.mro(space)
                if len(mro) > len(longest_mro):
                    longest_mro = mro
            # check that it is a sub-typedef of all other ones
            for w_base in bases_w:
                if w_base.instancetypedef not in longest_mro:
                    raise OperationError(space.w_TypeError,
                                space.wrap("instance layout conflicts in "
                                                    "multiple inheritance"))
            w_self.instancetypedef = longest_mro[0]
            nd = False
            for w_base in bases_w:
                if w_base.needs_new_dict:
                    nd = True
                    break
            
            # provide a __dict__ for the instances if there isn't any yet
            if w_self.lookup('__dict__') is None:
                w_self.needs_new_dict = True
                w_self.dict_w['__dict__'] = space.wrap(attrproperty_w('w__dict__'))
            elif nd:
                w_self.needs_new_dict = True
                
            

    def getmro(w_self):
        # XXX this is something that works not too bad right now
        # XXX do the complete mro thing later (see mro.py)
        mro = [w_self]
        for w_parent in w_self.bases_w:
            mro += w_parent.getmro()
        return mro

    def lookup(w_self, key):
        # note that this doesn't call __get__ on the result at all
        # XXX this should probably also return the (parent) class in which
        # the attribute was found
        space = w_self.space
        for w_class in w_self.getmro():
            try:
                return w_class.dict_w[key]
            except KeyError:
                pass
        return None

    def check_user_subclass(w_self, w_subtype, w_obj):
        """This morphs an object newly created by the w_self's __new__
        function into an instance of a subclass of w_self if needed."""
        space = w_self.space
        if space.is_true(space.is_(w_self, w_subtype)):
            return w_obj
        if not space.is_true(space.issubtype(w_subtype, w_self)):
            raise OperationError(space.w_TypeError,
                "%s.__new__(%s): %s is not a subtype of %s" % (
                    w_self.name, w_subtype.name, w_subtype.name, w_self.name))
        if w_self.instancetypedef is not w_subtype.instancetypedef:
            raise OperationError(space.w_TypeError,
                "%s.__new__(%s) is not safe, use %s.__new__()" % (
                    w_self.name, w_subtype.name, w_subtype.name))
        if w_self.instancetypedef is not w_obj.typedef:
            raise OperationError(space.w_TypeError,
                "%s.__new__(): got an object of type %s instead of %s" % (
                    w_self.name, space.type(w_obj).name, w_self.name))
        # stuff extra attributes into w_obj
        w_obj.w__class__ = w_subtype
        if w_subtype.needs_new_dict:
            w_obj.w__dict__ = space.newdict([])
        return w_obj

def call__Type(space, w_type, w_args, w_kwds):
    args_w = space.unpacktuple(w_args)
    # special case for type(x)
    if (space.is_true(space.is_(w_type, space.w_type)) and
        len(args_w) == 1 and not space.is_true(w_kwds)):
        return space.type(args_w[0])
    # invoke the __new__ of the type
    w_descr = w_type.lookup('__new__')
    w_extendedargs = space.newtuple([w_type] + args_w)
    w_newobject = space.call(w_descr, w_extendedargs, w_kwds)
    # maybe invoke the __init__ of the type
    if space.is_true(space.isinstance(w_newobject, w_type)):
        w_descr = space.lookup(w_newobject, '__init__')
        if w_descr is not None:
            space.get_and_call(w_descr, w_newobject, w_args, w_kwds)
    return w_newobject

def issubtype__Type_Type(space, w_type1, w_type2):
    return space.newbool(w_type2 in w_type1.getmro())

def repr__Type(space, w_obj):
    return space.wrap("<pypy type '%s'>" % w_obj.name)  # XXX remove 'pypy'

def getattr__Type_ANY(space, w_type, w_name):
    name = space.unwrap(w_name)
    w_descr = space.lookup(w_type, name)
    if w_descr is not None:
        if space.is_data_descr(w_descr):
            return space.get(w_descr,w_type,space.type(w_type))
    w_value = w_type.lookup(name)
    if w_value is not None:
        # __get__(None, type): turns e.g. functions into unbound methods
        return space.get(w_value, space.w_None, w_type)
    if w_descr is not None:
        return space.get(w_descr,w_type,space.type(w_type))
    raise OperationError(space.w_AttributeError,w_name)

# XXX __setattr__
# XXX __delattr__
# XXX __hash__ ??


register_all(vars())
