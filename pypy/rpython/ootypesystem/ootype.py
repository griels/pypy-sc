from pypy.rpython.lltypesystem.lltype import LowLevelType, Signed, Unsigned, Float, Char
from pypy.rpython.lltypesystem.lltype import Bool, Void, UniChar, typeOf, \
        Primitive, isCompatibleType, enforce, saferecursive
from pypy.rpython.lltypesystem.lltype import frozendict, isCompatibleType
from pypy.tool.uid import uid

STATICNESS = True

class OOType(LowLevelType):

    def _is_compatible(TYPE1, TYPE2):
        if TYPE1 == TYPE2:
            return True
        if isinstance(TYPE1, Instance) and isinstance(TYPE2, Instance):
            return isSubclass(TYPE1, TYPE2)
        else:
            return False

    def _enforce(TYPE2, value):
        TYPE1 = typeOf(value)
        if TYPE1 == TYPE2:
            return value
        if isinstance(TYPE1, Instance) and isinstance(TYPE2, Instance):
            if isSubclass(TYPE1, TYPE2):
                return value._enforce(TYPE2)
        raise TypeError


class Class(OOType):

    def _defl(self):
        return nullruntimeclass
    
Class = Class()

class Instance(OOType):
    """this is the type of user-defined objects"""
    def __init__(self, name, superclass, fields={}, methods={},
            _is_root=False):
        self._name = name

        if _is_root:
            self._superclass = None
        else:
            assert isinstance(superclass, Instance)
            self._superclass = superclass

        self._methods = frozendict()
        self._fields = frozendict()

        self._add_fields(fields)
        self._add_methods(methods)

        self._null = make_null_instance(self)
        self._class = _class(self)
        
    def _defl(self):
        return self._null

    def _example(self): return new(self)

    def __repr__(self):
        return '<%s>' % (self,)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self._name)

    def _add_fields(self, fields):
        fields = fields.copy()    # mutated below
        for name, defn in fields.iteritems():
            _, meth = self._lookup(name)
            if meth is not None:
                raise TypeError("Cannot add field %r: method already exists" % name)
        
            if self._superclass is not None:
                if self._superclass._has_field(name):
                    raise TypeError("Field %r exists in superclass" % name)

            if type(defn) is not tuple:
                if isinstance(defn, Meth):
                    raise TypeError("Attempting to store method in field")
                
                fields[name] = (defn, defn._defl())
            else:
                ootype, default = defn

                if isinstance(ootype, Meth):
                    raise TypeError("Attempting to store method in field")

                if ootype != typeOf(default):
                    raise TypeError("Expected type %r for default" % (ootype,))

        self._fields.update(fields)

    def _add_methods(self, methods):
        # Note to the unwary: _add_methods adds *methods* whereas
        # _add_fields adds *descriptions* of fields.  This is obvious
        # if you are in the right state of mind (swiss?), but
        # certainly not necessarily if not.
        for name, method in methods.iteritems():
            if self._has_field(name):
                raise TypeError("Can't add method %r: field already exists" % name)
            if not isinstance(typeOf(method), Meth):
                raise TypeError("added methods must be _meths, not %s" % type(method))
        self._methods.update(methods)

    def _init_instance(self, instance):
        if self._superclass is not None:
            self._superclass._init_instance(instance)
        
        for name, (ootype, default) in self._fields.iteritems():
            instance.__dict__[name] = enforce(ootype, default)

    def _has_field(self, name):
        try:
            self._fields[name]
            return True
        except KeyError:
            if self._superclass is None:
                return False

            return self._superclass._has_field(name)

    def _field_type(self, name):
        try:
            return self._fields[name][0]
        except KeyError:
            if self._superclass is None:
                raise TypeError("No field names %r" % name)

            return self._superclass._field_type(name)

    _check_field = _field_type

    def _lookup_field(self, name):
        field = self._fields.get(name)

        if field is None and self._superclass is not None:
            return self._superclass._lookup_field(name)

        try:
            return self, field[0]
        except TypeError:
            return self, None

    def _lookup(self, meth_name):
        meth = self._methods.get(meth_name)

        if meth is None and self._superclass is not None:
            return self._superclass._lookup(meth_name)

        return self, meth

    def _allfields(self):
        if self._superclass is None:
            all = {}
        else:
            all = self._superclass._allfields()
        all.update(self._fields)
        return all


class StaticMethod(OOType):
    __slots__ = ['_null']

    def __init__(self, args, result):
        self.ARGS = tuple(args)
        self.RESULT = result
        self._null = _static_meth(self, _callable=None)

    def _example(self):
        _retval = self.RESULT._example()
        return _static_meth(self, _callable=lambda *args: _retval)

    def _defl(self):
        return null(self)
    
class Meth(StaticMethod):

    def __init__(self, args, result):
        StaticMethod.__init__(self, args, result)


class BuiltinType(OOType):

    def _example(self):
        return new(self)

    def _defl(self):
        return self._null

    def _get_interp_class(self):
        raise NotImplementedError

class Record(BuiltinType):

    # We try to keep Record as similar to Instance as possible, so backends
    # can treat them polymorphically, if they choose to do so.
    
    def __init__(self, fields):
        self._fields = frozendict()
        self._add_fields(fields)
        self._null = _null_record(self)

    def _add_fields(self, fields):
        fields.copy()
        for name, ITEMTYPE in fields.items():
            fields[name] = ITEMTYPE, ITEMTYPE._defl()
        self._fields.update(fields)

    def _defl(self):
        return self._null

    def _get_interp_class(self):
        return _record

    def _field_type(self, name):
        try:
            return self._fields[name][0]
        except KeyError:
            raise TypeError("No field names %r" % name)

    _check_field = _field_type

    def _lookup(self, meth_name):
        return self, None

    def _lookup_field(self, name):
        try:
            return self, self._field_type(name)
        except TypeError:
            return self, None

    def __str__(self):
        item_str = ["%s: %s" % (str(name), str(ITEMTYPE))
                    for name, (ITEMTYPE, _) in self._fields.items()]
        return '%s(%s)' % (self.__class__.__name__, ", ".join(item_str))

class BuiltinADTType(BuiltinType):

    def _setup_methods(self, generic_types):
        methods = {}
        for name, meth in self._GENERIC_METHODS.iteritems():
            #args = [generic_types.get(arg, arg) for arg in meth.ARGS]
            #result = generic_types.get(meth.RESULT, meth.RESULT)
            args = [self._specialize_type(arg, generic_types) for arg in meth.ARGS]
            result = self._specialize_type(meth.RESULT, generic_types)
            methods[name] = Meth(args, result)
        self._METHODS = frozendict(methods)

    def _specialize_type(self, type_, generic_types):
        if isinstance(type_, BuiltinADTType):
            return type_._specialize(generic_types)
        else:
            return generic_types.get(type_, type_)

    def _specialize(self, generic_types):
        raise NotImplementedError

    def _lookup(self, meth_name):
        METH = self._METHODS.get(meth_name)
        meth = None
        if METH is not None:
            cls = self._get_interp_class()
            meth = _meth(METH, _name=meth_name, _callable=getattr(cls, meth_name))
        return self, meth


# WARNING: the name 'String' is rebound at the end of file
class String(BuiltinADTType):
    SELFTYPE_T = object()

    def __init__(self):
        self._null = _null_string(self)

        generic_types = { self.SELFTYPE_T: self }
        self._GENERIC_METHODS = frozendict({
            "ll_stritem_nonneg": Meth([Signed], Char),
            "ll_strlen": Meth([], Signed),
            "ll_strconcat": Meth([self.SELFTYPE_T], self.SELFTYPE_T)
        })
        self._setup_methods(generic_types)

    # TODO: should it return _null or ''?
    def _defl(self):
        return make_string("")
    
    def _example(self):
        return self._defl()

    def _get_interp_class(self):
        return _string

    def _specialize(self, generic_types):
        return self

# WARNING: the name 'StringBuilder' is rebound at the end of file
class StringBuilder(BuiltinADTType):
    def __init__(self):
        self._null = _null_string_builder(self)
        self._GENERIC_METHODS = frozendict({
            "ll_allocate": Meth([Signed], Void),
            "ll_append_char": Meth([Char], Void),
            "ll_append": Meth([String], Void),
            "ll_build": Meth([], String),
            })
        self._setup_methods({})

    def _defl(self):
        return self._null

    def _example(self):
        return self._defl()

    def _get_interp_class(self):
        return _string_builder

    def _specialize(self, generic_types):
        return self

class List(BuiltinADTType):
    # placeholders for types
    # make sure that each derived class has his own SELFTYPE_T
    # placeholder, because we want backends to distinguish that.
    SELFTYPE_T = object()
    ITEMTYPE_T = object()

    def __init__(self, ITEMTYPE=None):
        self._ITEMTYPE = ITEMTYPE
        self._null = _null_list(self)
        if ITEMTYPE is not None:
            self._init_methods()

    def _init_methods(self):
        # This defines the abstract list interface that backends will
        # have to map to their native list implementations.
        # 'ITEMTYPE_T' is used as a placeholder for indicating
        # arguments that should have ITEMTYPE type. 'SELFTYPE_T' indicates 'self'

        generic_types = {
            self.SELFTYPE_T: self,
            self.ITEMTYPE_T: self._ITEMTYPE,
            }

        # the methods are named after the ADT methods of lltypesystem's lists
        self._GENERIC_METHODS = frozendict({
            # "name": Meth([ARGUMENT1_TYPE, ARGUMENT2_TYPE, ...], RESULT_TYPE)
            "ll_length": Meth([], Signed),
            "ll_getitem_fast": Meth([Signed], self.ITEMTYPE_T),
            "ll_setitem_fast": Meth([Signed, self.ITEMTYPE_T], Void),
            "_ll_resize_ge": Meth([Signed], Void),
            "_ll_resize_le": Meth([Signed], Void),
            "_ll_resize": Meth([Signed], Void),
        })

        self._setup_methods(generic_types)

    # this is the equivalent of the lltypesystem ll_newlist that is
    # marked as typeMethod.
    def ll_newlist(self, length):
        from pypy.rpython.ootypesystem import rlist
        return rlist.ll_newlist(self, length)

    # NB: We are expecting Lists of the same ITEMTYPE to compare/hash
    # equal. We don't redefine __eq__/__hash__ since the implementations
    # from LowLevelType work fine, especially in the face of recursive
    # data structures. But it is important to make sure that attributes
    # of supposedly equal Lists compare/hash equal.

    def __eq__(self, other):
        if not isinstance(other, List):
            return False
        if self._ITEMTYPE is None or other._ITEMTYPE is None:
            raise TypeError("Can't compare uninitialized List type.")
        return BuiltinADTType.__eq__(self, other)    

    def __hash__(self):
        if self._ITEMTYPE is None:
            raise TypeError("Can't hash uninitialized List type.")
        return BuiltinADTType.__hash__(self)    

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                saferecursive(str, "...")(self._ITEMTYPE))

    def _get_interp_class(self):
        return _list

    def _specialize(self, generic_types):
        ITEMTYPE = self._specialize_type(self._ITEMTYPE, generic_types)
        return self.__class__(ITEMTYPE)
    
    def _defl(self):
        return self._null

    def _set_itemtype(self, ITEMTYPE):
        self._ITEMTYPE = ITEMTYPE
        self._init_methods()


class Dict(BuiltinADTType):
    # placeholders for types
    SELFTYPE_T = object()
    KEYTYPE_T = object()
    VALUETYPE_T = object()

    def __init__(self, KEYTYPE=None, VALUETYPE=None):
        self._KEYTYPE = KEYTYPE
        self._VALUETYPE = VALUETYPE
        self._null = _null_dict(self)

        if self._is_initialized():
            self._init_methods()

    def _is_initialized(self):
        return self._KEYTYPE is not None and self._VALUETYPE is not None

    def _init_methods(self):
        generic_types = {
            self.SELFTYPE_T: self,
            self.KEYTYPE_T: self._KEYTYPE,
            self.VALUETYPE_T: self._VALUETYPE
            }

        self._GENERIC_METHODS = frozendict({
            "ll_length": Meth([], Signed),
            "ll_get": Meth([self.KEYTYPE_T], self.VALUETYPE_T),
            "ll_set": Meth([self.KEYTYPE_T, self.VALUETYPE_T], Void),
            "ll_remove": Meth([self.KEYTYPE_T], Bool), # return False is key was not present
            "ll_contains": Meth([self.KEYTYPE_T], Bool),
            "ll_clear": Meth([], Void),
            "ll_get_items_iterator": Meth([], DictItemsIterator(self.KEYTYPE_T, self.VALUETYPE_T)),
        })

        self._setup_methods(generic_types)

    # NB: We are expecting Dicts of the same KEYTYPE, VALUETYPE to
    # compare/hash equal. We don't redefine __eq__/__hash__ since the
    # implementations from LowLevelType work fine, especially in the
    # face of recursive data structures. But it is important to make
    # sure that attributes of supposedly equal Dicts compare/hash
    # equal.

    def __str__(self):
        return '%s(%s, %s)' % (self.__class__.__name__,
                self._KEYTYPE, saferecursive(str, "...")(self._VALUETYPE))

    def __eq__(self, other):
        if not isinstance(other, Dict):
            return False
        if not self._is_initialized() or not other._is_initialized():
            raise TypeError("Can't compare uninitialized Dict type.")
        return BuiltinADTType.__eq__(self, other) 

    def __hash__(self):
        if not self._is_initialized():
            raise TypeError("Can't hash uninitialized Dict type.")
        return BuiltinADTType.__hash__(self)

    def _get_interp_class(self):
        return _dict

    def _specialize(self, generic_types):
        KEYTYPE = self._specialize_type(self._KEYTYPE, generic_types)
        VALUETYPE = self._specialize_type(self._VALUETYPE, generic_types)
        return self.__class__(KEYTYPE, VALUETYPE)

    def _set_types(self, KEYTYPE, VALUETYPE):
        self._KEYTYPE = KEYTYPE
        self._VALUETYPE = VALUETYPE
        self._init_methods()

class DictItemsIterator(BuiltinADTType):
    SELFTYPE_T = object()
    KEYTYPE_T = object()
    VALUETYPE_T = object()

    def __init__(self, KEYTYPE, VALUETYPE):
        self._KEYTYPE = KEYTYPE
        self._VALUETYPE = VALUETYPE
        self._null = _null_dict_items_iterator(self)

        generic_types = {
            self.SELFTYPE_T: self,
            self.KEYTYPE_T: KEYTYPE,
            self.VALUETYPE_T: VALUETYPE
            }

        # some words about the interface of the iterator: we can't
        # write the next() method directly in the backend because of
        # two reasons:
        #  1) tuples aren't BuiltinType, yet, so we can't make them
        #     generic; moreover, they are constructed on-the-fly, so the
        #     two-item tuple type that an hypotetic next() would return
        #     isn't available at this time.
        #  2) StopIteration is generated at translation time too, so
        #     this would prevent backends to do a precompilation of
        #     support code.

        self._GENERIC_METHODS = frozendict({
            "ll_go_next": Meth([], Bool), # move forward; return False is there is no more data available
            "ll_current_key": Meth([], self.KEYTYPE_T),
            "ll_current_value": Meth([], self.VALUETYPE_T),
        })

        self._setup_methods(generic_types)

    def __str__(self):
        return '%s%s' % (self.__class__.__name__,
                saferecursive(str, "(...)")((self._KEYTYPE, self._VALUETYPE)))

    def _get_interp_class(self):
        return _dict_items_iterator

    def _specialize(self, generic_types):
        KEYTYPE = self._specialize_type(self._KEYTYPE, generic_types)
        VALUETYPE = self._specialize_type(self._VALUETYPE, generic_types)
        return self.__class__(KEYTYPE, VALUETYPE)
    
# ____________________________________________________________

class _class(object):
    _TYPE = Class

    def __init__(self, INSTANCE):
        self._INSTANCE = INSTANCE

nullruntimeclass = _class(None)

class _instance(object):
    
    def __init__(self, INSTANCE):
        self.__dict__["_TYPE"] = INSTANCE
        INSTANCE._init_instance(self)

    def __repr__(self):
        return '<%s>' % (self,)

    def __str__(self):
        return '%r inst at 0x%x' % (self._TYPE._name, uid(self))

    def __getattr__(self, name):
        DEFINST, meth = self._TYPE._lookup(name)
        if meth is not None:
            return meth._bound(DEFINST, self)
        
        self._TYPE._check_field(name)

        return self.__dict__[name]

    def __setattr__(self, name, value):
        self.__getattr__(name)

        FLDTYPE = self._TYPE._field_type(name)
        try:
            val = enforce(FLDTYPE, value)
        except TypeError:
            raise TypeError("Expected type %r" % FLDTYPE)

        self.__dict__[name] = value

    def __nonzero__(self):
        return True    # better be explicit -- overridden in _null_instance

    def __eq__(self, other):
        if not isinstance(other, _instance):
            raise TypeError("comparing an _instance with %r" % (other,))
        return self is other   # same comment as __nonzero__

    def __ne__(self, other):
        return not (self == other)

    def _instanceof(self, INSTANCE):
        assert isinstance(INSTANCE, Instance)
        return bool(self) and isSubclass(self._TYPE, INSTANCE)

    def _classof(self):
        assert bool(self)
        return runtimeClass(self._TYPE)

    def _upcast(self, INSTANCE):
        assert instanceof(self, INSTANCE)
        return self

    _enforce = _upcast
    
    def _downcast(self, INSTANCE):
        assert instanceof(self, INSTANCE)
        return self

    def _identityhash(self):
        if self:
            return id(self)
        else:
            return 0   # for all null instances


def _null_mixin(klass):
    class mixin(object):

        def __str__(self):
            return '%r null inst' % (self._TYPE._name,)

        def __getattribute__(self, name):
            if name.startswith("_"):
                return object.__getattribute__(self, name)
        
            raise RuntimeError("Access to field in null object")

        def __setattr__(self, name, value):
            klass.__setattr__(self, name, value)

            raise RuntimeError("Assignment to field in null object")

        def __nonzero__(self):
            return False

        def __eq__(self, other):
            if not isinstance(other, klass):
                raise TypeError("comparing an %s with %r" % (klass.__name__, other))
            return not other

        def __hash__(self):
            return hash(self._TYPE)
    return mixin

class _null_instance(_null_mixin(_instance), _instance):

    def __init__(self, INSTANCE):
        self.__dict__["_TYPE"] = INSTANCE


class _view(object):

    def __init__(self, INSTANCE, inst):
        self.__dict__['_TYPE'] = INSTANCE
        assert isinstance(inst, _instance)
        assert isSubclass(inst._TYPE, INSTANCE)
        self.__dict__['_inst'] = inst

    def __repr__(self):
        if self._TYPE == self._inst._TYPE:
            return repr(self._inst)
        else:
            return '<%r view of %s>' % (self._TYPE._name, self._inst)

    def __ne__(self, other):
        return not (self == other)

    def __eq__(self, other):
        assert isinstance(other, _view)
        return self._inst == other._inst

    def __hash__(self):
        return hash(self._inst)

    def __nonzero__(self):
        return bool(self._inst)

    def __setattr__(self, name, value):
        self._TYPE._check_field(name)
        setattr(self._inst, name, value)

    def __getattr__(self, name):
        _, meth = self._TYPE._lookup(name)
        meth or self._TYPE._check_field(name)
        res = getattr(self._inst, name)
        if meth:
            assert isinstance(res, _bound_meth)
            return _bound_meth(res.DEFINST, _view(res.DEFINST, res.inst), res.meth)
        return res

    def _instanceof(self, INSTANCE):
        return self._inst._instanceof(INSTANCE)

    def _classof(self):
        return self._inst._classof()

    def _upcast(self, INSTANCE):
        assert isSubclass(self._TYPE, INSTANCE)
        return _view(INSTANCE, self._inst)

    _enforce = _upcast

    def _downcast(self, INSTANCE):
        assert isSubclass(INSTANCE, self._TYPE)
        return _view(INSTANCE, self._inst)

    def _identityhash(self):
        return self._inst._identityhash()

if STATICNESS:
    instance_impl = _view
else:
    instance_impl = _instance

def make_string(value):
    assert isinstance(value, str)
    return _string(String, value)

def make_instance(INSTANCE):
    inst = _instance(INSTANCE)
    if STATICNESS:
        inst = _view(INSTANCE, inst)
    return inst

def make_null_instance(INSTANCE):
    inst = _null_instance(INSTANCE)
    if STATICNESS:
        inst = _view(INSTANCE, inst)
    return inst

class _callable(object):

   def __init__(self, TYPE, **attrs):
       self._TYPE = TYPE
       self._name = "?"
       self._callable = None
       self.__dict__.update(attrs)

   def _checkargs(self, args, check_callable=True):
       if len(args) != len(self._TYPE.ARGS):
           raise TypeError,"calling %r with wrong argument number: %r" % (self._TYPE, args)

       checked_args = []
       for a, ARG in zip(args, self._TYPE.ARGS):
           try:
               a = enforce(ARG, a)
           except TypeError:
               raise TypeError,"calling %r with wrong argument types: %r" % (self._TYPE, args)
           checked_args.append(a)
       if not check_callable:
           return checked_args
       callb = self._callable
       if callb is None:
           raise RuntimeError,"calling undefined or null function"
       return callb, checked_args

   def __eq__(self, other):
       return (self.__class__ is other.__class__ and
               self.__dict__ == other.__dict__)

   def __ne__(self, other):
       return not (self == other)
   
   def __hash__(self):
       return hash(frozendict(self.__dict__))


class _static_meth(_callable):

   def __init__(self, STATICMETHOD, **attrs):
       assert isinstance(STATICMETHOD, StaticMethod)
       _callable.__init__(self, STATICMETHOD, **attrs)

   def __call__(self, *args):
       callb, checked_args = self._checkargs(args)
       return callb(*checked_args)

   def __repr__(self):
       return 'sm %s' % self._name

class _meth(_callable):
   
    def __init__(self, METHOD, **attrs):
        assert isinstance(METHOD, Meth)
        _callable.__init__(self, METHOD, **attrs)

    def _bound(self, DEFINST, inst):
        assert isinstance(inst, _instance) or isinstance(inst, _builtin_type)
        return _bound_meth(DEFINST, inst, self)

class _bound_meth(object):
    def __init__(self, DEFINST, inst, meth):
        self.DEFINST = DEFINST
        self.inst = inst
        self.meth = meth

    def __call__(self, *args):
       callb, checked_args = self.meth._checkargs(args)
       return callb(self.inst, *checked_args)


class _builtin_type(object):
    def __getattribute__(self, name):
        TYPE = object.__getattribute__(self, "_TYPE")
        _, meth = TYPE._lookup(name)
        if meth is not None:
            return meth._bound(TYPE, self)

        return object.__getattribute__(self, name)


class _string(_builtin_type):

    def __init__(self, STRING, value = ''):
        self._str = value
        self._TYPE = STRING

    def ll_stritem_nonneg(self, i):
        # NOT_RPYTHON
        assert i >= 0
        return self._str[i]

    def ll_strlen(self):
        # NOT_RPYTHON
        return len(self._str)

    def ll_strconcat(self, s):
        # NOT_RPYTHON
        return make_string(self._str + s._str)

    # delegate missing ll_* methods to self._str
    def __getattr__(self, attr):
        if attr.startswith('ll_'):
            return self.wrapper(getattr(self._str, attr[3:]))
        else:
            raise AttributeError, attr

    @staticmethod
    def wrapper(fn):
        def f(*args, **kwds):
            res = fn(*args, **kwds)
            if isinstance(res, str):
                return make_string(res)
            elif isinstance(res, list):
                # it must be a list of strings
                for i, item in enumerate(res):
                    res[i] = make_string(item)
                lst = _list(List(String))
                lst._list = res
                return lst
            else:
                return res
        return f

class _null_string(_null_mixin(_string), _string):
    def __init__(self, STRING):
        self.__dict__["_TYPE"] = STRING

class _string_builder(_builtin_type):
    def __init__(self, STRING_BUILDER):
        self._TYPE = STRING_BUILDER
        self._buf = []

    def ll_allocate(self, n):
        assert isinstance(n, int)
        # do nothing

    def ll_append_char(self, ch):
        assert isinstance(ch, str) and len(ch) == 1
        self._buf.append(ch)

    def ll_append(self, s):
        assert isinstance(s, _string)
        self._buf.append(s._str)

    def ll_build(self):
        return make_string(''.join(self._buf))

class _null_string_builder(_null_mixin(_string_builder), _string_builder):
    def __init__(self, STRING_BUILDER):
        self.__dict__["_TYPE"] = STRING_BUILDER


class _list(_builtin_type):
    def __init__(self, LIST):
        self._TYPE = LIST
        self._list = []

    # The following are implementations of the abstract list interface for
    # use by the llinterpreter and ootype tests. There are NOT_RPYTHON
    # because the annotator is not supposed to follow them.

    def ll_length(self):
        # NOT_RPYTHON
        return len(self._list)

    def _ll_resize_ge(self, length):
        # NOT_RPYTHON        
        if len(self._list) < length:
            diff = length - len(self._list)
            self._list += [self._TYPE._ITEMTYPE._defl()] * diff
        assert len(self._list) >= length

    def _ll_resize_le(self, length):
        # NOT_RPYTHON
        if length < len(self._list):
            del self._list[length:]
        assert len(self._list) <= length

    def _ll_resize(self, length):
        # NOT_RPYTHON
        if length > len(self._list):
            self._ll_resize_ge(length)
        elif length < len(self._list):
            self._ll_resize_le(length)
        assert len(self._list) == length

    def ll_getitem_fast(self, index):
        # NOT_RPYTHON
        assert typeOf(index) == Signed
        assert index >= 0
        return self._list[index]

    def ll_setitem_fast(self, index, item):
        # NOT_RPYTHON
        assert typeOf(item) == self._TYPE._ITEMTYPE
        assert typeOf(index) == Signed
        assert index >= 0
        self._list[index] = item

class _null_list(_null_mixin(_list), _list):

    def __init__(self, LIST):
        self.__dict__["_TYPE"] = LIST 

class _dict(_builtin_type):
    def __init__(self, DICT):
        self._TYPE = DICT
        self._dict = {}

    def ll_length(self):
        # NOT_RPYTHON
        return len(self._dict)

    def ll_get(self, key):
        # NOT_RPYTHON        
        assert typeOf(key) == self._TYPE._KEYTYPE
        assert key in self._dict
        return self._dict[key]

    def ll_set(self, key, value):
        # NOT_RPYTHON        
        assert typeOf(key) == self._TYPE._KEYTYPE
        assert typeOf(value) == self._TYPE._VALUETYPE
        self._dict[key] = value

    def ll_remove(self, key):
        # NOT_RPYTHON
        assert typeOf(key) == self._TYPE._KEYTYPE
        try:
            del self._dict[key]
            return True
        except KeyError:
            return False

    def ll_contains(self, key):
        # NOT_RPYTHON
        assert typeOf(key) == self._TYPE._KEYTYPE
        return key in self._dict

    def ll_clear(self):
        self._dict.clear()

    def ll_get_items_iterator(self):
        # NOT_RPYTHON
        ITER = DictItemsIterator(self._TYPE._KEYTYPE, self._TYPE._VALUETYPE)
        iter = _dict_items_iterator(ITER)
        iter._items = self._dict.items()
        return iter

class _null_dict(_null_mixin(_dict), _dict):
    def __init__(self, DICT):
        self.__dict__["_TYPE"] = DICT


class _dict_items_iterator(_builtin_type):
    def __init__(self, ITER):
        self._TYPE = ITER
        self._items = []
        self._index = -1

    def ll_go_next(self):
        # NOT_RPYTHON
        self._index += 1        
        if self._index >= len(self._items):
            return False
        else:
            return True

    def ll_current_key(self):
        # NOT_RPYTHON
        assert 0 <= self._index < len(self._items)
        return self._items[self._index][0]
    
    def ll_current_value(self):
        # NOT_RPYTHON
        assert 0 <= self._index < len(self._items)
        return self._items[self._index][1]

class _null_dict_items_iterator(_null_mixin(_dict_items_iterator), _dict_items_iterator):
    def __init__(self, ITER):
        self.__dict__["_TYPE"] = ITER


class _record(object):

    def __init__(self, TYPE):
        self._items = {}
        self._TYPE = TYPE
        for name, (_, default) in TYPE._fields.items():
            self._items[name] = default

    def __getattr__(self, name):
        items = self.__dict__["_items"]
        if name in items:
            return items[name]
        return self.__dict__[name]

    def __setattr__(self, name, value):
        if hasattr(self, "_items") and name in self._items:
            self._items[name] = value
        else:
            self.__dict__[name] = value

    def _identityhash(self):
        if self:
            return id(self)
        else:
            return 0 # for all null tuples

class _null_record(_null_mixin(_record), _record):

    def __init__(self, RECORD):
        self.__dict__["_TYPE"] = RECORD 


def new(TYPE):
    if isinstance(TYPE, Instance):
        return make_instance(TYPE)
    elif isinstance(TYPE, BuiltinType):
        return TYPE._get_interp_class()(TYPE)

def runtimenew(class_):
    assert isinstance(class_, _class)
    assert class_ is not nullruntimeclass
    return make_instance(class_._INSTANCE)

def static_meth(FUNCTION, name,  **attrs):
    return _static_meth(FUNCTION, _name=name, **attrs)

def meth(METHOD, **attrs):
    return _meth(METHOD, **attrs)

def null(INSTANCE_OR_FUNCTION):
    return INSTANCE_OR_FUNCTION._null

def instanceof(inst, INSTANCE):
    # this version of instanceof() accepts a NULL instance and always
    # returns False in this case.
    assert isinstance(typeOf(inst), Instance)
    return inst._instanceof(INSTANCE)

def classof(inst):
    assert isinstance(typeOf(inst), Instance)
    return inst._classof()

def dynamicType(inst):
    assert isinstance(typeOf(inst), Instance)
    return classof(inst)._INSTANCE

def subclassof(class1, class2):
    assert isinstance(class1, _class)
    assert isinstance(class2, _class)
    assert class1 is not nullruntimeclass
    assert class2 is not nullruntimeclass
    return isSubclass(class1._INSTANCE, class2._INSTANCE)

def addFields(INSTANCE, fields):
    INSTANCE._add_fields(fields)

def addMethods(INSTANCE, methods):
    INSTANCE._add_methods(methods)

def runtimeClass(INSTANCE):
    assert isinstance(INSTANCE, Instance)
    return INSTANCE._class

def isSubclass(C1, C2):
    c = C1
    while c is not None:
        if c == C2:
            return True
        c = c._superclass
    return False

def commonBaseclass(INSTANCE1, INSTANCE2):
    c = INSTANCE1
    while c is not None:
        if isSubclass(INSTANCE2, c):
            return c
        c = c._superclass
    return None

def ooupcast(INSTANCE, instance):
    return instance._upcast(INSTANCE)
    
def oodowncast(INSTANCE, instance):
    return instance._downcast(INSTANCE)

def ooidentityhash(inst):
    assert isinstance(typeOf(inst), (Instance, Record))
    return inst._identityhash()

def oostring(obj):
    "Convert char, int and str to str"
    return make_string(str(obj))

def setItemType(LIST, ITEMTYPE):
    return LIST._set_itemtype(ITEMTYPE)

def hasItemType(LIST):
    return LIST._ITEMTYPE is not None

def setDictTypes(DICT, KEYTYPE, VALUETYPE):
    return DICT._set_types(KEYTYPE, VALUETYPE)

def hasDictTypes(DICT):
    return DICT._is_initialized()

String = String()
StringBuilder = StringBuilder()
ROOT = Instance('Root', None, _is_root=True)
