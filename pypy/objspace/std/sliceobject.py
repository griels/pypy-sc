"""
Reviewed 03-06-21

slice object construction   tested, OK
indices method              tested, OK
"""

from pypy.objspace.std.objspace import *
from pypy.interpreter import gateway


class W_SliceObject(W_Object):
    from pypy.objspace.std.slicetype import slice_typedef as typedef
    
    def __init__(w_self, space, w_start, w_stop, w_step):
        W_Object.__init__(w_self, space)
        w_self.w_start = w_start
        w_self.w_stop = w_stop
        w_self.w_step = w_step

registerimplementation(W_SliceObject)

def app_repr__Slice(aslice):
    return 'slice(%r, %r, %r)' % (aslice.start, aslice.stop, aslice.step)

repr__Slice = gateway.app2interp(app_repr__Slice)

register_all(vars())
