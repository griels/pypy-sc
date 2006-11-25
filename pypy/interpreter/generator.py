from pypy.interpreter.error import OperationError
from pypy.interpreter.baseobjspace import Wrappable
from pypy.interpreter.eval import EvalFrame
from pypy.interpreter.pyframe import ControlFlowException, ExitFrame

#
# Generator support. Note that GeneratorFrame is not a subclass of PyFrame.
# PyCode objects use a custom subclass of both PyFrame and GeneratorFrame
# when they need to interpret Python bytecode that is a generator.
# Otherwise, GeneratorFrame could also be used to define, say,
# built-in generators (which are usually done in CPython as functions
# that return iterators).
#

class GeneratorFrameMixin(object):
    "A frame attached to a generator."
    _mixin_ = True

    def run(self):
        "Build a generator-iterator."
        return self.space.wrap(GeneratorIterator(self))

    ### extra opcodes ###

    # XXX mmmh, GeneratorFrame is supposed to be independent from
    # Python bytecode... Well, it is. These are not used when
    # GeneratorFrame is used with other kinds of Code subclasses.

    def RETURN_VALUE(f):  # overridden
        raise SGeneratorReturn()

    def YIELD_VALUE(f):
        w_yieldedvalue = f.valuestack.pop()
        raise SYieldValue(w_yieldedvalue)
    YIELD_STMT = YIELD_VALUE  # misnamed in old versions of dis.opname


class GeneratorIterator(Wrappable):
    "An iterator created by a generator."
    
    def __init__(self, frame):
        self.space = frame.space
        self.frame = frame
        self.running = False
        self.exhausted = False

    def descr__reduce__(self, space):
        from pypy.interpreter.mixedmodule import MixedModule
        w_mod    = space.getbuiltinmodule('_pickle_support')
        mod      = space.interp_w(MixedModule, w_mod)
        new_inst = mod.get('generator_new')
        w        = space.wrap

        tup = [
            w(self.frame),
            w(self.running),
            w(self.exhausted),
            ]

        return space.newtuple([new_inst, space.newtuple(tup)])

    def descr__iter__(self):
        """x.__iter__() <==> iter(x)"""
        return self.space.wrap(self)

    def descr_next(self):
        """x.next() -> the next value, or raise StopIteration"""
        space = self.space
        if self.running:
            raise OperationError(space.w_ValueError,
                                 space.wrap('generator already executing'))
        if self.exhausted:
            raise OperationError(space.w_StopIteration, space.w_None) 
        self.running = True
        try:
            try:
                return self.frame.resume()
            except OperationError:
                self.exhausted = True
                raise
        finally:
            self.frame.f_back = None
            self.running = False

#
# the specific ControlFlowExceptions used by generators
#

class SYieldValue(ControlFlowException):
    """Signals a 'yield' statement.
    Argument is the wrapped object to return."""

    def __init__(self, w_yieldvalue):
        self.w_yieldvalue = w_yieldvalue

    def action(self, frame):
        raise ExitFrame(self.w_yieldvalue)

class SGeneratorReturn(ControlFlowException):
    """Signals a 'return' statement inside a generator."""
    def emptystack(self, frame):
        raise OperationError(frame.space.w_StopIteration, frame.space.w_None) 
