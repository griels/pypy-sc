import py
py.test.skip("llvm is a state of flux")

from pypy.rpython.test.tool import BaseRtypingTest, LLRtypeMixin
from pypy.translator.llvm.buildllvm import llvm_is_on_path, llvm_version, gcc_version
from pypy.translator.llvm.genllvm import GenLLVM
from pypy.annotation.model import lltype_to_annotation
from pypy.rpython.lltypesystem.lltype import typeOf

optimize_tests = False
native_llvm_backend = True
MINIMUM_LLVM_VERSION = 1.9
FLOAT_PRECISION = 8

ext_modules = []

# prevents resource leaking
use_isolate = False

# if test can't be run using isolate, skip the test (useful for buildbots)
run_isolated_only = False

from pypy import conftest

def _cleanup(leave=0):
    from pypy.tool import isolate
    if leave:
        mods = ext_modules[:-leave]
    else:        
        mods = ext_modules
    for mod in mods:
        if isinstance(mod, isolate.Isolate):
            isolate.close_isolate(mod)        
    if leave:
        del ext_modules[:-leave]
    else:
        del ext_modules[:]
            
def teardown_module(mod):
    _cleanup()
    
def llvm_test():
    if not llvm_is_on_path():
        py.test.skip("could not find one of llvm-as or llvm-gcc")
    llvm_ver = llvm_version()
    if llvm_ver < MINIMUM_LLVM_VERSION:
        py.test.skip("llvm version not up-to-date (found "
                     "%.1f, should be >= %.1f)" % (llvm_ver, MINIMUM_LLVM_VERSION))

#______________________________________________________________________________

def genllvm_compile(function,
                    annotation,
                    
                    # debug options
                    debug=True,
                    logging=False,
                    isolate=True,

                    # pass to compile
                    optimize=True,
                    extra_opts={}):

    """ helper for genllvm """

    from pypy.translator.driver import TranslationDriver
    from pypy.config.pypyoption import get_pypy_config
    config = get_pypy_config({}, translating=True)
    options = {
        'translation.backend': 'llvm',
        'translation.llvm.debug': debug,
        'translation.llvm.logging': logging,
        'translation.llvm.isolate': isolate,
        'translation.backendopt.none': not optimize,
        'translation.gc': 'boehm',
        'translation.llvm_via_c' : not native_llvm_backend 
}
    options.update(extra_opts)
    config.set(**options)
    driver = TranslationDriver(config=config)
    driver.setup(function, annotation)
    driver.annotate()
    if conftest.option.view:
        driver.translator.view()
    driver.rtype()
    if conftest.option.view:
        driver.translator.view()
    driver.compile() 
    if conftest.option.view:
        driver.translator.view()
    return driver.c_module, driver.c_entryp

def compile_test(function, annotation, isolate_hint=True, **kwds):
    " returns module and compiled function "    
    llvm_test()

    if run_isolated_only and not isolate_hint:
        py.test.skip("skipping unrecommended isolated test")

    # turn off isolation?
    isolate = use_isolate and isolate_hint

    # maintain only 3 isolated process (if any)
    _cleanup(leave=3)
    optimize = kwds.pop('optimize', optimize_tests)
    mod, fn = genllvm_compile(function, annotation, optimize=optimize,
                              isolate=isolate, **kwds)
    if isolate:
        ext_modules.append(mod)
    return mod, fn

def compile_function(function, annotation, isolate_hint=True, **kwds):
    " returns compiled function "
    return compile_test(function, annotation, isolate_hint=isolate_hint, **kwds)[1]

# XXX Work in progress, this was mostly copied from cli
class InstanceWrapper:
    def __init__(self, class_name):
        self.class_name = class_name

class ExceptionWrapper:
    def __init__(self, class_name):
        self.class_name = class_name

    def __repr__(self):
        return 'ExceptionWrapper(%s)' % repr(self.class_name)


class LLVMTest(BaseRtypingTest, LLRtypeMixin):
    def __init__(self):
        self._func = None
        self._ann = None
        self._llvm_func = None

    def _compile(self, fn, args, ann=None):
        if ann is None:
            ann = [lltype_to_annotation(typeOf(x)) for x in args]
        if self._func is fn and self._ann == ann:
            return self._llvm_func
        else:
            self._llvm_func = compile_function(fn, ann)
            self._func = fn
            self._ann = ann
            return self._llvm_func

    def _skip_win(self, reason):
        if platform.system() == 'Windows':
            py.test.skip('Windows --> %s' % reason)

    def _skip_powerpc(self, reason):
        if platform.processor() == 'powerpc':
            py.test.skip('PowerPC --> %s' % reason)

    def _skip_llinterpreter(self, reason, skipLL=True, skipOO=True):
        pass

    def interpret(self, fn, args, annotation=None):
        f = self._compile(fn, args, annotation)
        res = f(*args)
        if isinstance(res, ExceptionWrapper):
            raise res
        return res

    def interpret_raises(self, exception, fn, args):
        import exceptions # needed by eval
        try:
            self.interpret(fn, args)
        except ExceptionWrapper, ex:
            assert issubclass(eval(ex.class_name), exception)
        else:
            assert False, 'function did raise no exception at all'

    def float_eq(self, x, y):
        diff = abs(x-y)
        return diff/x < 10**-FLOAT_PRECISION

    def is_of_type(self, x, type_):
        return True # we can't really test the type

    def ll_to_string(self, s):
        return s

    def ll_to_list(self, l):
        return l

    def ll_to_tuple(self, t):
        return t

    def class_name(self, value):
        return value.class_name.split(".")[-1] 

    def is_of_instance_type(self, val):
        return isinstance(val, InstanceWrapper)

    def read_attr(self, obj, name):
        py.test.skip('read_attr not supported on llvm tests')
