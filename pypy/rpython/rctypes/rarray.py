from ctypes import ARRAY, c_int
from pypy.annotation.model import SomeCTypesObject, SomeBuiltin
from pypy.rpython import extregistry
from pypy.rpython.rmodel import Repr
from pypy.rpython.lltypesystem import lltype
from pypy.annotation.pairtype import pairtype
from pypy.rpython.rmodel import IntegerRepr
from pypy.rpython.rctypes.rmodel import CTypesRefRepr

ArrayType = type(ARRAY(c_int, 10))

class ArrayRepr(CTypesRefRepr):
    def __init__(self, rtyper, s_array):
        array_ctype = s_array.knowntype
        
        item_ctype = array_ctype._type_
        self.length = array_ctype._length_
        
        # Find the repr and low-level type of items from their ctype
        self.r_item = rtyper.getrepr(SomeCTypesObject(item_ctype,
                                            SomeCTypesObject.MEMORYALIAS))

        # Here, self.c_data_type == self.ll_type
        c_data_type = lltype.Array(self.r_item.ll_type,
                                    hints={"nolength": True})
        
        # Array elements are of the low-level type (Signed, etc) and not 
        # of the boxed low level type (Ptr(GcStruct(...)))

        super(ArrayRepr, self).__init__(rtyper, s_array, c_data_type)

class __extend__(pairtype(ArrayRepr, IntegerRepr)):
    def rtype_setitem((r_array, r_int), hop):
        v_array, v_index, v_item = hop.inputargs(r_array, lltype.Signed,
                r_array.r_item.ll_type)
        v_c_data = r_array.get_c_data(hop.llops, v_array)
        hop.genop('setarrayitem', [v_c_data, v_index, v_item])

    def rtype_getitem((r_array, r_int), hop):
        v_array, v_index = hop.inputargs(r_array, lltype.Signed)

        v_c_data = r_array.get_c_data(hop.llops, v_array)
        return hop.genop('getarrayitem', [v_c_data, v_index],
                r_array.r_item.ll_type)

def arraytype_specialize_call(hop):
    r_array = hop.r_result
    return hop.genop("malloc_varsize", [
        hop.inputconst(lltype.Void, r_array.lowleveltype.TO), 
        hop.inputconst(lltype.Signed, r_array.length),
        ], resulttype=r_array.lowleveltype,
    )

def arraytype_compute_annotation(metatype, type):
    def compute_result_annotation(*arg_s):
        return SomeCTypesObject(type, SomeCTypesObject.OWNSMEMORY)
    return SomeBuiltin(compute_result_annotation, methodname=type.__name__)

extregistry.register_type(ArrayType, 
    compute_annotation=arraytype_compute_annotation,
    specialize_call=arraytype_specialize_call)

def arraytype_get_repr(rtyper, s_array):
    return ArrayRepr(rtyper, s_array)

extregistry.register_metatype(ArrayType, get_repr=arraytype_get_repr)
