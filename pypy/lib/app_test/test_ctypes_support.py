
from ctypes import *
try:
    from ctypes_support import standard_c_lib, get_errno, set_errno
except ImportError:    # on top of cpython
    from pypy.lib.ctypes_support import standard_c_lib, get_errno, set_errno


def test_stdlib_and_errno():
    write = standard_c_lib.write
    write.argtypes = [c_int, c_char_p, c_size_t]
    write.restype = c_size_t
    # clear errno first
    set_errno(0)
    assert get_errno() == 0
    write(-345, "abc", 3)
    assert get_errno() != 0
    set_errno(0)
    assert get_errno() == 0
