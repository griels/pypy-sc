from pypy.rpython.memory.lladdress import *
from pypy.annotation.model import SomeAddress, SomeChar
from pypy.translator.c.test.test_genc import compile

def test_null():
    def f():
        return NULL - NULL
    fc = compile(f, [])

def test_convert_to_bool():
    def f(x):
        if x:
            return bool(NULL)
        else:
            return bool(NULL + 1)
    fc = compile(f, [int])
    res = fc(1)
    assert isinstance(res, bool) and not res
    res = fc(0)
    assert isinstance(res, bool) and res

def test_memory_access():
    def f(value):
        addr = raw_malloc(16)
        addr.signed[0] = value
        return addr.signed[0]
    fc = compile(f, [int])
    res = fc(42)
    assert res == 42
    res = fc(1)
    assert res == 1
    
def test_pointer_arithmetic():
    def f(offset, char):
        addr = raw_malloc(10000)
        same_offset = (addr + 2 * offset - offset) - addr 
        addr.char[offset] = char
        result = (addr + same_offset).char[0]
        raw_free(addr)
        return result
    fc = compile(f, [int, SomeChar()])
    res = fc(10, "c")
    assert res == "c"
    res = fc(12, "x")
    assert res == "x"

def test_pointer_arithmetic_inplace():
    def f(offset, char):
        addr = raw_malloc(10000)
        addr += offset
        addr.char[-offset] = char
        addr -= offset
        return addr.char[0]
    fc = compile(f, [int, SomeChar()])
    res = fc(10, "c")
    assert res == "c"

def test_raw_memcopy():
    def f():
        addr = raw_malloc(100)
        addr.signed[0] = 12
        (addr + 10).signed[0] = 42
        (addr + 20).char[0] = "a"
        addr1 = raw_malloc(100)
        raw_memcopy(addr, addr1, 100)
        result = addr1.signed[0] == 12
        result = result and (addr1 + 10).signed[0] == 42
        result = result and (addr1 + 20).char[0] == "a"
        return result
    fc = compile(f, [])
    res = fc()
    assert res


