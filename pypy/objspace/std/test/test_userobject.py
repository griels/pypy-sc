import autopath
from pypy.tool import testit

class TestUserObject(testit.AppTestCase):
    def setUp(self):
        self.space = testit.objspace('std')

    def test_emptyclass(self):
        class empty: pass
        inst = empty()
        self.failUnless(isinstance(inst, empty))
        inst.attr=23
        self.assertEquals(inst.attr,23)

    def test_subclassing(self):
        for base in tuple, list, dict, str, int, float:
            try:
                class subclass(base): pass
                stuff = subclass()
            except:
                print 'not subclassable:', base
                if base is not dict:  # XXX must be fixed
                    raise
            else:
                self.failUnless(isinstance(stuff, base))

    def test_subclasstuple(self):
        class subclass(tuple): pass
        stuff = subclass()
        self.failUnless(isinstance(stuff, tuple))
        stuff.attr = 23
        self.assertEquals(stuff.attr,23)
        self.assertEquals(len(stuff),0)
        result = stuff + (1,2,3)
        self.assertEquals(len(result),3)

    def test_subsubclass(self):
        class base:
            baseattr = 12
        class derived(base):
            derivedattr = 34
        inst = derived()
        self.failUnless(isinstance(inst, base))
        self.assertEquals(inst.baseattr,12)
        self.assertEquals(inst.derivedattr,34)

    def test_descr_get(self):
        class C:
            class desc:
                def __get__(self, ob, cls=None):
                    return 42
            prop = desc()
        self.assertEquals(C().prop, 42)

    def test_descr_set(self):
        class C:
            class desc:
                def __set__(self, ob, val):
                    ob.wibble = val
            prop = desc()
        c = C()
        c.prop = 32
        self.assertEquals(c.wibble, 32)

    def test_descr_delete(self):
        class C:
            class desc:
                def __set__(self, ob, val):
                    oogabooga
                def __delete__(self, ob):
                    ob.wibble = 22
            prop = desc()
        c = C()
        del c.prop
        self.assertEquals(c.wibble, 22)

    def test_class_setattr(self):
        class C:
            pass
        C.a = 1
        self.assert_(hasattr(C, 'a'))
        self.assertEquals(C.a, 1)

    def test_add(self):
        class C:
            def __add__(self, other):
                return self, other
        c1 = C()
        self.assertEquals(c1+3, (c1, 3))

    def test_call(self):
        class C:
            def __call__(self, *args):
                return args
        c1 = C()
        self.assertEquals(c1(), ())
        self.assertEquals(c1(5), (5,))
        self.assertEquals(c1("hello", "world"), ("hello", "world"))

if __name__ == '__main__':
    testit.main()
