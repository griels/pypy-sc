import autopath, os
from py.process import cmdexec 
from pypy.tool.udir import udir
from pypy.translator.java.genjava import GenJava
from pypy.translator.test import snippet
from pypy.translator.translator import Translator


class TestNoTypeCGenTestCase:

    objspacename = 'flow'

    def build_jfunc(self, func):
        try: func = func.im_func
        except AttributeError: pass
        t = Translator(func)
        t.simplify()
        name = func.func_name
        self.jdir = udir.mkdir(name)
        self.gen = GenJava(self.jdir, t)

    def check(self, inputargs, expectedresult):
        self.gen.gen_test_class(inputargs, expectedresult)
        cwd = os.getcwd()
        try:
            os.chdir(str(self.jdir))
            cmdexec('javac *.java')
            assert cmdexec('java test').strip() == 'OK'
        finally:
            os.chdir(cwd)

    def test_simple_func(self):
        self.build_jfunc(snippet.simple_func)
        self.check([123], 124)

    def test_if_then_else(self):
        self.build_jfunc(snippet.if_then_else)
        self.check([2,3,4], 3)
        self.check([0,3,4], 4)
        self.check([-1,3,4], 3)

    def test_two_plus_two(self):
        self.build_jfunc(snippet.two_plus_two)
        self.check([], 4)

    def test_sieve_of_eratosthenes(self):
        self.build_jfunc(snippet.sieve_of_eratosthenes)
        self.check([], 1028)
