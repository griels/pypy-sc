import unittest, sys
import testsupport
from pypy.interpreter import unittest_w
from pypy.objspace.std import noneobject as nobj
from pypy.objspace.std.objspace import *


class TestW_NoneObject(unittest_w.TestCase_w):

    def setUp(self):
        self.space = StdObjSpace()

    def tearDown(self):
        pass

    def test_equality(self):
        self.assertEqual_w(self.space.w_None, self.space.w_None)
    
    def test_inequality(self):
        neresult = self.space.ne(self.space.w_None, self.space.w_None)
        self.failIf_w(neresult)

    def test_false(self):
        self.failIf_w(self.space.w_None)
        

if __name__ == '__main__':
    unittest.main()
