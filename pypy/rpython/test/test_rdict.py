
from pypy.rpython import lltype 
from pypy.rpython.test.test_llinterp import interpret 

import py

def test_dict_creation(): 
    def createdict(i): 
        d = {'hello' : i}
        return d['hello']

    res = interpret(createdict, [42])
    assert res == 42

def test_dict_getitem_setitem(): 
    def func(i): 
        d = {'hello' : i}
        d['world'] = i + 1
        return d['hello'] * d['world'] 
    res = interpret(func, [6])
    assert res == 42

def test_dict_getitem_keyerror(): 
    def func(i): 
        d = {'hello' : i}
        try:
            return d['world']
        except KeyError:
            return 0 
    res = interpret(func, [6])
    assert res == 0

def test_dict_del_simple():
    def func(i): 
        d = {'hello' : i}
        d['world'] = i + 1
        del d['hello']
        return len(d) 
    res = interpret(func, [6])
    assert res == 1

