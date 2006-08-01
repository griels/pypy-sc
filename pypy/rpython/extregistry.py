import weakref
import UserDict
from pypy.tool.uid import Hashable


class AutoRegisteringType(type):

    def __init__(selfcls, name, bases, dict):
        super(AutoRegisteringType, selfcls).__init__(selfcls,
                                                     name, bases, dict)
        if '_about_' in dict:
            selfcls._register_value(dict['_about_'])
            del selfcls._about_   # avoid keeping a ref
        if '_type_' in dict:
            selfcls._register_type(dict['_type_'])
            del selfcls._type_
        if '_metatype_' in dict:
            selfcls._register_metatype(dict['_metatype_'])
            del selfcls._metatype_

    def _register_value(selfcls, key):
        if isinstance(key, (tuple, list)):
            for k in key:
                selfcls._register_value(k)
        else:
            assert key not in EXT_REGISTRY_BY_VALUE
            EXT_REGISTRY_BY_VALUE[key] = selfcls

    def _register_type(selfcls, key):
        if isinstance(key, (tuple, list)):
            for k in key:
                selfcls._register_type(k)
        else:
            assert key not in EXT_REGISTRY_BY_TYPE
            EXT_REGISTRY_BY_TYPE[key] = selfcls

    def _register_metatype(selfcls, key):
        if isinstance(key, (tuple, list)):
            for k in key:
                selfcls._register_metatype(k)
        else:
            assert key not in EXT_REGISTRY_BY_METATYPE
            EXT_REGISTRY_BY_METATYPE[key] = selfcls


class ExtRegistryEntry(object):
    __metaclass__ = AutoRegisteringType

    def __init__(self, type, instance=None):
        self.type = type
        self.instance = instance

    # structural equality, and trying hard to be hashable: Entry instances
    # are used as keys to map annotations to Reprs in the rtyper.
    # Warning, it's based on only 'type' and 'instance'.
    def __eq__(self, other):
        return (self.__class__ is other.__class__ and
                self.type == other.type and
                self.instance == other.instance)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.__class__, self.type, Hashable(self.instance)))

    def compute_annotation(self):
        # default implementation useful for built-in functions,
        # can be overriden
        func = self.instance
        assert func is not None
        from pypy.annotation import model as annmodel
        analyser = self.compute_result_annotation
        methodname = getattr(func, '__name__', None)
        return annmodel.SomeBuiltin(analyser, methodname=methodname)

    def compute_result_annotation(self, *args_s, **kwds_s):
        # default implementation for built-in functions with a constant
        # result annotation, can be overriden
        return self.s_result_annotation

# ____________________________________________________________

class FlexibleWeakDict(UserDict.DictMixin):
    """A WeakKeyDictionary that accepts more or less anything as keys:
    weakly referenceable objects or not, hashable objects or not.
    """
    def __init__(self):
        self._regdict = {}
        self._weakdict = weakref.WeakKeyDictionary()
        self._iddict = {}

    def ref(self, key):
        try:
            hash(key)
        except TypeError:
            return self._iddict, Hashable(key)   # key is not hashable
        try:
            weakref.ref(key)
        except TypeError:
            return self._regdict, key            # key cannot be weakly ref'ed
        else:
            return self._weakdict, key           # normal case

    def __getitem__(self, key):
        d, key = self.ref(key)
        return d[key]

    def __setitem__(self, key, value):
        d, key = self.ref(key)
        d[key] = value

    def __delitem__(self, key):
        d, key = self.ref(key)
        del d[key]

    def keys(self):
        return (self._regdict.keys() +
                self._weakdict.keys() +
                [hashable.value for hashable in self._iddict])


EXT_REGISTRY_BY_VALUE = FlexibleWeakDict()
EXT_REGISTRY_BY_TYPE = weakref.WeakKeyDictionary()
EXT_REGISTRY_BY_METATYPE = weakref.WeakKeyDictionary()

# ____________________________________________________________
# Public interface to access the registry

def _lookup_type_cls(tp):
    try:
        return EXT_REGISTRY_BY_TYPE[tp]
    except (KeyError, TypeError):
        return EXT_REGISTRY_BY_METATYPE[type(tp)]

def lookup_type(tp):
    Entry = _lookup_type_cls(tp)
    return Entry(tp)

def is_registered_type(tp):
    try:
        _lookup_type_cls(tp)
    except KeyError:
        return False
    return True

def _lookup_cls(instance):
    try:
        return EXT_REGISTRY_BY_VALUE[instance]
    except (KeyError, TypeError):
        return _lookup_type_cls(type(instance))

def lookup(instance):
    Entry = _lookup_cls(instance)
    return Entry(type(instance), instance)

def is_registered(instance):
    try:
        _lookup_cls(instance)
    except KeyError:
        return False
    return True
