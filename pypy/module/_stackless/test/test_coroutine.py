from pypy.conftest import gettestobjspace, skip_on_missing_buildoption
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

    def test_pickle_coroutine_frame(self):
        #skip('passes in interactive interpreter but not here :/')
        # this requires py.magic.greenlet!
        import pickle, sys, new
        mod = new.module('mod')
        try: 
            sys.modules['mod'] = mod
            exec '''
import sys, _stackless as stackless

def f():
        global the_frame
        the_frame = sys._getframe()
        main_coro.switch()

co = stackless.coroutine()
main_coro = stackless.coroutine.getcurrent()
co.bind(f)
co.switch()
''' in mod.__dict__
            pckl = pickle.dumps(mod.the_frame)
            #co2 = pickle.loads(pckl)
        finally:
            del sys.modules['mod']

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
        skip("test is failing for atm unknown reasons")
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

    def test_finished(self):
        skip('should a coroutine be a zombie after being done?')
        import _stackless as stackless
        co = stackless.coroutine()
        def f():
            pass
        co.bind(f)
        co.switch()
        # doing an assert here runs into some (infinite looking)
        # cycle.
        # Lots of "GC Warning: Finalization cycle involving xxxx"
        if not co.is_zombie:
            raise Exception('co should be a zombie now')

    def test_kill(self):
        import _stackless as stackless
        co = stackless.coroutine()
        def f():
            pass
        co.bind(f)
        assert co.is_alive
        co.kill()
        assert not co.is_alive
