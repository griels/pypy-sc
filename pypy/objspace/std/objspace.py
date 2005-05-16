from pypy.objspace.std.register_all import register_all
from pypy.interpreter.baseobjspace import ObjSpace, BaseWrappable
from pypy.interpreter.error import OperationError
from pypy.interpreter.typedef import get_unique_interplevel_subclass
from pypy.interpreter.typedef import instantiate
from pypy.tool.cache import Cache 
from pypy.objspace.std.model import W_Object, UnwrapError
from pypy.objspace.std.model import W_ANY, MultiMethod, StdTypeModel
from pypy.objspace.std.multimethod import FailedToImplement
from pypy.objspace.descroperation import DescrOperation
from pypy.objspace.std import stdtypedef
import types
import sys


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

    def _freeze_(self): 
        return True 

    def initialize(self):
        "NOT_RPYTHON: only for initializing the space."
        self._typecache = Cache()

        # Import all the object types and implementations
        self.model = StdTypeModel()

        # install all the MultiMethods into the space instance
        for name, mm in self.MM.__dict__.items():
            if isinstance(mm, MultiMethod) and not hasattr(self, name):
                if name.endswith('_w'): # int_w, str_w...: these do not return a wrapped object
                    func = mm.install_not_sliced(self.model.typeorder, baked_perform_call=True)
                else:               
                    exprargs, expr, miniglobals, fallback = (
                        mm.install_not_sliced(self.model.typeorder, baked_perform_call=False))

                    func = stdtypedef.make_perform_trampoline('__mm_'+name,
                                                              exprargs, expr, miniglobals,
                                                              mm)
                
                                                  # e.g. add(space, w_x, w_y)
                boundmethod = func.__get__(self)  # bind the 'space' argument
                setattr(self, name, boundmethod)  # store into 'space' instance

        # hack to avoid imports in the time-critical functions below
        for cls in self.model.typeorder:
            globals()[cls.__name__] = cls

        # singletons
        self.w_None  = W_NoneObject(self)
        self.w_False = W_BoolObject(self, False)
        self.w_True  = W_BoolObject(self, True)
        from pypy.interpreter.special import NotImplemented, Ellipsis
        self.w_NotImplemented = self.wrap(NotImplemented(self))  
        self.w_Ellipsis = self.wrap(Ellipsis(self))  

        # types
        self.types_w = {}
        for typedef in self.model.pythontypes:
            w_type = self.gettypeobject(typedef)
            setattr(self, 'w_' + typedef.name, w_type)

        # exceptions & builtins
        mod = self.setup_exceptions()
        self.make_builtins()
        self.sys.setmodule(self.wrap(mod))

        # dummy old-style classes types
        self.w_classobj = W_TypeObject(self, 'classobj', [self.w_object], {})
        self.w_instance = W_TypeObject(self, 'instance', [self.w_object], {})

        # fix up a problem where multimethods apparently don't 
        # like to define this at interp-level 
        self.appexec([self.w_dict], """
            (dict): 
                def fromkeys(cls, seq, value=None):
                    r = cls()
                    for s in seq:
                        r[s] = value
                    return r
                dict.fromkeys = classmethod(fromkeys)
        """) 
        # old-style classes
        self.setup_old_style_classes()

    def enable_old_style_classes_as_default_metaclass(self):
        self.setitem(self.builtin.w_dict, self.wrap('__metaclass__'), self.w_classobj)

    def enable_new_style_classes_as_default_metaclass(self):
        space = self
        try: 
            self.delitem(self.builtin.w_dict, self.wrap('__metaclass__')) 
        except OperationError, e: 
            if not e.match(space, space.w_KeyError): 
                raise 

    def setup_old_style_classes(self):
        """NOT_RPYTHON"""
        from pypy.module import classobjinterp
        # sanity check that this approach is working and is not too late
        assert not self.is_true(self.contains(self.builtin.w_dict,self.wrap('_classobj'))),"app-level code has seen dummy old style classes"
        w_setup = classobjinterp.initclassobj(self)
        w_classobj, w_instance, w_purify = self.unpackiterable(w_setup)
        self.call_function(w_purify)
        self.w_classobj = w_classobj
        self.w_instance = w_instance

    def setup_exceptions(self):
        """NOT_RPYTHON"""
        ## hacking things in
        from pypy.module import exceptionsinterp as ex
        def call(w_type, w_args):
            space = self
            # too early for unpackiterable as well :-(
            name  = space.unwrap(space.getitem(w_args, space.wrap(0)))
            bases = space.unpacktuple(space.getitem(w_args, space.wrap(1)))
            dic   = space.unwrap(space.getitem(w_args, space.wrap(2)))
            dic = dict([(key,space.wrap(value)) for (key, value) in dic.items()])
            bases = list(bases)
            if not bases:
                bases = [space.w_object]
            res = W_TypeObject(space, name, bases, dic)
            return res
        try:
            # note that we hide the real call method by an instance variable!
            self.call = call
            w_dic = ex.initexceptions(self)

            self.w_IndexError = self.getitem(w_dic, self.wrap("IndexError"))
            self.w_StopIteration = self.getitem(w_dic, self.wrap("StopIteration"))
        finally:
            del self.call # revert

        names_w = self.unpackiterable(self.call_function(self.getattr(w_dic, self.wrap("keys"))))

        for w_name in names_w:
            name = self.str_w(w_name)
            if not name.startswith('__'):
                excname = name
                w_exc = self.getitem(w_dic, w_name)
                setattr(self, "w_"+excname, w_exc)
                        
        # XXX refine things, clean up, create a builtin module...
        # but for now, we do a regular one.
        from pypy.interpreter.module import Module
        return Module(self, self.wrap("exceptions"), w_dic)

    def createexecutioncontext(self):
        # add space specific fields to execution context
        ec = ObjSpace.createexecutioncontext(self)
        DescrOperation.setup_ec(self, ec)
        ec._py_repr = self.newdict([])
        return ec

    def gettypeobject(self, typedef):
        # types_w maps each StdTypeDef instance to its
        # unique-for-this-space W_TypeObject instance
        return self.fromcache(stdtypedef.TypeCache).getorbuild(typedef)

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
            return W_IntObject(self, x)
        if isinstance(x, str):
            return W_StringObject(self, x)
        if isinstance(x, dict):
            items_w = [(self.wrap(k), self.wrap(v)) for (k, v) in x.iteritems()]
            return W_DictObject(self, items_w)
        if isinstance(x, float):
            return W_FloatObject(self, x)
        if isinstance(x, tuple):
            wrappeditems = [self.wrap(item) for item in x]
            return W_TupleObject(self, wrappeditems)
        if isinstance(x, list):
            wrappeditems = [self.wrap(item) for item in x]
            return W_ListObject(self, wrappeditems)
        if isinstance(x, BaseWrappable):
            w_result = x.__spacebind__(self)
            #print 'wrapping', x, '->', w_result
            return w_result
        if isinstance(x, long):
            from pypy.objspace.std.longobject import args_from_long
            return W_LongObject(self, *args_from_long(x))
        if isinstance(x, complex):
            # XXX is this right?   YYY no, this is wrong right now  (CT)
            # ZZZ hum, seems necessary for complex literals in co_consts (AR)
            c = self.builtin.get('complex') 
            return self.call_function(c,
                                      self.wrap(x.real), 
                                      self.wrap(x.imag))
        # anything below this line is implicitly XXX'ed
        if isinstance(x, type(Exception)) and issubclass(x, Exception):
            w_result = self.wrap_exception_cls(x)
            if w_result is not None:
                return w_result
        from fake import fake_object
        return fake_object(self, x)

    wrap._specialize_ = "argtypes"

    def wrap_exception_cls(self, x):
        """NOT_RPYTHON"""
        if hasattr(self, 'w_' + x.__name__):
            w_result = getattr(self, 'w_' + x.__name__)            
            return w_result
        return None
        
    def unwrap(self, w_obj):
        if isinstance(w_obj, BaseWrappable):
            return w_obj
        if isinstance(w_obj, W_Object):
            return w_obj.unwrap()
        raise UnwrapError, "cannot unwrap: %r" % w_obj
        

    def newint(self, intval):
        return W_IntObject(self, intval)

    def newfloat(self, floatval):
        return W_FloatObject(self, floatval)

    def newlong(self, uint): # for now just take a r_uint
        if uint == 0:
            sign = 0
        else:
            sign = 1
        return W_LongObject(self, [uint], sign)
        
    def newtuple(self, list_w):
        assert isinstance(list_w, list)
        return W_TupleObject(self, list_w)

    def newlist(self, list_w):
        return W_ListObject(self, list_w)

    def newdict(self, list_pairs_w):
        return W_DictObject(self, list_pairs_w)

    def newslice(self, w_start, w_end, w_step):
        return W_SliceObject(self, w_start, w_end, w_step)

    def newstring(self, chars_w):
        try:
            chars = [chr(self.int_w(w_c)) for w_c in chars_w]
        except ValueError:  # chr(out-of-range)
            raise OperationError(self.w_ValueError,
                                 self.wrap("character code not in range(256)"))
        return W_StringObject(self, ''.join(chars))

    def newseqiter(self, w_obj):
        return W_SeqIterObject(self, w_obj)

    def type(self, w_obj):
        return w_obj.getclass(self)

    def lookup(self, w_obj, name):
        w_type = w_obj.getclass(self)
        return w_type.lookup(name)

    def lookup_where(self, w_obj, name):
        w_type = w_obj.getclass(self)
        return w_type.lookup_where(name)

    def allocate_instance(self, cls, w_subtype):
        """Allocate the memory needed for an instance of an internal or
        user-defined type, without actually __init__ializing the instance."""
        w_type = self.gettypeobject(cls.typedef)
        if self.is_true(self.is_(w_type, w_subtype)):
            instance =  instantiate(cls)
        else:
            w_subtype = w_type.check_user_subclass(w_subtype)
            subcls = get_unique_interplevel_subclass(cls, w_subtype.hasdict, w_subtype.nslots != 0)
            instance = instantiate(subcls)
            instance.user_setup(self, w_subtype, w_subtype.nslots)
        assert isinstance(instance, cls)
        return instance
    allocate_instance._specialize_ = "location"
            

    def unpacktuple(self, w_tuple, expected_length=-1):
        assert isinstance(w_tuple, W_TupleObject)
        t = w_tuple.wrappeditems
        if expected_length != -1 and expected_length != len(t):
            raise ValueError, "got a tuple of length %d instead of %d" % (
                len(t), expected_length)
        return t

    def is_(self, w_one, w_two):
        # XXX a bit of hacking to gain more speed 
        if w_one is w_two:
            return self.w_True
        return self.w_False

    # short-cut
    def is_w(self, w_one, w_two):
        return w_one is w_two

    def is_true(self, w_obj):
        # XXX don't look!
        if isinstance(w_obj, W_DictObject):
            return not not w_obj.used
        else:
            return DescrOperation.is_true(self, w_obj)

    # support for the deprecated __getslice__, __setslice__, __delslice__

    def getslice(self, w_obj, w_start, w_stop):
        w_descr = self.lookup(w_obj, '__getslice__')
        if w_descr is not None:
            w_start, w_stop = old_slice_range(self, w_obj, w_start, w_stop)
            return self.get_and_call_function(w_descr, w_obj, w_start, w_stop)
        else:
            return ObjSpace.getslice(self, w_obj, w_start, w_stop)

    def setslice(self, w_obj, w_start, w_stop, w_sequence):
        w_descr = self.lookup(w_obj, '__setslice__')
        if w_descr is not None:
            w_start, w_stop = old_slice_range(self, w_obj, w_start, w_stop)
            self.get_and_call_function(w_descr, w_obj, w_start, w_stop,
                                       w_sequence)
        else:
            ObjSpace.setslice(self, w_obj, w_start, w_stop, w_sequence)

    def delslice(self, w_obj, w_start, w_stop):
        w_descr = self.lookup(w_obj, '__delslice__')
        if w_descr is not None:
            w_start, w_stop = old_slice_range(self, w_obj, w_start, w_stop)
            self.get_and_call_function(w_descr, w_obj, w_start, w_stop)
        else:
            ObjSpace.delslice(self, w_obj, w_start, w_stop)

    class MM:
        "Container for multimethods."
        call    = MultiMethod('call', 1, ['__call__'], general__args__=True)
        init    = MultiMethod('__init__', 1, general__args__=True)
        getnewargs = MultiMethod('__getnewargs__', 1)
        # special visible multimethods
        int_w   = MultiMethod('int_w', 1, [])     # returns an unwrapped int
        str_w   = MultiMethod('str_w', 1, [])     # returns an unwrapped string
        float_w = MultiMethod('float_w', 1, [])   # returns an unwrapped float
        uint_w  = MultiMethod('uint_w', 1, [])    # returns an unwrapped unsigned int (r_uint)

        # add all regular multimethods here
        for _name, _symbol, _arity, _specialnames in ObjSpace.MethodTable:
            if _name not in locals():
                mm = MultiMethod(_symbol, _arity, _specialnames)
                locals()[_name] = mm
                del mm

        pow.extras['defaults'] = (None,)


# what is the maximum value slices can get on CPython?
# we need to stick to that value, because fake.py etc.
class Temp:
    def __getslice__(self, i, j):
        return j
slice_max = Temp()[:]
del Temp


def old_slice_range(space, w_obj, w_start, w_stop):
    """Only for backward compatibility for __getslice__()&co methods."""
    if space.is_w(w_start, space.w_None):
        w_start = space.wrap(0)
    elif space.is_true(space.lt(w_start, space.wrap(0))):
        w_start = space.add(w_start, space.len(w_obj))
        # NB. the language ref is inconsistent with the new-style class
        # behavior when w_obj doesn't implement __len__(), so we just
        # ignore this case.
    if space.is_w(w_stop, space.w_None):
        w_stop = space.wrap(slice_max)
    elif space.is_true(space.lt(w_stop, space.wrap(0))):
        w_stop = space.add(w_stop, space.len(w_obj))
    return w_start, w_stop
