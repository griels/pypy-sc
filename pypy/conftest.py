import py, sys
from pypy.interpreter.gateway import app2interp_temp 
from pypy.interpreter.error import OperationError
from pypy.tool.pytest import appsupport 
from pypy.tool.option import make_config
from inspect import isclass, getmro

rootdir = py.magic.autopath().dirpath()

#
# PyPy's command line extra options (these are added 
# to py.test's standard options) 
#
Option = py.test.Config.Option

#class Options: 
#    group = "pypy options" 
#    optionlist = 

def usemodules_callback(option, opt, value, parser):
    parser.values.usemodules.append(value)

# XXX these options should go away

option = py.test.Config.addoptions("pypy options", 
        Option('-O', '--objspace', action="store", default=None, 
               type="string", dest="objspace", 
               help="object space to run tests on."),
        Option('--oldstyle', action="store_true",dest="oldstyle", default=False,
               help="enable oldstyle classes as default metaclass"),
        Option('--nofaking', action="store_true", 
               dest="nofaking", default=False,
               help="avoid faking of modules and objects completely."),
        Option('--usemodules', action="callback", type="string", metavar="NAME",
               callback=usemodules_callback, default=[],
               help="(mixed) modules to use."),
        Option('--compiler', action="store", type="string", dest="compiler",
               metavar="[ast|cpython]", default='ast',
               help="""select compiling approach. see pypy/doc/README.compiling"""),
        Option('--view', action="store_true", dest="view", default=False,
               help="view translation tests' flow graphs with Pygame"),
        Option('--gc', action="store", default=None, 
               type="choice", dest="gcpolicy",
               choices=['ref', 'boehm', 'none', 'framework', 'exact_boehm'],
               help="GcPolicy class to use for genc tests"),
        Option('-A', '--runappdirect', action="store_true", 
               default=False, dest="runappdirect",
               help="run applevel tests directly on python interpreter (not through PyPy)"), 
    )

_SPACECACHE={}
def getobjspace(name=None, **kwds): 
    """ helper for instantiating and caching space's for testing. 
    """ 
    config = make_config(option, objspace=name, **kwds)
    key = config.getkey()
    try:
        return _SPACECACHE[key]
    except KeyError:
        if option.runappdirect:
            return TinyObjSpace(**kwds)
        mod = __import__('pypy.objspace.%s' % config.objspace.name,
                         None, None, ['Space'])
        Space = mod.Space
        try: 
            space = Space(config)
        except OperationError, e:
            check_keyboard_interrupt(e)
            if option.verbose:  
                import traceback 
                traceback.print_exc() 
            py.test.fail("fatal: cannot initialize objspace:  %r" %(Space,))
        _SPACECACHE[key] = space
        space.setitem(space.builtin.w_dict, space.wrap('AssertionError'), 
                      appsupport.build_pytest_assertion(space))
        space.setitem(space.builtin.w_dict, space.wrap('raises'),
                      space.wrap(appsupport.app_raises))
        space.setitem(space.builtin.w_dict, space.wrap('skip'),
                      space.wrap(appsupport.app_skip))
        space.raises_w = appsupport.raises_w.__get__(space)
        space.eq_w = appsupport.eq_w.__get__(space) 
        return space

class TinyObjSpace(object):
    def __init__(self, **kwds):
        import sys
        for key, value in kwds.iteritems():
            if key == 'usemodules':
                for modname in value:
                    try:
                        __import__(modname)
                    except ImportError:
                        py.test.skip("cannot runappdirect test: "
                                     "module %r required" % (modname,))
                continue
            if not hasattr(sys, 'pypy_translation_info'):
                py.test.skip("cannot runappdirect this test on top of CPython")
            has = sys.pypy_translation_info.get(key, None)
            if has != value:
                print sys.pypy_translation_info
                py.test.skip("cannot runappdirect test: space needs %s = %s, "\
                    "while pypy-c was built with %s" % (key, value, has))

    def appexec(self, args, body):
        src = py.code.Source("def anonymous" + body.lstrip())
        d = {}
        exec src.compile() in d
        return d['anonymous'](*args)

    def wrap(self, obj):
        return obj

    def unpackiterable(self, itr):
        return list(itr)


class OpErrKeyboardInterrupt(KeyboardInterrupt):
    pass

def check_keyboard_interrupt(e):
    # we cannot easily convert w_KeyboardInterrupt to KeyboardInterrupt
    # in general without a space -- here is an approximation
    try:
        if e.w_type.name == 'KeyboardInterrupt':
            tb = sys.exc_info()[2]
            raise OpErrKeyboardInterrupt, OpErrKeyboardInterrupt(), tb
    except AttributeError:
        pass

# 
# Interfacing/Integrating with py.test's collection process 
#
#
def ensure_pytest_builtin_helpers(helpers='skip raises'.split()):
    """ hack (py.test.) raises and skip into builtins, needed
        for applevel tests to run directly on cpython but 
        apparently earlier on "raises" was already added
        to module's globals. 
    """ 
    import __builtin__
    for helper in helpers: 
        if not hasattr(__builtin__, helper):
            setattr(__builtin__, helper, getattr(py.test, helper))

class Module(py.test.collect.Module): 
    """ we take care of collecting classes both at app level 
        and at interp-level (because we need to stick a space 
        at the class) ourselves. 
    """
    def funcnamefilter(self, name): 
        if name.startswith('test_'):
            return not option.runappdirect
        if name.startswith('app_test_'):
            return True
        return False

    def classnamefilter(self, name): 
        if name.startswith('Test'):
            return not option.runappdirect
        if name.startswith('AppTest'):
            return True
        return False

    def setup(self): 
        # stick py.test raise in module globals -- carefully
        ensure_pytest_builtin_helpers() 
        super(Module, self).setup() 
        #    if hasattr(mod, 'objspacename'): 
        #        mod.space = getttestobjspace(mod.objspacename)

    def join(self, name): 
        obj = getattr(self.obj, name) 
        if isclass(obj): 
            if name.startswith('AppTest'): 
                return AppClassCollector(name, parent=self) 
            else: 
                return IntClassCollector(name, parent=self) 
        elif hasattr(obj, 'func_code'): 
            if name.startswith('app_test_'): 
                assert not obj.func_code.co_flags & 32, \
                    "generator app level functions? you must be joking" 
                return AppTestFunction(name, parent=self) 
            elif obj.func_code.co_flags & 32: # generator function 
                return self.Generator(name, parent=self) 
            else: 
                return IntTestFunction(name, parent=self) 

def gettestobjspace(name=None, **kwds):
    space = getobjspace(name, **kwds)
    return space

def skip_on_missing_buildoption(**ropts): 
    __tracebackhide__ = True
    import sys
    options = getattr(sys, 'pypy_translation_info', None)
    if options is None:
        py.test.skip("not running on translated pypy "
                     "(btw, i would need options: %s)" %
                     (ropts,))
    for opt in ropts: 
        if not options.has_key(opt) or options[opt] != ropts[opt]: 
            break
    else:
        return
    py.test.skip("need translated pypy with: %s, got %s" 
                 %(ropts,options))

def getwithoutbinding(x, name):
    try:
        return x.__dict__[name]
    except (AttributeError, KeyError):
        for cls in getmro(x.__class__):
            if name in cls.__dict__:
                return cls.__dict__[name]
        # uh? not found anywhere, fall back (which might raise AttributeError)
        return getattr(x, name)

class LazyObjSpaceGetter(object):
    def __get__(self, obj, cls=None):
        space = gettestobjspace()
        if cls:
            cls.space = space
        return space


class PyPyTestFunction(py.test.Function):
    # All PyPy test items catch and display OperationErrors specially.
    #
    def execute_appex(self, space, target, *args):
        try:
            target(*args)
        except OperationError, e:
            if e.match(space, space.w_KeyboardInterrupt):
                tb = sys.exc_info()[2]
                raise OpErrKeyboardInterrupt, OpErrKeyboardInterrupt(), tb
            appexcinfo = appsupport.AppExceptionInfo(space, e) 
            if appexcinfo.traceback: 
                raise self.Failed(excinfo=appsupport.AppExceptionInfo(space, e))
            raise 

_pygame_imported = False

class IntTestFunction(PyPyTestFunction):
    def haskeyword(self, keyword):
        if keyword == 'interplevel':
            return True 
        return super(IntTestFunction, self).haskeyword(keyword)

    def execute(self, target, *args):
        co = target.func_code
        try:
            if 'space' in co.co_varnames[:co.co_argcount]: 
                space = gettestobjspace() 
                target(space, *args)  
            else:
                target(*args)
        except OperationError, e:
            check_keyboard_interrupt(e)
            raise
        except Exception, e:
            cls = e.__class__
            while cls is not Exception:
                if cls.__name__ == 'DistutilsPlatformError':
                    from distutils.errors import DistutilsPlatformError
                    if isinstance(e, DistutilsPlatformError):
                        py.test.skip('%s: %s' % (e.__class__.__name__, e))
                cls = cls.__bases__[0]
            raise
        if 'pygame' in sys.modules:
            global _pygame_imported
            if not _pygame_imported:
                _pygame_imported = True
                assert option.view, ("should not invoke Pygame "
                                     "if conftest.option.view is False")

class AppTestFunction(PyPyTestFunction): 
    def haskeyword(self, keyword):
        return keyword == 'applevel' or super(AppTestFunction, self).haskeyword(keyword)

    def execute(self, target, *args):
        assert not args 
        if option.runappdirect:
            return target(*args)
        space = gettestobjspace() 
        func = app2interp_temp(target)
        print "executing", func
        self.execute_appex(space, func, space)

class AppTestMethod(AppTestFunction): 

    def setup(self): 
        super(AppTestMethod, self).setup() 
        instance = self.parent.obj 
        w_instance = self.parent.w_instance 
        space = instance.space  
        for name in dir(instance): 
            if name.startswith('w_'): 
                if option.runappdirect:
                    # if the value is a function living on the class,
                    # don't turn it into a bound method here
                    obj = getwithoutbinding(instance, name)
                    setattr(w_instance, name[2:], obj)
                else:
                    space.setattr(w_instance, space.wrap(name[2:]), 
                                  getattr(instance, name)) 

    def execute(self, target, *args): 
        assert not args 
        if option.runappdirect:
            return target(*args)
        space = target.im_self.space 
        func = app2interp_temp(target.im_func) 
        w_instance = self.parent.w_instance 
        self.execute_appex(space, func, space, w_instance) 

class PyPyClassCollector(py.test.collect.Class):
    def setup(self): 
        cls = self.obj 
        cls.space = LazyObjSpaceGetter()
        super(PyPyClassCollector, self).setup() 
    
class IntClassCollector(PyPyClassCollector): 
    Function = IntTestFunction 

    def haskeyword(self, keyword):
        return keyword == 'interplevel' or \
               super(IntClassCollector, self).haskeyword(keyword)

class AppClassInstance(py.test.collect.Instance): 
    Function = AppTestMethod 

    def setup(self): 
        super(AppClassInstance, self).setup()         
        instance = self.obj 
        space = instance.space 
        w_class = self.parent.w_class 
        if option.runappdirect:
            self.w_instance = instance
        else:
            self.w_instance = space.call_function(w_class)

class AppClassCollector(PyPyClassCollector): 
    Instance = AppClassInstance 

    def haskeyword(self, keyword):
        return keyword == 'applevel' or \
               super(AppClassCollector, self).haskeyword(keyword)

    def setup(self): 
        super(AppClassCollector, self).setup()         
        cls = self.obj 
        space = cls.space 
        clsname = cls.__name__ 
        if option.runappdirect:
            w_class = cls
        else:
            w_class = space.call_function(space.w_type,
                                          space.wrap(clsname),
                                          space.newtuple([]),
                                          space.newdict())
        self.w_class = w_class 
