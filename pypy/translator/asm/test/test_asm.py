from pypy.translator.translator import Translator
import py
import os

class TestAsm(object):
        
    def setup_class(cls):
        if os.uname()[-1] != 'Power Macintosh':
            py.test.skip('asm generation only on PPC')
        cls.processor = 'ppc'
    
    def getcompiled(self, func, view=False):
        t = Translator(func, simplifying=True)
        # builds starting-types from func_defs 
        argstypelist = []
        if func.func_defaults is None:
            assert func.func_code.co_argcount == 0
            argtypes = []
        else:
            assert len(func.func_defaults) == func.func_code.co_argcount
            argtypes = list(func.func_defaults)
        a = t.annotate(argtypes)
        a.simplify()
        t.specialize()
        t.checkgraphs()
#        t.backend_optimizations()
        if view:
            t.view()
        return t.asmcompile(self.processor)

    def dont_test_trivial(self):
        def testfn():
            return None
        f = self.getcompiled(testfn)
        assert f() == None
        
    def test_int_add(self):
        def testfn(x=int, y=int):
            z = 1 + x
            if z > 0:
                return x + y + z
            else:
                return x + y - 42
        f = self.getcompiled(testfn)#, view=True)
        assert f(2, 3) == testfn(2, 3)
        assert f(-2, 3) == testfn(-2, 3)
        
        
