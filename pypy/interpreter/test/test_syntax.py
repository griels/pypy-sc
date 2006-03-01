import py

def splitcases(s):
    lines = [line.rstrip() for line in s.split('\n')]
    s = '\n'.join(lines)
    result = []
    for case in s.split('\n\n'):
        if case.strip():
            result.append(str(py.code.Source(case))+'\n')
    return result


VALID = splitcases("""

    def f():
        def g():
            global x
            exec "hi"
            x

    def f():
        def g():
            global x
            from a import *
            x

    def f(x):
        def g():
            global x
            exec "hi"
            x

    def f(x):
        def g():
            global x
            from a import *
            x

    def f():
        def g():
            from a import *

    def f():
        def g():
            exec "hi"

    def f():
        from a import *

    def f():
        exec "hi"

    def f():
        from a import *
        def g():
            global x
            x

    def f():
        exec "hi"
        def g():
            global x
            x

    def f():
        from a import *
        def g(x):
            x

    def f():
        exec "hi"
        def g(x):
            x

    def f():
        from a import *
        lambda x: x

    def f():
        exec "hi"
        lambda x: x

    def f():
        from a import *
        x

    def f():
        exec "hi"
        x

    def f():
        from a import *
        (i for i in x)

    def f():
        exec "hi"
        (i for i in x)

    def f():
        class g:
            exec "hi"
            x

    def f(x):
        class g:
            exec "hi"
            x

    def f():
        class g:
            from a import *
            x

    def f(x):
        class g:
            from a import *
            x

""")


INVALID = splitcases("""

    def f():
        def g():
            exec "hi"
            x

    def f(x):
        def g():
            exec "hi"
            x

    def f():
        def g():
            from a import *
            x

    def f(x):
        def g():
            from a import *
            x

    def f():
        exec "hi"
        def g():
            x

    def f():
        exec "hi"
        lambda x: y

    def f():
        from a import *
        def g():
            x

    def f():
        from a import *
        lambda x: y

    def f():
        exec "hi"
        class g:
            x

    def f():
        from a import *
        class g:
            x

    def f():
        exec "hi"
        class g:
            def h():
                x

    def f():
        from a import *
        class g:
            def h():
                x

    def f(x):
        exec "hi"
        class g:
            x

    def f(x):
        from a import *
        class g:
            x

    def f(x):
        exec "hi"
        class g:
            def h():
                x

    def f(x):
        from a import *
        class g:
            def h():
                x

    def f():
        (i for i in x) = 10

""")


for i in range(len(VALID)):
    exec """def test_valid_%d(space):
                checkvalid(space, %r)
""" % (i, VALID[i])

for i in range(len(INVALID)):
    exec """def test_invalid_%d(space):
                checkinvalid(space, %r)
""" % (i, INVALID[i])


def checkvalid(space, s):
    try:
        space.call_function(space.builtin.get('compile'),
                            space.wrap(s),
                            space.wrap('?'),
                            space.wrap('exec'))
    except:
        print '\n' + s
        raise

def checkinvalid(space, s):
    from pypy.interpreter.error import OperationError
    try:
        try:
            space.call_function(space.builtin.get('compile'),
                                space.wrap(s),
                                space.wrap('?'),
                                space.wrap('exec'))
        except OperationError, e:
            if not e.match(space, space.w_SyntaxError):
                raise
        else:
            raise Exception("Should have raised SyntaxError")
    except:
        print '\n' + s
        raise


class AppTestCondExpr:

    def test_condexpr(self):
        for s, expected in [("x = 1 if True else 2", 1),
                            ("x = 1 if False else 2", 2)]:
            exec s
            assert x == expected

class AppTestWith:
    def test_with(self):

        s = """if 1:
        # from __future__ import with_statement
        class Context:
            def __init__(self):
                self.calls = list()
            def __context__(self):
                self.calls.append('__context__')
                return self
            def __enter__(self):
                self.calls.append('__enter__')
                pass
            def __exit__(self, exc_type, exc_value, exc_tb):
                self.calls.append('__exit__')
                pass
        acontext = Context()
        with acontext:
            pass
        """
        exec s

        assert acontext.calls == '__context__ __enter__ __exit__'.split()
        
if __name__ == '__main__':
    # only to check on top of CPython (you need 2.4)
    from py.test import raises
    for s in VALID:
        try:
            compile(s, '?', 'exec')
        except Exception, e:
            print '-'*20, 'FAILED TO COMPILE:', '-'*20
            print s
            print '%s: %s' % (e.__class__, e)
            print '-'*60
    for s in INVALID:
        try:
            raises(SyntaxError, compile, s, '?', 'exec')
        except Exception ,e:
            print '-'*20, 'UNEXPECTEDLY COMPILED:', '-'*20
            print s
            print '%s: %s' % (e.__class__, e)
            print '-'*60
