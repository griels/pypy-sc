"""
  None Object implementation

  ok and tested
""" 

from pypy.objspace.std.objspace import *
from pypy.objspace.std.register_all import register_all
from nonetype import W_NoneType

class W_NoneObject(W_Object):
    statictype = W_NoneType
registerimplementation(W_NoneObject)

def unwrap__None(space, w_none):
    return None

def is_true__None(space, w_none):
    return False

def repr__None(space, w_none):
    return space.wrap('None')

register_all(vars())

