import sys

class ExecutionContext:

    def __init__(self, space):
        self.space = space
        self.framestack = []

    def eval_frame(self, frame):
        __executioncontext__ = self
        self.framestack.append(frame)
        try:
            result = frame.eval(self)
        finally:
            self.framestack.pop()
        return result

    def get_w_builtins(self):
        if self.framestack:
            return self.framestack[-1].w_builtins
        else:
            return self.space.w_builtins

    def make_standard_w_globals(self):
        "Create a new empty 'globals' dictionary."
        w_key = self.space.wrap("__builtins__")
        w_value = self.get_w_builtins()
        w_globals = self.space.newdict([(w_key, w_value)])
        return w_globals

    def exception_trace(self, operationerr):
        "Trace function called upon OperationError."
        operationerr.record_interpreter_traceback()
        #operationerr.print_detailed_traceback(self.space)


class OperationError(Exception):
    """Interpreter-level exception that signals an exception that should be
    sent to the application level.

    OperationError instances have three public attributes (and no .args),
    w_type, w_value and w_traceback, which contain the wrapped type, value
    and traceback describing the exception."""

    def __init__(self, w_type, w_value, w_traceback=None):
        self.w_type = w_type
        self.w_value = w_value
        self.w_traceback = w_traceback
        self.debug_tb = None

    def match(self, space, w_check_class):
        "Check if this application-level exception matches 'w_check_class'."
        return space.is_true(space.exception_match(self.w_type, w_check_class))

    def __str__(self):
        "Convenience for tracebacks."
        return '[%s: %s]' % (self.w_type, self.w_value)

    def errorstr(self, space):
        "The exception class and value, as a string."
        exc_type  = space.unwrap(self.w_type)
        exc_value = space.unwrap(self.w_value)
        return '%s: %s' % (exc_type.__name__, exc_value)

    def record_interpreter_traceback(self):
        """Records the current traceback inside the interpreter.
        This traceback is only useful to debug the interpreter, not the
        application."""
        if self.debug_tb is None:
            self.debug_tb = sys.exc_info()[2]

    def print_application_traceback(self, space, file=None):
        "Dump a standard application-level traceback."
        if file is None: file = sys.stderr
        self.print_app_tb_only(file)
        print >> file, self.errorstr(space)

    def print_app_tb_only(self, file):
        tb = self.w_traceback
        if tb:
            import linecache
            tb = self.w_traceback[:]
            tb.reverse()
            print >> file, "Traceback (application-level):"
            for f, i in tb:
                co = f.bytecode
                lineno = offset2lineno(co, i)
                fname = co.co_filename
                if fname.startswith('<inline>\n'):
                    lines = fname.split('\n')
                    fname = lines[0].strip()
                    try:
                        l = lines[lineno]
                    except IndexError:
                        l = ''
                else:
                    l = linecache.getline(fname, lineno)
                print >> file, "  File", `fname`+',',
                print >> file, "line", lineno, "in", co.co_name
                if l:
                    if l.endswith('\n'):
                        l = l[:-1]
                    print >> file, l

    def print_detailed_traceback(self, space, file=None):
        """Dump a nice detailed interpreter- and application-level traceback,
        useful to debug the interpreter."""
        if file is None: file = sys.stderr
        self.print_app_tb_only(file)
        if self.debug_tb:
            import traceback
            interpr_file = LinePrefixer(file, '||')
            print >> interpr_file, "Traceback (interpreter-level):"
            traceback.print_tb(self.debug_tb, file=interpr_file)
        exc_type  = space.unwrap(self.w_type)
        exc_value = space.unwrap(self.w_value)
        print >> file, '(application-level)', exc_type.__name__+':', exc_value


class NoValue(Exception):
    """Raised to signal absence of value, e.g. in the iterator accessing
    method 'op.next()' of object spaces."""


# Utilities

def inlinecompile(source, symbol='exec'):
    """Compile the given 'source' string.
    This function differs from the built-in compile() because it abuses
    co_filename to store a copy of the complete source code.
    This lets OperationError.print_application_traceback() print the
    actual source line in the traceback."""
    return compile(source, '<inline>\n' + source, symbol)

def offset2lineno(c, stopat):
    tab = c.co_lnotab
    line = c.co_firstlineno
    addr = 0
    for i in range(0, len(tab), 2):
        addr = addr + ord(tab[i])
        if addr > stopat:
            break
        line = line + ord(tab[i+1])
    return line

class LinePrefixer:
    """File-like class that inserts a prefix string
    at the beginning of each line it prints."""
    def __init__(self, file, prefix):
        self.file = file
        self.prefix = prefix
        self.linestart = True
    def write(self, data):
        if self.linestart:
            self.file.write(self.prefix)
        if data.endswith('\n'):
            data = data[:-1]
            self.linestart = True
        else:
            self.linestart = False
        self.file.write(data.replace('\n', '\n'+self.prefix))
        if self.linestart:
            self.file.write('\n')
