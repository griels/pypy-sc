"""

Gateway between app-level and interpreter-level:
* BuiltinCode (call interp-level code from app-level)
* app2interp  (embed an app-level function into an interp-level callable)
* interp2app  (publish an interp-level object to be visible from app-level)
* exportall   (mass-call interp2app on a whole dict of objects)
* importall   (mass-call app2interp on a whole dict of objects)

"""

import types, sys

from pypy.tool import hack
from pypy.interpreter.error import OperationError 
from pypy.interpreter import eval
from pypy.interpreter.function import Function, Method
from pypy.interpreter.baseobjspace import W_Root,ObjSpace, BaseWrappable, Wrappable
from pypy.interpreter.argument import Arguments
from pypy.tool.cache import Cache 
# internal non-translatable parts: 
from pypy.tool.getpy import py  # XXX from interpreter/ we get py.py 

NoneNotWrapped = object()

class Signature:
    def __init__(self, func=None, argnames=None, varargname=None,
                 kwargname=None, name = None):
        self.func = func
        if func is not None:
            self.name = func.__name__
        else:
            self.name = name
        if argnames is None:
            argnames = []
        self.argnames = argnames
        self.varargname = varargname
        self.kwargname = kwargname

    def next_arg(self):
        return self._argiter.next()

    def append(self, argname):
        self.argnames.append(argname)

    def signature(self):
        return self.argnames, self.varargname, self.kwargname

    def apply_unwrap_spec(self, unwrap_spec, recipe, new_sig):
        self._argiter = iter(self.argnames)
        for el in unwrap_spec:
            recipe(el, self, new_sig)
        return new_sig


class UnwrapSpecRecipe:

    bases_order = [BaseWrappable, W_Root, ObjSpace, Arguments, object]

    def dispatch(self, meth_family, el, orig_sig, new_sig):
        if isinstance(el,str):
            getattr(self, "%s_%s" % (meth_family, el))(el, orig_sig, new_sig)
        else:
            for typ in self.bases_order:
                if issubclass(el, typ):
                    getattr(self, "%s__%s" % (meth_family, typ.__name__))(el, orig_sig, new_sig)
                    break
            else:
                assert False, "no match for unwrap_spec element: %s" % el

    def check(self, el, orig_sig, new_sig):
        self.dispatch("check", el, orig_sig, new_sig)

    def emit(self, el, orig_sig, new_sig):
        self.dispatch("emit", el, orig_sig, new_sig)


    # checks for checking interp2app func argument names wrt unwrap_spec
    # and synthetizing an app-level signature

    def check__BaseWrappable(self, el, orig_sig, app_sig):
        name = el.__name__
        argname = orig_sig.next_arg()
        assert not argname.startswith('w_'), (
            "unwrapped %s argument %s of built-in function %r should "
            "not start with 'w_'" % (name, argname, orig_sig.func))
        app_sig.append(argname)
        
    def check__ObjSpace(self, el, orig_sig, app_sig):
        orig_sig.next_arg()

    def check__W_Root(self, el, orig_sig, app_sig):
        assert el is W_Root, "oops"
        argname = orig_sig.next_arg()
        assert argname.startswith('w_'), (
            "argument %s of built-in function %r should "
            "start with 'w_'" % (argname, orig_sig.func))
        app_sig.append(argname[2:])

    def check__Arguments(self, el, orig_sig, app_sig):
        argname = orig_sig.next_arg()
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = 'args'
        app_sig.kwargname = 'keywords'

    def check_starargs(self, el, orig_sig, app_sig):
        varargname = orig_sig.varargname
        assert varargname.endswith('_w'), (
            "argument *%s of built-in function %r should end in '_w'" %
            (varargname, orig_sig.func))
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = varargname[:-2]

    def check_args_w(self, el, orig_sig, app_sig):
        argname = orig_sig.next_arg()
        assert argname.endswith('_w'), (
            "rest arguments arg %s of built-in function %r should end in '_w'" %
            (argname, orig_sig.func))
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = argname[:-2]    

    def check_w_args(self, el, orig_sig, app_sig):
        argname = orig_sig.next_arg()
        assert argname.startswith('w_'), (
            "rest arguments arg %s of built-in function %r should start 'w_'" %
            (argname, orig_sig.func))
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = argname[2:]

    def check__object(self, el, orig_sig, app_sig):
        if el not in (int, str, float):
            assert False, "unsupported basic type in uwnrap_spec"
        name = el.__name__
        argname = orig_sig.next_arg()
        assert not argname.startswith('w_'), (
            "unwrapped %s argument %s of built-in function %r should "
            "not start with 'w_'" % (name, argname, orig_sig.func))
        app_sig.append(argname)        

    # collect code to emit for interp2app builtin frames based on unwrap_spec

    def emit__BaseWrappable(self, el, orig_sig, emit_sig):
        name = el.__name__
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "obj = self.space.interpclass_w(scope_w[%d])" % cur)
        emit_sig.setfastscope.append(
            "if obj is None or not isinstance(obj, %s):" % name)
        emit_sig.setfastscope.append(
            "    raise OperationError(self.space.w_TypeError,self.space.wrap('expected %%s' %% %s.typedef.name ))" % name) # xxx
        emit_sig.miniglobals[name] = el
        emit_sig.miniglobals['OperationError'] = OperationError
        emit_sig.setfastscope.append(
            "self.%s_arg%d = obj" % (name,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.%s_arg%d" % (name,cur))

    def emit__ObjSpace(self, el, orig_sig, emit_sig):
        emit_sig.run_args.append('self.space')

    def emit__W_Root(self, el, orig_sig, emit_sig):
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "self.w_arg%d = scope_w[%d]" % (cur,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.w_arg%d" % cur)

    def emit__Arguments(self, el, orig_sig, emit_sig):
        cur = emit_sig.through_scope_w
        emit_sig.through_scope_w += 2
        emit_sig.miniglobals['Arguments'] = Arguments
        emit_sig.setfastscope.append(
            "self.arguments_arg = "
            "Arguments.frompacked(self.space,scope_w[%d],scope_w[%d])"
                % (cur, cur+1))
        emit_sig.run_args.append("self.arguments_arg")

    def emit_starargs(self, el, orig_sig, emit_sig):
        emit_sig.setfastscope.append(
            "self.starargs_arg_w = self.space.unpacktuple(scope_w[%d])" %
                (emit_sig.through_scope_w))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("*self.starargs_arg_w")

    def emit_args_w(self, el, orig_sig, emit_sig):
        emit_sig.setfastscope.append(
            "self.args_w = self.space.unpacktuple(scope_w[%d])" %
                 (emit_sig.through_scope_w))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.args_w")

    def emit_w_args(self, el, orig_sig, emit_sig):
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "self.w_args = scope_w[%d]" % cur)
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.w_args")

    def emit__object(self, el, orig_sig, emit_sig):
        if el not in (int, str, float):
            assert False, "unsupported basic type in uwnrap_spec"
        name = el.__name__
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "self.%s_arg%d = self.space.%s_w(scope_w[%d])" %
                (name,cur,name,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.%s_arg%d" % (name,cur))

class BuiltinFrame(eval.Frame):
    "Frame emulation for BuiltinCode."
    # Subclasses of this are defined with the function to delegate to attached through miniglobals.
    # Initialization of locals is already done by the time run() is called,
    # via the interface defined in eval.Frame.

    def setfastscope(self, scope_w):
        """Subclasses with behavior specific for an unwrap spec are generated"""
        raise TypeError, "abstract"

    def getfastscope(self):
        raise OperationError(self.space.w_TypeError,
            self.space.wrap("cannot get fastscope of a BuiltinFrame"))

    def run(self):
        """Subclasses with behavior specific for an unwrap spec are generated"""
        raise TypeError, "abstract"

class BuiltinCodeSignature(Signature):

    def __init__(self,*args,**kwds):
        Signature.__init__(self,*args,**kwds)
        self.setfastscope = []
        self.run_args = []
        self.through_scope_w = 0
        self.miniglobals = {}

    def make_frame_class(self, func):
        setfastscope = self.setfastscope
        if not setfastscope:
            setfastscope = ["pass"]
        setfastscope = ["def setfastscope(self, scope_w):",
                        #"print 'ENTER',self.code.func.__name__",
                        #"print scope_w"
                        ] + setfastscope
        setfastscope = '\n  '.join(setfastscope)
        # Python 2.2 SyntaxError without newline: Bug #501622
        setfastscope += '\n'
        d = {}
        exec compile(setfastscope, '', 'exec') in self.miniglobals, d

        self.miniglobals['func'] = func
        self.miniglobals['OperationError'] = OperationError
        source = """if 1: 
            def run(self):
                try:
                    w_result = func(%s)
                except KeyboardInterrupt: 
                    raise OperationError(self.space.w_KeyboardInterrupt, self.space.w_None) 
                except MemoryError: 
                    raise OperationError(self.space.w_MemoryError, self.space.w_None) 
                except RuntimeError, e: 
                    raise OperationError(self.space.w_RuntimeError, 
                                         self.space.wrap("internal error" + str(e))) 
                if w_result is None:
                    w_result = self.space.w_None
                return w_result
            \n""" % ','.join(self.run_args) 
        exec compile(source, '', 'exec') in self.miniglobals, d
        return type("BuiltinFrame_for_%s" % self.name,
                    (BuiltinFrame,),d)
        
def make_builtin_frame_class(func, orig_sig, unwrap_spec):
    "NOT_RPYTHON"
    name = (getattr(func, '__module__', None) or '')+'_'+func.__name__
    emit_sig = orig_sig.apply_unwrap_spec(unwrap_spec, UnwrapSpecRecipe().emit,
                                              BuiltinCodeSignature(name=name))
    cls = emit_sig.make_frame_class(func)
    return cls



class BuiltinCode(eval.Code):
    "The code object implementing a built-in (interpreter-level) hook."

    # When a BuiltinCode is stored in a Function object,
    # you get the functionality of CPython's built-in function type.

    def __init__(self, func, ismethod=None, spacearg=None, unwrap_spec = None, self_type = None):
        "NOT_RPYTHON"
        # 'implfunc' is the interpreter-level function.
        # Note that this uses a lot of (construction-time) introspection.
        eval.Code.__init__(self, func.__name__)
        self.docstring = func.__doc__

        # unwrap_spec can be passed to interp2app or
        # attached as an attribute to the function.
        # It is a list of types or singleton objects:
        #  baseobjspace.ObjSpace is used to specify the space argument
        #  baseobjspace.W_Root is for wrapped arguments to keep wrapped
        #  baseobjspace.BaseWrappable subclasses imply interpclass_w and a typecheck
        #  argument.Arguments is for a final rest arguments Arguments object
        # 'args_w' for unpacktuple applied to rest arguments
        # 'w_args' for rest arguments passed as wrapped tuple
        # str,int,float: unwrap argument as such type
        
        # First extract the signature from the (CPython-level) code object
        from pypy.interpreter import pycode
        argnames, varargname, kwargname = pycode.cpython_code_signature(func.func_code)

        assert not ismethod, ("ismethod is not expected anymore")
        assert not spacearg, ("spacearg is not expected anymore")

        if unwrap_spec is None:
            unwrap_spec = getattr(func,'unwrap_spec',None)

        if unwrap_spec is None and argnames == ['space', '__args__']: #xxx for geninterp
            #print sys._getframe(2).f_globals['__name__']
            unwrap_spec = [ObjSpace, Arguments]

        if unwrap_spec is None:
            unwrap_spec = [ObjSpace]+ [W_Root] * (len(argnames)-1)

            if self_type:
                unwrap_spec = ['self'] + unwrap_spec[1:]
            
        if self_type:
            assert unwrap_spec[0] == 'self',"self_type without 'self' spec element"
            unwrap_spec = list(unwrap_spec)
            unwrap_spec[0] = self_type

        orig_sig = Signature(func, argnames, varargname, kwargname)

        app_sig = orig_sig.apply_unwrap_spec(unwrap_spec, UnwrapSpecRecipe().check,
                                             Signature(func))

        self.sig = argnames, varargname, kwargname = app_sig.signature()

        self.minargs = len(argnames)
        if varargname:
            self.maxargs = sys.maxint
        else:
            self.maxargs = self.minargs

        self.framecls = make_builtin_frame_class(func, orig_sig, unwrap_spec)

    def create_frame(self, space, w_globals, closure=None):
        return self.framecls(space, self, w_globals)

    def signature(self):
        return self.sig

    def getdocstring(self):
        return self.docstring


class interp2app(Wrappable):
    """Build a gateway that calls 'f' at interp-level."""

    # NOTICE interp2app defaults are stored and passed as
    # wrapped values, this to avoid having scope_w be of mixed
    # wrapped and unwrapped types;
    # an exception is made for the NoneNotWrapped special value
    # which is passed around as default as an unwrapped None,
    # unwrapped None and wrapped types are compatible
    #
    # Takes optionally an unwrap_spec, see BuiltinCode

    NOT_RPYTHON_ATTRIBUTES = ['_staticdefs']
    
    def __init__(self, f, app_name=None,
                 ismethod=None, spacearg=None, unwrap_spec = None):
        "NOT_RPYTHON"
        Wrappable.__init__(self)
        # f must be a function whose name does NOT start with 'app_'
        self_type = None
        if hasattr(f, 'im_func'):
            self_type = f.im_class
            f = f.im_func
        if not isinstance(f, types.FunctionType):
            raise TypeError, "function expected, got %r instead" % f
        if app_name is None:
            if f.func_name.startswith('app_'):
                raise ValueError, ("function name %r suspiciously starts "
                                   "with 'app_'" % f.func_name)
            app_name = f.func_name
        self._code = BuiltinCode(f, ismethod=ismethod,
                                  spacearg=spacearg,
                                  unwrap_spec=unwrap_spec,
                                  self_type = self_type)
        self.__name__ = f.func_name
        self.name = app_name
        self._staticdefs = list(f.func_defaults or ())

    def _getdefaults(self, space):
        "NOT_RPYTHON"
        defs_w = []
        for val in self._staticdefs:
            if val is NoneNotWrapped:
                defs_w.append(None)
            else:
                defs_w.append(space.wrap(val))
        return defs_w

    # lazy binding to space

    def __spacebind__(self, space):
        # we first make a real Function object out of it
        # and the result is a wrapped version of this Function.
        return self.get_function(space)

    def get_function(self, space):
        return space.loadfromcache(self, 
                                   interp2app.build_function, 
                                   self.getcache(space))

    def getcache(self, space):
        return space._gatewaycache 

    def get_method(self, obj):
        # to bind this as a method out of an instance, we build a
        # Function and get it.
        # the object space is implicitely fetched out of the instance
        assert self._code.ismethod, (
            'global built-in function %r used as method' %
            self._code.func)

        space = obj.space
        fn = self.get_function(space)
        w_obj = space.wrap(obj)
        return Method(space, space.wrap(fn),
                      w_obj, space.type(w_obj))


    def build_function(self, space):
        "NOT_RPYTHON"
        cache = self.getcache(space) 
        try: 
            return cache.content[self] 
        except KeyError: 
            defs = self._getdefaults(space)  # needs to be implemented by subclass
            code = self._code
            fn = Function(space, code, None, defs, forcename = self.name)
            cache.content[self] = fn 
            return fn
        
def exportall(d, temporary=False):
    """NOT_RPYTHON: Publish every function from a dict."""
    if temporary:
        i2a = interp2app_temp
    else:
        i2a = interp2app
    for name, obj in d.items():
        if isinstance(obj, types.FunctionType):
            # names starting in 'app_' are supposedly already app-level
            if name.startswith('app_'):
                continue
            # ignore tricky functions with another interp-level meaning
            if name in ('__init__', '__new__'):
                continue
            # ignore names in '_xyz'
            if name.startswith('_') and not name.endswith('_'):
                continue
            if 'app_'+name not in d:
                d['app_'+name] = i2a(obj, name)

def export_values(space, dic, w_namespace):
    "NOT_RPYTHON"
    for name, w_value in dic.items():
        if name.startswith('w_'):
            if name == 'w_dict':
                w_name = space.wrap('__dict__')
            elif name == 'w_name':
                w_name = space.wrap('__name__')
            else:
                w_name = space.wrap(name[2:])
            space.setitem(w_namespace, w_name, w_value)

def importall(d, temporary=False):
    """NOT_RPYTHON: Import all app_-level functions as Gateways into a dict."""
    if temporary:
        a2i = app2interp_temp
    else:
        a2i = app2interp
    for name, obj in d.items():
        if name.startswith('app_') and name[4:] not in d:
            if isinstance(obj, types.FunctionType):
                d[name[4:]] = a2i(obj)

# 
# the next gateways are to be used only for 
# temporary/initialization purposes 
     
class interp2app_temp(interp2app): 
    "NOT_RPYTHON"
    def getcache(self, space): 
        return self.__dict__.setdefault(space, Cache())


# and now for something completely different ... 
#

class applevel:
    """A container for app-level source code that should be executed
    as a module in the object space;  interphook() builds a static
    interp-level function that invokes the callable with the given
    name at app-level."""

    NOT_RPYTHON_ATTRIBUTES = ['code']

    def __init__(self, source):
        "NOT_RPYTHON"
        self.code = py.code.Source(source).compile()

    def getwdict(self, space):
        return space.loadfromcache(self, applevel._builddict,
                                   space._gatewaycache)

    def buildmodule(self, space, name='applevel'):
        from pypy.interpreter.module import Module
        return Module(space, space.wrap(name), self.getwdict(space))

    def _builddict(self, space):
        "NOT_RPYTHON"
        w_glob = space.newdict([])
        space.exec_(self.code, w_glob, w_glob)
        return w_glob
    
    def wget(self, space, name): 
        w_globals = self.getwdict(space) 
        return space.getitem(w_globals, space.wrap(name))

    def interphook(self, name):
        "NOT_RPYTHON"
        def appcaller(space, *args_w):
            args = Arguments(space, args_w)
            w_func = self.wget(space, name) 
            return space.call_args(w_func, args)
        def get_function(space):
            w_func = self.wget(space, name) 
            return space.unwrap(w_func)
        appcaller = hack.func_with_new_name(appcaller, name)
        appcaller.get_function = get_function
        return appcaller

## XXX experimental code using geninterplevel

class applevelinterp(applevel):
    """ same as applevel, but using translation to interp-level.
    Hopefully this will replace applevel at some point.
    """
    NOT_RPYTHON_ATTRIBUTES = ['initfunc']

    def __init__(self, source, modname = 'applevelinterp'):
        "NOT_RPYTHON"
        from pypy.translator.geninterplevel import translate_as_module
        self.initfunc = translate_as_module(source, modname)

    def getwdict(self, space):
        return space.loadfromcache(self, applevelinterp._builddict,
                                   space._gatewaycache)

    def _builddict(self, space):
        "NOT_RPYTHON"
        w_glob = self.initfunc(space)
        return w_glob

## XXX there is a problem with the naming convention of app_xxx not allowed
## for interp2app! What shall we do?

def appdef(source, applevel=applevel):
    """ NOT_RPYTHON: build an app-level helper function, like for example:
    myfunc = appdef('''myfunc(x, y):
                           return x+y
                    ''')
    """ 
    from pypy.interpreter.pycode import PyCode
    if not isinstance(source, str): 
        source = str(py.code.Source(source).strip())
        assert source.startswith("def "), "can only transform functions" 
        source = source[4:]
    p = source.find('(')
    assert p >= 0
    funcname = source[:p].strip()
    source = source[p:]
    return applevel("def %s%s\n" % (funcname, source)).interphook(funcname)

app2interp = appdef   # backward compatibility


# the following two will probably get merged into one
class applevel_temp(applevel):
    def getwdict(self, space):
        return self._builddict(space)   # no cache

class applevelinterp_temp(applevelinterp):
    def getwdict(self, space):
        return self._builddict(space)   # no cache

# app2interp_temp is used for testing mainly
def app2interp_temp(func, applevel_temp=applevel_temp):
    """ NOT_RPYTHON """
    return appdef(func, applevel_temp)
