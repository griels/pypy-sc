
from pypy.interpreter.typedef import TypeDef, GetSetProperty
from pypy.interpreter.baseobjspace import W_Root, ObjSpace, Wrappable, \
     Arguments
from pypy.interpreter.gateway import interp2app
from pypy.interpreter.error import OperationError
from pypy.interpreter.callmethod import object_getattribute
from pypy.interpreter.function import StaticMethod, Method
from pypy.interpreter.typedef import GetSetProperty, descr_get_dict, \
     descr_set_dict

class W_Super(Wrappable):
    def __init__(self, space, w_selftype, w_starttype, w_type, w_self):
        self.w_selftype = w_selftype
        self.w_starttype = w_starttype
        self.w_type = w_type
        self.w_self = w_self

    def get(self, space, w_obj, w_type=None):
        w = space.wrap
        if self.w_self is None or space.is_w(w_obj, space.w_None):
            return w(self)
        else:
            return space.call_function(self.w_selftype, self.w_starttype, w_obj
                                       )
    get.unwrap_spec = ['self', ObjSpace, W_Root, W_Root]

    def getattribute(self, space, name):
        w = space.wrap
        if name == '__class__':
            return self.w_selftype
        if self.w_type is None:
            return space.call_function(object_getattribute(space),
                                       w(self), w(name))
            
        w_value = space.lookup_in_type_starting_at(self.w_type,
                                                   self.w_starttype,
                                                   name)
        if w_value is None:
            return space.getattr(w(self), w(name))

        try:
            w_get = space.getattr(w_value, space.wrap('__get__'))
            if space.is_w(self.w_self, self.w_type):
                w_self = space.w_None
            else:
                w_self = self.w_self
        except OperationError, o:
            if not o.match(space, space.w_AttributeError):
                raise
            return w_value
        return space.call_function(w_get, w_self, self.w_type)
    getattribute.unwrap_spec = ['self', ObjSpace, str]

def descr_new_super(space, w_self, w_starttype, w_obj_or_type=None):
    if space.is_w(w_obj_or_type, space.w_None):
        w_type = None  # unbound super object
    else:
        w_objtype = space.type(w_obj_or_type)
        if space.is_true(space.issubtype(w_objtype, space.w_type)) and \
            space.is_true(space.issubtype(w_obj_or_type, w_starttype)):
            w_type = w_obj_or_type # special case for class methods
        elif space.is_true(space.issubtype(w_objtype, w_starttype)):
            w_type = w_objtype # normal case
        else:
            try:
                w_type = space.getattr(w_obj_or_type, space.wrap('__class__'))
            except OperationError, o:
                if not o.match(space, space.w_AttributeError):
                    raise
                w_type = w_objtype
            if not space.is_true(space.issubtype(w_type, w_starttype)):
                raise OperationError(space.w_TypeError,
                    space.wrap("super(type, obj): "
                               "obj must be an instance or subtype of type"))
    return space.wrap(W_Super(space, w_self, w_starttype, w_type, w_obj_or_type))
descr_new_super.unwrap_spec = [ObjSpace, W_Root, W_Root, W_Root]

W_Super.typedef = TypeDef(
    'super',
    __new__          = interp2app(descr_new_super),
    __getattribute__ = interp2app(W_Super.getattribute),
    __get__          = interp2app(W_Super.get),
    __doc__          =     """super(type) -> unbound super object
super(type, obj) -> bound super object; requires isinstance(obj, type)
super(type, type2) -> bound super object; requires issubclass(type2, type)

Typical use to call a cooperative superclass method:

class C(B):
    def meth(self, arg):
        super(C, self).meth(arg)"""
)

class W_ClassMethod(Wrappable):
    def __init__(self, w_function):
        self.w_function = w_function

    def new(space, w_type, w_function):
        if not space.is_true(space.callable(w_function)):
            name = space.getattr(space.type(w_function), space.wrap('__name__'))
            raise OperationError(space.w_TypeError, space.wrap(
                                 "'%s' object is not callable" % name))
        return W_ClassMethod(w_function)

    def get(self, space, w_obj, w_klass=None):
        if space.is_w(w_klass, space.w_None):
            w_klass = space.type(w_obj)
        return space.wrap(Method(space, self.w_function, w_klass, space.w_None))

W_ClassMethod.typedef = TypeDef(
    'classmethod',
    __new__ = interp2app(W_ClassMethod.new.im_func,
                         unwrap_spec=[ObjSpace, W_Root, W_Root]),
    __get__ = interp2app(W_ClassMethod.get,
                         unwrap_spec=['self', ObjSpace, W_Root, W_Root]),
    __doc__ = """classmethod(function) -> class method

Convert a function to be a class method.

A class method receives the class as implicit first argument,
just like an instance method receives the instance.
To declare a class method, use this idiom:

  class C:
      def f(cls, arg1, arg2, ...): ...
      f = classmethod(f)

It can be called either on the class (e.g. C.f()) or on an instance
(e.g. C().f()).  The instance is ignored except for its class.
If a class method is called for a derived class, the derived class
object is passed as the implied first argument.""",
)

class W_Property(Wrappable):
    def __init__(self, space, w_fget, w_fset, w_fdel, doc):
        self.w_fget = w_fget
        self.w_fset = w_fset
        self.w_fdel = w_fdel
        self.doc = doc

    def new(space, w_type, w_fget=None, w_fset=None, w_fdel=None, doc=''):
        return W_Property(space, w_fget, w_fset, w_fdel, doc)
    new.unwrap_spec = [ObjSpace, W_Root, W_Root, W_Root, W_Root, str]

    def get(self, space, w_obj, w_objtype=None):
        if space.is_w(w_obj, space.w_None):
            return space.wrap(self)
        if space.is_w(self.w_fget, space.w_None):
            raise OperationError(space.w_AttributeError, space.wrap(
                "unreadable attribute"))
        return space.call_function(self.w_fget, w_obj)
    get.unwrap_spec = ['self', ObjSpace, W_Root, W_Root]

    def set(self, space, w_obj, w_value):
        if space.is_w(self.w_fset, space.w_None):
            raise OperationError(space.w_AttributeError, space.wrap(
                "can't set attribute"))
        space.call_function(self.w_fset, w_obj, w_value)
        return space.w_None
    set.unwrap_spec = ['self', ObjSpace, W_Root, W_Root]

    def delete(self, space, w_obj):
        if space.is_w(self.w_fdel, space.w_None):
            raise OperationError(space.w_AttributeError, space.wrap(
                "can't delete attribute"))
        space.call_function(self.w_fdel, w_obj)
        return space.w_None
    delete.unwrap_spec = ['self', ObjSpace, W_Root]

    def getattribute(self, space, attr):
        if attr == '__doc__':
            return space.wrap(self.doc)
        # shortcuts
        return space.call_function(object_getattribute(space),
                                   space.wrap(self), space.wrap(attr))
    getattribute.unwrap_spec = ['self', ObjSpace, str]

    def fget(space, self):
        return self.w_fget

    def fset(space, self):
        return self.w_fset

    def fdel(space, self):
        return self.w_fdel

    def setattr(self, space, attr, w_value):
        raise OperationError(space.w_TypeError, space.wrap(
            "Trying to set readonly attribute %s on property" % (attr,)))
    setattr.unwrap_spec = ['self', ObjSpace, str, W_Root]

W_Property.typedef = TypeDef(
    'property',
    __doc__ = '''property(fget=None, fset=None, fdel=None, doc=None) -> property attribute

fget is a function to be used for getting an attribute value, and likewise
fset is a function for setting, and fdel a function for deleting, an
attribute.  Typical use is to define a managed attribute x:
class C(object):
    def getx(self): return self.__x
    def setx(self, value): self.__x = value
    def delx(self): del self.__x
    x = property(getx, setx, delx, "I am the 'x' property.")''',
    __new__ = interp2app(W_Property.new.im_func),
    __get__ = interp2app(W_Property.get),
    __set__ = interp2app(W_Property.set),
    __delete__ = interp2app(W_Property.delete),
    __getattribute__ = interp2app(W_Property.getattribute),
    __setattr__ = interp2app(W_Property.setattr),
    fdel = GetSetProperty(W_Property.fdel),
    fget = GetSetProperty(W_Property.fget),
    fset = GetSetProperty(W_Property.fset),
)

