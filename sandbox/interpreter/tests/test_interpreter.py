import unittest, sys, os
sys.path.insert(0, '..')

from pyframe import PyFrame
import trivialspace


class TestInterpreter(unittest.TestCase):

    def test_trivial1(self):
        # build frame
        space = trivialspace
        bytecode = compile('def f(x): return x+1', '', 'exec').co_consts[0]
        w_globals = space.wrap({'__builtins__': __builtins__})
        w_locals = space.wrap({})
        frame = PyFrame(space, bytecode, w_globals, w_locals)

        # perform call
        w_input = frame.space.wrap((5,))
        frame.setargs(w_input)
        w_output = frame.eval()
        self.assertEquals(frame.space.unwrap(w_output), 6)

    def test_trivial_call(self):
        # build frame
        space = trivialspace
        d = {}
        exec '''
def f(): return 42
def g(): return f()''' in d 
        w_globals = space.wrap(d)
        w_locals = space.wrap({})
        bytecode = d['g'].func_code
        frame = PyFrame(space, bytecode, w_globals, w_locals)

        # perform call
        w_input = frame.space.wrap(())
        frame.setargs(w_input)
        w_output = frame.eval()
        self.assertEquals(frame.space.unwrap(w_output), 42)

if __name__ == '__main__':
    unittest.main()
