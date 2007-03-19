from pypy.module.pypyjit.test.conftest import option
from pypy.tool.udir import udir
import py
import sys, os

def setup_module(mod):
    if option.pypy_c is None:
        py.test.skip("pass --pypy_c!")
    mod.tmpdir = udir.join('pypy-jit')
    mod.tmpdir.ensure(dir=1)
    mod.counter = 0


def run_source(source, testcases):
    global counter
    source = py.code.Source(source)
    filepath = tmpdir.join('case%d.py' % counter)
    logfilepath = filepath.new(ext='.log')
    counter += 1
    f = filepath.open('w')
    print >> f, source
    # some support code...
    print >> f, py.code.Source("""
        import sys, pypyjit
        pypyjit.enable(main.func_code)

        def check(args, expected):
            print >> sys.stderr, 'trying:', args
            result = main(*args)
            print >> sys.stderr, 'got:', repr(result)
            assert result == expected
            assert type(result) is type(expected)
    """)
    for testcase in testcases * 2:
        print >> f, "check(%r, %r)" % testcase
    print >> f, "print 'OK :-)'"
    f.close()

    # we don't have os.popen() yet on pypy-c...
    if sys.platform.startswith('win'):
        py.test.skip("XXX this is not Windows-friendly")
    child_stdin, child_stdout = os.popen2('PYPYJITLOG="%s" "%s" "%s"' % (
        logfilepath, option.pypy_c, filepath))
    child_stdin.close()
    result = child_stdout.read()
    child_stdout.close()
    assert result
    assert result.splitlines()[-1].strip() == 'OK :-)'
    assert logfilepath.check()


def test_f():
    run_source("""
        def main(n):
            return (n+5)+6
    """,
               [([100], 111),
                ([-5], 6),
                ([sys.maxint], sys.maxint+11),
                ([-sys.maxint-5], long(-sys.maxint+6)),
                ])

def test_f1():
    run_source('''
        def main(n):
            "Arbitrary test function."
            i = 0
            x = 1
            while i<n:
                j = 0   #ZERO
                while j<=i:
                    j = j + 1
                    x = x + (i&j)
                i = i + 1
            return x
    ''',
               [([2117], 1083876708)])

def test_factorial():
    run_source('''
        def main(n):
            r = 1
            while n > 1:
                r *= n
                n -= 1
            return r
    ''',
               [([5], 120),
                ([20], 2432902008176640000L)])

def test_factorialrec():
    run_source('''
        def main(n):
            if n > 1:
                return n * main(n-1)
            else:
                return 1
    ''',
               [([5], 120),
                ([20], 2432902008176640000L)])

def test_richards():
    run_source('''
        import sys; sys.path[:] = %r
        from pypy.translator.goal import richards
        
        def main():
            return richards.main(iterations = 1)
    ''' % (sys.path,),
               [([], 42)])
