"""
Generate a Python source file from the flowmodel.
The purpose is to create something that allows
to restart code generation after flowing and maybe
annotation.
"""
import autopath, os, sys, new, __builtin__

from pypy.translator.gensupp import uniquemodulename, NameManager, UniqueList
from pypy.translator.gensupp import builtin_base
from pypy.rpython.rarithmetic import r_int, r_uint
from pypy.objspace.flow.model import Variable, Constant, SpaceOperation
from pypy.objspace.flow.model import FunctionGraph, Block, Link
from pypy.interpreter.baseobjspace import ObjSpace

from pickle import whichmodule, PicklingError
import pickle

from types import *

# ____________________________________________________________


class GenPickle:

    def __init__(self, translator):
        self.translator = translator
        self.initcode = UniqueList([
            'import new, types, sys',
            ])

        self.latercode = []    # list of generators generating extra lines
        self.debugstack = ()   # linked list of nested nameof()
        self.initcode = UniqueList(self.initcode)

        self.picklenames = {Constant(None):  'None',
                            Constant(False): 'False',
                            Constant(True):  'True',
                            }
        self.namespace = NameManager()
        self.namespace.make_reserved_names('None False True')

    def nameof(self, obj, debug=None, namehint=None):
        key = Constant(obj)
        try:
            return self.picklenames[key]
        except KeyError:
            if debug:
                stackentry = debug, obj
            else:
                stackentry = obj
            self.debugstack = (self.debugstack, stackentry)
            obj_builtin_base = builtin_base(obj)
            if obj_builtin_base in (object, int, long) and type(obj) is not obj_builtin_base:
                # assume it's a user defined thingy
                name = self.nameof_instance(obj)
            else:
                for cls in type(obj).__mro__:
                    meth = getattr(self,
                                   'nameof_' + cls.__name__.replace(' ', ''),
                                   None)
                    if meth:
                        break
                else:
                    raise Exception, "nameof(%r)" % (obj,)

                code = meth.im_func.func_code
                if namehint and 'namehint' in code.co_varnames[:code.co_argcount]:
                    name = meth(obj, namehint=namehint)
                else:
                    name = meth(obj)
            self.debugstack, x = self.debugstack
            assert x is stackentry
            self.picklenames[key] = name
            return name

    def uniquename(self, basename):
        return self.namespace.uniquename(basename)

    def initcode_python(self, name, pyexpr):
        # generate init code that will evaluate the given Python expression
        #self.initcode.append("print 'setting up', %r" % name)
        self.initcode.append("%s = %s" % (name, pyexpr))

    def nameof_object(self, value):
        if type(value) is not object:
            raise Exception, "nameof(%r)" % (value,)
        name = self.uniquename('g_object')
        self.initcode_python(name, "object()")
        return name

    def nameof_module(self, value):
        assert value is os or not hasattr(value, "__file__") or \
               not (value.__file__.endswith('.pyc') or
                    value.__file__.endswith('.py') or
                    value.__file__.endswith('.pyo')), \
               "%r is not a builtin module (probably :)"%value
        name = self.uniquename('mod%s'%value.__name__)
        self.initcode_python(name, "__import__(%r)" % (value.__name__,))
        return name
        

    def nameof_int(self, value):
        return repr(value)

    # we don't need to name the following const types.
    # the compiler folds the consts the same way as we do.
    # note that true pickling is more exact, here.
    nameof_long = nameof_float = nameof_bool = nameof_NoneType = nameof_int

    def nameof_str(self, value):
        name = self.uniquename('gstr_' + value[:32])
        self.initcode_python(name, repr(value))
        return name

    def nameof_unicode(self, value):
        name = self.uniquename('guni_' + str(value[:32]))
        self.initcode_python(name, repr(value))
        return name

    def skipped_function(self, func):
        # debugging only!  Generates a placeholder for missing functions
        # that raises an exception when called.
        if self.translator.frozen:
            warning = 'NOT GENERATING'
        else:
            warning = 'skipped'
        printable_name = '(%s:%d) %s' % (
            func.func_globals.get('__name__', '?'),
            func.func_code.co_firstlineno,
            func.__name__)
        print warning, printable_name
        name = self.uniquename('gskippedfunc_' + func.__name__)
        self.initcode.append('def %s(*a,**k):' % name)
        self.initcode.append('  raise NotImplementedError')
        return name

    def nameof_staticmethod(self, sm):
        # XXX XXX XXXX
        func = sm.__get__(42.5)
        name = self.uniquename('gsm_' + func.__name__)
        functionname = self.nameof(func)
        self.initcode_python(name, 'staticmethod(%s)' % functionname)
        return name

    def nameof_instancemethod(self, meth):
        if meth.im_self is None:
            # no error checking here
            return self.nameof(meth.im_func)
        else:
            ob = self.nameof(meth.im_self)
            func = self.nameof(meth.im_func)
            typ = self.nameof(meth.im_class)
            name = self.uniquename('gmeth_'+meth.im_func.__name__)
            self.initcode_python(name, 'new.instancemethod(%s, %s, %s)' % (
                func, ob, typ))
            return name

    def should_translate_attr(self, pbc, attr):
        ann = self.translator.annotator
        if ann is None or isinstance(pbc, ObjSpace):
            ignore = getattr(pbc.__class__, 'NOT_RPYTHON_ATTRIBUTES', [])
            if attr in ignore:
                return False
            else:
                return "probably"   # True
        classdef = ann.getuserclasses().get(pbc.__class__)
        if classdef and classdef.about_attribute(attr) is not None:
            return True
        return False

    def nameof_builtin_function_or_method(self, func):
        if func.__self__ is None:
            # builtin function
            # where does it come from? Python2.2 doesn't have func.__module__
            for modname, module in sys.modules.items():
                if hasattr(module, '__file__'):
                    if (module.__file__.endswith('.py') or
                        module.__file__.endswith('.pyc') or
                        module.__file__.endswith('.pyo')):
                        continue    # skip non-builtin modules
                if func is getattr(module, func.__name__, None):
                    break
            else:
                raise Exception, '%r not found in any built-in module' % (func,)
            name = self.uniquename('gbltin_' + func.__name__)
            if modname == '__builtin__':
                self.initcode_python(name, func.__name__)
            else:
                modname = self.nameof(module)
                self.initcode_python(name, '%s.%s' % (modname, func.__name__))
        else:
            # builtin (bound) method
            name = self.uniquename('gbltinmethod_' + func.__name__)
            selfname = self.nameof(func.__self__)
            self.initcode_python(name, '%s.%s' % (selfname, func.__name__))
        return name

    def nameof_classobj(self, cls):
        if cls.__doc__ and cls.__doc__.lstrip().startswith('NOT_RPYTHON'):
            raise Exception, "%r should never be reached" % (cls,)

        try:
            return self.save_global(cls)
        except PicklingError:
            pass
        
        metaclass = "type"
        if issubclass(cls, Exception):
            # if cls.__module__ == 'exceptions':
            # don't rely on this, py.magic redefines AssertionError
            if getattr(__builtin__,cls.__name__,None) is cls:
                name = self.uniquename('gexc_' + cls.__name__)
                self.initcode_python(name, cls.__name__)
                return name
            #else:
            #    # exceptions must be old-style classes (grr!)
            #    metaclass = "&PyClass_Type"
        # For the moment, use old-style classes exactly when the
        # pypy source uses old-style classes, to avoid strange problems.
        if not isinstance(cls, type):
            assert type(cls) is ClassType
            metaclass = "types.ClassType"

        name = self.uniquename('gcls_' + cls.__name__)
        basenames = [self.nameof(base) for base in cls.__bases__]
        def initclassobj():
            content = cls.__dict__.items()
            content.sort()
            ignore = getattr(cls, 'NOT_RPYTHON_ATTRIBUTES', [])
            for key, value in content:
                if key.startswith('__'):
                    if key in ['__module__', '__doc__', '__dict__',
                               '__weakref__', '__repr__', '__metaclass__']:
                        continue
                    # XXX some __NAMES__ are important... nicer solution sought
                    #raise Exception, "unexpected name %r in class %s"%(key, cls)
                if isinstance(value, staticmethod) and value.__get__(1) not in self.translator.flowgraphs and self.translator.frozen:
                    print value
                    continue
                if isinstance(value, classmethod):
                    doc = value.__get__(cls).__doc__
                    if doc and doc.lstrip().startswith("NOT_RPYTHON"):
                        continue
                if isinstance(value, FunctionType) and value not in self.translator.flowgraphs and self.translator.frozen:
                    print value
                    continue
                if key in ignore:
                    continue
                    
                yield '%s.%s = %s' % (name, key, self.nameof(value))

        baseargs = ", ".join(basenames)
        if baseargs:
            baseargs = '(%s)' % baseargs
        self.initcode.append('class %s%s:' % (name, baseargs))
        self.initcode.append('  __metaclass__ = %s' % metaclass)
        self.later(initclassobj())
        return name

    nameof_class = nameof_classobj   # for Python 2.2

    typename_mapping = {
        InstanceType: 'types.InstanceType',
        type(None):   'type(None)',
        CodeType:     'types.CodeType',
        type(sys):    'type(new)',

        r_int:        'r_int',
        r_uint:       'r_uint',

        # XXX more hacks
        # type 'builtin_function_or_method':
        type(len): 'type(len)',
        # type 'method_descriptor':
        type(list.append): 'type(list.append)',
        # type 'wrapper_descriptor':
        type(type(None).__repr__): 'type(type(None).__repr__)',
        # type 'getset_descriptor':
        type(type.__dict__['__dict__']): "type(type.__dict__['__dict__'])",
        # type 'member_descriptor':
        type(type.__dict__['__basicsize__']): "type(type.__dict__['__basicsize__'])",
        }

    def nameof_type(self, cls):
        if cls.__module__ != '__builtin__':
            return self.nameof_classobj(cls)   # user-defined type
        name = self.uniquename('gtype_%s' % cls.__name__)
        if getattr(__builtin__, cls.__name__, None) is cls:
            expr = cls.__name__    # type available from __builtin__
        else:
            expr = self.typename_mapping[cls]
        self.initcode_python(name, expr)
        return name

    def nameof_tuple(self, tup):
        name = self.uniquename('g%dtuple' % len(tup))
        args = [self.nameof(x) for x in tup]
        args = ', '.join(args)
        if args:
            args += ','
        self.initcode_python(name, '(%s)' % args)
        return name

    def nameof_list(self, lis):
        name = self.uniquename('g%dlist' % len(lis))
        def initlist():
            for i in range(len(lis)):
                item = self.nameof(lis[i])
                yield '%s.append(%s)' % (name, item)
        self.initcode_python(name, '[]')
        self.later(initlist())
        return name

    def nameof_dict(self, dic):
        if '__name__' in dic:
            module = dic['__name__']
            try:
                __import__(module)
                mod = sys.modules[module]
            except (ImportError, KeyError):
                pass
            else:
                if dic is mod.__dict__:
                    dictname = module.split('.')[-1] + '__dict__'
                    dictname = self.uniquename(dictname)
                    self.initcode.append('from %s import __dict__ as %s' % (
                            module, dictname) )
                    self.picklenames[Constant(dic)] = dictname
                    return dictname
        name = self.uniquename('g%ddict' % len(dic))
        def initdict():
            for k in dic:
                if type(k) is str:
                    yield '%s[%r] = %s' % (name, k, self.nameof(dic[k]))
                else:
                    yield '%s[%s] = %s' % (name, self.nameof(k),
                                           self.nameof(dic[k]))
        self.initcode_python(name, '{}')
        self.later(initdict())
        return name

    # strange prebuilt instances below, don't look too closely
    # XXX oh well.
    def nameof_member_descriptor(self, md):
        name = self.uniquename('gdescriptor_%s_%s' % (
            md.__objclass__.__name__, md.__name__))
        cls = self.nameof(md.__objclass__)
        self.initcode_python(name, '%s.__dict__[%r]' % (cls, md.__name__))
        return name
    nameof_getset_descriptor  = nameof_member_descriptor
    nameof_method_descriptor  = nameof_member_descriptor
    nameof_wrapper_descriptor = nameof_member_descriptor

    def nameof_instance(self, instance):
        klass = instance.__class__
        name = self.uniquename('ginst_' + klass.__name__)
        cls = self.nameof(klass)
        if hasattr(klass, '__base__'):
            base_class = builtin_base(instance)
            base = self.nameof(base_class)
        else:
            base_class = None
            base = cls
        def initinstance():
            content = instance.__dict__.items()
            content.sort()
            for key, value in content:
                if self.should_translate_attr(instance, key):
                    line = '%s.%s = %s' % (name, key, self.nameof(value))
                    yield line
        if hasattr(instance, '__reduce_ex__'):
            reduced = instance.__reduce_ex__()
            restorer = reduced[0]
            restorename = self.save_global(restorer)
            restoreargs = reduced[1]
            # ignore possible dict, handled later by initinstance filtering
            # in other cases, we expect that the class knows what to pickle.
        else:
            restoreargs = (base, cls)
            restorename = '%s.__new__' % base
        restoreargsname = self.nameof(restoreargs)
        if isinstance(cls, type):
            self.initcode.append('%s = %s(*%s)' % (name, restorename,
                                                   restoreargsname))
        else:
            self.initcode.append('%s = new.instance(%s)' % (name, cls))
        if hasattr(instance, '__dict__'):
            self.later(initinstance())
        return name

    def save_global(self, obj):
        # this is almost similar to pickle.py
        name = obj.__name__
        key = Constant(obj)
        if key not in self.picklenames:
            module = getattr(obj, "__module__", None)
            if module is None:
                module = whichmodule(obj, name)

            try:
                __import__(module)
                mod = sys.modules[module]
                klass = getattr(mod, name)
            except (ImportError, KeyError, AttributeError):
                raise PicklingError(
                    "Can't pickle %r: it's not found as %s.%s" %
                    (obj, module, name))
            else:
                if klass is not obj:
                    raise PicklingError(
                        "Can't pickle %r: it's not the same object as %s.%s" %
                        (obj, module, name))
            # from here we do our own stuff
            restorename = self.uniquename(obj.__name__)
            if restorename != obj.__name__:
                self.initcode.append('from %s import %s as %s' % (
                    module, obj.__name__, restorename) )
            else:
                self.initcode.append('from %s import %s' % (
                    module, obj.__name__) )
            self.picklenames[key] = restorename
        return self.picklenames[key]

    def nameof_function(self, func):
        # look for skipped functions
        if self.translator.frozen:
            if func not in self.translator.flowgraphs:
                return self.skipped_function(func)
        else:
            if (func.func_doc and
                func.func_doc.lstrip().startswith('NOT_RPYTHON')):
                return self.skipped_function(func)
        # we produce an almost equivalent function,
        # omitting the closure for now (how to do cells?)
        args = (func.func_code, func.func_globals, func.func_name,
                func.func_defaults, ) #func.func_closure) # closure omitted
        pyfuncobj = self.uniquename('gfunc_' + func.__name__)
        self.initcode.append('%s = new.function(*%s)' % (pyfuncobj,
                            self.nameof(args)) )
        return pyfuncobj

    def nameof_code(self, code):
        args = (code.co_argcount, code.co_nlocals, code.co_stacksize,
                code.co_flags, code.co_code, code.co_consts, code.co_names,
                code.co_varnames, code.co_filename, code.co_name,
                code.co_firstlineno, code.co_lnotab, code.co_freevars,
                code.co_cellvars)
        # make the code, filename and lnotab strings nicer
        codestr = code.co_code
        codestrname = self.uniquename('gcodestr_' + code.co_name)
        self.picklenames[Constant(codestr)] = codestrname
        self.initcode.append('%s = %r' % (codestrname, codestr))
        fnstr = code.co_filename
        fnstrname = self.uniquename('gfname_' + code.co_name)
        self.picklenames[Constant(fnstr)] = fnstrname
        self.initcode.append('%s = %r' % (fnstrname, fnstr))
        lnostr = code.co_lnotab
        lnostrname = self.uniquename('glnotab_' + code.co_name)
        self.picklenames[Constant(lnostr)] = lnostrname
        self.initcode.append('%s = %r' % (lnostrname, lnostr))
        argobj = self.nameof(args)
        codeobj = self.uniquename('gcode_' + code.co_name)
        self.initcode.append('%s = new.code(%s)' % (codeobj, argobj))
        return codeobj

    def nameof_file(self, fil):
        if fil is sys.stdin:  return "sys.stdin"
        if fil is sys.stdout: return "sys.stdout"
        if fil is sys.stderr: return "sys.stderr"
        raise Exception, 'Cannot translate an already-open file: %r' % (fil,)

    def later(self, gen):
        self.latercode.append((gen, self.debugstack))

    def collect_initcode(self):
        while self.latercode:
            gen, self.debugstack = self.latercode.pop()
            #self.initcode.extend(gen) -- eats TypeError! bad CPython!
            for line in gen:
                self.initcode.append(line)
            self.debugstack = ()

    def getfrozenbytecode(self):
        self.initcode.append('')
        source = '\n'.join(self.initcode)
        del self.initcode[:]
        co = compile(source, '<initcode>', 'exec')
        originalsource = source
        small = zlib.compress(marshal.dumps(co))
        source = """if 1:
            import zlib, marshal
            exec marshal.loads(zlib.decompress(%r))""" % small
        # Python 2.2 SyntaxError without newline: Bug #501622
        source += '\n'
        co = compile(source, '<initcode>', 'exec')
        del source
        return marshal.dumps(co), originalsource
