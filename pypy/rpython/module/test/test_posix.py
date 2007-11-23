import py
from pypy.rpython.test.tool import BaseRtypingTest, LLRtypeMixin, OORtypeMixin
from pypy.tool.udir import udir
import os
exec 'import %s as posix' % os.name

def setup_module(module):
    testf = udir.join('test.txt')
    module.path = testf.strpath

class BaseTestPosix(BaseRtypingTest):

    def setup_method(self, meth):
        # prepare/restore the file before each test
        testfile = open(path, 'wb')
        testfile.write('This is a test')
        testfile.close()

    def test_open(self):
        def f():
            ff = posix.open(path,posix.O_RDONLY,0777)
            return ff
        func = self.interpret(f,[])
        assert type(func) == int

    def test_fstat(self):
        def fo(fi):
            g = posix.fstat(fi)
            return g
        fi = os.open(path,os.O_RDONLY,0777)
        func = self.interpret(fo,[fi])
        stat = os.fstat(fi)
        for i in range(len(stat)):
            assert getattr(func, 'item%d' % i) == stat[i]


    def test_times(self):
        import py; py.test.skip("llinterp does not like tuple returns")
        from pypy.rpython.test.test_llinterp import interpret
        times = interpret(lambda: posix.times(), ())
        assert isinstance(times, tuple)
        assert len(times) == 5
        for value in times:
            assert isinstance(value, int)


    def test_lseek(self):
        def f(fi,pos):
            posix.lseek(fi,pos,0)
        fi = os.open(path,os.O_RDONLY,0777)
        func = self.interpret(f,[fi,5]) 
        res = os.read(fi,2)
        assert res =='is'

    def test_isatty(self):
        def f(fi):
            posix.isatty(fi)
        fi = os.open(path,os.O_RDONLY,0777)
        func = self.interpret(f,[fi])
        assert not func
        os.close(fi)
        func = self.interpret(f,[fi])
        assert not func

    def test_getcwd(self):
        def f():
            return posix.getcwd()
        res = self.interpret(f,[])
        cwd = os.getcwd()
        #print res.chars,cwd
        assert self.ll_to_string(res) == cwd

    def test_write(self):
        def f(fi):
            text = 'This is a test'
            return posix.write(fi,text)
        fi = os.open(path,os.O_WRONLY,0777)
        text = 'This is a test'
        func = self.interpret(f,[fi])
        os.close(fi)
        fi = os.open(path,os.O_RDONLY,0777)
        res = os.read(fi,20)
        assert res == text

    def test_read(self):
        def f(fi,len):
            return posix.read(fi,len)
        fi = os.open(path,os.O_WRONLY,0777)
        text = 'This is a test'
        os.write(fi,text)
        os.close(fi)
        fi = os.open(path,os.O_RDONLY,0777)
        res = self.interpret(f,[fi,20])
        assert self.ll_to_string(res) == text

    def test_close(self):
        def f(fi):
            return posix.close(fi)
        fi = os.open(path,os.O_WRONLY,0777)
        text = 'This is a test'
        os.write(fi,text)
        res = self.interpret(f,[fi])
        raises( OSError, os.fstat, fi)

    if hasattr(os, 'ftruncate'):
        def test_ftruncate(self):
            def f(fi,len):
                os.ftruncate(fi,len)
            fi = os.open(path,os.O_RDWR,0777)
            func = self.interpret(f,[fi,6]) 
            assert os.fstat(fi).st_size == 6

    if hasattr(os, 'getuid'):
        def test_getuid(self):
            def f():
                return os.getuid()
            assert self.interpret(f, []) == f()

    if hasattr(os, 'getgid'):
        def test_getgid(self):
            def f():
                return os.getgid()
            assert self.interpret(f, []) == f()


    if hasattr(os, 'setuid'):
        def test_os_setuid(self):
            def f():
                os.setuid(os.getuid())
                return os.getuid()
            assert self.interpret(f, []) == f()

class TestLLtype(BaseTestPosix, LLRtypeMixin):
    pass

class TestOOtype(BaseTestPosix, OORtypeMixin):
    def test_fstat(self):
        py.test.skip("ootypesystem does not support os.fstat")


def test_os_wstar():
    from pypy.rpython.module.ll_os import RegisterOs
    from pypy.translator.c.test.test_genc import compile
    for name in RegisterOs.w_star:
        if not hasattr(os, name):
            continue
        def fun(s):
            return getattr(os, name)(s)

        fun_c = compile(fun, [int])
        for value in [0, 1, 127, 128, 255]:
            res = fun_c(value)
            assert res == fun(value)

