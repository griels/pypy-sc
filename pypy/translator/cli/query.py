import cPickle as pickle
import os.path
from py.compat import subprocess
from pypy.rpython.ootypesystem import ootype
from pypy.translator.cli.rte import Query
from pypy.translator.cli.sdk import SDK
from pypy.translator.cli.support import log
from pypy.translator.cli.dotnet import CLR, CliNamespace, CliClass,\
     NativeInstance, _overloaded_static_meth, _static_meth
    
ClassCache = {}
OOTypeCache = {}
Descriptions = {}

class Dummy: pass
fake_root = Dummy()
fake_root._INSTANCE = ootype.ROOT
ClassCache['ROOT'] = fake_root
ClassCache['System.Array'] = fake_root
del fake_root
del Dummy

def _descfilename(filename):
    if filename is None:
        curdir = os.path.dirname(__file__)
        return os.path.join(curdir, 'query-descriptions')
    else:
        return filename

def savedesc(filename=None):
    f = open(_descfilename(filename), 'wb')
    pickle.dump(Descriptions, f, protocol=-1)
    f.close()

def loaddesc(filename=None):
    filename = _descfilename(filename)
    if not os.path.exists(filename):
        return
    f = open(filename, 'rb')
    try:
        newdesc = pickle.load(f)        
    except pickle.UnpicklingError:
        log.WARNING('query-descriptions file exits, but failed to unpickle')
    else:
        Descriptions.clear()
        Descriptions.update(newdesc)

def getattr_ex(target, attr):
    parts = attr.split('.')
    for part in parts:
        target = getattr(target, part)
    return target

def setattr_ex(target, attr, value):
    if '.' in attr:
        namespace, attr = attr.rsplit('.', 1)
        target = getattr_ex(target, namespace)
    setattr(target, attr, value)

def load_class_or_namespace(name):
    try:
        desc = Descriptions[name]
    except KeyError:
        desc = query_description(name)
        Descriptions[name] = desc
    setattr_ex(CLR, name, desc.build())

def query_description(name):
    log.query('Loading description for %s' % name)
    arglist = SDK.runtime() + [Query.get(), name]
    query = subprocess.Popen(arglist, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = query.communicate()
    retval = query.wait()
    if retval == 0:
        cls = ClassDesc()
        exec stdout in cls.__dict__
        del cls.__dict__['__builtins__']
        return cls
    elif retval == 1:
        raise RuntimeError, 'query.exe failed with this message:\n%s' % stderr
    elif retval == 2:
        # can't load type, assume it's a namespace
        return NamespaceDesc(name)

def load_class_maybe(name):
    if name not in ClassCache:
        load_class_or_namespace(name)


class Desc:
    def build(self):
        raise NotImplementedError
    
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __hash__(self):
        raise TypeError
    
class NamespaceDesc(Desc):
    def __init__(self, name):
        self.name = name

    def build(self):
        return CliNamespace(self.name)

class ClassDesc(Desc):
    def build(self):
        assert self.Assembly.startswith('mscorlib') # TODO: support external assemblies
        namespace, name = self.FullName.rsplit('.', 1)

        # construct OOTYPE and CliClass
        load_class_maybe(self.BaseType)
        BASETYPE = ClassCache[self.BaseType]._INSTANCE
        TYPE = NativeInstance('[mscorlib]', namespace, name, BASETYPE, {}, {})
        Class = CliClass(TYPE, {})
        OOTypeCache[self.OOType] = TYPE
        ClassCache[self.FullName] = Class

        # render dependencies
        for name in self.Depend:
            load_class_maybe(name)

        # add both static and instance methods
        static_meths = self.group_methods(self.StaticMethods, _overloaded_static_meth,
                                          _static_meth, ootype.StaticMethod, always_group=True)
        meths = self.group_methods(self.Methods, ootype.overload, ootype.meth, ootype.Meth)
        Class._add_methods(static_meths)
        TYPE._add_methods(meths)
        return Class

    def group_methods(self, methods, overload, meth, Meth, always_group=False):
        groups = {}
        for name, args, result in methods:
            groups.setdefault(name, []).append((args, result))

        res = {}
        for name, methlist in groups.iteritems():
            if len(methlist) == 1 and not always_group:
                args, result = methlist[0]
                TYPE = self.get_method_type(Meth, args, result)
                res[name] = meth(TYPE)
            else:
                TYPES = [self.get_method_type(Meth, args, result) for (args, result) in methlist]
                meths = [meth(TYPE) for TYPE in TYPES]
                res[name] = overload(*meths)
        return res

    def get_method_type(self, Meth, args, result):
        ARGS = [self.get_ootype(arg) for arg in args]
        RESULT = self.get_ootype(result)
        return Meth(ARGS, RESULT)

    def get_ootype(self, t):
        # a bit messy, but works
        if t.startswith('ootype.'):
            _, name = t.split('.')
            return getattr(ootype, name)
        else:
            return OOTypeCache[t]


loaddesc() ## automatically loads the cached Dependencies
