import __future__
import autopath
import py
from pypy.interpreter.pycompiler import CPythonCompiler, Compiler
from pypy.interpreter.pycode import PyCode


class TestCompiler:
    def setup_method(self, method):
        self.compiler = CPythonCompiler(self.space)

    def test_compile(self):
        code = self.compiler.compile('6*7', '<hello>', 'eval', 0)
        assert isinstance(code, PyCode)
        assert code.co_filename == '<hello>'
        space = self.space
        w_res = code.exec_code(space, space.newdict([]), space.newdict([]))
        assert space.int_w(w_res) == 42

    def test_compile_command(self):
        c0 = self.compiler.compile_command('\t # hello\n ', '?', 'exec', 0)
        c1 = self.compiler.compile_command('print 6*7', '?', 'exec', 0)
        c2 = self.compiler.compile_command('if 1:\n  x\n', '?', 'exec', 0)
        assert c0 is not None
        assert c1 is not None
        assert c2 is not None
        c3 = self.compiler.compile_command('if 1:\n  x', '?', 'exec', 0)
        c4 = self.compiler.compile_command('x = (', '?', 'exec', 0)
        c5 = self.compiler.compile_command('x = (\n', '?', 'exec', 0)
        c6 = self.compiler.compile_command('x = (\n\n', '?', 'exec', 0)
        assert c3 is None
        assert c4 is None
        assert c5 is None
        assert c6 is None
        space = self.space
        space.raises_w(space.w_SyntaxError, self.compiler.compile_command,
                       'if 1:\n  x x', '?', 'exec', 0)

    def test_getcodeflags(self):
        code = self.compiler.compile('from __future__ import division\n',
                                     '<hello>', 'exec', 0)
        flags = self.compiler.getcodeflags(code)
        assert flags & __future__.division.compiler_flag
        # check that we don't get more flags than the compiler can accept back
        code2 = self.compiler.compile('print 6*7', '<hello>', 'exec', flags)
        # check that the flag remains in force
        flags2 = self.compiler.getcodeflags(code2)
        assert flags == flags2


class TestECCompiler(TestCompiler):
    def setup_method(self, method):
        self.compiler = self.space.getexecutioncontext().compiler
