from pypy.interpreter.error import OperationError
from pypy.interpreter.baseobjspace import ObjSpace

class Object:
    def descr__getattribute__(space, w_obj, w_name):
        name = space.unwrap(w_name)
        w_descr = space.lookup(w_obj, name)
        if w_descr is not None:
            if space.is_data_descr(w_descr):  # 
                return space.get(w_descr,w_obj,space.type(w_obj))
        w_dict = space.getdict(w_obj)   # 
        if w_dict is not None:  
            try:
                return space.getitem(w_dict,w_name)
            except OperationError, e:
                if not e.match(space,space.w_KeyError):
                    raise
        if w_descr is not None:
            return space.get(w_descr,w_obj,space.wrap(type))
        raise OperationError(space.w_AttributeError,w_name)
        
class DescrOperation:

    def getdict(self, w_obj):
        if isinstance(w_obj, Wrappable):
            descr = self.lookup(w_obj, '__dict__')
            if descr is None:
                return None 
            return #w_dict 
        else:
            try:
                return w_obj.__dict__
            except AttributeError:
                return None 

    def call(space, w_obj, w_args, w_kwargs):
        print "call %r, %r, %r" %(w_obj, w_args, w_kwargs)
        w_descr = space.lookup(w_obj, '__call__')
        if w_descr is None:
            raise OperationError(space.w_TypeError, 
                                 space.wrap('object is not callable'))
        return space.get_and_call(w_descr, w_obj, w_args, w_kwargs)

    def get(space,w_descr,w_obj,w_type):
        w_get = space.lookup(w_descr,'__get__')
        if w_get is None:
            return w_obj
        return space.get_and_call_function(w_descr,w_obj,w_type)

    def set(space,w_descr,w_obj,w_val):
        w_get = space.lookup(w_descr,'__set__')
        if w_get is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object is not a descriptor with set"))
        return space.get_and_call_function(w_descr,w_obj,w_val)

    def delete(space,w_descr,w_obj):
        w_get = space.lookup(w_descr,'__get__')
        if w_get is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object is not a descriptor with delete"))
        return space.get_and_call_function(w_descr,w_obj)

    def getattr(space,w_obj,w_name):
        w_descr = space.lookup(w_obj,'__getattribute__')
        try:
            return space.get_and_call_function(w_descr,w_obj,w_name)
        except OperatioError,e:
            if not e.match(space,space.w_AttributeError):
                raise
        w_descr = space.lookup(w_obj,'__getattr__')
        return space.get_and_call_function(w_descr,w_obj,w_name)

    def setattr(space,w_obj,w_name,w_val):
        w_descr = space.lookup(w_obj,'__setattr__')
        if w_descr is None:
            raise OperationError(space.w_AttributeError,
                   space.wrap("object is readonly"))
        return space.get_and_call_function(w_descr,w_obj,w_name,w_val)

    def delattr(space,w_obj,w_name):
        w_descr = space.lookup(w_obj,'__delattr__')
        if w_descr is None:
            raise OperationError(space.w_AttributeError,
                    space.wrap("object does not support attribute removal"))
        return space.get_and_call_function(w_descr,w_obj,w_name)

    def str(space,w_obj):
        w_descr = space.lookup(w_obj,'__str__')
        return space.get_and_call_function(w_descr,w_obj)

    def repr(space,w_obj):
        w_descr = space.lookup(w_obj,'__repr__')
        return space.get_and_call_function(w_descr,w_obj)

    def contains(space,w_obj,w_val):
        w_descr = space.lookup(w_obj,'__contains__')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object doesn't know about contains"))
        return space.get_and_call_function(w_descr,w_obj,w_val)
        
    def iter(space,w_obj):
        w_descr = space.lookup(w_obj,'__iter__')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object is not iter()-able"))
        return space.get_and_call_function(w_descr,w_obj)

    def getitem(space,w_obj,w_key):
        w_descr = space.lookup(w_obj,'__getitem__')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                    space.wrap("cannot get items from object"))
        return space.get_and_call_function(w_descr,w_obj,w_key)

    def setitem(space,w_obj,w_key,w_val):
        w_descr = space.lookup(w_obj,'__setitem__')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                    space.wrap("cannot set items on object"))
        return space.get_and_call_function(w_descr,w_obj,w_key,w_val)

    def delitem(space,w_obj,w_key):
        w_descr = space.lookup(w_obj,'__delitem__')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("cannot delete items from object"))
        return space.get_and_call_function(w_descr,w_obj,w_key)


    # not_ has a default implementation

    # xxx round, not_ 



# helpers

def _invoke_binop(self,w_impl,w_obj1,w_obj2):
    if w_impl is not None:
        w_res = space.get_and_call_function(w_impl,w_obj1,w_obj2)
        if not space.is_true(space.is_(w_res.space.w_NotImplemented)):
            return w_res
    return None

# helper for invoking __cmp__

def _conditional_neg(space,w_obj,flag):
    if flag:
        return space.neg(w_obj)
    else:
        return w_obj

def _cmp(space,w_obj1,w_obj2):
    w_typ1 = space.type(w_obj1)
    w_typ2 = space.type(w_obj2)
    w_left_impl = space.lookup(w_obj1,'__cmp__')
    do_neg1 = False
    do_neg2 = True
    if space.is_true(space.is_(w_typ1,w_typ2)):
        w_right_impl = None
    else:
        w_right_impl = space.lookup(w_obj2,'__cmp__')
        if space.issubtype(w_typ1,w_typ2):
            w_obj1,w_obj2 = w_obj2,w_obj1
            w_left_impl,w_right_impl = w_right_impl,w_left_impl
            do_neg1,do_neg2 = do_neg2,do_neg1

    w_res = _invoke_binop(w_left_impl,w_obj1,w_obj2)
    if w_res is not None:
        return _conditional_neg(space,w_res,do_neg1)
    w_res = _invoke_binop(w_right_impl,w_obj2,w_obj1)
    if w_res is not None:
        return _conditional_neg(space,w_res,do_neg2)
    raise OperationError(space.w_TypeError) # xxx error

# regular methods def helpers

def _make_binop_impl(specialnames):
    left, right = specialnames
    def binop_impl(space,w_obj1,w_obj2):
        w_typ1 = space.type(w_obj1)
        w_typ2 = space.type(w_obj2)
        w_left_impl = space.lookup(w_obj1,left)
        if space.is_true(space.is_(w_typ1,w_typ2)):
            w_right_impl = None
        else:
            w_right_impl = space.lookup(w_obj2,right)
            if space.issubtype(w_typ1,w_typ2):
                w_obj1,w_obj2 = w_obj2,w_obj1
                w_left_impl,w_right_impl = w_right_impl,w_left_impl

        w_res = _invoke_binop(w_left_impl,w_obj1,w_obj2)
        if w_res is not None:
            return w_res
        w_res = _invoke_binop(w_right_impl,w_obj2,w_obj1)
        if w_res is not None:
            return w_res
        raise OperationError(space.w_TypeError) # xxx error
    return binop_impl

def _make_comparison_impl(specialnames):
    left, right = specialnames
    def comparison_impl(space,w_obj1,w_obj2):
        w_typ1 = space.type(w_obj1)
        w_typ2 = space.type(w_obj2)
        w_left_impl = space.lookup(w_obj1,left)
        w_first = w_obj1
        w_second = w_obj2
        
        if space.is_true(space.is_(w_typ1,w_typ2)):
            w_right_impl = None
        else:
            w_right_impl = space.lookup(w_obj2,right)
            if space.issubtype(w_typ1,w_typ2):
                w_obj1,w_obj2 = w_obj2,w_obj1
                w_left_impl,w_right_impl = w_right_impl,w_left_impl

        w_res = _invoke_binop(w_left_impl,w_obj1,w_obj2)
        if w_res is not None:
            return w_res
        w_res = _invoke_binop(w_right_impl,w_obj2,w_obj1)
        if w_res is not None:
            return w_res
        w_res = _cmp(space,w_first,w_second)
        # fallback: lt(a,b) <= lt(cmp(a,b),0) ...
        if space.is_true(comparison_impl(space,w_res,space.wrap(0))):
            return space.w_True
        else:
            return space.w_False

    return comparison_impl

def _make_inplace_impl(specialnames):
    specialname, = specialnames
    def inplace_impl(space,w_lhs,w_rhs):
        w_impl = space.lookup(w_lhs,specialname)
        if w_impl is None:
            raise OperationError(space.w_TypeError) # xxx error
        space.get_and_call_function(w_impl,w_lhs,w_rhs)
    return inplace_impl

def _make_unaryop_impl(specialnames):
    def unaryop_impl(space,w_obj):
        w_impl = space.lookup(w_obj,specialname)
        if w_impl is None:
            raise OperationError(space.w_TypeError) # xxx error
        space.get_and_call_function(w_impl,w_obj)
    return unaryop_impl
    

# add regular methods

for _name, _symbol, _arity, _specialnames in ObjSpace.MethodTable:
    if not hasattr(DescrOperation,_name):
        _impl_maker = None
        if _arity ==2 and _name in ['lt','le','gt','ge','ne','eq']:
            #print "comparison",_specialnames
            _impl_maker = _make_comparison_impl
        elif _arity == 2 and _name.startswith('inplace_'):
            #print "inplace",_specialnames
            _impl_maker = _make_inplace_impl
        elif _arity == 2 and len(_specialnames) == 2:
            #print "binop",_specialnames
            _impl_maker = _make_binop_impl     
        elif _arity == 1 and len(_specialnames) == 1:
            #print "unaryop",_specialnames
            _impl_maker = _make_unaryop_impl    
        if _impl_maker:
            setattr(DescrOperation,_name,_impl_maker(_specialnames))
        elif _name not in ['id','type','issubtype',
                           # not really to be defined in DescrOperation
                           'ord','not_','round']:
            print "missing %s" % _name
            
            

