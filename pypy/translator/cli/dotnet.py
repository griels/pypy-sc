import types

from pypy.annotation.pairtype import pair, pairtype
from pypy.annotation.model import SomeObject, SomeOOInstance, SomeInteger, s_None,\
     s_ImpossibleValue, lltype_to_annotation, annotation_to_lltype, SomeChar, SomeString
from pypy.rpython.error import TyperError
from pypy.rpython.extregistry import ExtRegistryEntry
from pypy.rpython.rmodel import Repr
from pypy.rpython.rint import IntegerRepr
from pypy.rpython.ootypesystem.rootype import OOInstanceRepr
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.ootypesystem.ootype import meth, overload, Meth, StaticMethod
from pypy.translator.cli.support import PythonNet

## Annotation model

class SomeCliClass(SomeObject):
    def getattr(self, s_attr):
        assert self.is_constant()
        assert s_attr.is_constant()
        return SomeCliStaticMethod(self.const, s_attr.const)

    def simple_call(self, *s_args):
        assert self.is_constant()
        return SomeOOInstance(self.const._INSTANCE)

    def rtyper_makerepr(self, rtyper):
        return CliClassRepr(self.const)

    def rtyper_makekey(self):
        return self.__class__, self.const


class SomeCliStaticMethod(SomeObject):
    def __init__(self, cli_class, meth_name):
        self.cli_class = cli_class
        self.meth_name = meth_name

    def simple_call(self, *args_s):
        return self.cli_class._ann_static_method(self.meth_name, args_s)

    def rtyper_makerepr(self, rtyper):
        return CliStaticMethodRepr(self.cli_class, self.meth_name)

    def rtyper_makekey(self):
        return self.__class__, self.cli_class, self.meth_name

class __extend__(pairtype(SomeOOInstance, SomeInteger)):
    def getitem((ooinst, index)):
        if ooinst.ootype._isArray:
            return SomeOOInstance(ooinst.ootype._ELEMENT)
        return s_ImpossibleValue
    

## Rtyper model

class CliClassRepr(Repr):
    lowleveltype = ootype.Void

    def __init__(self, cli_class):
        self.cli_class = cli_class

    def rtype_getattr(self, hop):
        return hop.inputconst(ootype.Void, self.cli_class)

    def rtype_simple_call(self, hop):
        # TODO: resolve constructor overloading
        INSTANCE = hop.args_r[0].cli_class._INSTANCE
        cINST = hop.inputconst(ootype.Void, INSTANCE)
        vlist = hop.inputargs(*hop.args_r)[1:] # discard the first argument
        hop.exception_is_here()
        return hop.genop("new", [cINST]+vlist, resulttype=hop.r_result.lowleveltype)

class CliStaticMethodRepr(Repr):
    lowleveltype = ootype.Void

    def __init__(self, cli_class, meth_name):
        self.cli_class = cli_class
        self.meth_name = meth_name

    def _build_desc(self, args_v):
        ARGS = tuple([v.concretetype for v in args_v])
        return self.cli_class._lookup(self.meth_name, ARGS)

    def rtype_simple_call(self, hop):
        vlist = []
        for i, repr in enumerate(hop.args_r[1:]):
            vlist.append(hop.inputarg(repr, i+1))
        resulttype = hop.r_result.lowleveltype
        desc = self._build_desc(vlist)
        cDesc = hop.inputconst(ootype.Void, desc)
        return hop.genop("direct_call", [cDesc] + vlist, resulttype=resulttype)

class __extend__(pairtype(OOInstanceRepr, IntegerRepr)):

    def rtype_getitem((r_inst, r_int), hop):
        if not r_inst.lowleveltype._isArray:
            raise TyperError("getitem() on a non-array instance")
        v_array, v_index = hop.inputargs(r_inst, ootype.Signed)
        hop.exception_is_here()
        return hop.genop('cli_getelem', [v_array, v_index], hop.r_result.lowleveltype)


## OOType model

class OverloadingResolver(ootype.OverloadingResolver):

    def _can_convert_from_to(self, ARG1, ARG2):
        if ARG1 is ootype.Void and isinstance(ARG2, NativeInstance):
            return True # ARG1 could be None, that is always convertible to a NativeInstance
        else:
            return ootype.OverloadingResolver._can_convert_from_to(self, ARG1, ARG2)

    def annotation_to_lltype(cls, ann):
        if isinstance(ann, SomeChar):
            return ootype.Char
        elif isinstance(ann, SomeString):
            return ootype.String
        else:
            return annotation_to_lltype(ann)
    annotation_to_lltype = classmethod(annotation_to_lltype)

    def lltype_to_annotation(cls, TYPE):
        if TYPE is ootype.Char:
            return SomeChar()
        elif TYPE is ootype.String:
            return SomeString()
        else:
            return lltype_to_annotation(TYPE)
    lltype_to_annotation = classmethod(lltype_to_annotation)



class _static_meth(object):

    def __init__(self, TYPE):
        self._TYPE = TYPE

    def _set_attrs(self, cls, name):
        self._cls = cls
        self._name = name

    def _get_desc(self, ARGS):
        #assert ARGS == self._TYPE.ARGS
        return self


class _overloaded_static_meth(object):
    def __init__(self, *overloadings, **attrs):
        resolver = attrs.pop('resolver', OverloadingResolver)
        assert not attrs
        self._resolver = resolver(overloadings)

    def _set_attrs(self, cls, name):
        for meth in self._resolver.overloadings:
            meth._set_attrs(cls, name)

    def _get_desc(self, ARGS):
        meth = self._resolver.resolve(ARGS)
        assert isinstance(meth, _static_meth)
        return meth._get_desc(ARGS)


class NativeInstance(ootype.Instance):
    def __init__(self, assembly, namespace, name, superclass,
                 fields={}, methods={}, _is_root=False, _hints = {}):
        fullname = '%s%s.%s' % (assembly, namespace, name)
        self._namespace = namespace
        self._classname = name
        ootype.Instance.__init__(self, fullname, superclass, fields, methods, _is_root, _hints)


## RPython interface definition

class CliClass(object):
    def __init__(self, INSTANCE, static_methods):
        self._name = INSTANCE._name
        self._INSTANCE = INSTANCE
        self._static_methods = {}
        self._add_methods(static_methods)

    def __repr__(self):
        return '<%s>' % (self,)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self._INSTANCE._name)

    def _add_methods(self, methods):
        self._static_methods.update(methods)
        for name, meth in methods.iteritems():
            meth._set_attrs(self, name)

    def _lookup(self, meth_name, ARGS):
        meth = self._static_methods[meth_name]
        return meth._get_desc(ARGS)

    def _ann_static_method(self, meth_name, args_s):
        meth = self._static_methods[meth_name]
        return meth._resolver.annotate(args_s)

    def _load_class(self):
        names = self._INSTANCE._namespace.split('.')
        names.append(self._INSTANCE._classname)
        obj = PythonNet
        for name in names:
            obj = getattr(obj, name)
        self._PythonNet_class = obj

    def __getattr__(self, attr):
        if attr in self._static_methods:
            self._load_class()
            return getattr(self._PythonNet_class, attr)
        else:
            raise AttributeError

    def __call__(self, *args):
        self._load_class()
        return self._PythonNet_class(*args)


class Entry(ExtRegistryEntry):
    _type_ = CliClass

    def compute_annotation(self):
        return SomeCliClass()


class CliNamespace(object):
    def __init__(self, name):
        self._name = name

    def __fullname(self, name):
        if self._name is None:
            return name
        else:
            return '%s.%s' % (self._name, name)

    def __getattr__(self, attr):
        from pypy.translator.cli.query import load_class_or_namespace
        # .NET namespace are not self-entities but just parts of the
        # FullName of a class. This imply that there is no way ask
        # .NET if a particular name is a namespace; there are many
        # names that are clearly not namespaces such as im_self and
        # _freeze_, but there is no general rule and we have to guess.
        # For now, the heuristic simply check is the first char of the
        # name is a UPPERCASE letter.
        
        if attr[0].isalpha() and attr[0] == attr[0].upper():
            # we assume it's a class or namespace
            name = self.__fullname(attr)
            load_class_or_namespace(name)
            assert attr in self.__dict__
            return getattr(self, attr)
        else:
            raise AttributeError

CLR = CliNamespace(None)


BOXABLE_TYPES = [ootype.Signed, ootype.Unsigned, ootype.SignedLongLong,
                 ootype.UnsignedLongLong, ootype.Bool, ootype.Float,
                 ootype.Char, ootype.String]

def box(x):
    return x

def unbox(x, TYPE):
    # TODO: check that x is really of type TYPE
    return x


class Entry(ExtRegistryEntry):
    _about_ = box

    def compute_result_annotation(self, x_s):
        return SomeOOInstance(CLR.System.Object._INSTANCE)

    def specialize_call(self, hop):
        v_obj, = hop.inputargs(*hop.args_r)
        if v_obj.concretetype not in BOXABLE_TYPES:
            raise TyperError, "Can't box values of type %s" % v_obj.concretetype
        
        if (v_obj.concretetype is ootype.String):
            return hop.genop('ooupcast', [v_obj], hop.r_result.lowleveltype)
        else:
            return hop.genop('clibox', [v_obj], hop.r_result.lowleveltype)

class Entry(ExtRegistryEntry):
    _about_ = unbox

    def compute_result_annotation(self, x_s, type_s):
        assert isinstance(x_s, SomeOOInstance)
        assert x_s.ootype == CLR.System.Object._INSTANCE
        assert type_s.is_constant()
        TYPE = type_s.const
        assert TYPE in BOXABLE_TYPES
        return OverloadingResolver.lltype_to_annotation(TYPE)

    def specialize_call(self, hop):
        v_obj, v_type = hop.inputargs(*hop.args_r)
        if v_type.value is ootype.String:
            return hop.genop('oodowncast', [v_obj], hop.r_result.lowleveltype)
        else:
            return hop.genop('cliunbox', [v_obj, v_type], hop.r_result.lowleveltype)



native_exc = {}
def NativeException(cliClass):
    try:
        return native_exc[cliClass._name]
    except KeyError:
        res = _create_NativeException(cliClass)
        native_exc[cliClass._name] = res
        return res

def _create_NativeException(cliClass):
    from pypy.translator.cli.query import getattr_ex
    TYPE = cliClass._INSTANCE
    if PythonNet.__name__ == 'CLR':
        # we are using pythonnet -- use the .NET class
        name = '%s.%s' % (TYPE._namespace, TYPE._classname)
        res = getattr_ex(PythonNet, name)
    else:
        # we are not using pythonnet -- create a fake class
        res = types.ClassType(TYPE._classname, (Exception,), {})
    res._rpython_hints = {'native_class': cliClass._name}
    return res
