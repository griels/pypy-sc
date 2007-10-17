
""" Interpreter-level implementation of structure, exposing ll-structure
to app-level with apropriate interface
"""

from pypy.interpreter.baseobjspace import W_Root, ObjSpace, Wrappable,\
     Arguments
from pypy.interpreter.gateway import interp2app
from pypy.interpreter.typedef import TypeDef, GetSetProperty
from pypy.rpython.lltypesystem import lltype, rffi
from pypy.interpreter.error import OperationError, wrap_oserror
# XXX we've got the very same info in two places - one is native_fmttable
# the other one is in rlib/libffi, we should refactor it to reuse the same
# logic, I'll not touch it by now, and refactor it later
from pypy.module.struct.nativefmttable import native_fmttable as struct_native_fmttable
from pypy.module._ffi.interp_ffi import wrap_value, unwrap_value

native_fmttable = {}
for key, value in struct_native_fmttable.items():
    native_fmttable[key] = {'size': value['size'],
                            'alignment': value.get('alignment', value['size'])}

def unpack_fields(space, w_fields):
    fields_w = space.unpackiterable(w_fields)
    fields = []
    for w_tup in fields_w:
        l_w = space.unpackiterable(w_tup)
        if not len(l_w) == 2:
            raise OperationError(space.w_ValueError, space.wrap(
                "Expected list of 2-size tuples"))
        fields.append((space.str_w(l_w[0]), space.str_w(l_w[1])))
    return fields

def size_and_pos(fields):
    size = native_fmttable[fields[0][1]]['size']
    pos = [0]
    for i in range(1, len(fields)):
        field_desc = native_fmttable[fields[i][1]]
        missing = size % field_desc.get('alignment', 1)
        if missing:
            size += field_desc['alignment'] - missing
        pos.append(size)
        size += field_desc['size']
    return size, pos

def push_field(self, num, value):
    ptr = rffi.ptradd(self.ll_buffer, self.ll_positions[num])
    TP = lltype.typeOf(value)
    T = lltype.Ptr(rffi.CArray(TP))
    rffi.cast(T, ptr)[0] = value
push_field._annspecialcase_ = 'specialize:argtype(2)'
    
def cast_pos(self, i, ll_t):
    pos = rffi.ptradd(self.ll_buffer, self.ll_positions[i])
    TP = lltype.Ptr(rffi.CArray(ll_t))
    return rffi.cast(TP, pos)[0]
cast_pos._annspecialcase_ = 'specialize:arg(2)'

class W_StructureInstance(Wrappable):
    def __init__(self, space, w_shape, w_address, w_fieldinits):
        self.free_afterwards = False
        w_fields = space.getattr(w_shape, space.wrap('fields'))
        fields = unpack_fields(space, w_fields)
        size, pos = size_and_pos(fields)
        self.fields = fields
        if space.is_true(w_address):
            self.ll_buffer = rffi.cast(rffi.VOIDP, space.int_w(w_address))
        else:
            self.free_afterwards = True
            self.ll_buffer = lltype.malloc(rffi.VOIDP.TO, size, flavor='raw',
                                           zero=True)
        self.ll_positions = pos
        if space.is_true(w_fieldinits):
            for w_field in space.unpackiterable(w_fieldinits):
                w_value = space.getitem(w_fieldinits, w_field)
                self.setattr(space, space.str_w(w_field), w_value)

    def getattr(self, space, attr):
        if attr.startswith('tm'):
            pass
        for i in range(len(self.fields)):
            name, c = self.fields[i]
            if name == attr:
                return wrap_value(space, cast_pos, self, i, c)
        raise OperationError(space.w_AttributeError, space.wrap(
            "C Structure has no attribute %s" % attr))
    getattr.unwrap_spec = ['self', ObjSpace, str]

    def setattr(self, space, attr, w_value):
        for i in range(len(self.fields)):
            name, c = self.fields[i]
            if name == attr:
                unwrap_value(space, push_field, self, i, c, w_value, None)
                return
    setattr.unwrap_spec = ['self', ObjSpace, str, W_Root]

    def __del__(self):
        if self.free_afterwards:
            lltype.free(self.ll_buffer, flavor='raw')

    def getbuffer(space, self):
        return space.wrap(rffi.cast(rffi.INT, self.ll_buffer))

def descr_new_structure_instance(space, w_type, w_shape, w_adr, w_fieldinits):
    return W_StructureInstance(space, w_shape, w_adr, w_fieldinits)

W_StructureInstance.typedef = TypeDef(
    'StructureInstance',
    __new__     = interp2app(descr_new_structure_instance),
    __getattr__ = interp2app(W_StructureInstance.getattr),
    __setattr__ = interp2app(W_StructureInstance.setattr),
    buffer      = GetSetProperty(W_StructureInstance.getbuffer),
)
