import operator
from pypy.interpreter.error import OperationError
from pypy.interpreter.baseobjspace import ObjSpace
from pypy.interpreter.function import Function
from pypy.interpreter.gateway import BuiltinCode
from pypy.interpreter.argument import Arguments

class Object:
    def descr__getattribute__(space, w_obj, w_name):
        name = space.unwrap(w_name)
        w_descr = space.lookup(w_obj, name)
        if w_descr is not None:
            if space.is_data_descr(w_descr):
                return space.get(w_descr,w_obj)
        w_dict = space.getdict(w_obj)
        if w_dict is not None:  
            try:
                return space.getitem(w_dict,w_name)
            except OperationError, e:
                if not e.match(space,space.w_KeyError):
                    raise
        if w_descr is not None:
            return space.get(w_descr,w_obj)
        raise OperationError(space.w_AttributeError,w_name)

    def descr__setattr__(space, w_obj, w_name, w_value):
        name = space.unwrap(w_name)
        w_descr = space.lookup(w_obj, name)
        if w_descr is not None:
            if space.is_data_descr(w_descr):
                return space.set(w_descr,w_obj,w_value)
        w_dict = space.getdict(w_obj)
        if w_dict is not None:
            return space.setitem(w_dict,w_name,w_value)
        raise OperationError(space.w_AttributeError,w_name)

    def descr__delattr__(space, w_obj, w_name):
        name = space.unwrap(w_name)
        w_descr = space.lookup(w_obj, name)
        if w_descr is not None:
            if space.is_data_descr(w_descr):
                return space.delete(w_descr,w_obj)
        w_dict = space.getdict(w_obj)
        if w_dict is not None:
            try:
                return space.delitem(w_dict,w_name)
            except OperationError, ex:
                if not ex.match(space, space.w_KeyError):
                    raise
        raise OperationError(space.w_AttributeError,w_name)

    def descr__init__(space, w_obj, __args__):
        pass   # XXX some strange checking maybe

SlotWrapper = type(None).__repr__

class DescrOperation:

    def getdict(space, w_obj):
        return w_obj.getdict()

    def is_data_descr(space, w_obj):
        return space.lookup(w_obj, '__set__') is not None

    def get_and_call_args(space, w_descr, w_obj, args):
        descr = space.unwrap_builtin(w_descr)
        # some special cases to avoid infinite recursion
        if type(descr) is Function:
            if isinstance(descr.code, BuiltinCode):
                # this sub-special case is ONLY for performance reasons
                w_result = descr.code.performance_shortcut_call_meth(
                    space, w_obj, args)
                if w_result is not None:
                    return w_result
            return descr.call_args(args.prepend(w_obj))
        elif type(descr) is type(space.wrap(SlotWrapper)):
            return descr.call_args(args.prepend(w_obj))
        else:
            w_impl = space.get(w_descr, w_obj)
            return space.call_args(w_impl, args)

    def get_and_call_function(space, w_descr, w_obj, *args_w):
        args = Arguments(space, list(args_w))
        return space.get_and_call_args(w_descr, w_obj, args)

    def unwrap_builtin(self, w_obj):
        return w_obj    # hook for hack by TrivialObjSpace

##    def call(space, w_obj, w_args, w_kwargs):
##        #print "call %r, %r, %r" %(w_obj, w_args, w_kwargs)
##        w_descr = space.lookup(w_obj, '__call__')
##        if w_descr is None:
##            raise OperationError(space.w_TypeError, 
##                              space.wrap('object %r is not callable' % (w_obj,)))
##        return space.get_and_call(w_descr, w_obj, w_args, w_kwargs)

    def call_args(space, w_obj, args):
        if type(w_obj) is Function and isinstance(w_obj.code, BuiltinCode):
            # this special case is ONLY for performance reasons
            w_result = w_obj.code.performance_shortcut_call(space, args)
            if w_result is not None:
                return w_result
        w_descr = space.lookup(w_obj, '__call__')
        if w_descr is None:
            raise OperationError(space.w_TypeError, 
                                 space.wrap('object %r is not callable' % (w_obj,)))
        return space.get_and_call_args(w_descr, w_obj, args)

    def get(space,w_descr,w_obj,w_type=None):
        w_get = space.lookup(w_descr,'__get__')
        if w_get is None:
            return w_descr
        if w_type is None:
            w_type = space.type(w_obj)
        return space.get_and_call_function(w_get,w_descr,w_obj,w_type)

    def set(space,w_descr,w_obj,w_val):
        w_set = space.lookup(w_descr,'__set__')
        if w_set is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object is not a descriptor with set"))
        return space.get_and_call_function(w_set,w_descr,w_obj,w_val)

    def delete(space,w_descr,w_obj):
        w_delete = space.lookup(w_descr,'__delete__')
        if w_delete is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object is not a descriptor with delete"))
        return space.get_and_call_function(w_delete,w_descr,w_obj)

    def getattr(space,w_obj,w_name):
        w_descr = space.lookup(w_obj,'__getattribute__')
        try:
            return space.get_and_call_function(w_descr,w_obj,w_name)
        except OperationError,e:
            if not e.match(space,space.w_AttributeError):
                raise
            w_descr = space.lookup(w_obj,'__getattr__')
            if w_descr is None:
                raise
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

    def is_true(space,w_obj):
        if w_obj == space.w_False:
            return False
        if w_obj == space.w_True:
            return True
        if w_obj == space.w_None:
            return False
        w_descr = space.lookup(w_obj, '__nonzero__')
        if w_descr is not None:
            w_res = space.get_and_call_function(w_descr,w_obj)
            return space.is_true(w_res)
        w_descr = space.lookup(w_obj, '__len__')
        if w_descr is not None:
            w_res = space.get_and_call_function(w_descr,w_obj)
            return space.is_true(w_res)
        return True

    def str(space,w_obj):
        w_descr = space.lookup(w_obj,'__str__')
        return space.get_and_call_function(w_descr,w_obj)
        # XXX PyObject_Str() checks that the result is a string

    def repr(space,w_obj):
        w_descr = space.lookup(w_obj,'__repr__')
        return space.get_and_call_function(w_descr,w_obj)
        # XXX PyObject_Repr() probably checks that the result is a string

    def contains(space,w_obj,w_val):
        w_descr = space.lookup(w_obj,'__contains__')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("object doesn't know about contains"))
        return space.get_and_call_function(w_descr,w_obj,w_val)
        
    def iter(space,w_obj):
        w_descr = space.lookup(w_obj,'__iter__')
        if w_descr is None:
            w_descr = space.lookup(w_obj,'__getitem__')
            if w_descr is None:
                raise OperationError(space.w_TypeError,
                                     space.wrap("object is not iter()-able"))
            return space.newseqiter(w_obj)
        return space.get_and_call_function(w_descr,w_obj)

    def next(space,w_obj):
        w_descr = space.lookup(w_obj,'next')
        if w_descr is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("iterator has no next() method"))
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

    def pow(space,w_obj1,w_obj2,w_obj3):
        w_typ1 = space.type(w_obj1)
        w_typ2 = space.type(w_obj2)
        w_left_impl = space.lookup(w_obj1,'__pow__')
        if space.is_true(space.is_(w_typ1,w_typ2)):
            w_right_impl = None
        else:
            w_right_impl = space.lookup(w_obj2,'__rpow__')
            if space.is_true(space.issubtype(w_typ1,w_typ2)):
                w_obj1,w_obj2 = w_obj2,w_obj1
                w_left_impl,w_right_impl = w_right_impl,w_left_impl
        if w_left_impl is not None:
            w_res = space.get_and_call_function(w_left_impl,w_obj1,w_obj2,
                                                w_obj3)
            if _check_notimplemented(space,w_res):
                return w_res
        if w_right_impl is not None:
           w_res = space.get_and_call_function(w_right_impl,w_obj2,w_obj1,
                                                w_obj3)
           if _check_notimplemented(space,w_res):
               return w_res

        raise OperationError(space.w_TypeError,
                space.wrap("operands do not support **"))

    def contains(space,w_container,w_item):
        w_descr = space.lookup(w_container,'__contains__')
        if w_descr is not None:
            return space.get_and_call_function(w_descr,w_container,w_item)
        w_iter = space.iter(w_container)
        while 1:
            try:
                w_next = space.next(w_iter)
            except OperationError, e:
                if not e.match(space, space.w_StopIteration):
                    raise
                return space.w_False
            if space.is_true(space.eq(w_next, w_item)):
                return space.w_True
    

    # xxx round, ord



# helpers

def _check_notimplemented(space,w_obj):
    return not space.is_true(space.is_(w_obj,space.w_NotImplemented))

def _invoke_binop(space,w_impl,w_obj1,w_obj2):
    if w_impl is not None:
        w_res = space.get_and_call_function(w_impl,w_obj1,w_obj2)
        if _check_notimplemented(space,w_res):
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
        if space.is_true(space.issubtype(w_typ1,w_typ2)):
            w_obj1,w_obj2 = w_obj2,w_obj1
            w_left_impl,w_right_impl = w_right_impl,w_left_impl
            do_neg1,do_neg2 = do_neg2,do_neg1

    w_res = _invoke_binop(space,w_left_impl,w_obj1,w_obj2)
    if w_res is not None:
        return _conditional_neg(space,w_res,do_neg1)
    w_res = _invoke_binop(space,w_right_impl,w_obj2,w_obj1)
    if w_res is not None:
        return _conditional_neg(space,w_res,do_neg2)
    # fall back to internal rules
    if space.is_true(space.is_(w_obj1, w_obj2)):
        return space.wrap(0)
    if space.is_true(space.is_(w_obj1, space.w_None)):
        return space.wrap(-1)
    if space.is_true(space.is_(w_obj2, space.w_None)):
        return space.wrap(1)
    if space.is_true(space.is_(w_typ1, w_typ2)):
        w_id1 = space.id(w_obj1)
        w_id2 = space.id(w_obj2)
    else:
        w_id1 = space.id(w_typ1)
        w_id2 = space.id(w_typ2)
    if space.is_true(space.lt(w_id1, w_id2)):
        return space.wrap(-1)
    else:
        return space.wrap(1)

# regular methods def helpers

def _make_binop_impl(symbol,specialnames):
    left, right = specialnames
    def binop_impl(space,w_obj1,w_obj2):
        w_typ1 = space.type(w_obj1)
        w_typ2 = space.type(w_obj2)
        w_left_impl = space.lookup(w_obj1,left)
        if space.is_true(space.is_(w_typ1,w_typ2)):
            w_right_impl = None
        else:
            w_right_impl = space.lookup(w_obj2,right)
            if space.is_true(space.issubtype(w_typ1,w_typ2)):
                w_obj1,w_obj2 = w_obj2,w_obj1
                w_left_impl,w_right_impl = w_right_impl,w_left_impl

        w_res = _invoke_binop(space,w_left_impl,w_obj1,w_obj2)
        if w_res is not None:
            return w_res
        w_res = _invoke_binop(space,w_right_impl,w_obj2,w_obj1)
        if w_res is not None:
            return w_res
        raise OperationError(space.w_TypeError,
                space.wrap("unsupported operand type(s) for %s" % symbol))
    return binop_impl

def _make_comparison_impl(symbol,specialnames):
    left, right = specialnames
    op = getattr(operator, left)
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
            if space.is_true(space.issubtype(w_typ1,w_typ2)):
                w_obj1,w_obj2 = w_obj2,w_obj1
                w_left_impl,w_right_impl = w_right_impl,w_left_impl

        w_res = _invoke_binop(space,w_left_impl,w_obj1,w_obj2)
        if w_res is not None:
            return w_res
        w_res = _invoke_binop(space,w_right_impl,w_obj2,w_obj1)
        if w_res is not None:
            return w_res
        # fallback: lt(a,b) <= lt(cmp(a,b),0) ...
        w_res = _cmp(space,w_first,w_second)
        res = space.unwrap(w_res)
        return space.wrap(op(res, 0))

    return comparison_impl

def _make_inplace_impl(symbol,specialnames):
    specialname, = specialnames
    assert specialname.startswith('__i') and specialname.endswith('__')
    noninplacespacemethod = specialname[3:-2]
    if noninplacespacemethod in ['or', 'and']:
        noninplacespacemethod += '_'     # not too clean
    def inplace_impl(space,w_lhs,w_rhs):
        w_impl = space.lookup(w_lhs,specialname)
        if w_impl is not None:
            w_res = space.get_and_call_function(w_impl,w_lhs,w_rhs)
            if _check_notimplemented(space,w_res):
                return w_res
        # XXX fix the error message we get here
        return getattr(space, noninplacespacemethod)(w_lhs,w_rhs)

    return inplace_impl

def _make_unaryop_impl(symbol,specialnames):
    specialname, = specialnames
    def unaryop_impl(space,w_obj):
        w_impl = space.lookup(w_obj,specialname)
        if w_impl is None:
            raise OperationError(space.w_TypeError,
                   space.wrap("operand does not support unary %s" % symbol))
        return space.get_and_call_function(w_impl,w_obj)
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
            setattr(DescrOperation,_name,_impl_maker(_symbol,_specialnames))
        elif _name not in ['id','type','issubtype',
                           # not really to be defined in DescrOperation
                           'ord','round']:
            raise Exception,"missing def for operation%s" % _name
            
            

