import testsupport

class TestInterpreter(testsupport.TestCase):

    def codetest(self, source, functionname, args):
        """Compile and run the given code string, and then call its function
        named by 'functionname' with arguments 'args'."""
        from pypy.interpreter import baseobjspace, executioncontext, pyframe
        space = self.space

        compile = space.builtin.compile
        w = space.wrap
        w_code = compile(w(source), w('<string>'), w('exec'), w(0), w(0))

        ec = executioncontext.ExecutionContext(space)

        w_tempmodule = space.newmodule(w("__temp__"))
        w_glob = space.getattr(w_tempmodule, w("__dict__"))
        space.setitem(w_glob, w("__builtins__"), space.w_builtins)
        
        frame = pyframe.PyFrame(space, space.unwrap(w_code), w_glob, w_glob)
        ec.eval_frame(frame)

        wrappedargs = w(args)
        wrappedfunc = space.getitem(w_glob, w(functionname))
        wrappedkwds = space.newdict([])
        try:
            w_output = space.call(wrappedfunc, wrappedargs, wrappedkwds)
        except baseobjspace.OperationError, e:
            e.print_detailed_traceback(space)
            return '<<<%s>>>' % e.errorstr(space)
        else:
            return space.unwrap(w_output)

    def setUp(self):
        self.space = testsupport.objspace()

    def test_trivial(self):
        x = self.codetest('''
def g(): return 42''', 'g', [])
        self.assertEquals(x, 42)

    def test_trivial_call(self):
        x = self.codetest('''
def f(): return 42
def g(): return f()''', 'g', [])
        self.assertEquals(x, 42)

    def test_trivial_call2(self):
        x = self.codetest('''
def f(): return 1 + 1
def g(): return f()''', 'g', [])
        self.assertEquals(x, 2)

    def test_print(self):
        x = self.codetest('''
def g(): print 10''', 'g', [])
        self.assertEquals(x, None)

    def test_identity(self):
        x = self.codetest('''
def g(x): return x''', 'g', [666])
        self.assertEquals(x, 666)

    def test_exception_trivial(self):
        x = self.codetest('''
def f():
    try:
        raise Exception()
    except Exception, e:
        return 1
    return 2
''', 'f', [])
        self.assertEquals(x, 1)

    def XXXtest_exception(self):
        """ exception raising currently semi-broken """
        x = self.codetest('''
def f():
    try:
        raise Exception, 1
    except Exception, e:
        return e.args[0]
''', 'f', [])
        self.assertEquals(x, 1)

    def test_finally(self):
        code = '''
def f(a):
    try:
        if a:
            raise Exception
        a = -12
    finally:
        return a
'''
        self.assertEquals(self.codetest(code, 'f', [0]), -12)
        self.assertEquals(self.codetest(code, 'f', [1]), 1)

    def XXXtest_raise(self):
        """ depends on being able to import types """
        x = self.codetest('''
def f():
    raise 1
''', 'f', [])
        self.assertEquals(x, '<<<TypeError: exceptions must be classes, instances, or strings (deprecated), not int>>>')

    def XXXtest_except2(self):
        """ depends on being able to import types """
        x = self.codetest('''
def f():
    try:
        z = 0
        try:
            "x"+1
        except TypeError, e:
            z = 5
            raise e
    except TypeError:
        return z
''', 'f', [])
        self.assertEquals(x, 5)

    def test_except3(self):
        code = '''
def f(v):
    z = 0
    try:
        z = 1//v
    except ZeroDivisionError, e:
        z = "infinite result"
    return z
'''
        self.assertEquals(self.codetest(code, 'f', [2]), 0)
        self.assertEquals(self.codetest(code, 'f', [0]), "infinite result")
        ess = "TypeError: unsupported operand type"
        res = self.codetest(code, 'f', ['x'])
        self.failUnless(res.index(ess) >= 0)
        # the following (original) test was a bit too strict...:
        # self.assertEquals(self.codetest(code, 'f', ['x']), "<<<TypeError: unsupported operand type(s) for //: 'int' and 'str'>>>")

    def test_break(self):
        code = '''
def f(n):
    total = 0
    for i in range(n):
        try:
            if i == 4:
                break
        finally:
            total += i
    return total
'''
        self.assertEquals(self.codetest(code, 'f', [4]), 1+2+3)
        self.assertEquals(self.codetest(code, 'f', [9]), 1+2+3+4)

    def test_continue(self):
        code = '''
def f(n):
    total = 0
    for i in range(n):
        try:
            if i == 4:
                continue
        finally:
            total += 100
        total += i
    return total
'''
        self.assertEquals(self.codetest(code, 'f', [4]), 1+2+3+400)
        self.assertEquals(self.codetest(code, 'f', [9]),
                          1+2+3 + 5+6+7+8+900)


if __name__ == '__main__':
    testsupport.main()
