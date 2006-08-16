import autopath
from pypy.objspace.std.dictmultiobject import \
     W_DictMultiObject, setitem__DictMulti_ANY_ANY, getitem__DictMulti_ANY, \
     EmptyDictImplementation, RDictImplementation, StrDictImplementation, SmallDictImplementation
from pypy.conftest import gettestobjspace
from pypy.objspace.std.test import test_dictobject

class TestW_DictObject(test_dictobject.TestW_DictObject):
    def setup_class(cls):
        cls.space = gettestobjspace(**{"objspace.std.withmultidict": True})

class AppTest_DictObject(test_dictobject.AppTest_DictObject):
    def setup_class(cls):
        cls.space = gettestobjspace(**{"objspace.std.withmultidict": True})

class FakeSpace(test_dictobject.FakeSpace):
    def str_w(self, string):
        assert isinstance(string, str)
        return string

    def wrap(self, obj):
        return obj

class TestDictImplementation:
    def setup_method(self,method):
        self.space = FakeSpace()
        self.space.emptydictimpl = EmptyDictImplementation(self.space)
        self.space.DictObjectCls = W_DictMultiObject

    def test_stressdict(self):
        from random import randint
        d = self.space.DictObjectCls(self.space)
        N = 10000
        pydict = {}
        for i in range(N):
            x = randint(-N, N)
            setitem__DictMulti_ANY_ANY(self.space, d, x, i)
            pydict[x] = i
        for x in pydict:
            assert pydict[x] == getitem__DictMulti_ANY(self.space, d, x)

class TestRDictImplementation:
    ImplementionClass = RDictImplementation

    def setup_method(self,method):
        self.space = FakeSpace()
        self.space.emptydictimpl = EmptyDictImplementation(self.space)
        self.space.DictObjectCls = W_DictMultiObject
        self.string = self.space.str_w("fish")
        self.string2 = self.space.str_w("fish2")
        self.impl = self.get_impl()

    def get_impl(self):
        return self.ImplementionClass(self.space)

    def test_setitem(self):
        assert self.impl.setitem(self.string, 1000) is self.impl
        assert self.impl.get(self.string) == 1000

    def test_delitem(self):
        self.impl.setitem(self.string, 1000)
        self.impl.setitem(self.string2, 2000)
        assert self.impl.delitem(self.string) is self.impl
        assert self.impl.delitem(self.string2) is self.space.emptydictimpl

    def test_keys(self):
        self.impl.setitem(self.string, 1000)
        self.impl.setitem(self.string2, 2000)
        keys = self.impl.keys()
        keys.sort()
        assert keys == [self.string, self.string2]

    def test_values(self):
        self.impl.setitem(self.string, 1000)
        self.impl.setitem(self.string2, 2000)
        values = self.impl.values()
        values.sort()
        assert values == [1000, 2000]

    def test_items(self):
        self.impl.setitem(self.string, 1000)
        self.impl.setitem(self.string2, 2000)
        items = self.impl.items()
        items.sort()
        assert items == zip([self.string, self.string2], [1000, 2000])

    def test_devolve(self):
        impl = self.impl
        for x in xrange(100):
            impl = impl.setitem(self.space.str_w(str(x)), x)
            impl = impl.setitem(x, x)
        assert isinstance(impl, RDictImplementation)

class TestStrDictImplementation(TestRDictImplementation):
    ImplementionClass = StrDictImplementation

class TestSmallDictImplementation(TestRDictImplementation):
    ImplementionClass = SmallDictImplementation

    def get_impl(self):
        return self.ImplementionClass(self.space, self.string, self.string2)

