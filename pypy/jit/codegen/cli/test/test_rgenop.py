import py
from pypy.rpython.ootypesystem import ootype
from pypy.jit.codegen.cli.rgenop import RCliGenOp
from pypy.jit.codegen.test.rgenop_tests import AbstractRGenOpTests, OOType
from pypy.translator.cli.test.runtest import compile_function

passing = set()
def fn():
    prefixes = [
        'test_adder',
        'test_dummy',
        'test_hide_and_reveal',
        'test_hide_and_reveal_p',
        'test_largedummy_direct', # _compile works if we set a higher maxstack
        'test_branching',
        ]

    for p in prefixes:
        passing.add(p)
        passing.add(p + '_direct')
        passing.add(p + '_compile')
fn()
del fn

class TestRCliGenop(AbstractRGenOpTests):
    RGenOp = RCliGenOp
    T = OOType

    # for the individual tests see
    # ====> ../../test/rgenop_tests.py

    def getcompiled(self, fn, annotation, annotatorpolicy):
        return compile_function(fn, annotation,
                                annotatorpolicy=annotatorpolicy,
                                nowrap=True)

    def cast(self, gv, nb_args):
        "NOT_RPYTHON"
        def fn(*args):
            return gv.obj.Invoke(*args)
        return fn

    def directtesthelper(self, FUNCTYPE, func):
        py.test.skip('???')

    def __getattribute__(self, name):
        if name.startswith('test_') and name not in passing:
            def fn():
                py.test.skip("doesn't work yet")
            return fn
        else:
            return object.__getattribute__(self, name)
