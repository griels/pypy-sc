import sys
from pypy.interpreter.miscutils import Stack
from pypy.interpreter.error import OperationError

class ExecutionContext:
    """An ExecutionContext holds the state of an execution thread
    in the Python interpreter."""

    def __init__(self, space):
        self.space = space
        self.framestack = Stack()
        self.w_tracefunc = None
        self.w_profilefunc = None
        self.is_tracing = 0
        self.ticker = 0
        self.compiler = space.createcompiler()

    def enter(self, frame):
        if self.framestack.depth() > self.space.sys.recursionlimit:
            raise OperationError(self.space.w_RuntimeError,
                                 self.space.wrap("maximum recursion depth exceeded"))
        try:
            frame.f_back = self.framestack.top()
        except IndexError:
            frame.f_back = None

        if not frame.hide():
            self.framestack.push(frame)

    def leave(self, frame):
        if self.w_profilefunc:
            self._trace(frame, 'leaveframe', None)
                
        if not frame.hide():
            self.framestack.pop()

    def get_builtin(self):
        try:
            return self.framestack.top().builtin
        except IndexError:
            return self.space.builtin

    # XXX this one should probably be dropped in favor of a module
    def make_standard_w_globals(self):
        "Create a new empty 'globals' dictionary."
        w_key = self.space.wrap("__builtins__")
        w_value = self.space.wrap(self.get_builtin())
        w_globals = self.space.newdict([(w_key, w_value)])
        return w_globals

    def call_trace(self, frame):
        "Trace the call of a function"
        self._trace(frame, 'call', self.space.w_None)

    def return_trace(self, frame, w_retval):
        "Trace the return from a function"
        self._trace(frame, 'return', w_retval)

    def bytecode_trace(self, frame):
        "Trace function called before each bytecode."
        self.decrease_ticker_bytecode_trace()
        if frame.w_f_trace is not None:
            self.do_bytecode_trace(frame)

    def decrease_ticker_bytecode_trace(self):
        # First, call yield_thread() before each Nth bytecode,
        #     as selected by sys.setcheckinterval()
        ticker = self.ticker
        if ticker <= 0:
            self.space.threadlocals.yield_thread()
            ticker = self.space.sys.checkinterval
        self.ticker = ticker - 1


    def do_bytecode_trace(self, frame):
        # Tracing logic
        if self.is_tracing:
            return
        code = getattr(frame, 'pycode')
        if frame.instr_lb <= frame.last_instr < frame.instr_ub:
            if frame.last_instr <= frame.instr_prev:
                # We jumped backwards in the same line.
                self._trace(frame, 'line', self.space.w_None)
        else:
            size = len(code.co_lnotab) / 2
            addr = 0
            line = code.co_firstlineno
            p = 0
            lineno = code.co_lnotab
            while size > 0:
                c = ord(lineno[p])
                if (addr + c) > frame.last_instr:
                    break
                addr += c
                if c:
                    frame.instr_lb = addr

                line += ord(lineno[p + 1])
                p += 2
                size -= 1

            if size > 0:
                while True:
                    size -= 1
                    if size < 0:
                        break
                    addr += ord(lineno[p])
                    if ord(lineno[p + 1]):
                        break
                    p += 2
                frame.instr_ub = addr
            else:
                frame.instr_ub = sys.maxint

            if frame.instr_lb == frame.last_instr: # At start of line!
                frame.f_lineno = line
                self._trace(frame, 'line', self.space.w_None)

        frame.instr_prev = frame.last_instr
            
    def exception_trace(self, frame, operationerr):
        "Trace function called upon OperationError."
        operationerr.record_interpreter_traceback()
        space = self.space
        self._trace(frame, 'exception', None, operationerr)
        #operationerr.print_detailed_traceback(self.space)

    def sys_exc_info(self): # attn: the result is not the wrapped sys.exc_info() !!!
        """Implements sys.exc_info().
        Return an OperationError instance or None."""
        for i in range(self.framestack.depth()):
            frame = self.framestack.top(i)
            if frame.last_exception is not None:
                return frame.last_exception
        return None

    def settrace(self, w_func):
        """Set the global trace function."""
        if self.space.is_w(w_func, self.space.w_None):
            self.w_tracefunc = None
        else:
            self.w_tracefunc = w_func

    def setprofile(self, w_func):
        """Set the global trace function."""
        if self.space.is_w(w_func, self.space.w_None):
            self.w_profilefunc = None
        else:
            self.w_profilefunc = w_func

    def call_tracing(self, w_func, w_args):
        is_tracing = self.is_tracing
        self.is_tracing = 0
        try:
            return self.space.call(w_func, w_args)
        finally:
            self.is_tracing = is_tracing

    def _trace(self, frame, event, w_arg, operr=None):
        if self.is_tracing or frame.hide():
            return

        space = self.space
        
        # Tracing cases
        if event == 'call':
            w_callback = self.w_tracefunc
        else:
            w_callback = frame.w_f_trace

        if w_callback is not None and event != "leaveframe":
            if operr is not None:
                w_arg =  space.newtuple([operr.w_type, operr.w_value,
                                     space.wrap(operr.application_traceback)])

            self.is_tracing += 1
            try:
                try:
                    w_result = space.call_function(w_callback, space.wrap(frame), space.wrap(event), w_arg)
                    if space.is_w(w_result, space.w_None):
                        frame.w_f_trace = None
                    else:
                        frame.w_f_trace = w_result
                except:
                    self.settrace(space.w_None)
                    frame.w_f_trace = None
                    raise
            finally:
                self.is_tracing -= 1

        # Profile cases
        if self.w_profilefunc is not None:
            if event not in ['leaveframe', 'call']:
                return

            last_exception = None
            if event == 'leaveframe':
                last_exception = frame.last_exception
                event = 'return'

            assert self.is_tracing == 0 
            self.is_tracing += 1
            try:
                try:
                    w_result = space.call_function(self.w_profilefunc,
                                                        space.wrap(frame),
                                                        space.wrap(event), w_arg)
                except:
                    self.w_profilefunc = None
                    raise

            finally:
                frame.last_exception = last_exception
                self.is_tracing -= 1

