import py
from pypy.translator.cli.test.runtest import CliTest
from pypy.rpython.test.test_exception import BaseTestException
from pypy.rpython.test.test_rclass import BaseTestRclass
from pypy.rpython.test.test_rlist import BaseTestRlist
from pypy.rpython.test.test_rpbc import BaseTestRPBC

class TestCliException(CliTest, BaseTestException):
    pass


class TestCliClass(CliTest, BaseTestRclass):
    def test_recursive_prebuilt_instance(self):
        py.test.skip("gencli doesn't support recursive constants, yet")


class TestCliPBC(CliTest, BaseTestRPBC):
    def test_call_memoized_cache(self):
        py.test.skip("gencli doesn't support recursive constants, yet")        

    def test_multiple_specialized_functions(self):
        py.test.skip("CLI doesn't support string, yet")

    def test_specialized_method_of_frozen(self):
        py.test.skip("CLI doesn't support string, yet")

    def test_specialized_method(self):
        py.test.skip("CLI doesn't support string, yet")


class TestCliList(CliTest, BaseTestRlist):
    def test_recursive(self):
        py.test.skip("CLI doesn't support recursive lists")

    def test_list_comparestr(self):
        py.test.skip("CLI doesn't support string, yet")

    def test_not_a_char_list_after_all(self):
        py.test.skip("CLI doesn't support string, yet")
        
    def test_list_str(self):
        py.test.skip("CLI doesn't support string, yet")

    def test_inst_list(self):
        py.test.skip("CLI doesn't support string, yet")
