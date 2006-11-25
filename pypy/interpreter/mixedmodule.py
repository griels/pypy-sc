from pypy.interpreter.module import Module
from pypy.interpreter.function import Function, BuiltinFunction
from pypy.interpreter import gateway 
from pypy.interpreter.error import OperationError 
from pypy.interpreter.baseobjspace import W_Root
import os, sys

import inspect

class MixedModule(Module):

    NOT_RPYTHON_ATTRIBUTES = ['loaders']

    applevel_name = None
    expose__file__attribute = True
    
    def __init__(self, space, w_name): 
        """ NOT_RPYTHON """ 
        Module.__init__(self, space, w_name) 
        self.lazy = True 
        self.__class__.buildloaders()

    def get(self, name):
        space = self.space
        w_value = self.getdictvalue_w(space, name) 
        if w_value is None: 
            raise OperationError(space.w_AttributeError, space.wrap(name))
        return w_value 

    def call(self, name, *args_w): 
        w_builtin = self.get(name) 
        return self.space.call_function(w_builtin, *args_w)

    def getdictvalue(self, space, w_name):
        w_value = space.finditem(self.w_dict, w_name)
        if self.lazy and w_value is None:
            name = space.str_w(w_name)
            w_name = space.new_interned_w_str(w_name)
            try: 
                loader = self.loaders[name]
            except KeyError: 
                return None 
            else: 
                #print "trying to load", name
                w_value = loader(space) 
                #print "loaded", w_value 
                # obscure
                func = space.interpclass_w(w_value)
                if type(func) is Function:
                    try:
                        bltin = func._builtinversion_
                    except AttributeError:
                        bltin = BuiltinFunction(func)
                        bltin.w_module = self.w_name
                        func._builtinversion_ = bltin
                        bltin.name = name
                    w_value = space.wrap(bltin)
                space.setitem(self.w_dict, w_name, w_value) 
        return w_value

    def getdict(self): 
        if self.lazy: 
            space = self.space
            for name in self.loaders: 
                w_value = self.get(name)  
                space.setitem(self.w_dict, space.new_interned_str(name), w_value) 
            self.lazy = False 
        return self.w_dict 

    def _freeze_(self):
        self.getdict()
        # hint for the annotator: Modules can hold state, so they are
        # not constant
        return False

    def buildloaders(cls): 
        """ NOT_RPYTHON """ 
        if not hasattr(cls, 'loaders'): 
            # build a constant dictionary out of
            # applevel/interplevel definitions 
            cls.loaders = loaders = {}
            pkgroot = cls.__module__
            for name, spec in cls.interpleveldefs.items(): 
                loaders[name] = getinterpevalloader(pkgroot, spec) 
            for name, spec in cls.appleveldefs.items(): 
                loaders[name] = getappfileloader(pkgroot, spec) 
            assert '__file__' not in loaders 
            if cls.expose__file__attribute:
                loaders['__file__'] = cls.get__file__
            if '__doc__' not in loaders:
                loaders['__doc__'] = cls.get__doc__

    buildloaders = classmethod(buildloaders)

    def extra_interpdef(self, name, spec):
        cls = self.__class__
        pkgroot = cls.__module__
        loader = getinterpevalloader(pkgroot, spec)
        space = self.space
        w_obj = loader(space)
        space.setattr(space.wrap(self), space.wrap(name), w_obj)

    def get__file__(cls, space): 
        """ NOT_RPYTHON. 
        return the __file__ attribute of a MixedModule 
        which is the root-directory for the various 
        applevel and interplevel snippets that make
        up the module. 
        """ 
        try: 
            fname = cls._fname 
        except AttributeError: 
            pkgroot = cls.__module__
            mod = __import__(pkgroot, None, None, ['__doc__'])
            fname = mod.__file__ 
            assert os.path.basename(fname).startswith('__init__.py')
            # make it clear that it's not really the interp-level module
            # at this path that we are seeing, but an app-level version of it
            fname = os.path.join(os.path.dirname(fname), '*.py')
            cls._fname = fname 
        return space.wrap(fname) 

    get__file__ = classmethod(get__file__) 

    def get__doc__(cls, space):
        return space.wrap(cls.__doc__)
    get__doc__ = classmethod(get__doc__)


def getinterpevalloader(pkgroot, spec):
    """ NOT_RPYTHON """     
    def ifileloader(space): 
        d = {'space' : space}
        # EVIL HACK (but it works, and this is not RPython :-) 
        while 1: 
            try: 
                value = eval(spec, d) 
            except NameError, ex: 
                name = ex.args[0].split("'")[1] # super-Evil 
                if name in d:
                    raise   # propagate the NameError
                try: 
                    d[name] = __import__(pkgroot+'.'+name, None, None, [name])
                except ImportError:
                    etype, evalue, etb = sys.exc_info()
                    try:
                        d[name] = __import__(name, None, None, [name])
                    except ImportError:
                        # didn't help, re-raise the original exception for
                        # clarity
                        raise etype, evalue, etb
            else: 
                #print spec, "->", value
                if hasattr(value, 'func_code'):  # semi-evil 
                    return space.wrap(gateway.interp2app(value))

                try:
                    is_type = issubclass(value, W_Root)  # pseudo-evil
                except TypeError:
                    is_type = False
                if is_type:
                    return space.gettypefor(value)

                W_Object = getattr(space, 'W_Object', ()) # for cpyobjspace
                assert isinstance(value, (W_Root, W_Object)), (
                    "interpleveldef %s.%s must return a wrapped object "
                    "(got %r instead)" % (pkgroot, spec, value))
                return value 
    return ifileloader 
        
applevelcache = {}
def getappfileloader(pkgroot, spec):
    """ NOT_RPYTHON """ 
    # hum, it's a bit more involved, because we usually 
    # want the import at applevel
    modname, attrname = spec.split('.')
    impbase = pkgroot + '.' + modname 
    mod = __import__(impbase, None, None, ['attrname'])
    try:
        app = applevelcache[mod]
    except KeyError:
        source = inspect.getsource(mod) 
        fn = mod.__file__
        if fn.endswith('.pyc') or fn.endswith('.pyo'):
            fn = fn[:-1]
        app = gateway.applevel(source, filename=fn)
        applevelcache[mod] = app

    def afileloader(space): 
        return app.wget(space, attrname)
    return afileloader 

# ____________________________________________________________
# Helper to test mixed modules on top of CPython

def testmodule(name):
    """Helper to test mixed modules on top of CPython,
    running with the CPy Object Space.  The module should behave
    more or less as if it had been compiled, either with the
    pypy/bin/compilemodule.py tool, or within pypy-c.

    Try:   testmodule('_demo')
    """
    import sys, new
    from pypy.objspace.cpy.objspace import CPyObjSpace
    space = CPyObjSpace()
    fullname = "pypy.module.%s" % name 
    Module = __import__(fullname, 
                        None, None, ["Module"]).Module
    if Module.applevel_name is not None:
        appname = Module.applevel_name
    else:
        appname = name
    mod = Module(space, space.wrap(appname))
    moddict = space.unwrap(mod.getdict())
    res = new.module(appname)
    res.__dict__.update(moddict)
    sys.modules[appname] = res
    return res

def compilemodule(name, interactive=False):
    "Compile a PyPy module for CPython."
    from pypy.rpython.rctypes.tool.compilemodule import compilemodule
    return compilemodule(name, interactive=interactive)
