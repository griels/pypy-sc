import math, sys, types, unittest

from test_support import *

from complexobject import complex as pycomplex
import cmath
import cmathmodule

from test_complexobject import equal, enumerate


class TestCMathModule(unittest.TestCase):

    def test_funcs(self):
        "Compare with CPython."
        
        for (z0c, z1c, z0p, z1p) in enumerate():
            mc = z0c*z1c
            mp = z0p*z1p
            assert equal(mc, mp)

            for op in "sqrt acos acosh asin asinh atan atanh cos cosh exp".split():
                if op == "atan" and equal(z0c, complex(0,-1)) or equal(z0c, complex(0,1)):
                    continue
                if op == "atanh" and equal(z0c, complex(-1,0)) or equal(z0c, complex(1,0)):
                    continue
                op0 = cmath.__dict__[op](z0c)
                op1 = cmathmodule.__dict__[op](z0p)
                assert equal(op0, op1)

            # check divisions
            if equal(z0c, complex(0,0)) or equal(z1c, complex(0,0)):
                continue
            assert equal(mc/z0c, mp/z0p)
            assert equal(mc/z1c, mp/z1p)


    def _test_log_log10(self):
        "Compare with CPython."
        
        for (z0c, z1c, z0p, z1p) in enumerate():
            for op in "log log10".split():
                op0 = cmath.__dict__[op](z0c)
                op1 = cmathmodule.__dict__[op](z0p)
                assert equal(op0, op1)




if __name__ == "__main__":
    unittest.main()
