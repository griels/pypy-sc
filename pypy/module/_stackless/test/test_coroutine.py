from pypy.conftest import gettestobjspace
from py.test import skip

# no real testing possible without compiling stackless pypy
#

class AppTest_Coroutine:

    def setup_class(cls):
        space = gettestobjspace(usemodules=('_stackless',))
        cls.space = space

    def test_pickle_coroutine_empty(self):
        # this test is limited to basic pickling.
        # real stacks can only tested with a stackless pypy build.
        import _stackless as stackless
        co = stackless.coroutine()
        import pickle
        pckl = pickle.dumps(co)
        co2 = pickle.loads(pckl)
        # the empty unpickled coroutine can still be used:
        result = []
        co2.bind(result.append, 42)
        co2.switch()
        assert result == [42]

    def test_pickle_coroutine_bound(self):
        import pickle
        import _stackless
        lst = [4]
        co = _stackless.coroutine()
        co.bind(lst.append, 2)
        pckl = pickle.dumps((co, lst))

        (co2, lst2) = pickle.loads(pckl)
        assert lst2 == [4]
        co2.switch()
        assert lst2 == [4, 2]

    def test_raise_propagate(self):
        import _stackless as stackless
        co = stackless.coroutine()
        def f():
            return 1/0
        co.bind(f)
        try:
            co.switch()
        except ZeroDivisionError:
            pass
        else:
            raise AssertionError("exception not propagated")

    def test_strange_test(self):
        from _stackless import coroutine
        def f():
            print "in new coro"
            return 42
        def create():
            b = coroutine()
            b.bind(f)
            print "bound"
            b.switch()
            print "switched"
            return b
        a = coroutine()
        a.bind(create)
        b = a.switch()
        # now b.parent = a
        def nothing():
            pass
        a.bind(nothing)
        def kill():
            # this sets a.parent = b
            a.kill()
        b.bind(kill)
        b.switch()

    def test_kill(self):
        import _stackless as stackless
        co = stackless.coroutine()
        def f():
            pass
        co.bind(f)
        assert co.is_alive
        co.kill()
        assert not co.is_alive

    def test_bogus_bind(self):
        import _stackless as stackless
        co = stackless.coroutine()
        def f():
            pass
        co.bind(f)
        raises(ValueError, co.bind, f)
