"""

Gateway between app-level and interpreter-level:
* BuiltinCode (call interp-level code from app-level)
* app2interp  (embed an app-level function into an interp-level callable)
* interp2app  (publish an interp-level object to be visible from app-level)

"""

import types, sys, md5, os

NoneNotWrapped = object()

from pypy.tool.sourcetools import func_with_new_name
from pypy.interpreter.error import OperationError 
from pypy.interpreter import eval
from pypy.interpreter.function import Function, Method
from pypy.interpreter.baseobjspace import W_Root, ObjSpace, Wrappable
from pypy.interpreter.baseobjspace import Wrappable, SpaceCache
from pypy.interpreter.argument import Arguments
from pypy.tool.sourcetools import NiceCompile, compile2

# internal non-translatable parts: 
import py

class Signature:
    "NOT_RPYTHON"
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
    "NOT_RPYTHON"

    bases_order = [Wrappable, W_Root, ObjSpace, Arguments, object]

    def dispatch(self, el, *args):
        if isinstance(el, str):
            getattr(self, "visit_%s" % (el,))(el, *args)
        elif isinstance(el, tuple):
            self.visit_function(el, *args)
        else:
            for typ in self.bases_order:
                if issubclass(el, typ):
                    visit = getattr(self, "visit__%s" % (typ.__name__,))
                    visit(el, *args)
                    break
            else:
                raise Exception("%s: no match for unwrap_spec element %s" % (
                    self.__class__.__name__, el))


class UnwrapSpec_Check(UnwrapSpecRecipe):

    # checks for checking interp2app func argument names wrt unwrap_spec
    # and synthetizing an app-level signature

    def visit_function(self, (func, cls), orig_sig, app_sig):
        self.dispatch(cls, orig_sig, app_sig)
        
    def visit__Wrappable(self, el, orig_sig, app_sig):
        name = el.__name__
        argname = orig_sig.next_arg()
        assert not argname.startswith('w_'), (
            "unwrapped %s argument %s of built-in function %r should "
            "not start with 'w_'" % (name, argname, orig_sig.func))
        app_sig.append(argname)
        
    def visit__ObjSpace(self, el, orig_sig, app_sig):
        orig_sig.next_arg()

    def visit__W_Root(self, el, orig_sig, app_sig):
        assert el is W_Root, "oops"
        argname = orig_sig.next_arg()
        assert argname.startswith('w_'), (
            "argument %s of built-in function %r should "
            "start with 'w_'" % (argname, orig_sig.func))
        app_sig.append(argname[2:])

    def visit__Arguments(self, el, orig_sig, app_sig):
        argname = orig_sig.next_arg()
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = 'args'
        app_sig.kwargname = 'keywords'

    def visit_starargs(self, el, orig_sig, app_sig):
        varargname = orig_sig.varargname
        assert varargname.endswith('_w'), (
            "argument *%s of built-in function %r should end in '_w'" %
            (varargname, orig_sig.func))
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = varargname[:-2]

    def visit_args_w(self, el, orig_sig, app_sig):
        argname = orig_sig.next_arg()
        assert argname.endswith('_w'), (
            "rest arguments arg %s of built-in function %r should end in '_w'" %
            (argname, orig_sig.func))
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = argname[:-2]    

    def visit_w_args(self, el, orig_sig, app_sig):
        argname = orig_sig.next_arg()
        assert argname.startswith('w_'), (
            "rest arguments arg %s of built-in function %r should start 'w_'" %
            (argname, orig_sig.func))
        assert app_sig.varargname is None,(
            "built-in function %r has conflicting rest args specs" % orig_sig.func)
        app_sig.varargname = argname[2:]

    def visit__object(self, el, orig_sig, app_sig):
        if el not in (int, str, float):
            assert False, "unsupported basic type in unwrap_spec"
        name = el.__name__
        argname = orig_sig.next_arg()
        assert not argname.startswith('w_'), (
            "unwrapped %s argument %s of built-in function %r should "
            "not start with 'w_'" % (name, argname, orig_sig.func))
        app_sig.append(argname)        


class UnwrapSpec_Emit(UnwrapSpecRecipe):

    # collect code to emit for interp2app builtin frames based on unwrap_spec

    def visit_function(self, (func, cls), orig_sig, emit_sig):
        name = func.__name__
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "obj = %s(scope_w[%d])" % (name, cur))
        emit_sig.miniglobals[name] = func
        emit_sig.setfastscope.append(
            "self.%s_arg%d = obj" % (name,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.%s_arg%d" % (name,cur))

    def visit__Wrappable(self, el, orig_sig, emit_sig):
        name = el.__name__
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "obj = self.space.interp_w(%s, scope_w[%d])" % (name, cur))
        emit_sig.miniglobals[name] = el
        emit_sig.setfastscope.append(
            "self.%s_arg%d = obj" % (name,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.%s_arg%d" % (name,cur))

    def visit__ObjSpace(self, el, orig_sig, emit_sig):
        emit_sig.run_args.append('self.space')

    def visit__W_Root(self, el, orig_sig, emit_sig):
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "self.w_arg%d = scope_w[%d]" % (cur,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.w_arg%d" % cur)

    def visit__Arguments(self, el, orig_sig, emit_sig):
        cur = emit_sig.through_scope_w
        emit_sig.through_scope_w += 2
        emit_sig.miniglobals['Arguments'] = Arguments
        emit_sig.setfastscope.append(
            "self.arguments_arg = "
            "Arguments.frompacked(self.space,scope_w[%d],scope_w[%d])"
                % (cur, cur+1))
        emit_sig.run_args.append("self.arguments_arg")

    def visit_starargs(self, el, orig_sig, emit_sig):
        emit_sig.setfastscope.append(
            "self.starargs_arg_w = self.space.unpacktuple(scope_w[%d])" %
                (emit_sig.through_scope_w))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("*self.starargs_arg_w")

    def visit_args_w(self, el, orig_sig, emit_sig):
        emit_sig.setfastscope.append(
            "self.args_w = self.space.unpacktuple(scope_w[%d])" %
                 (emit_sig.through_scope_w))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.args_w")

    def visit_w_args(self, el, orig_sig, emit_sig):
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "self.w_args = scope_w[%d]" % cur)
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.w_args")

    def visit__object(self, el, orig_sig, emit_sig):
        if el not in (int, str, float):
            assert False, "unsupported basic type in uwnrap_spec"
        name = el.__name__
        cur = emit_sig.through_scope_w
        emit_sig.setfastscope.append(
            "self.%s_arg%d = self.space.%s_w(scope_w[%d])" %
                (name,cur,name,cur))
        emit_sig.through_scope_w += 1
        emit_sig.run_args.append("self.%s_arg%d" % (name,cur))


class UnwrapSpec_FastFunc_Unwrap(UnwrapSpecRecipe):

    def visit_function(self, (func, cls), info):
        raise FastFuncNotSupported

    def visit__Wrappable(self, el, info):
        name = el.__name__
        cur = info.narg
        info.unwrap.append("space.interp_w(%s, w%d)" % (name, cur))
        info.miniglobals[name] = el
        info.narg += 1

    def visit__ObjSpace(self, el, info):
        if info.index != 0:
            raise FastFuncNotSupported
        info.unwrap.append("space")
        
    def visit__W_Root(self, el, info):
        cur = info.narg
        info.unwrap.append("w%d" % cur)
        info.narg += 1

    def visit__Arguments(self, el, info):
        raise FastFuncNotSupported

    def visit_starargs(self, el, info):
        raise FastFuncNotSupported

    def visit_args_w(self, el, info):
        raise FastFuncNotSupported

    def visit_w_args(self, el, info):
        raise FastFuncNotSupported

    def visit__object(self, el, info):
        if el not in (int, str, float):
            assert False, "unsupported basic type in uwnrap_spec"
        name = el.__name__
        cur = info.narg
        info.unwrap.append("space.%s_w(w%d)" % (name,cur))
        info.narg +=1 


class BuiltinFrame(eval.Frame):
    "Frame emulation for BuiltinCode."
    # Subclasses of this are defined with the function to delegate to attached through miniglobals.
    # Initialization of locals is already done by the time run() is called,
    # via the interface defined in eval.Frame.

    def __init__(self, space, code, w_globals=None, numlocals=-1):
        self.bltn_code = code
        eval.Frame.__init__(self, space, w_globals, numlocals)

    def getcode(self):
        return self.bltn_code

    def setfastscope(self, scope_w):
        """Subclasses with behavior specific for an unwrap spec are generated"""
        raise TypeError, "abstract"

    def getfastscope(self):
        raise OperationError(self.space.w_TypeError,
            self.space.wrap("cannot get fastscope of a BuiltinFrame"))

    def run(self):
        try:
            w_result = self._run()
        except KeyboardInterrupt: 
            raise OperationError(self.space.w_KeyboardInterrupt, self.space.w_None) 
        except MemoryError: 
            raise OperationError(self.space.w_MemoryError, self.space.w_None) 
        except RuntimeError, e: 
            raise OperationError(self.space.w_RuntimeError, 
                                 self.space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = self.space.w_None
        return w_result

    def _run(self):
        """Subclasses with behavior specific for an unwrap spec are generated"""
        raise TypeError, "abstract"

class BuiltinFrameFactory(object):
    """Subclasses can create builtin frames for a associated  builtin"""
    
    def create(self, space, code, w_globals):
        raise TypeError, "abstract"

class BuiltinCodeSignature(Signature):
    "NOT_RPYTHON"

    def __init__(self,*args,**kwds):
        self.unwrap_spec = kwds.get('unwrap_spec')
        del kwds['unwrap_spec']
        Signature.__init__(self,*args,**kwds)
        self.setfastscope = []
        self.run_args = []
        self.through_scope_w = 0
        self.miniglobals = {}

    def _make_unwrap_frame_factory_class(self, cache={}):
        try:
            key = tuple(self.unwrap_spec)
            frame_factory_cls, run_args = cache[key]
            assert run_args == self.run_args,"unexpected: same spec, different run_args"
            return frame_factory_cls
        except KeyError:
            parts = []          
            for el in self.unwrap_spec:
                if isinstance(el, tuple):
                    parts.append(''.join([getattr(subel, '__name__', subel) for subel in el]))
                else:
                    parts.append(getattr(el, '__name__', el))
            label = '_'.join(parts)
            #print label
            setfastscope = self.setfastscope
            if not setfastscope:
                setfastscope = ["pass"]
            setfastscope = ["def setfastscope_UWS_%s(self, scope_w):" % label,
                            #"print 'ENTER',self.code.func.__name__",
                            #"print scope_w"
                            ] + setfastscope
            setfastscope = '\n  '.join(setfastscope)
            # Python 2.2 SyntaxError without newline: Bug #501622
            setfastscope += '\n'
            d = {}
            exec compile2(setfastscope) in self.miniglobals, d
            d['setfastscope'] = d['setfastscope_UWS_%s' % label]
            del d['setfastscope_UWS_%s' % label]

            self.miniglobals['OperationError'] = OperationError
            self.miniglobals['os'] = os
            source = """if 1: 
                def _run_UWS_%s(self):
                    try:
                        return self.behavior(%s)
                    except MemoryError:
                        os.write(2, 'Fail in _run() of ' + self.b_name + '\\n')
                        raise
                \n""" % (label, ','.join(self.run_args))
            exec compile2(source) in self.miniglobals, d
            d['_run'] = d['_run_UWS_%s' % label]
            del d['_run_UWS_%s' % label]

            frame_cls = type("BuiltinFrame_UwS_%s" % label, (BuiltinFrame,), d)

            class MyBuiltinFrameFactory(BuiltinFrameFactory):
                # export 'unwrap_spec' for inspection from outside gateway.py
                unwrap_spec = self.unwrap_spec

                def create(self, space, code, w_globals):
                    newframe = frame_cls(space, code, w_globals)
                    newframe.behavior = self.behavior
                    newframe.b_name = self.b_name
                    return newframe

            MyBuiltinFrameFactory.__name__ = 'BuiltinFrameFactory_UwS_%s' % label

            cache[key] = MyBuiltinFrameFactory, self.run_args
            return MyBuiltinFrameFactory

    def make_frame_factory(self, func):
        frame_uw_factory_cls = self._make_unwrap_frame_factory_class()
        
        factory = frame_uw_factory_cls()
        factory.behavior = func
        factory.b_name = func.__name__

        return factory
        
def make_builtin_frame_factory(func, orig_sig, unwrap_spec):
    "NOT_RPYTHON"
    name = (getattr(func, '__module__', None) or '')+'_'+func.__name__
    emit_sig = orig_sig.apply_unwrap_spec(unwrap_spec, UnwrapSpec_Emit().dispatch,
                                              BuiltinCodeSignature(name=name, unwrap_spec=unwrap_spec))
    return emit_sig.make_frame_factory(func)

class FastFuncNotSupported(Exception):
    pass

class FastFuncInfo(object):
    def __init__(self):
        self.index = 0
        self.narg = 0
        self.unwrap = []
        self.miniglobals = {}

def make_fastfunc(func, unwrap_spec):
    info = FastFuncInfo()
    recipe = UnwrapSpec_FastFunc_Unwrap().dispatch
    for el in unwrap_spec:
        recipe(el, info)
        info.index += 1
        if info.narg > 4:
            raise FastFuncNotSupported
    args = ['space'] + ['w%d' % n for n in range(info.narg)]
    if args == info.unwrap:
        fastfunc = func
    else:
        # try to avoid excessive bloat
        if func.__module__ == 'pypy.interpreter.astcompiler.ast':
            raise FastFuncNotSupported
        if (not func.__module__.startswith('pypy.module.__builtin__') and
            not func.__module__.startswith('pypy.module.sys') and
            not func.__module__.startswith('pypy.module.math')):
            if not func.__name__.startswith('descr'):
                raise FastFuncNotSupported
        d = {}
        info.miniglobals['func'] = func
        source = """if 1: 
            def fastfunc_%s_%d(%s):
                return func(%s)
            \n""" % (func.__name__, info.narg, ', '.join(args), ', '.join(info.unwrap))
        exec compile2(source) in info.miniglobals, d
        fastfunc = d['fastfunc_%s_%d' % (func.__name__, info.narg)]
    return info.narg, fastfunc
        
class BuiltinCode(eval.Code):
    "The code object implementing a built-in (interpreter-level) hook."
    hidden_applevel = True

    # When a BuiltinCode is stored in a Function object,
    # you get the functionality of CPython's built-in function type.

    def __init__(self, func, unwrap_spec = None, self_type = None):
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
        #  baseobjspace.Wrappable subclasses imply interp_w and a typecheck
        #  argument.Arguments is for a final rest arguments Arguments object
        # 'args_w' for unpacktuple applied to rest arguments
        # 'w_args' for rest arguments passed as wrapped tuple
        # str,int,float: unwrap argument as such type
        # (function, cls) use function to check/unwrap argument of type cls
        
        # First extract the signature from the (CPython-level) code object
        from pypy.interpreter import pycode
        argnames, varargname, kwargname = pycode.cpython_code_signature(func.func_code)

        if unwrap_spec is None:
            unwrap_spec = getattr(func,'unwrap_spec',None)

        if unwrap_spec is None:
            unwrap_spec = [ObjSpace]+ [W_Root] * (len(argnames)-1)

            if self_type:
                unwrap_spec = ['self'] + unwrap_spec[1:]
            
        if self_type:
            assert unwrap_spec[0] == 'self',"self_type without 'self' spec element"
            unwrap_spec = list(unwrap_spec)
            unwrap_spec[0] = self_type

        orig_sig = Signature(func, argnames, varargname, kwargname)

        app_sig = orig_sig.apply_unwrap_spec(unwrap_spec, UnwrapSpec_Check().dispatch,
                                             Signature(func))

        self.sig = argnames, varargname, kwargname = app_sig.signature()

        self.minargs = len(argnames)
        if varargname:
            self.maxargs = sys.maxint
        else:
            self.maxargs = self.minargs

        self.framefactory = make_builtin_frame_factory(func, orig_sig, unwrap_spec)

        # speed hack
        if 0 <= len(unwrap_spec) <= 5:
            try:
                arity, fastfunc = make_fastfunc(func, unwrap_spec)
            except FastFuncNotSupported:
                if unwrap_spec == [ObjSpace, Arguments]:
                    self.__class__ = BuiltinCodePassThroughArguments0
                    self.func__args__ = func
                elif unwrap_spec == [ObjSpace, W_Root, Arguments]:
                    self.__class__ = BuiltinCodePassThroughArguments1
                    self.func__args__ = func
            else:
                self.__class__ = globals()['BuiltinCode%d' % arity]
                setattr(self, 'fastfunc_%d' % arity, fastfunc)


    def create_frame(self, space, w_globals, closure=None):
        return self.framefactory.create(space, self, w_globals)

    def signature(self):
        return self.sig

    def getdocstring(self):
        return self.docstring


# (verbose) performance hack below

class BuiltinCodePassThroughArguments0(BuiltinCode):

    def funcrun(self, func, args):
        space = func.space
        try:
            w_result = self.func__args__(space, args)
        except KeyboardInterrupt: 
            raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
        except MemoryError: 
            raise OperationError(space.w_MemoryError, space.w_None) 
        except RuntimeError, e: 
            raise OperationError(space.w_RuntimeError, 
                                 space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = space.w_None
        return w_result

class BuiltinCodePassThroughArguments1(BuiltinCode):

    def funcrun(self, func, args):
        space = func.space
        w_obj, newargs = args.popfirst()
        if w_obj is not None:
            try:
                w_result = self.func__args__(space, w_obj, newargs)
            except KeyboardInterrupt: 
                raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
            except MemoryError: 
                raise OperationError(space.w_MemoryError, space.w_None) 
            except RuntimeError, e: 
                raise OperationError(space.w_RuntimeError, 
                                     space.wrap("internal error: " + str(e))) 
            if w_result is None:
                w_result = space.w_None
            return w_result
        else:
            return BuiltinCode.funcrun(self, func, args)

class BuiltinCode0(BuiltinCode):
    def fastcall_0(self, space, w_func):
        try:
            w_result = self.fastfunc_0(space)
        except KeyboardInterrupt: 
            raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
        except MemoryError: 
            raise OperationError(space.w_MemoryError, space.w_None) 
        except RuntimeError, e: 
            raise OperationError(space.w_RuntimeError, 
                                 space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = space.w_None
        return w_result

class BuiltinCode1(BuiltinCode):
    def fastcall_1(self, space, w_func, w1):
        try:
            w_result = self.fastfunc_1(space, w1)
        except KeyboardInterrupt: 
            raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
        except MemoryError: 
            raise OperationError(space.w_MemoryError, space.w_None) 
        except RuntimeError, e: 
            raise OperationError(space.w_RuntimeError, 
                                 space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = space.w_None
        return w_result

class BuiltinCode2(BuiltinCode):
    def fastcall_2(self, space, w_func, w1, w2):
        try:
            w_result = self.fastfunc_2(space, w1, w2)
        except KeyboardInterrupt: 
            raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
        except MemoryError: 
            raise OperationError(space.w_MemoryError, space.w_None) 
        except RuntimeError, e: 
            raise OperationError(space.w_RuntimeError, 
                                 space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = space.w_None
        return w_result

class BuiltinCode3(BuiltinCode):
    def fastcall_3(self, space, func, w1, w2, w3):
        try:
            w_result = self.fastfunc_3(space, w1, w2, w3)
        except KeyboardInterrupt: 
            raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
        except MemoryError: 
            raise OperationError(space.w_MemoryError, space.w_None) 
        except RuntimeError, e: 
            raise OperationError(space.w_RuntimeError, 
                                 space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = space.w_None
        return w_result

class BuiltinCode4(BuiltinCode):
    def fastcall_4(self, space, func, w1, w2, w3, w4):
        try:
            w_result = self.fastfunc_4(space, w1, w2, w3, w4)
        except KeyboardInterrupt: 
            raise OperationError(space.w_KeyboardInterrupt, space.w_None) 
        except MemoryError: 
            raise OperationError(space.w_MemoryError, space.w_None) 
        except RuntimeError, e: 
            raise OperationError(space.w_RuntimeError, 
                                 space.wrap("internal error: " + str(e))) 
        if w_result is None:
            w_result = space.w_None
        return w_result


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
    
    def __init__(self, f, app_name=None, unwrap_spec = None):
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
        self._code = BuiltinCode(f, unwrap_spec=unwrap_spec, self_type = self_type)
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
        return self.getcache(space).getorbuild(self)

    def getcache(self, space):
        return space.fromcache(GatewayCache)

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


class GatewayCache(SpaceCache):
    def build(cache, gateway):
        "NOT_RPYTHON"
        space = cache.space
        defs = gateway._getdefaults(space) # needs to be implemented by subclass
        code = gateway._code
        fn = Function(space, code, None, defs, forcename = gateway.name)
        return fn


# 
# the next gateways are to be used only for 
# temporary/initialization purposes 
     
class interp2app_temp(interp2app): 
    "NOT_RPYTHON"
    def getcache(self, space): 
        return self.__dict__.setdefault(space, GatewayCache(space))


# and now for something completely different ... 
#

class ApplevelClass:
    """NOT_RPYTHON
    A container for app-level source code that should be executed
    as a module in the object space;  interphook() builds a static
    interp-level function that invokes the callable with the given
    name at app-level."""

    hidden_applevel = True

    def __init__(self, source, filename = None, modname = '__builtin__'):
        self.filename = filename
        if self.filename is None:
            self.code = py.code.Source(source).compile()
        else:
            self.code = NiceCompile(self.filename)(source)
        self.modname = modname
        # look at the first three lines for a NOT_RPYTHON tag
        first = "\n".join(source.split("\n", 3)[:3])
        if "NOT_RPYTHON" in first:
            self.can_use_geninterp = False
        else:
            self.can_use_geninterp = True

    def getwdict(self, space):
        return space.fromcache(ApplevelCache).getorbuild(self)

    def buildmodule(self, space, name='applevel'):
        from pypy.interpreter.module import Module
        return Module(space, space.wrap(name), self.getwdict(space))

    def wget(self, space, name): 
        if hasattr(space, '_applevelclass_hook'):   # XXX for the CPyObjSpace
            return space._applevelclass_hook(self, name)
        w_globals = self.getwdict(space) 
        return space.getitem(w_globals, space.wrap(name))

    def interphook(self, name):
        "NOT_RPYTHON"
        def appcaller(space, *args_w):
            if not isinstance(space, ObjSpace): 
                raise TypeError("first argument must be a space instance.")
            # redirect if the space handles this specially
            # XXX can this be factored a bit less flow space dependently?
            if hasattr(space, 'specialcases'):
                sc = space.specialcases
                if ApplevelClass in sc:
                    ret_w = sc[ApplevelClass](space, self, name, args_w)
                    if ret_w is not None: # it was RPython
                        return ret_w
            args = Arguments(space, list(args_w))
            w_func = self.wget(space, name) 
            return space.call_args(w_func, args)
        def get_function(space):
            w_func = self.wget(space, name) 
            return space.unwrap(w_func)
        appcaller = func_with_new_name(appcaller, name)
        appcaller.get_function = get_function
        return appcaller

    def _freeze_(self):
        return True  # hint for the annotator: applevel instances are constants


class ApplevelCache(SpaceCache):
    """NOT_RPYTHON
    The cache mapping each applevel instance to its lazily built w_dict"""

    def build(self, app):
        "NOT_RPYTHON.  Called indirectly by Applevel.getwdict()."
        if self.space.config.objspace.geninterp and app.can_use_geninterp:
            return PyPyCacheDir.build_applevelinterp_dict(app, self.space)
        else:
            return build_applevel_dict(app, self.space)


# __________ pure applevel version __________

def build_applevel_dict(self, space):
    "NOT_RPYTHON"
    from pypy.interpreter.pycode import PyCode
    w_glob = space.newdict([])
    space.setitem(w_glob, space.wrap('__name__'), space.wrap('__builtin__'))
    space.exec_(self.code, w_glob, w_glob,
                hidden_applevel=self.hidden_applevel)
    return w_glob

# __________ geninterplevel version __________

class PyPyCacheDir:
    "NOT_RPYTHON"
    # similar to applevel, but using translation to interp-level.
    # This version maintains a cache folder with single files.

    def build_applevelinterp_dict(cls, self, space):
        "NOT_RPYTHON"
        # N.B. 'self' is the ApplevelInterp; this is a class method,
        # just so that we have a convenient place to store the global state.
        if not cls._setup_done:
            cls._setup()

        from pypy.translator.geninterplevel import translate_as_module
        import marshal
        scramble = md5.new(cls.seed)
        scramble.update(marshal.dumps(self.code))
        key = scramble.hexdigest()
        initfunc = cls.known_code.get(key)
        if not initfunc:
            # try to get it from file
            name = key
            if self.filename:
                prename = os.path.splitext(os.path.basename(self.filename))[0]
            else:
                prename = 'zznoname'
            name = "%s_%s" % (prename, name)
            try:
                __import__("pypy._cache."+name)
            except ImportError, x:
                # print x
                pass
            else:
                initfunc = cls.known_code[key]
        if not initfunc:
            # build it and put it into a file
            initfunc, newsrc = translate_as_module(
                self.code, self.filename, self.modname)
            fname = cls.cache_path.join(name+".py").strpath
            f = file(fname, "w")
            print >> f, """\
# self-destruct on double-click:
if __name__ == "__main__":
    from pypy import _cache
    import os
    namestart = os.path.join(os.path.split(_cache.__file__)[0], '%s')
    for ending in ('.py', '.pyc', '.pyo'):
        try:
            os.unlink(namestart+ending)
        except os.error:
            pass""" % name
            print >> f
            print >> f, newsrc
            print >> f, "from pypy._cache import known_code"
            print >> f, "known_code[%r] = %s" % (key, initfunc.__name__)
            f.close()
        w_glob = initfunc(space)
        return w_glob
    build_applevelinterp_dict = classmethod(build_applevelinterp_dict)

    _setup_done = False

    def _setup(cls):
        """NOT_RPYTHON"""
        lp = py.path.local
        import pypy, os
        p = lp(pypy.__file__).new(basename='_cache').ensure(dir=1)
        cls.cache_path = p
        ini = p.join('__init__.py')
        try:
            if not ini.check():
                raise ImportError  # don't import if only a .pyc file left!!!
            from pypy._cache import known_code, \
                 GI_VERSION_RENDERED
        except ImportError:
            GI_VERSION_RENDERED = 0
        from pypy.translator.geninterplevel import GI_VERSION
        cls.seed = md5.new(str(GI_VERSION)).digest()
        if GI_VERSION != GI_VERSION_RENDERED or GI_VERSION is None:
            for pth in p.listdir():
                try:
                    pth.remove()
                except: pass
            f = file(str(ini), "w")
            f.write("""\
# This folder acts as a cache for code snippets which have been
# compiled by compile_as_module().
# It will get a new entry for every piece of code that has
# not been seen, yet.
#
# Caution! Only the code snippet is checked. If something
# is imported, changes are not detected. Also, changes
# to geninterplevel or gateway are also not checked.
# Exception: There is a checked version number in geninterplevel.py
#
# If in doubt, remove this file from time to time.

GI_VERSION_RENDERED = %r

known_code = {}

# self-destruct on double-click:
def harakiri():
    import pypy._cache as _c
    import py
    lp = py.path.local
    for pth in lp(_c.__file__).dirpath().listdir():
        try:
            pth.remove()
        except: pass

if __name__ == "__main__":
    harakiri()

del harakiri
""" % GI_VERSION)
            f.close()
        import pypy._cache
        cls.known_code = pypy._cache.known_code
        cls._setup_done = True
    _setup = classmethod(_setup)

# ____________________________________________________________

def appdef(source, applevel=ApplevelClass):
    """ NOT_RPYTHON: build an app-level helper function, like for example:
    myfunc = appdef('''myfunc(x, y):
                           return x+y
                    ''')
    """ 
    if not isinstance(source, str): 
        source = str(py.code.Source(source).strip())
        assert source.startswith("def "), "can only transform functions" 
        source = source[4:]
    p = source.find('(')
    assert p >= 0
    funcname = source[:p].strip()
    source = source[p:]
    return applevel("def %s%s\n" % (funcname, source)).interphook(funcname)

applevel = ApplevelClass   # backward compatibility
app2interp = appdef   # backward compatibility


class applevel_temp(ApplevelClass):
    hidden_applevel = False
    def getwdict(self, space):    # no cache
        return build_applevel_dict(self, space)


class applevelinterp_temp(ApplevelClass):
    hidden_applevel = False
    def getwdict(self, space):   # no cache
        return PyPyCacheDir.build_applevelinterp_dict(self, space)

# app2interp_temp is used for testing mainly
def app2interp_temp(func, applevel_temp=applevel_temp):
    """ NOT_RPYTHON """
    return appdef(func, applevel_temp)
