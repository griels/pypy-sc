
import autopath
import os
from pypy.interpreter.extmodule import BuiltinModule

class TestBuiltinModule: 
    def test_foomodule(self):
        space = self.space
        sourcefile = os.path.join(autopath.this_dir, 'foomodule.py')
        m = BuiltinModule(space, 'foo', sourcefile=sourcefile)
        w = space.wrap
        w_m = space.wrap(m)
        assert self.space.eq_w(space.getattr(w_m, w('__name__')), w('foo'))
        assert self.space.eq_w(space.getattr(w_m, w('__file__')), w(sourcefile))
        # check app-level definitions
        assert self.space.eq_w(m.w_foo, space.w_Ellipsis)
        assert self.space.eq_w(space.getattr(w_m, w('foo1')), space.w_Ellipsis)
        assert self.space.eq_w(space.getattr(w_m, w('foo')), space.w_Ellipsis)
        assert self.space.eq_w(space.call_method(w_m, 'bar', w(4), w(3)), w(12))
        assert self.space.eq_w(space.getattr(w_m, w('foo2')), w('hello'))
        assert self.space.eq_w(space.getattr(w_m, w('foo3')), w('hi, guido!'))
        # check interp-level definitions
        assert self.space.eq_w(m.w_foo2, w('hello'))
        assert self.space.eq_w(m.foobuilder(w('xyzzy')), w('hi, xyzzy!'))
        assert self.space.eq_w(m.fortytwo, w(42))
