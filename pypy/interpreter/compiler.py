"""
General classes for bytecode compilers.
Compiler instances are stored into 'space.getexecutioncontext().compiler'.
"""
from codeop import PyCF_DONT_IMPLY_DEDENT
from pypy.interpreter.error import OperationError


class Compiler:
    """Abstract base class for a bytecode compiler."""

    # The idea is to grow more methods here over the time,
    # e.g. to handle .pyc files in various ways if we have multiple compilers.

    def __init__(self, space):
        self.space = space

    def compile(self, source, filename, mode, flags):
        """Compile and return an pypy.interpreter.eval.Code instance."""
        raise NotImplementedError

    def getcodeflags(self, code):
        """Return the __future__ compiler flags that were used to compile
        the given code object."""
        return 0

    def compile_command(self, source, filename, mode, flags):
        """Same as compile(), but tries to compile a possibly partial
        interactive input.  If more input is needed, it returns None.
        """
        # Hackish default implementation based on the stdlib 'codeop' module.
        # See comments over there.
        space = self.space
        flags |= PyCF_DONT_IMPLY_DEDENT
        # Check for source consisting of only blank lines and comments
        if mode != "eval":
            in_comment = False
            for c in source:
                if c in ' \t\f\v':   # spaces
                    pass
                elif c == '#':
                    in_comment = True
                elif c in '\n\r':
                    in_comment = False
                elif not in_comment:
                    break    # non-whitespace, non-comment character
            else:
                source = "pass"     # Replace it with a 'pass' statement

        try:
            code = self.compile(source, filename, mode, flags)
            return code   # success
        except OperationError, err:
            if not err.match(space, space.w_SyntaxError):
                raise

        try:
            self.compile(source + "\n", filename, mode, flags)
            return None   # expect more
        except OperationError, err1:
            if not err1.match(space, space.w_SyntaxError):
                raise

        try:
            self.compile(source + "\n\n", filename, mode, flags)
            raise     # uh? no error with \n\n.  re-raise the previous error
        except OperationError, err2:
            if not err2.match(space, space.w_SyntaxError):
                raise

        if space.eq_w(err1.w_value, err2.w_value):
            raise     # twice the same error, re-raise

        return None   # two different errors, expect more


# ____________________________________________________________
# faked compiler

import __future__
compiler_flags = 0
for fname in __future__.all_feature_names:
    compiler_flags |= getattr(__future__, fname).compiler_flag


class CPythonCompiler(Compiler):
    """Faked implementation of a compiler, using the underlying compile()."""

    def compile(self, source, filename, mode, flags):
        flags |= __future__.generators.compiler_flag   # always on (2.2 compat)
        space = self.space
        try:
            # hack to make the flow space happy: 'warnings' should not look
            # like a Constant
            warnings = __import__('warnings')
            old_warn_explicit = warnings.warn_explicit 
            warnings.warn_explicit = self._warn_explicit
            try:
                c = compile(source, filename, mode, flags, True)
            finally:
                warnings.warn_explicit = old_warn_explicit
        # It would be nice to propagate all exceptions to app level,
        # but here we only propagate the 'usual' ones, until we figure
        # out how to do it generically.
        except SyntaxError,e:
            raise OperationError(space.w_SyntaxError,space.wrap(e.args))
        except ValueError,e:
            raise OperationError(space.w_ValueError,space.wrap(str(e)))
        except TypeError,e:
            raise OperationError(space.w_TypeError,space.wrap(str(e)))
        from pypy.interpreter.pycode import PyCode
        return space.wrap(PyCode(space)._from_code(c))

    def getcodeflags(self, code):
        from pypy.interpreter.pycode import PyCode
        if isinstance(code, PyCode):
            return code.co_flags & compiler_flags
        else:
            return 0

    def _warn_explicit(self, message, category, filename, lineno,
                       module=None, registry=None):
        if hasattr(category, '__bases__') and \
           issubclass(category, SyntaxWarning): 
            assert isinstance(message, str)
            space = self.space
            w_mod = space.sys.getmodule('warnings')
            if w_mod is not None: 
                w_dict = w_mod.getdict() 
                w_reg = space.call_method(w_dict, 'setdefault', 
                                          space.wrap("__warningregistry__"),     
                                          space.newdict([]))
                try: 
                    space.call_method(w_mod, 'warn_explicit', 
                                      space.wrap(message), 
                                      space.w_SyntaxWarning, 
                                      space.wrap(filename), 
                                      space.wrap(lineno), 
                                      space.w_None, 
                                      space.w_None) 
                except OperationError, e: 
                    if e.match(space, space.w_SyntaxWarning): 
                        raise OperationError(
                                space.w_SyntaxError, 
                                space.wrap(message))
                    raise 

    def setup_warn_explicit(self, warnings, prev=None):
        """
        this is a hack until we have our own parsing/compiling 
        in place: we bridge certain warnings to the applevel 
        warnings module to let it decide what to do with
        a syntax warning ... 
        """ 
        return old_warn_explicit 
