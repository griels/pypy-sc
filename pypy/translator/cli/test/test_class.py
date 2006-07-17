import py
from pypy.translator.cli.test.runtest import CliTest
from pypy.rpython.test.test_rclass import BaseTestRclass
from pypy.rpython.test.test_rspecialcase import BaseTestRspecialcase

class TestCliClass(CliTest, BaseTestRclass):
    def test_abstract_method(self):
        class Base:
            pass
        class A(Base):
            def f(self, x):
                return x+1
        class B(Base):
            def f(self, x):
                return x+2
        def call(obj, x):
            return obj.f(x)
        def fn(x):
            a = A()
            b = B()
            return call(a, x) + call(b, x)
        assert self.interpret(fn, [0]) == 3

    def test_same_name(self):
        class A:
            pass
        B=A
        class A:
            pass
        assert A is not B
        assert A.__name__ == B.__name__
        def fn():
            obj1 = A()
            obj2 = B()
        self.interpret(fn, [])

class TestCliSpecialCase(CliTest, BaseTestRspecialcase):
    pass
