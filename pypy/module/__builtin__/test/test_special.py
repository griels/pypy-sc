import py 

from pypy import conftest

def setup_module(mod):
    if conftest.option.runappdirect:
        py.test.skip("doesn't make sense with -A")

def app_test__isfake(): 
    assert not _isfake(map) 
    assert not _isfake(object) 
    assert not _isfake(_isfake) 

def app_test__isfake_currently_true(): 
    import select
    assert _isfake(select) 

def XXXapp_test__isfake_file(): # only if you are not using --file
    import sys
    assert _isfake(sys.stdout)

