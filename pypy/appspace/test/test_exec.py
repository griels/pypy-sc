"""Test the exec statement functionality.

New for PyPy - Could be incorporated into CPython regression tests.
"""
import autopath
from pypy.tool import test 

class TestExecStmt(test.AppTestCase):

    def setUp(self):
        self.space = test.objspace()

    def test_string(self):
        g = {}
        l = {}
        exec "a = 3" in g, l
        self.failUnlessEqual(l['a'], 3)

    def test_localfill(self):
        g = {}
        exec "a = 3" in g
        self.failUnlessEqual(g['a'], 3)
        
    def test_builtinsupply(self):
        g = {}
        exec "pass" in g
        self.failUnless(g.has_key('__builtins__'))

    def test_invalidglobal(self):
        def f():
            exec 'pass' in 1
        self.failUnlessRaises(TypeError,f)

    def test_invalidlocal(self):
        def f():
            exec 'pass' in {}, 2
        self.failUnlessRaises(TypeError,f)

    def test_codeobject(self):
        co = compile("a = 3", '<string>', 'exec')
        g = {}
        l = {}
        exec co in g, l
        self.failUnlessEqual(l['a'], 3)
        
##    # Commented out as PyPy give errors using open()
##    #     ["Not availible in restricted mode"]
##    def test_file(self):
##        fo = open("test_exec.py", 'r')
##        g = {}
##        exec fo in g
##        self.failUnless(g.has_key('TestExecStmt'))
        
    def test_implicit(self):
        a = 4
        exec "a = 3"
        self.failUnlessEqual(a,3)

    def test_tuplelocals(self):
        g = {}
        l = {}
        exec ("a = 3", g, l)
        self.failUnlessEqual(l['a'], 3)
        
    def test_tupleglobals(self):
        g = {}
        exec ("a = 3", g)
        self.failUnlessEqual(g['a'], 3)

    def test_exceptionfallthrough(self):
        def f():
            exec 'raise TypeError' in {}
        self.failUnlessRaises(TypeError,f)

if __name__ == "__main__":
    test.main()
