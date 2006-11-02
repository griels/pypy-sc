import py
from os.path import dirname, join
from pypy.translator.c.test.test_genc import compile

try:
    from pypy.jit.codegen.llvm import llvmjit
except OSError:
    py.test.skip("libllvmjit not found (see ../README.TXT)")

#helper data
curdir = dirname(__file__)
square = join(curdir, 'square')
mul2   = join(curdir, 'mul2')

llsquare = '''int %square(int %n) {
block0:
    %n2 = mul int %n, %n
    ret int %n2
}'''

llmul2 = '''int %mul2(int %n) {
block0:
    %n2 = mul int %n, 2
    ret int %n2
}'''

#helpers
def execute(llsource, function_name, param):
    assert llvmjit.compile(llsource)
    f = llvmjit.FindFunction(function_name)
    assert f.function
    return llvmjit.execute(f.function, param)
    #return function(param) #XXX this does not seem to translate, how to do it instead?

#tests...
def test_restart():
    for i in range(3):
        llvmjit.restart()
        assert not llvmjit.find_function('square')
        assert llvmjit.compile(llsquare)
        assert llvmjit.find_function('square')

def test_find_function():
    for i in range(3):
        llvmjit.restart()
        assert not llvmjit.find_function('square')
        assert not llvmjit.find_function('square')
        assert llvmjit.compile(llsquare)
        assert llvmjit.find_function('square')
        assert llvmjit.find_function('square')

def test_compile():
    llvmjit.restart()
    assert llvmjit.compile(llsquare)

def test_execute():
    llvmjit.restart()
    assert execute(llsquare, 'square', 4) == 4 * 4

def test_execute_multiple():
    llvmjit.restart()
    llvmjit.compile(llsquare)
    llvmjit.compile(llmul2)
    square = llvmjit.find_function('square')
    mul2   = llvmjit.find_function('mul2')
    for i in range(5):
        assert llvmjit.execute(square, i) == i * i
        assert llvmjit.execute(mul2  , i) == i * 2

def test_call_found_function():
    llvmjit.restart()
    llvmjit.compile(llsquare)
    llvmjit.compile(llmul2)
    square = llvmjit.FindFunction('square')
    mul2   = llvmjit.FindFunction('mul2')
    for i in range(5):
        assert square(i) == i * i
        assert mul2(i) == i * 2

def DONTtest_execute_accross_module():
    pass

def DONTtest_modify_global_data():
    pass

def DONTtest_call_back_to_parent(): #call JIT-compiler again for it to add case(s) to flexswitch
    pass

def DONTtest_delete_function():
    pass

def DONTtest_functions_with_different_signatures():
    pass

def DONTtest_llvm_transformations():
    pass

def DONTtest_layers_of_codegenerators():    #e.g. i386 code until function stabilizes then llvm
    pass
    
def test_execute_translation(): #put this one last because it takes the most time
    llvmjit.restart()
    def f(x):
        return execute(llsquare, 'square', x + 5)
    fn = compile(f, [int])
    res = fn(1)
    assert res == 36
