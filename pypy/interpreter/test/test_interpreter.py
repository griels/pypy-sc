import autopath
import textwrap
from pypy.tool import testit

class TestInterpreter(testit.TestCase):

    def codetest(self, source, functionname, args):
        """Compile and run the given code string, and then call its function
        named by 'functionname' with arguments 'args'."""
        from pypy.interpreter import baseobjspace, executioncontext
        from pypy.interpreter import pyframe, gateway, module
        space = self.space

        compile = space.builtin.compile
        w = space.wrap
        w_code = compile(w(source), w('<string>'), w('exec'), w(0), w(0))

        ec = executioncontext.ExecutionContext(space)

        tempmodule = module.Module(space, w("__temp__"))
        w_glob = tempmodule.w_dict
        space.setitem(w_glob, w("__builtins__"), space.w_builtins)

        code = space.unwrap(w_code)
        code.exec_code(space, w_glob, w_glob)

        wrappedargs = [w(a) for a in args]
        wrappedfunc = space.getitem(w_glob, w(functionname))
        try:
            w_output = space.call_function(wrappedfunc, *wrappedargs)
        except baseobjspace.OperationError, e:
            #e.print_detailed_traceback(space)
            return '<<<%s>>>' % e.errorstr(space)
        else:
            return space.unwrap(w_output)

    def setUp(self):
        self.space = testit.objspace()

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

    def test_exception(self):
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

##     def test_raise(self):
##         x = self.codetest('''
## def f():
##     raise 1
## ''', 'f', [])
##         self.assertEquals(x, '<<<TypeError: exceptions must be instances or subclasses of Exception or strings (deprecated), not int>>>')

    def test_except2(self):
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
        self.failUnless(res.find(ess) >= 0)
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

    def test_import(self):
        # Regression test for a bug in PyInterpFrame.IMPORT_NAME: when an
        # import statement was executed in a function without a locals dict, a
        # plain unwrapped None could be passed into space.call_function causing
        # assertion errors later on.
        real_call_function = self.space.call_function
        def safe_call_function(w_obj, *arg_w):
            for arg in arg_w:
                assert arg is not None
            return real_call_function(w_obj, *arg_w)
        self.space.call_function = safe_call_function
        code = textwrap.dedent('''
            def f():
                import sys
            ''')
        self.codetest(code, 'f', [])

    def test_extended_arg(self):
        longexpr = 'x = x or ' + '-x' * 2500
        code = '''
def f(x):
    %s
    %s
    %s
    %s
    %s
    %s
    %s
    %s
    %s
    %s
    while x:
        x -= 1   # EXTENDED_ARG is for the JUMP_ABSOLUTE at the end of the loop
    return x
''' % ((longexpr,)*10)
        self.assertEquals(self.codetest(code, 'f', [3]), 0)


class AppTestInterpreter(testit.AppTestCase):
    def test_trivial(self):
        x = 42
        self.assertEquals(x, 42)

    def test_trivial_call(self):
        def f(): return 42
        self.assertEquals(f(), 42)

    def test_trivial_call2(self):
        def f(): return 1 + 1
        self.assertEquals(f(), 2)

    def test_print(self):
        import sys
        save = sys.stdout 
        class Out:
            def __init__(self):
                self.args = []
            def write(self, *args):
                self.args.extend(args)
        out = Out()
        try:
            sys.stdout = out
            print 10
            self.assertEquals(out.args, ['10','\n'])
        finally:
            sys.stdout = save

    def test_identity(self):
        def f(x): return x
        self.assertEquals(f(666), 666)


if __name__ == '__main__':
    testit.main()
