from pypy.interpreter import gateway, baseobjspace

# commonly imported there, used from types, variable, thread
from pypy.module._stackless.clonable import ClonableCoroutine

import os

NO_DEBUG_INFO = [True]
def w(*msgs):
    """writeln"""
    if NO_DEBUG_INFO[0]: return
    v(*msgs)
    os.write(1, ' \n')

def v(*msgs):
    """write"""
    if NO_DEBUG_INFO[0]: return
    for msg in list(msgs):
        os.write(1, msg)
        os.write(1, ' ')

def get_current_cspace(space):
    curr = ClonableCoroutine.w_getcurrent(space)
    assert isinstance(curr, ClonableCoroutine)
    assert hasattr(curr, '_cspace')
    return curr._cspace


def interp_id(space, w_obj):
    "debugging purposes only"
    assert isinstance(w_obj, baseobjspace.W_Root) 
    return space.newint(id(w_obj))
app_interp_id = gateway.interp2app(interp_id)

def switch_debug_info(space):
    NO_DEBUG_INFO[0] = not NO_DEBUG_INFO[0]
app_switch_debug_info = gateway.interp2app(switch_debug_info)

