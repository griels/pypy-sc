import autopath
import os, sys, unittest, re, warnings, unittest, traceback
from unittest import TestCase, TestLoader

import pypy.interpreter.unittest_w
from pypy.tool.optik import make_option
from pypy.tool import optik, option
from pypy.tool.option import objspace

IntTestCase = pypy.interpreter.unittest_w.IntTestCase
AppTestCase = pypy.interpreter.unittest_w.AppTestCase
TestCase = IntTestCase

class MyTestSuite(unittest.TestSuite):
    def __call__(self, result):
        """ execute the tests, invokes underlyning unittest.__call__"""

        # XXX here is probably not the best place 
        #     to check for test/objspace mismatch 
        count = self.countTestCases()
        if not count:
            return result

        fm = getattr(self, 'frommodule','')
        if fm and fm.startswith('pypy.objspace.std') and \
           Options.spacename != 'std':
            sys.stderr.write("\n%s skip for objspace %r" % (
                fm, Options.spacename))
            return result

        if fm and Options.verbose==0:
            sys.stderr.write('\n%s [%d]' %(fm, count))
        result = unittest.TestSuite.__call__(self, result)
        return result

    def addTest(self, test, frommodule=None):
        if test.countTestCases()>0:
            test.frommodule = frommodule
            unittest.TestSuite.addTest(self, test)

    def __nonzero__(self):
        return self.countTestCases()>0


# register MyTestSuite to unittest
unittest.TestLoader.suiteClass = MyTestSuite

class MyTestResult(unittest.TestResult):
    def __init__(self):
        unittest.TestResult.__init__(self)
        self.successes = []
    def addError(self, test, err):
        # XXX not nice:
        from pypy.interpreter.baseobjspace import OperationError
        if isinstance(err[1], OperationError):
            if err[1].match(test.space, test.space.w_AssertionError):
                self.addFailure(test, err)
                return
        unittest.TestResult.addError(self, test, err)
    def addSuccess(self, test):
        self.successes.append(test)

class MyTextTestResult(unittest._TextTestResult):
    def addFailure(self, test, err):
        unittest._TextTestResult.addFailure(self, test, err)
    def munge(self, list, test, err):
        import StringIO
        from pypy.interpreter.baseobjspace import OperationError
        text1 = list.pop()[1]
        if isinstance(err[1], OperationError):
            sio = StringIO.StringIO()
            err[1].print_application_traceback(test.space, sio)
            text2 = sio.getvalue()
            
            list.append((test, text1 + "\nand at app-level:\n\n" + text2))
        else:
            list.append((test, text1))
        
    def addError(self, test, err):
        from pypy.interpreter.baseobjspace import OperationError
        if isinstance(err[1], OperationError):
            if err[1].match(test.space, test.space.w_AssertionError):
                self.addFailure(test, err)
                return
        unittest._TextTestResult.addError(self, test, err)
        self.munge(self.errors, test, err)
        
    def addFailure(self, test, err):
        unittest._TextTestResult.addFailure(self, test, err)
        self.munge(self.failures, test, err)

class CtsTestRunner:
    def run(self, test):
        import pickle

        output = sys.stdout
        result = MyTestResult()
        sso = sys.stdout
        sse = sys.stderr
        try:
            sys.stdout = open('/dev/null', 'w')
            sys.stderr = open('/dev/null', 'w')
            test(result)
        finally:
            sys.stdout = sso
            sys.stderr = sse

        ostatus = {}
        if os.path.exists('testcts.pickle'):
            ostatus = pickle.load(open('testcts.pickle','r'))

        status = {}

        for e in result.errors:
            name = e[0].__class__.__name__ + '.' + \
                   e[0]._TestCase__testMethodName
            status[name] = 'ERROR'
        for f in result.failures:
            name = f[0].__class__.__name__ + '.' + \
                   f[0]._TestCase__testMethodName
            status[name] = 'FAILURE'
        for s in result.successes:
            name = s.__class__.__name__ + '.' + s._TestCase__testMethodName
            status[name] = 'success'

        keys = status.keys()
        keys.sort()

        for k in keys:
            old = ostatus.get(k, 'success')
            if k in ostatus:
                del ostatus[k]
            new = status[k]
            if old != new:
                print >>output, k, 'has transitioned from', old, 'to', new
            elif new != 'success':
                print >>output, k, "is still a", new

        for k in ostatus:
            print >>output, k, 'was a', ostatus[k], 'was not run this time'
            status[k] = ostatus[k]

        pickle.dump(status, open('testcts.pickle','w'))

        return result

class MyTextTestRunner(unittest.TextTestRunner):
    def _makeResult(self):
        return MyTextTestResult(self.stream, self.descriptions, self.verbosity)


def testsuite_from_main():
    """ return test modules from __main__

    """
    loader = unittest.TestLoader()
    m = __import__('__main__')
    return loader.loadTestsFromModule(m)

def testsuite_from_dir(root, filterfunc=None, recursive=0, loader=None):
    """ return test modules that optionally match filterfunc. 

    all files matching the glob-pattern "test_*.py" are considered.
    additionally their fully qualified python module path has
    to be accepted by filterfunc (if it is not None). 
    """
    if Options.verbose>2:
        print >>sys.stderr, "scanning for test files in", root

    if loader is None:
        loader = unittest.TestLoader()

    root = os.path.abspath(root)

    suite = unittest.TestLoader.suiteClass()
    for fn in os.listdir(root):
        if fn.startswith('.'):
            continue
        fullfn = os.path.join(root, fn)
        if os.path.isfile(fullfn) and \
               fn.startswith('test_') and \
               fn.endswith('.py'):
            modpath = fullfn[len(autopath.pypydir)+1:-3]
            modpath = 'pypy.' + modpath.replace(os.sep, '.')
            if not filterfunc or filterfunc(modpath):
                subsuite = loader.loadTestsFromName(modpath)
                suite.addTest(subsuite, modpath)
        elif recursive and os.path.isdir(fullfn):
            subsuite = testsuite_from_dir(fullfn, filterfunc, 1, loader)
            if subsuite:
                suite._tests.extend(subsuite._tests)
    return suite

class Options(option.Options):
    testreldir = 0
    runcts = 0
    spacename = ''

class RegexFilterFunc:
    """ stateful function to filter included/excluded strings via
    a Regular Expression. 

    An 'excluded' regular expressions has a '%' prependend. 
    """

    def __init__(self, *regex):
        self.exclude = []
        self.include = []
        for x in regex:
            if x[:1]=='%':
                self.exclude.append(re.compile(x[1:]).search)
            else:
                self.include.append(re.compile(x).search)

    def __call__(self, arg):
        for exclude in self.exclude:
            if exclude(arg):
                return
        if not self.include:
            return arg
        for include in self.include:
            if include(arg):
                return arg

def get_test_options():
    options = option.get_standard_options()
    options.append(make_option(
        '-r', action="store_true", dest="testreldir",
        help="gather only tests relative to current dir"))
    options.append(make_option(
        '-c', action="store_true", dest="runcts",
        help="run CtsTestRunner (catches stdout and prints report "
        "after testing) [unix only, for now]"))
    return options

def run_tests(suite):
    for spacename in Options.spaces or ['']:
        run_tests_on_space(suite, spacename)

def run_tests_on_space(suite, spacename=''):
    """ run the suite on the given space """
    if Options.runcts:
        runner = CtsTestRunner() # verbosity=Options.verbose+1)
    else:
        runner = MyTextTestRunner(verbosity=Options.verbose+1)

    if spacename:
        Options.spacename = spacename

    warnings.defaultaction = Options.showwarning and 'default' or 'ignore'
    print >>sys.stderr, "running tests via", repr(objspace())
    runner.run(suite)

def main(root=None):
    """ run this to test everything in the __main__ or
    in the given root-directory (recursive)"""
    args = option.process_options(get_test_options(), Options)
    
    filterfunc = RegexFilterFunc(*args)
    if Options.testreldir:
        root = os.path.abspath('.')
    if root is None:
        suite = testsuite_from_main()
    else:
        suite = testsuite_from_dir(root, filterfunc, 1)
    run_tests(suite)

if __name__ == '__main__':
    # test all of pypy
    main(autopath.pypydir)
