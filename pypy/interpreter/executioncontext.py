from pypy.interpreter.miscutils import getthreadlocals, Stack
from pypy.interpreter.error import OperationError

class ExecutionContext:
    """An ExecutionContext holds the state of an execution thread
    in the Python interpreter."""
    
    def __init__(self, space):
        # Note that self.framestack only contains PyFrames
        self.space = space
        self.framestack = Stack()
        self.stateDict = {}
        self.w_tracefunc = None
        self.is_tracing = 0

    def enter(self, frame):
        if self.framestack.depth() > self.space.sys.recursionlimit:
            raise OperationError(self.space.w_RuntimeError,
                                 self.space.wrap("maximum recursion depth exceeded"))
        locals = getthreadlocals()
        previous_ec = locals.executioncontext
        locals.executioncontext = self
        if self.framestack.empty():
            frame.f_back = None
        else:
            frame.f_back = self.framestack.top()
        self.framestack.push(frame)
        return previous_ec
    
    def leave(self, previous_ec):
        self.framestack.pop()
        locals = getthreadlocals()
        locals.executioncontext = previous_ec

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
        self._trace(self.framestack.top(), 'return', w_retval)

    def bytecode_trace(self, frame):
        "Trace function called before each bytecode."

    def exception_trace(self, operationerr):
        "Trace function called upon OperationError."
        operationerr.record_interpreter_traceback()
        exc_info = self.sys_exc_info()
        frame = self.framestack.top()
        self._trace(self.framestack.top(), 'exception',
                        exc_info)
        #operationerr.print_detailed_traceback(self.space)

    def sys_exc_info(self):
        """Implements sys.exc_info().
        Return an OperationError instance or None."""
        for i in range(self.framestack.depth()):
            frame = self.framestack.top(i)
            if frame.last_exception is not None:
                return frame.last_exception
        return None

    def get_state_dict(self):
        """A mechanism to store arbitrary per ExecutionContext data.
        Similar to cpython's PyThreadState_GetDict.
        """
        return self.stateDict

    def settrace(self, w_func):
        """Set the global trace function."""
        if self.space.is_true(self.space.is_(w_func, self.space.w_None)):
            self.w_tracefunc = None
        else:
            self.w_tracefunc = w_func

    def _trace(self, frame, event, w_arg):
        if event == 'call':
            w_callback = self.w_tracefunc
        else:
            w_callback = frame.w_f_trace
        if self.is_tracing or w_callback is None:
            return
        self.is_tracing += 1
        try:
            try:
                w_result = self.space.call_function(w_callback, self.space.wrap(frame), self.space.wrap(event), w_arg)
                if self.space.is_true(self.space.is_(w_result, self.space.w_None)):
                    frame.w_f_trace = None
                else:
                    frame.w_f_trace = w_result
            except:
                self.settrace(self.space.w_None)
                frame.w_f_trace = None
                raise
        finally:
            self.is_tracing -= 1
