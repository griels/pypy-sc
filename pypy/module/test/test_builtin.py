import autopath

from pypy.tool import test

class TestBuiltinApp(test.AppTestCase):
    def setUp(self):
        self.space = test.objspace()
    
    def test_import(self):
        d = {}
        m = __import__('types', d, d, [])
        self.assertEquals(m.IntType, type(123))
        self.assertEquals(m.__name__, "types")

    def test_chr(self):
        self.assertEquals(chr(65), 'A')
        self.assertRaises(ValueError, chr, -1)
        self.assertRaises(TypeError, chr, 'a')

    def test_type_selftest(self):
        self.assert_(type(type) is type)

    def test_xrange_args(self):
        x = xrange(2)
        self.assertEquals(x.start, 0)
        self.assertEquals(x.stop, 2)
        self.assertEquals(x.step, 1)

        x = xrange(2,10,2)
        self.assertEquals(x.start, 2)
        self.assertEquals(x.stop, 10)
        self.assertEquals(x.step, 2)

        self.assertRaises(ValueError, xrange, 0, 1, 0) 

    def test_xrange_up(self):
        x = xrange(2)
        self.assertEquals(x.start, 0)
        self.assertEquals(x.stop, 2)
        self.assertEquals(x.step, 1)

        iter_x = iter(x)
        self.assertEquals(iter_x.next(), 0)
        self.assertEquals(iter_x.next(), 1)
        self.assertRaises(StopIteration, iter_x.next)

    def test_xrange_down(self):
        x = xrange(4,2,-1)

        iter_x = iter(x)
        self.assertEquals(iter_x.next(), 4)
        self.assertEquals(iter_x.next(), 3)
        self.assertRaises(StopIteration, iter_x.next)

    def test_cmp(self):
        self.assertEquals(cmp(9,9), 0)
        self.assert_(cmp(0,9) < 0)
        self.assert_(cmp(9,0) > 0)

class TestInternal(test.IntTestCase):

    def setUp(self):
        self.space = space = test.objspace()

    def get_builtin(self, name):
        w = self.space.wrap
        w_builtins = self.space.w_builtins
        w_obj = self.space.getitem(w_builtins, w(name))
        return w_obj
   
    def test_execfile(self):
        # we need cpython's tempfile currently to test 
        from tempfile import mktemp
        fn = mktemp()
        f = open(fn, 'w')
        print >>f, "i=42"
        f.close()

        try:
            w_execfile = self.get_builtin('execfile')
            space = self.space
            w_dict = space.newdict([])
            self.space.call(w_execfile, space.newtuple([
                space.wrap(fn), w_dict, space.w_None]), space.newdict([]))
            w_value = space.getitem(w_dict, space.wrap('i'))
            self.assertEqual_w(w_value, space.wrap(42))
        finally:
            import os
            os.remove(fn)

if __name__ == '__main__':
    test.main()
 
