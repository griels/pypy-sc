import py
from pypy.translator.llvm.genllvm import genllvm_compile

optimize_tests = False
MINIMUM_LLVM_VERSION = 1.6

def llvm_is_on_path():
    try:
        py.path.local.sysfind("llvm-as")
        py.path.local.sysfind("llvm-gcc")
    except py.error.ENOENT: 
        return False 
    return True

def llvm_version():
    import os
    v = os.popen('llvm-as -version 2>&1').readline()
    v = ''.join([c for c in v if c.isdigit()])
    v = int(v) / 10.0
    return v

def llvm_test():
    if not llvm_is_on_path():
        py.test.skip("llvm not found")
        return False
    v = llvm_version()
    if v < MINIMUM_LLVM_VERSION:
        py.test.skip("llvm version not up-to-date (found "
                     "%.1f, should be >= %.1f)" % (v, MINIMUM_LLVM_VERSION))
        return False
    return True

def compile_test(function, annotation, **kwds):
    if llvm_test():        
        return genllvm_compile(function, annotation, optimize=optimize_tests,
                               logging=False, **kwds)

def compile_function(function, annotation, **kwds):
    if llvm_test():
        return compile_test(function, annotation, return_fn=True, **kwds)

