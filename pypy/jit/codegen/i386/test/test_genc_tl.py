import py
from pypy.jit.timeshifter.test import test_tl
from pypy.jit.codegen.i386.test.test_genc_ts import I386TimeshiftingTestMixin


class TestTLR(I386TimeshiftingTestMixin,
              test_tl.TestTL):

    # for the individual tests see
    # ====> ../../../timeshifter/test/test_tl.py

    pass
