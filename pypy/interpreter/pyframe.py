""" PyFrame class implementation with the interpreter main loop.
"""

from pypy.interpreter import eval, baseobjspace, gateway
from pypy.interpreter.miscutils import Stack
from pypy.interpreter.error import OperationError


class PyFrame(eval.Frame):
    """Represents a frame for a regular Python function
    that needs to be interpreted.

    See also pyopcode.PyStandardFrame and pynestedscope.PyNestedScopeFrame.

    Public fields:
     * 'space' is the object space this frame is running in
     * 'code' is the PyCode object this frame runs
     * 'w_locals' is the locals dictionary to use
     * 'w_globals' is the attached globals dictionary
     * 'w_builtins' is the attached built-ins dictionary
     * 'valuestack', 'blockstack', 'next_instr' control the interpretation
    """

    def __init__(self, space, code, w_globals, closure):
        eval.Frame.__init__(self, space, code, w_globals, code.co_nlocals)
        self.valuestack = Stack()
        self.blockstack = Stack()
        self.last_exception = None
        self.next_instr = 0
        self.w_builtins = self.space.w_builtins
        # regular functions always have CO_OPTIMIZED and CO_NEWLOCALS.
        # class bodies only have CO_NEWLOCALS.
        if code.dictscope_needed():
            self.w_locals = space.newdict([])  # set to None by Frame.__init__

    def getclosure(self):
        return None

    def eval(self, executioncontext):
        "Interpreter main loop!"
        try:
            while True:
                try:
                    executioncontext.bytecode_trace(self)
                    last_instr = self.next_instr
                    try:
                        # fetch and dispatch the next opcode
                        # dispatch() is abstract, see pyopcode.
                        self.dispatch()
                    except OperationError, e:
                        #import traceback
                        #traceback.print_exc()
                        e.record_application_traceback(self, last_instr)
                        self.last_exception = e
                        executioncontext.exception_trace(e)
                        # convert an OperationError into a control flow
                        # exception
                        import sys
                        tb = sys.exc_info()[2]
                        raise SApplicationException(e, tb)
                    # XXX some other exceptions could be caught here too,
                    #     like KeyboardInterrupt

                except ControlFlowException, ctlflowexc:
                    # we have a reason to change the control flow
                    # (typically unroll the stack)
                    ctlflowexc.action(self, last_instr, executioncontext)
            
        except ExitFrame, e:
            # leave that frame
            w_exitvalue = e.args[0]
            return w_exitvalue

    ### exception stack ###

    def clean_exceptionstack(self):
        # remove all exceptions that can no longer be re-raised
        # because the current valuestack is no longer deep enough
        # to hold the corresponding information
        while self.exceptionstack:
            ctlflowexc, valuestackdepth = self.exceptionstack.top()
            if valuestackdepth <= self.valuestack.depth():
                break
            self.exceptionstack.pop()

    ### public attributes ###

    def pypy_getattr(self, w_attr):
        # XXX surely not the Right Way to do this
        attr = self.space.unwrap(w_attr)
        if attr == 'f_locals':   return self.w_locals
        if attr == 'f_globals':  return self.w_globals
        if attr == 'f_builtins': return self.w_builtins
        if attr == 'f_code':     return self.space.wrap(self.code)
        raise OperationError(self.space.w_AttributeError, w_attr)

    ### cloning (for FlowObjSpace) ###

    def getflowstate(self):
        mergeablestate = self.getfastscope() + self.valuestack.items
        nonmergeablestate = (
            self.blockstack.items[:],
            self.last_exception,
            self.next_instr,
            )
        return mergeablestate, nonmergeablestate

    def setflowstate(self, (mergeablestate, nonmergeablestate)):
        self.setfastscope(mergeablestate[:len(self.fastlocals_w)])
        self.valuestack.items[:] = mergeablestate[len(self.fastlocals_w):]
        (
            self.blockstack.items[:],
            self.last_exception,
            self.next_instr,
            ) = nonmergeablestate
        
    def clone(self):
        # Clone the frame, making a copy of the mutable state
        cls = self.__class__
        f = cls(self.space, self.code, self.w_globals, self.getclosure())
        f.setflowstate(self.getflowstate())


### Frame Blocks ###

class FrameBlock:

    """Abstract base class for frame blocks from the blockstack,
    used by the SETUP_XXX and POP_BLOCK opcodes."""

    def __init__(self, frame, handlerposition):
        self.handlerposition = handlerposition
        self.valuestackdepth = frame.valuestack.depth()

    def cleanupstack(self, frame):
        for i in range(self.valuestackdepth, frame.valuestack.depth()):
            frame.valuestack.pop()

    def cleanup(self, frame):
        "Clean up a frame when we normally exit the block."
        self.cleanupstack(frame)

    def unroll(self, frame, unroller):
        "Clean up a frame when we abnormally exit the block."
        self.cleanupstack(frame)


class LoopBlock(FrameBlock):
    """A loop block.  Stores the end-of-loop pointer in case of 'break'."""

    def unroll(self, frame, unroller):
        if isinstance(unroller, SContinueLoop):
            # re-push the loop block without cleaning up the value stack,
            # and jump to the beginning of the loop, stored in the
            # exception's argument
            frame.blockstack.push(self)
            jump_to = unroller.args[0]
            frame.next_instr = jump_to
            raise StopUnrolling
        self.cleanupstack(frame)
        if isinstance(unroller, SBreakLoop):
            # jump to the end of the loop
            frame.next_instr = self.handlerposition
            raise StopUnrolling


class ExceptBlock(FrameBlock):
    """An try:except: block.  Stores the position of the exception handler."""

    def unroll(self, frame, unroller):
        self.cleanupstack(frame)
        if isinstance(unroller, SApplicationException):
            # push the exception to the value stack for inspection by the
            # exception handler (the code after the except:)
            operationerr = unroller.args[0]
            w_normalized = normalize_exception(frame.space,
                                               operationerr.w_type,
                                               operationerr.w_value)
            w_type, w_value = frame.space.unpacktuple(w_normalized, 2)
            # the stack setup is slightly different than in CPython:
            # instead of the traceback, we store the unroller object,
            # wrapped.
            frame.valuestack.push(frame.space.wrap(unroller))
            frame.valuestack.push(w_value)
            frame.valuestack.push(w_type)
            frame.next_instr = self.handlerposition   # jump to the handler
            raise StopUnrolling

def app_normalize_exception(etype, evalue):
    # XXX should really be defined as a method on OperationError,
    # but this is not so easy because OperationError cannot be
    # at the same time an old-style subclass of Exception and a
    # new-style subclass of Wrappable :-(
    # moreover, try importing gateway from errors.py and you'll see :-(
    
    # mistakes here usually show up as infinite recursion, which is fun.
    if isinstance(evalue, etype):
        return etype, evalue
    if isinstance(etype, type) and issubclass(etype, Exception):
        if evalue is None:
            evalue = ()
        elif not isinstance(evalue, tuple):
            evalue = (evalue,)
        evalue = etype(*evalue)
    else:
        raise Exception, "?!"   # XXX
    return etype, evalue
normalize_exception = gateway.app2interp(app_normalize_exception)


class FinallyBlock(FrameBlock):
    """A try:finally: block.  Stores the position of the exception handler."""

    def cleanup(self, frame):
        # upon normal entry into the finally: part, the standard Python
        # bytecode pushes a single None for END_FINALLY.  In our case we
        # always push three values into the stack: the wrapped ctlflowexc,
        # the exception value and the exception type (which are all None
        # here).
        self.cleanupstack(frame)
        # one None already pushed by the bytecode
        frame.valuestack.push(frame.space.w_None)
        frame.valuestack.push(frame.space.w_None)

    def unroll(self, frame, unroller):
        # any abnormal reason for unrolling a finally: triggers the end of
        # the block unrolling and the entering the finally: handler.
        # see comments in cleanup().
        self.cleanupstack(frame)
        frame.valuestack.push(frame.space.wrap(unroller))
        frame.valuestack.push(frame.space.w_None)
        frame.valuestack.push(frame.space.w_None)
        frame.next_instr = self.handlerposition   # jump to the handler
        raise StopUnrolling


### Internal exceptions that change the control flow ###
### and (typically) unroll the block stack           ###

class ControlFlowException(Exception):
    """Abstract base class for interpreter-level exceptions that
    instruct the interpreter to change the control flow and the
    block stack.

    The concrete subclasses correspond to the various values WHY_XXX
    values of the why_code enumeration in ceval.c:

		WHY_NOT,	OK, not this one :-)
		WHY_EXCEPTION,	SApplicationException
		WHY_RERAISE,	we don't think this is needed
		WHY_RETURN,	SReturnValue
		WHY_BREAK,	SBreakLoop
		WHY_CONTINUE,	SContinueLoop
		WHY_YIELD	SYieldValue

    """
    def action(self, frame, last_instr, executioncontext):
        "Default unroller implementation."
        try:
            while not frame.blockstack.empty():
                block = frame.blockstack.pop()
                block.unroll(frame, self)
            self.emptystack(frame)
        except StopUnrolling:
            pass

    def emptystack(self, frame):
        "Default behavior when the block stack is exhausted."
        # could occur e.g. when a BREAK_LOOP is not actually within a loop
        raise BytecodeCorruption, "block stack exhausted"

class SApplicationException(ControlFlowException):
    """Unroll the stack because of an application-level exception
    (i.e. an OperationException)."""
    def emptystack(self, frame):
        # propagate the exception to the caller
        operationerr, tb = self.args
        raise operationerr.__class__, operationerr, tb

class SBreakLoop(ControlFlowException):
    """Signals a 'break' statement."""

class SContinueLoop(ControlFlowException):
    """Signals a 'continue' statement.
    Argument is the bytecode position of the beginning of the loop."""

class SReturnValue(ControlFlowException):
    """Signals a 'return' statement.
    Argument is the wrapped object to return."""
    def emptystack(self, frame):
        w_returnvalue = self.args[0]
        raise ExitFrame(w_returnvalue)

class StopUnrolling(Exception):
    "Signals the end of the block stack unrolling."

class ExitFrame(Exception):
    """Signals the end of the frame execution.
    The argument is the returned or yielded value, already wrapped."""

class BytecodeCorruption(ValueError):
    """Detected bytecode corruption.  Never caught; it's an error."""


