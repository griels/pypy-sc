from pypy.objspace.std.register_all import register_all
from pypy.interpreter.baseobjspace import *
from pypy.objspace.std.multimethod import *
from pypy.objspace.descroperation import DescrOperation
import types


class W_Object:
    "Parent base class for wrapped objects."
    typedef = None
    
    def __init__(w_self, space):
        w_self.space = space     # XXX not sure this is ever used any more

    def __repr__(self):
        return '<objwrapper %s(%s)>' % (
            self.__class__.__name__,
           #', '.join(['%s=%r' % keyvalue for keyvalue in self.__dict__.items()])
            getattr(self, 'name', '')
            )

# delegation priorities
PRIORITY_SAME_TYPE    = 2  # converting between several impls of the same type
PRIORITY_PARENT_TYPE  = 1  # converting to a base type (e.g. bool -> int)
PRIORITY_PARENT_IMPL  = 0  # hard-wired in multimethod.py (W_IntObject->W_Object)
PRIORITY_CHANGE_TYPE  = -1 # changing type altogether (e.g. int -> float)
PRIORITY_ANY          = -999 # hard-wired in multimethod.py (... -> W_ANY)

def registerimplementation(implcls):
    # this function should ultimately register the implementation class somewhere
    # it may be modified to take 'typedef' instead of requiring it to be
    # stored in 'implcls' itself
    assert issubclass(implcls, W_Object)


##################################################################

class StdObjSpace(ObjSpace, DescrOperation):
    """The standard object space, implementing a general-purpose object
    library in Restricted Python."""

    PACKAGE_PATH = 'objspace.std'

    def standard_types(self):
        class result:
            "Import here the types you want to have appear in __builtin__."

            from objecttype import object_typedef
            from booltype   import bool_typedef
            from inttype    import int_typedef
            from floattype  import float_typedef
            from tupletype  import tuple_typedef
            from listtype   import list_typedef
            from dicttype   import dict_typedef
            from stringtype import str_typedef
            from typetype   import type_typedef
            from slicetype  import slice_typedef
        return [value for key, value in result.__dict__.items()
                      if not key.startswith('_')]   # don't look

    def clone_exception_hierarchy(self):
        from pypy.objspace.std.typeobject import W_TypeObject
        from pypy.interpreter import gateway
        w = self.wrap
        def app___init__(self, *args):
            self.args = args
        w_init = w(gateway.app2interp(app___init__))
        def app___str__(self):
            l = len(self.args)
            if l == 0:
                return ''
            elif l == 1:
                return str(self.args[0])
            else:
                return str(self.args)
        w_str = w(gateway.app2interp(app___str__))
        import exceptions

        # to create types, we should call the standard type object;
        # but being able to do that depends on the existence of some
        # of the exceptions...
        
        self.w_Exception = W_TypeObject(
            self,
            'Exception',
            [self.w_object],
            {'__init__': w_init,
             '__str__': w_str},
            )
        done = {'Exception': self.w_Exception}

        # some of the complexity of the following is due to the fact
        # that we need to create the tree root first, but the only
        # connections we have go in the inconvenient direction...
        
        for k in dir(exceptions):
            if k not in done:
                v = getattr(exceptions, k)
                if isinstance(v, str):
                    continue
                stack = [k]
                while stack:
                    next = stack[-1]
                    if next not in done:
                        v = getattr(exceptions, next)
                        b = v.__bases__[0]
                        if b.__name__ not in done:
                            stack.append(b.__name__)
                            continue
                        else:
                            base = done[b.__name__]
                            newtype = W_TypeObject(
                                self,
                                next,
                                [base],
                                {},
                                )
                            setattr(self,
                                    'w_' + next,
                                    newtype)
                            done[next] = newtype
                            stack.pop()
                    else:
                        stack.pop()
        return done
                            
    def initialize(self):
        from noneobject    import W_NoneObject
        from boolobject    import W_BoolObject

        # singletons
        self.w_None  = W_NoneObject(self)
        self.w_False = W_BoolObject(self, False)
        self.w_True  = W_BoolObject(self, True)
        self.w_NotImplemented = self.wrap(NotImplemented)  # XXX do me
        self.w_Ellipsis = self.wrap(Ellipsis)  # XXX do me too

        for_builtins = {"False": self.w_False,
                        "True" : self.w_True,
                        "None" : self.w_None,
                        "NotImplemented": self.w_NotImplemented,
                        "Ellipsis": self.w_Ellipsis,
#                        "long": self.wrap(long),  # XXX temporary
                        }

        # types
        from pypy.objspace.std.objecttype import object_typedef
        self.object_typedef = object_typedef
        self.types_w = {}
        for typedef in self.standard_types():
            w_type = self.gettypeobject(typedef)
            setattr(self, 'w_' + typedef.name, w_type)
            for_builtins[typedef.name] = w_type

        # exceptions
        for_builtins.update(self.clone_exception_hierarchy())
        
        self.make_builtins()
        
        # insert stuff into the newly-made builtins
        for key, w_value in for_builtins.items():
            self.setitem(self.w_builtins, self.wrap(key), w_value)

    def gettypeobject(self, typedef):
        # types_w maps each StdTypeDef instance to its
        # unique-for-this-space W_TypeObject instance
        try:
            w_type = self.types_w[typedef]
        except KeyError:
            from pypy.objspace.std.stdtypedef import buildtypeobject
            w_type = self.types_w[typedef] = buildtypeobject(typedef, self)
        return w_type

    def wrap(self, x):
        "Wraps the Python value 'x' into one of the wrapper classes."
        if x is None:
            return self.w_None
        if isinstance(x, W_Object):
            raise TypeError, "attempt to wrap already wrapped object: %s"%(x,)
        if isinstance(x, OperationError):
            raise TypeError, ("attempt to wrap already wrapped exception: %s"%
                              (x,))
        if isinstance(x, int):
            if isinstance(bool, type) and isinstance(x, bool):
                return self.newbool(x)
            import intobject
            return intobject.W_IntObject(self, x)
        if isinstance(x, str):
            import stringobject
            return stringobject.W_StringObject(self, x)
        if isinstance(x, dict):
            items_w = [(self.wrap(k), self.wrap(v)) for (k, v) in x.iteritems()]
            import dictobject
            return dictobject.W_DictObject(self, items_w)
        if isinstance(x, float):
            import floatobject
            return floatobject.W_FloatObject(self, x)
        if isinstance(x, tuple):
            wrappeditems = [self.wrap(item) for item in x]
            import tupleobject
            return tupleobject.W_TupleObject(self, wrappeditems)
        if isinstance(x, list):
            wrappeditems = [self.wrap(item) for item in x]
            import listobject
            return listobject.W_ListObject(self, wrappeditems)
        if isinstance(x, Wrappable):
            return x.__spacebind__(self)
        import cpythonobject
        SlotWrapperType = type(type(None).__repr__)
        if isinstance(x, (types.FunctionType, types.BuiltinFunctionType, SlotWrapperType)):
            return cpythonobject.W_BuiltinFunctionObject(self, x) 
        print "cpython wrapping %r (%s)" % (x, type(x))
        #if hasattr(x, '__bases__'): 
        #    print "cpython wrapping a class %r (%s)" % (x, type(x))
            #raise TypeError, "cannot wrap classes"
        return cpythonobject.W_CPythonObject(self, x)

    def newint(self, int_w):
        import intobject
        return intobject.W_IntObject(self, int_w)

    def newfloat(self, int_w):
        import floatobject
        return floatobject.W_FloatObject(self, int_w)

    def newtuple(self, list_w):
        assert isinstance(list_w, list)
        import tupleobject
        return tupleobject.W_TupleObject(self, list_w)

    def newlist(self, list_w):
        import listobject
        return listobject.W_ListObject(self, list_w)

    def newdict(self, list_pairs_w):
        import dictobject
        return dictobject.W_DictObject(self, list_pairs_w)

    def newslice(self, w_start, w_end, w_step):
        # w_step may be a real None
        import sliceobject
        return sliceobject.W_SliceObject(self, w_start, w_end, w_step)

    def newstring(self, chars_w):
        try:
            chars = [chr(self.unwrap(w_c)) for w_c in chars_w]
        except TypeError:   # chr(not-an-integer)
            raise OperationError(self.w_TypeError,
                                 self.wrap("an integer is required"))
        except ValueError:  # chr(out-of-range)
            raise OperationError(self.w_ValueError,
                                 self.wrap("character code not in range(256)"))
        import stringobject
        return stringobject.W_StringObject(self, ''.join(chars))

    def type(self, w_obj):
        from pypy.objspace.std.cpythonobject import W_CPythonObject
        if isinstance(w_obj, W_CPythonObject):
            #raise TypeError, str(w_obj.cpyobj)
            return self.wrap(type(w_obj.cpyobj))
        elif hasattr(w_obj, 'w__class__'):
            return w_obj.w__class__    # user-defined classes
        else:
            assert w_obj.typedef, w_obj
            return self.gettypeobject(w_obj.typedef)

    def lookup(self, w_obj, name):
        from pypy.objspace.std.cpythonobject import W_CPythonObject
        if not isinstance(w_obj, W_CPythonObject):
            # usual case
            w_type = self.type(w_obj)
            return w_type.lookup(name)
        else:
            # hack
            for cls in w_obj.cpyobj.__class__.__mro__:
                if name in cls.__dict__:
                    return self.wrap(cls.__dict__[name])
            return None

    def unpacktuple(self, w_tuple, expected_length=None):
        import tupleobject
        assert isinstance(w_tuple, tupleobject.W_TupleObject)
        t = w_tuple.wrappeditems
        if expected_length is not None and expected_length != len(t):
            raise ValueError, "got a tuple of length %d instead of %d" % (
                len(t), expected_length)
        return t


    class MM:
        "Container for multimethods."
        #is_data_descr = MultiMethod('is_data_descr', 1, []) # returns an unwrapped bool
        #getdict = MultiMethod('getdict', 1, [])  # get '.__dict__' attribute
        next    = MultiMethod('next', 1, ['next'])     # iterator interface
        call    = MultiMethod('call', 1, ['__call__'], varargs=True, keywords=True)
        #getattribute = MultiMethod('getattr', 2, ['__getattribute__'])  # XXX hack
        # special visible multimethods
        delegate = DelegateMultiMethod()          # delegators
        unwrap  = MultiMethod('unwrap', 1, [])    # returns an unwrapped object
        is_true = MultiMethod('nonzero', 1, [])   # returns an unwrapped bool
        issubtype = MultiMethod('issubtype', 2, [])
        id = MultiMethod('id', 1, [])

    unwrap = MM.unwrap
    delegate = MM.delegate
    is_true = MM.is_true

    def is_(self, w_one, w_two):
        # XXX a bit of hacking to gain more speed 
        #
        if w_one is w_two:
            return self.newbool(1)
        from cpythonobject import W_CPythonObject
        if isinstance(w_one, W_CPythonObject):
            if isinstance(w_two, W_CPythonObject):
                if w_one.cpyobj is w_two.cpyobj:
                    return self.newbool(1)
                return self.newbool(self.unwrap(w_one) is self.unwrap(w_two))
        return self.newbool(0)

# add all regular multimethods to StdObjSpace
for _name, _symbol, _arity, _specialnames in ObjSpace.MethodTable:
    if not hasattr(StdObjSpace.MM, _name):
##         if isinstance(getattr(StdObjSpace, _name, None), MultiMethod):
##             mm = getattr(StdObjSpace, _name)
##         else:
        mm = MultiMethod(_symbol, _arity, _specialnames)
        setattr(StdObjSpace.MM, _name, mm)
    if not hasattr(StdObjSpace, _name):
        setattr(StdObjSpace, _name, getattr(StdObjSpace.MM, _name))

# import the common base W_ObjectObject as well as
# default implementations of some multimethods for all objects
# that don't explicitely override them or that raise FailedToImplement
from pypy.objspace.std.register_all import register_all
import pypy.objspace.std.objectobject
import pypy.objspace.std.default
