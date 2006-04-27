import py
from pypy.translator.cl.clrepr import clrepr

def test_const():
    py.test.skip('changed')
    assert repr_const(True) == 't'
    assert repr_const(False) == 'nil'
    assert repr_const(42) == '42'
    assert repr_const(1.5) == '1.5'
    assert repr_const(None) == 'nil'
    assert repr_const('a') == '#\\a'
    assert repr_const('answer') == '"answer"'
    assert repr_const((2, 3)) == "'(2 3)"
    assert repr_const([2, 3]) == "#(2 3)"
