import py
from pypy.translator.jvm.test.runtest import JvmTest
from pypy.rpython.test.test_rfloat import BaseTestRfloat

class TestJvmFloat(JvmTest, BaseTestRfloat):
    def test_parse_float(self):
        ex = ['', '    ', '0', '1', '-1.5', '1.5E2', '2.5e-1', ' 0 ', '?']
        def fn(i):
            s = ex[i]
            try:
                return float(s)
            except ValueError:
                return -999.0
        
        for i in range(len(ex)):
            expected = fn(i)
            res = self.interpret(fn, [i])
            assert res == expected