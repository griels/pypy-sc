import autopath
from pypy.tool import test
from pypy.objspace.trace import TraceObjSpace 
from pypy.interpreter.gateway import app2interp
from pypy.tool import pydis
    
class Test_TraceObjSpace(test.IntTestCase):

    def setUp(self):
        self.space = test.objspace('trivial')

    def tearDown(self):
        pass

    def perform_trace(self, app_func):
        tspace = TraceObjSpace(self.space)
        func_gw = app2interp(app_func) 
        func = func_gw.get_function(tspace)
        tspace.settrace()
        func() 
        res = tspace.getresult()
        return res 

    def test_simpletrace(self):
        def app_f(): 
            pass
        res = self.perform_trace(app_f)
        disresult = pydis.pydis(app_f)
        self.assertEquals(disresult._bytecodes, list(res.getbytecodes()))
        #self.assertEquals(len(list(res.getoperations())), 0)

    def test_trace_oneop(self):
        def app_f(): 
            1 + 1
        w = self.space.wrap
        res = self.perform_trace(app_f)
        disresult = pydis.pydis(app_f)
        self.assertEquals(disresult._bytecodes, list(res.getbytecodes()))
        ops = list(res.getoperations())
        self.assert_(len(ops) > 0)
        #op = ops[0]
        #self.assertEquals(pydis.getbytecodename(op.bytecode), 'binary_add') # XXX 
        #self.assertEquals(op.name, 'add')
        #expected_w = (w(1), w(1))
        #self.assertEquals_w(op.args_w, expected_w)

if __name__ == '__main__':
    test.main()
