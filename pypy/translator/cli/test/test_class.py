import py
from pypy.translator.cli.test.runtest import CliTest
from pypy.rpython.test.test_rclass import BaseTestRclass

class TestCliClass(CliTest, BaseTestRclass):
    def test_recursive_prebuilt_instance_classattr(self):
        py.test.skip("gencli doesn't support abstract methods, yet")
    test_common_class_attribute = test_recursive_prebuilt_instance_classattr
