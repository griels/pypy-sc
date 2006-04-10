# ______________________________________________________________________
import sys, operator, types
from pypy.interpreter.baseobjspace import ObjSpace, Wrappable
from pypy.interpreter.pycode import PyCode, cpython_code_signature
from pypy.interpreter.module import Module
from pypy.interpreter.error import OperationError
from pypy.objspace.flow.model import *
from pypy.objspace.flow import flowcontext
from pypy.objspace.flow.operation import FunctionByName

debug = 0

class UnwrapException(Exception):
    "Attempted to unwrap a Variable."

class WrapException(Exception):
    """Attempted wrapping of a type that cannot sanely appear in flow graph or during its construction"""

# method-wrappers
method_wrapper = type(complex.real.__get__)


# ______________________________________________________________________
class FlowObjSpace(ObjSpace):
    """NOT_RPYTHON.
    The flow objspace space is used to produce a flow graph by recording
    the space operations that the interpreter generates when it interprets
    (the bytecode of) some function.
    """
    
    full_exceptions = False

    builtins_can_raise_exceptions = False
    do_imports_immediately = True

    def initialize(self):
        import __builtin__
        self.concrete_mode = 1
        self.w_None     = Constant(None)
        self.builtin    = Module(self, Constant('__builtin__'), Constant(__builtin__.__dict__))
        def pick_builtin(w_globals):
            return self.builtin
        self.builtin.pick_builtin = pick_builtin
        self.sys        = Module(self, Constant('sys'), Constant(sys.__dict__))
        self.sys.recursionlimit = 100
        self.w_False    = Constant(False)
        self.w_True     = Constant(True)
        self.w_type     = Constant(type)
        self.w_tuple    = Constant(tuple)
        self.concrete_mode = 0
        for exc in [KeyError, ValueError, IndexError, StopIteration,
                    AssertionError, TypeError, AttributeError, ImportError]:
            clsname = exc.__name__
            setattr(self, 'w_'+clsname, Constant(exc))
        # the following exceptions are the ones that should not show up
        # during flow graph construction; they are triggered by
        # non-R-Pythonic constructs or real bugs like typos.
        for exc in [NameError, UnboundLocalError]:
            clsname = exc.__name__
            setattr(self, 'w_'+clsname, None)
        self.specialcases = {}
        #self.make_builtins()
        #self.make_sys()
        # objects which should keep their SomeObjectness
        self.not_really_const = NOT_REALLY_CONST
        # tracking variables which might in turn turn into constants.
        self.const_tracker = None

    def enter_cache_building_mode(self):
        # when populating the caches, the flow space switches to
        # "concrete mode".  In this mode, only Constants are allowed
        # and no SpaceOperation is recorded.
        previous_recorder = self.executioncontext.recorder
        self.executioncontext.recorder = flowcontext.ConcreteNoOp()
        self.concrete_mode += 1
        return previous_recorder

    def leave_cache_building_mode(self, previous_recorder):
        self.executioncontext.recorder = previous_recorder
        self.concrete_mode -= 1

    def newdict(self, items_w):
        if self.concrete_mode:
            content = [(self.unwrap(w_key), self.unwrap(w_value))
                       for w_key, w_value in items_w]
            return Constant(dict(content))
        flatlist_w = []
        for w_key, w_value in items_w:
            flatlist_w.append(w_key)
            flatlist_w.append(w_value)
        return self.do_operation('newdict', *flatlist_w)

    def newtuple(self, args_w):
        try:
            content = [self.unwrap(w_arg) for w_arg in args_w]
        except UnwrapException:
            return self.do_operation('newtuple', *args_w)
        else:
            return Constant(tuple(content))

    def newlist(self, args_w):
        if self.concrete_mode:
            content = [self.unwrap(w_arg) for w_arg in args_w]
            return Constant(content)
        return self.do_operation('newlist', *args_w)

    def newslice(self, w_start, w_stop, w_step):
        if self.concrete_mode:
            return Constant(slice(self.unwrap(w_start),
                                  self.unwrap(w_stop),
                                  self.unwrap(w_step)))
        return self.do_operation('newslice', w_start, w_stop, w_step)

    def wrap(self, obj):
        if isinstance(obj, (Variable, Constant)):
            raise TypeError("already wrapped: " + repr(obj))
        # method-wrapper have ill-defined comparison and introspection
        # to appear in a flow graph
        if type(obj) is method_wrapper:
            raise WrapException
        return Constant(obj)

    def int_w(self, w_obj):
        if isinstance(w_obj, Constant):
            val = w_obj.value
            if type(val) not in (int,long):
                raise TypeError("expected integer: " + repr(w_obj))
            return val
        return self.unwrap(w_obj)

    def uint_w(self, w_obj):
        if isinstance(w_obj, Constant):
            from pypy.rpython.rarithmetic import r_uint
            val = w_obj.value
            if type(val) is not r_uint:
                raise TypeError("expected unsigned: " + repr(w_obj))
            return val
        return self.unwrap(w_obj)


    def str_w(self, w_obj):
        if isinstance(w_obj, Constant):
            val = w_obj.value
            if type(val) is not str:
                raise TypeError("expected string: " + repr(w_obj))
            return val
        return self.unwrap(w_obj)                                

    def float_w(self, w_obj):
        if isinstance(w_obj, Constant):
            val = w_obj.value
            if type(val) is not float:
                raise TypeError("expected float: " + repr(w_obj))
            return val
        return self.unwrap(w_obj)

    def unwrap(self, w_obj):
        if isinstance(w_obj, Variable):
            raise UnwrapException
        elif isinstance(w_obj, Constant):
            return w_obj.value
        else:
            raise TypeError("not wrapped: " + repr(w_obj))

    def unwrap_for_computation(self, w_obj):
        obj = self.unwrap(w_obj)
        to_check = obj
        if hasattr(to_check, 'im_self'):
            to_check = to_check.im_self
        if (not isinstance(to_check, (type, types.ClassType, types.ModuleType)) and
            # classes/types/modules are assumed immutable
            hasattr(to_check, '__class__') and to_check.__class__.__module__ != '__builtin__'):
            frozen = hasattr(to_check, '_freeze_') and to_check._freeze_()
            if not frozen:
                if self.concrete_mode:
                    # xxx do we want some warning? notice that some stuff is harmless
                    # like setitem(dict, 'n', mutable)
                    pass
                else: # cannot count on it not mutating at runtime!
                    raise UnwrapException
        return obj

    def interpclass_w(self, w_obj):
        obj = self.unwrap(w_obj)
        if isinstance(obj, Wrappable):
            return obj
        return None

    def getexecutioncontext(self):
        return getattr(self, 'executioncontext', None)

    def setup_executioncontext(self, ec):
        self.executioncontext = ec
        from pypy.objspace.flow import specialcase
        specialcase.setup(self)

    def exception_match(self, w_exc_type, w_check_class):
        self.executioncontext.recorder.crnt_block.exc_handler = True
        try:
            check_class = self.unwrap(w_check_class)
        except UnwrapException:
            raise Exception, "non-constant except guard"
        if not isinstance(check_class, tuple):
            # the simple case
            return ObjSpace.exception_match(self, w_exc_type, w_check_class)
        # checking a tuple of classes
        for w_klass in self.unpacktuple(w_check_class):
            if ObjSpace.exception_match(self, w_exc_type, w_klass):
                return True
        return False

    def getconstclass(space, w_cls):
        try:
            ecls = space.unwrap(w_cls)
        except UnwrapException:
            pass
        else:
            if isinstance(ecls, (type, types.ClassType)):
                return ecls
        return None

    def abstract_issubclass(self, w_obj, w_cls, failhard=False):
        return self.issubtype(w_obj, w_cls)

    def abstract_isinstance(self, w_obj, w_cls):
        return self.isinstance(w_obj, w_cls)

    def abstract_isclass(self, w_obj):
        return self.isinstance(w_obj, self.w_type)

    def abstract_getclass(self, w_obj):
        return self.type(w_obj)


    def build_flow(self, func, constargs={}):
        """
        """
        if func.func_doc and func.func_doc.lstrip().startswith('NOT_RPYTHON'):
            raise Exception, "%r is tagged as NOT_RPYTHON" % (func,)
        code = func.func_code
        code = PyCode._from_code(self, code)
        if func.func_closure is None:
            closure = None
        else:
            closure = [extract_cell_content(c) for c in func.func_closure]
        # CallableFactory.pycall may add class_ to functions that are methods
        name = func.func_name
        class_ = getattr(func, 'class_', None)
        if class_ is not None:
            name = '%s.%s' % (class_.__name__, name)
        for c in "<>&!":
            name = name.replace(c, '_')
        ec = flowcontext.FlowExecutionContext(self, code, func.func_globals,
                                              constargs, closure, name)
        graph = ec.graph
        graph.func = func
        # attach a signature and defaults to the graph
        # so that it becomes even more interchangeable with the function
        # itself
        graph.signature = cpython_code_signature(code)
        graph.defaults = func.func_defaults
        self.setup_executioncontext(ec)
        ec.build_flow()
        checkgraph(graph)
        return graph

    def unpacktuple(self, w_tuple, expected_length=None):
##        # special case to accept either Constant tuples
##        # or real tuples of Variables/Constants
##        if isinstance(w_tuple, tuple):
##            result = w_tuple
##        else:
        unwrapped = self.unwrap(w_tuple)
        result = tuple([Constant(x) for x in unwrapped])
        if expected_length is not None and len(result) != expected_length:
            raise ValueError, "got a tuple of length %d instead of %d" % (
                len(result), expected_length)
        return result

    def unpackiterable(self, w_iterable, expected_length=None):
        if not isinstance(w_iterable, Variable):
            l = list(self.unwrap(w_iterable))
            if expected_length is not None and len(l) != expected_length:
                raise ValueError
            return [self.wrap(x) for x in l]
        if isinstance(w_iterable, Variable) and expected_length is None:
            raise UnwrapException, ("cannot unpack a Variable iterable"
                                    "without knowing its length")
##            # XXX TEMPORARY HACK XXX TEMPORARY HACK XXX TEMPORARY HACK
##            print ("*** cannot unpack a Variable iterable "
##                   "without knowing its length,")
##            print "    assuming a list or tuple with up to 7 items"
##            items = []
##            w_len = self.len(w_iterable)
##            i = 0
##            while True:
##                w_i = self.wrap(i)
##                w_cond = self.eq(w_len, w_i)
##                if self.is_true(w_cond):
##                    break  # done
##                if i == 7:
##                    # too many values
##                    raise OperationError(self.w_AssertionError, self.w_None)
##                w_item = self.do_operation('getitem', w_iterable, w_i)
##                items.append(w_item)
##                i += 1
##            return items
##            # XXX TEMPORARY HACK XXX TEMPORARY HACK XXX TEMPORARY HACK
        elif expected_length is not None:
            w_len = self.len(w_iterable)
            w_correct = self.eq(w_len, self.wrap(expected_length))
            if not self.is_true(w_correct):
                e = OperationError(self.w_ValueError, self.w_None)
                e.normalize_exception(self)
                raise e
            return [self.do_operation('getitem', w_iterable, self.wrap(i)) 
                        for i in range(expected_length)]
        return ObjSpace.unpackiterable(self, w_iterable, expected_length)

    # ____________________________________________________________
    def do_operation(self, name, *args_w):
        spaceop = SpaceOperation(name, args_w, Variable())
        if hasattr(self, 'executioncontext'):  # not here during bootstrapping
            spaceop.offset = self.executioncontext.crnt_offset
            self.executioncontext.recorder.append(spaceop)
        return spaceop.result

    def do_operation_with_implicit_exceptions(self, name, *args_w):
        w_result = self.do_operation(name, *args_w)
        self.handle_implicit_exceptions(implicit_exceptions.get(name))
        return w_result

    def is_true(self, w_obj):
        try:
            obj = self.unwrap_for_computation(w_obj)
        except UnwrapException:
            pass
        else:
            return bool(obj)
        w_truthvalue = self.do_operation('is_true', w_obj)
        context = self.getexecutioncontext()
        return context.guessbool(w_truthvalue)

    def next(self, w_iter):
        w_item = self.do_operation("next", w_iter)
        context = self.getexecutioncontext()
        outcome, w_exc_cls, w_exc_value = context.guessexception(StopIteration)
        if outcome is StopIteration:
            raise OperationError(self.w_StopIteration, w_exc_value)
        else:
            return w_item

    def setitem(self, w_obj, w_key, w_val):
        if self.concrete_mode:
            try:
                obj = self.unwrap_for_computation(w_obj)
                key = self.unwrap_for_computation(w_key)
                val = self.unwrap_for_computation(w_val)
                operator.setitem(obj, key, val)
                return self.w_None
            except UnwrapException:
                pass
        return self.do_operation_with_implicit_exceptions('setitem', w_obj, 
                                                          w_key, w_val)

    def call_args(self, w_callable, args):
        try:
            fn = self.unwrap(w_callable)
            sc = self.specialcases[fn]   # TypeError if 'fn' not hashable
        except (UnwrapException, KeyError, TypeError):
            pass
        else:
            return sc(self, fn, args)

        try:
            args_w, kwds_w = args.unpack()
        except UnwrapException:
            args_w, kwds_w = '?', '?'
        # NOTE: annrpython needs to know about the following two operations!
        if not kwds_w:
            # simple case
            w_res = self.do_operation('simple_call', w_callable, *args_w)
        else:
            # general case
            shape, args_w = args.flatten()
            w_res = self.do_operation('call_args', w_callable, Constant(shape),
                                      *args_w)

        # maybe the call has generated an exception (any one)
        # but, let's say, not if we are calling a built-in class or function
        # because this gets in the way of the special-casing of
        #
        #    raise SomeError(x)
        #
        # as shown by test_objspace.test_raise3.
        
        exceptions = [Exception]   # *any* exception by default
        if isinstance(w_callable, Constant):
            c = w_callable.value
            if not self.builtins_can_raise_exceptions:
                if (isinstance(c, (types.BuiltinFunctionType,
                                   types.BuiltinMethodType,
                                   types.ClassType,
                                   types.TypeType)) and
                      c.__module__ in ['__builtin__', 'exceptions']):
                    exceptions = implicit_exceptions.get(c, None)
        self.handle_implicit_exceptions(exceptions)
        return w_res

    def handle_implicit_exceptions(self, exceptions):
        if exceptions:
            # catch possible exceptions implicitly.  If the OperationError
            # below is not caught in the same function, it will produce an
            # exception-raising return block in the flow graph.  Note that
            # even if the interpreter re-raises the exception, it will not
            # be the same ImplicitOperationError instance internally.
            context = self.getexecutioncontext()
            outcome, w_exc_cls, w_exc_value = context.guessexception(*exceptions)
            if outcome is not None:
                # we assume that the caught exc_cls will be exactly the
                # one specified by 'outcome', and not a subclass of it,
                # unless 'outcome' is Exception.
                #if outcome is not Exception:
                    #w_exc_cls = Constant(outcome) Now done by guessexception itself
                    #pass
                 raise flowcontext.ImplicitOperationError(w_exc_cls,
                                                         w_exc_value)

# the following gives us easy access to declare more for applications:
NOT_REALLY_CONST = {
    Constant(sys): {
        Constant('maxint'): True,
        Constant('maxunicode'): True,
        Constant('api_version'): True,
        Constant('exit'): True,
        Constant('exc_info'): True,
        Constant('getrefcount'): True,
        Constant('getdefaultencoding'): True,
        # this is an incomplete list of true constants.
        # if we add much more, a dedicated class
        # might be considered for special objects.
        }
    }

# ______________________________________________________________________

op_appendices = {}
for _name, _exc in(
    ('ovf', OverflowError),
    ('idx', IndexError),
    ('key', KeyError),
    ('att', AttributeError),
    ('typ', TypeError),
    ('zer', ZeroDivisionError),
    ('val', ValueError),
    #('flo', FloatingPointError)
    ):
    op_appendices[_exc] = _name
del _name, _exc

implicit_exceptions = {
    int: [ValueError],      # built-ins that can always raise exceptions
    chr: [ValueError],
    unichr: [ValueError],
    }

def _add_exceptions(names, exc):
    for name in names.split():
        lis = implicit_exceptions.setdefault(name, [])
        if exc in lis:
            raise ValueError, "your list is causing duplication!"
        lis.append(exc)
        assert exc in op_appendices

def _add_except_ovf(names):
    # duplicate exceptions and add OverflowError
    for name in names.split():
        lis = implicit_exceptions.setdefault(name, [])[:]
        lis.append(OverflowError)
        implicit_exceptions[name+"_ovf"] = lis

for _err in IndexError, KeyError:
    _add_exceptions("""getitem setitem delitem""", _err)
for _name in 'getattr', 'delattr':
    _add_exceptions(_name, AttributeError)
for _name in 'iter', 'coerce':
    _add_exceptions(_name, TypeError)
del _name, _err

_add_exceptions("""div mod divmod truediv floordiv pow
                   inplace_div inplace_mod inplace_divmod inplace_truediv
                   inplace_floordiv inplace_pow""", ZeroDivisionError)
_add_exceptions("""pow inplace_pow lshift inplace_lshift rshift
                   inplace_rshift""", ValueError)
##_add_exceptions("""add sub mul truediv floordiv div mod divmod pow
##                   inplace_add inplace_sub inplace_mul inplace_truediv
##                   inplace_floordiv inplace_div inplace_mod inplace_divmod
##                   inplace_pow""", FloatingPointError)
_add_exceptions("""truediv divmod
                   inplace_add inplace_sub inplace_mul inplace_truediv
                   inplace_floordiv inplace_div inplace_mod inplace_pow
                   inplace_lshift""", OverflowError) # without a _ovf version
_add_except_ovf("""neg abs add sub mul
                   floordiv div mod pow lshift""")   # with a _ovf version
_add_exceptions("""pow""",
                OverflowError) # for the float case
del _add_exceptions, _add_except_ovf

def extract_cell_content(c):
    """Get the value contained in a CPython 'cell', as read through
    the func_closure of a function object."""
    # yuk! this is all I could come up with that works in Python 2.2 too
    class X(object):
        def __cmp__(self, other):
            self.other = other
            return 0
        def __eq__(self, other):
            self.other = other
            return True
    x = X()
    x_cell, = (lambda: x).func_closure
    x_cell == c
    return x.other    # crashes if the cell is actually empty

def make_op(name, symbol, arity, specialnames):
    if hasattr(FlowObjSpace, name):
        return # Shouldn't do it

    import __builtin__

    op = None
    skip = False

    if name.startswith('del') or name.startswith('set') or name.startswith('inplace_'):
        # skip potential mutators
        if debug: print "Skip", name
        skip = True
    elif name in ['id', 'hash', 'iter', 'userdel']: 
        # skip potential runtime context dependecies
        if debug: print "Skip", name
        skip = True
    elif name in ['repr', 'str']:
        rep = getattr(__builtin__, name)
        def op(obj):
            s = rep(obj)
            if s.find("at 0x") > -1:
                print >>sys.stderr, "Warning: captured address may be awkward"
            return s
    else:
        op = FunctionByName[name]

    if not op:
        if not skip:
            if debug: print >> sys.stderr, "XXX missing operator:", name
    else:
        if debug: print "Can constant-fold operation: %s" % name

    def generic_operator(self, *args_w):
        assert len(args_w) == arity, name+" got the wrong number of arguments"
        if op:
            args = []
            for w_arg in args_w:
                try:
                    arg = self.unwrap_for_computation(w_arg)
                except UnwrapException:
                    break
                else:
                    args.append(arg)
            else:
                # All arguments are constants: call the operator now
                #print >> sys.stderr, 'Constant operation', op
                try:
                    result = op(*args)
                except:
                    etype, evalue, etb = sys.exc_info()
                    msg = "generated by a constant operation:  %s%r" % (
                        name, tuple(args))
                    raise flowcontext.OperationThatShouldNotBePropagatedError(
                        self.wrap(etype), self.wrap(msg))
                else:
                    try:
                        return self.wrap(result)
                    except WrapException:
                        # type cannot sanely appear in flow graph,
                        # store operation with variable result instead
                        pass

        #print >> sys.stderr, 'Variable operation', name, args_w
        w_result = self.do_operation_with_implicit_exceptions(name, *args_w)
        return w_result

    setattr(FlowObjSpace, name, generic_operator)

for line in ObjSpace.MethodTable:
    make_op(*line)

"""
Strategy for a new import logic
-------------------------------

It is an old problem to decide whether to use do_imports_immediately.
In general, it would be nicer not to use this flag for RPython, in order
to make it easy to support imports at run-time for extensions.

On the other hand, there are situations where this is absolutely needed:
Some of the ll helper functions need to import something late, to
avoid circular imports. Not doing the import immediately would cause
a crash, because the imported object would become SomeObject.

We would like to have control over imports even on a per-import policy.

As a general solution, I came up with the following trick, or maybe it's
not a trick but a good concept:

By declaring the imported subject as a global, you trigger the immediate
import. This is consistent with the RPython concept that globals
should never change, just with the addition that objects may be added.
In addition, we consider global modules to be immutable, making attribute
access a constant operation.

As a generalisation, we can enforce that getattr/setattr on any
object that is unwrappable for computation is evaluated
immediately. This gives us early detection of programming errors.
XXX this step isn't done, yet, need to discuss this.

Implementation
--------------

It is not completely trivial, since we have to intercept the process
of flowing, to keep trak of which variable might become a constant.
Finally I ended up with a rather simple solution:
Flowcontext monitors every link creation, by no longer using
Link() directly, but redirecting this to a function make_link,
which can be patched to record the creation of links.

The actual tracking and constant resolving is implemented in the
ConstTracker class below.

"""

def override():
    from __builtin__ import getattr as _getattr # uhmm
    
    def getattr(self, w_obj, w_name):
        # handling special things like sys
        # (maybe this will vanish with a unique import logic)
        if w_obj in self.not_really_const:
            const_w = self.not_really_const[w_obj]
            if w_name not in const_w:
                return self.do_operation_with_implicit_exceptions('getattr', w_obj, w_name)
        w_res = self.regular_getattr(w_obj, w_name)
        # tracking variables which might be(come) constants
        if self.const_tracker:
            self.track_possible_constant(w_res, _getattr, w_obj, w_name)
        return w_res

    FlowObjSpace.regular_getattr = FlowObjSpace.getattr
    FlowObjSpace.getattr = getattr

    # protect us from globals access but support constant import into globals
    def setitem(self, w_obj, w_key, w_val):
        ec = self.getexecutioncontext()
        if not (ec and w_obj is ec.w_globals):
            return self.regular_setitem(w_obj, w_key, w_val)
        globals = self.unwrap(w_obj)
        try:
            key = self.unwrap_for_computation(self.resolve_constant(w_key))
            val = self.unwrap_for_computation(self.resolve_constant(w_val))
            if key not in globals or val == globals[key]:
                globals[key] = val
                return self.w_None
        except UnwrapException:
            pass
        raise SyntaxError, "attempt to modify global attribute %r in %r" % (w_key, ec.graph.func)

    FlowObjSpace.regular_setitem = FlowObjSpace.setitem
    FlowObjSpace.setitem = setitem

    def track_possible_constant(self, w_ret, func, *args_w):
        if not self.const_tracker:
            self.const_tracker = ConstTracker(self)
        tracker = self.const_tracker
        tracker.track_call(w_ret, func, *args_w)
        self.getexecutioncontext().start_monitoring(tracker.monitor_transition)

    FlowObjSpace.track_possible_constant = track_possible_constant

    def resolve_constant(self, w_obj):
        if self.const_tracker:
            w_obj = self.const_tracker.resolve_const(w_obj)
        return w_obj

    FlowObjSpace.resolve_constant = resolve_constant

override()


class ConstTracker(object):
    def __init__(self, space):
        assert isinstance(space, FlowObjSpace)
        self.space = space
        self.known_consts = {}
        self.tracked_vars = {}
        self.mapping = {}

    def track_call(self, w_res, callable, *args_w):
        """ defer evaluation of this expression until a const is needed
        """
        self.mapping[w_res] = w_res
        self.tracked_vars[w_res] = callable, args_w

    def monitor_transition(self, link):
        for vin, vout in zip(link.args, link.target.inputargs):
            # we record all true transitions, but no cycles.
            if vin in self.mapping and vout not in self.mapping:
                # the mapping leads directly to the origin.
                self.mapping[vout] = self.mapping[vin]

    def resolve_const(self, w_obj):
        """ compute a latent constant expression """
        if isinstance(w_obj, Constant):
            return w_obj
        w = self.mapping.get(w_obj, w_obj)
        if w in self.known_consts:
            return self.known_consts[w]
        if w not in self.tracked_vars:
            raise SyntaxError, 'RPython: cannot compute a constant for %s in %s' % (
                w_obj, self.space.getexecutioncontext().graph.func)
        callable, args_w = self.tracked_vars.pop(w)
        args_w = [self.resolve_const(w_x) for w_x in args_w]
        args = [self.space.unwrap_for_computation(w_x) for w_x in args_w]
        w_ret = self.space.wrap(callable(*args))
        self.known_consts[w] = w_ret
        return w_ret

# ______________________________________________________________________
# End of objspace.py
