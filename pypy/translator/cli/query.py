import sys
import cPickle as pickle
import os.path
import py
from py.compat import subprocess
from pypy.tool.udir import udir
from pypy.rpython.ootypesystem import ootype
from pypy.translator.cli.rte import Query
from pypy.translator.cli.sdk import SDK
from pypy.translator.cli.support import log
from pypy.translator.cli.dotnet import CLR, CliNamespace, CliClass,\
     NativeInstance, _overloaded_static_meth, _static_meth, OverloadingResolver

Assemblies = set()
Types = {} # TypeName -> ClassDesc
Namespaces = set()
mscorlib = 'mscorlib, Version=2.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089'

#_______________________________________________________________________________
# This is the public interface of query.py

def load_assembly(name):
    if name in Assemblies:
        return
    Query.get() # clear the cache if we need to recompile
    _cache = get_cachedir()
    outfile = _cache.join(name + '.pickle')
    if outfile.check():
        f = outfile.open('rb')
        types = pickle.load(f)
        f.close()
    else:
        types = load_and_cache_assembly(name, outfile)

    for ttype in types:
        parts = ttype.split('.')
        ns = parts[0]
        Namespaces.add(ns)
        for part in parts[1:-1]:
            ns = '%s.%s' % (ns, part)
            Namespaces.add(ns)
    Assemblies.add(name)
    Types.update(types)


def get_cli_class(name):
    desc = get_class_desc(name)
    return desc.get_cliclass()

#_______________________________________________________________________________


def get_cachedir():
    import pypy
    _cache = py.path.local(pypy.__file__).new(basename='_cache').ensure(dir=1)
    return _cache

def load_and_cache_assembly(name, outfile):
    tmpfile = udir.join(name)
    arglist = SDK.runtime() + [Query.get(), name, str(tmpfile)]
    retcode = subprocess.call(arglist)
    assert retcode == 0
    mydict = {}
    execfile(str(tmpfile), mydict)
    types = mydict['types']
    f = outfile.open('wb')
    pickle.dump(types, f, pickle.HIGHEST_PROTOCOL)
    f.close()
    return types

def get_ootype(name):
    # a bit messy, but works
    if name.startswith('ootype.'):
        _, name = name.split('.')
        return getattr(ootype, name)
    else:
        cliclass = get_cli_class(name)
        return cliclass._INSTANCE

def get_class_desc(name):
    if name in Types:
        return Types[name]

    if name == 'System.Array':
        desc = ClassDesc()
        desc.Assembly = mscorlib
        desc.FullName = name
        desc.BaseType = 'System.Object'
        desc.IsArray = True
        desc.ElementType = 'System.Object' # not really true, but we need something
        desc.StaticMethods = []
        desc.Methods = []
    elif name.endswith('[]'): # it's an array
        itemname = name[:-2]
        itemdesc = get_class_desc(itemname)
        desc = ClassDesc()
        desc.Assembly = mscorlib
        desc.FullName = name
        desc.BaseType = 'System.Array'
        desc.ElementType = itemdesc.FullName
        desc.IsArray = True
        desc.StaticMethods = []
        desc.Methods = [
            ('Get', ['ootype.Signed', ], itemdesc.FullName),
            ('Set', ['ootype.Signed', itemdesc.FullName], 'ootype.Void')
            ]
    else:
        assert False, 'Unknown desc'

    Types[name] = desc
    return desc


class ClassDesc(object):
    _cliclass = None

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        raise TypeError

    def get_cliclass(self):
        if self._cliclass is not None:
            return self._cliclass
        
        assert self.Assembly.startswith('mscorlib') # TODO: support external assemblies
        namespace, name = self.FullName.rsplit('.', 1)

        # construct OOTYPE and CliClass
        # no superclass for now, will add it later
        TYPE = NativeInstance('[mscorlib]', namespace, name, None, {}, {})
        Class = CliClass(TYPE, {})
        self._cliclass = Class
        # we need to check also for System.Array to prevent a circular recursion
        if self.FullName in ('System.Object', 'System.Array'):
            TYPE._set_superclass(ootype.ROOT)
        else:
            BASETYPE = get_ootype(self.BaseType)
            TYPE._set_superclass(BASETYPE)

        TYPE._isArray = self.IsArray
        if self.IsArray:
            TYPE._ELEMENT = get_ootype(self.ElementType)

        # add both static and instance methods
        static_meths = self.group_methods(self.StaticMethods, _overloaded_static_meth,
                                          _static_meth, ootype.StaticMethod)
        meths = self.group_methods(self.Methods, ootype.overload, ootype.meth, ootype.Meth)
        Class._add_methods(static_meths)
        TYPE._add_methods(meths)
        return Class

    def group_methods(self, methods, overload, meth, Meth):
        groups = {}
        for name, args, result in methods:
            groups.setdefault(name, []).append((args, result))

        res = {}
        attrs = dict(resolver=OverloadingResolver)
        for name, methlist in groups.iteritems():
            TYPES = [self.get_method_type(Meth, args, result) for (args, result) in methlist]
            meths = [meth(TYPE) for TYPE in TYPES]
            res[name] = overload(*meths, **attrs)
        return res

    def get_method_type(self, Meth, args, result):
        ARGS = [get_ootype(arg) for arg in args]
        RESULT = get_ootype(result)
        return Meth(ARGS, RESULT)
