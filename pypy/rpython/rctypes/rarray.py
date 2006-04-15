from ctypes import ARRAY, c_int
from pypy.rpython.rbuiltin import gen_cast_subarray_pointer
from pypy.rpython.rmodel import IntegerRepr, inputconst
from pypy.rpython.lltypesystem import lltype
from pypy.annotation.pairtype import pairtype
from pypy.rpython.rctypes.rmodel import CTypesRefRepr, CTypesValueRepr
from pypy.rpython.rctypes.rmodel import genreccopy, reccopy
from pypy.rpython.rctypes.rprimitive import PrimitiveRepr
from pypy.annotation.model import SomeCTypesObject

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
        c_data_type = lltype.FixedSizeArray(self.r_item.ll_type,
                                            self.length)

        super(ArrayRepr, self).__init__(rtyper, s_array, c_data_type)

    def initialize_const(self, p, value):
        for i in range(self.length):
            llitem = self.r_item.convert_const(value[i])
            if isinstance(self.r_item, CTypesRefRepr):
                # ByRef case
                reccopy(llitem.c_data, p.c_data[i])
            else:
                # ByValue case
                p.c_data[i] = llitem.c_data[0]

    def get_c_data_of_item(self, llops, v_array, v_index):
        v_c_array = self.get_c_data(llops, v_array)
        if isinstance(self.r_item, CTypesRefRepr):
            # ByRef case
            return llops.genop('getarraysubstruct', [v_c_array, v_index],
                               lltype.Ptr(self.r_item.c_data_type))
        else:
            # ByValue case
            A = lltype.FixedSizeArray(self.r_item.ll_type, 1)
            return gen_cast_subarray_pointer(llops, lltype.Ptr(A),
                                             v_c_array, v_index)

    def get_item_value(self, llops, v_array, v_index):
        # ByValue case only
        assert isinstance(self.r_item, CTypesValueRepr)
        v_c_array = self.get_c_data(llops, v_array)
        return llops.genop('getarrayitem', [v_c_array, v_index],
                           resulttype = self.r_item.ll_type)

    def set_item_value(self, llops, v_array, v_index, v_newvalue):
        # ByValue case only
        assert isinstance(self.r_item, CTypesValueRepr)
        v_c_array = self.get_c_data(llops, v_array)
        llops.genop('setarrayitem', [v_c_array, v_index, v_newvalue])


class __extend__(pairtype(ArrayRepr, IntegerRepr)):
    def rtype_getitem((r_array, r_int), hop):
        v_array, v_index = hop.inputargs(r_array, lltype.Signed)
        if isinstance(r_array.r_item, CTypesRefRepr):
            # ByRef case
            v_c_data = r_array.get_c_data_of_item(hop.llops, v_array, v_index)
            return r_array.r_item.return_c_data(hop.llops, v_c_data)
        else:
            # ByValue case (optimization; the above also works in this case)
            v_value = r_array.get_item_value(hop.llops, v_array, v_index)
            return r_array.r_item.return_value(hop.llops, v_value)

    def rtype_setitem((r_array, r_int), hop):
        v_array, v_index, v_item = hop.inputargs(r_array, lltype.Signed,
                                                 r_array.r_item)
        if isinstance(r_array.r_item, CTypesRefRepr):
            # ByRef case
            v_item_c_data = r_array.r_item.get_c_data(hop.llops, v_item)
            v_c_data = r_array.get_c_data_of_item(hop.llops, v_array, v_index)
            # copy the whole structure's content over
            genreccopy(hop.llops, v_item_c_data, v_c_data)
        else:
            # ByValue case (optimization; the above also works in this case)
            v_newvalue = r_array.r_item.getvalue(hop.llops, v_item)
            r_array.set_item_value(hop.llops, v_array, v_index, v_newvalue)
