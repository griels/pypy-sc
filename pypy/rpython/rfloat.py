from pypy.annotation.pairtype import pairtype
from pypy.annotation import model as annmodel
from pypy.rpython.lltype import Signed, Unsigned, Bool, Float, Void
from pypy.rpython.rmodel import Repr, TyperError, FloatRepr
from pypy.rpython.rmodel import IntegerRepr, BoolRepr
from pypy.rpython.robject import PyObjRepr, pyobj_repr


debug = False

class __extend__(annmodel.SomeFloat):
    def rtyper_makerepr(self, rtyper):
        return float_repr
    def rtyper_makekey(self):
        return None


float_repr = FloatRepr()


class __extend__(pairtype(FloatRepr, FloatRepr)):

    #Arithmetic

    def rtype_add(_, hop):
        return _rtype_template(hop, 'add')

    rtype_inplace_add = rtype_add

    def rtype_sub(_, hop):
        return _rtype_template(hop, 'sub')

    rtype_inplace_sub = rtype_sub

    def rtype_mul(_, hop):
        return _rtype_template(hop, 'mul')

    rtype_inplace_mul = rtype_mul

    def rtype_div(_, hop):
        return _rtype_template(hop, 'div')

    rtype_inplace_div = rtype_div

    def rtype_mod(_, hop):
        return _rtype_template(hop, 'mod')

    rtype_inplace_mod = rtype_mod

    def rtype_pow(_, hop):
        s_float3 = hop.args_s[2]
        if s_float3.is_constant() and s_float3.const is None:
            vlist = hop.inputargs(Float, Float, Void)[:2]
            return hop.genop('float_pow', vlist, resulttype=Float)
        else:
            raise TyperError("cannot handle pow with three float arguments")

    def rtype_inplace_pow(_, hop):
        return _rtype_template(hop, 'pow')

    #comparisons: eq is_ ne lt le gt ge

    def rtype_eq(_, hop):
        return _rtype_compare_template(hop, 'eq')

    rtype_is_ = rtype_eq

    def rtype_ne(_, hop):
        return _rtype_compare_template(hop, 'ne')

    def rtype_lt(_, hop):
        return _rtype_compare_template(hop, 'lt')

    def rtype_le(_, hop):
        return _rtype_compare_template(hop, 'le')

    def rtype_gt(_, hop):
        return _rtype_compare_template(hop, 'gt')

    def rtype_ge(_, hop):
        return _rtype_compare_template(hop, 'ge')


#Helpers FloatRepr,FloatRepr

def _rtype_template(hop, func):
    vlist = hop.inputargs(Float, Float)
    return hop.genop('float_'+func, vlist, resulttype=Float)

def _rtype_compare_template(hop, func):
    vlist = hop.inputargs(Float, Float)
    return hop.genop('float_'+func, vlist, resulttype=Bool)

#

class __extend__(FloatRepr):

    def convert_const(self, value):
        if not isinstance(value, (int, float)):  # can be bool too
            raise TyperError("not a float: %r" % (value,))
        return float(value)

    def rtype_is_true(_, hop):
        vlist = hop.inputargs(Float)
        return hop.genop('float_is_true', vlist, resulttype=Bool)

    def rtype_neg(_, hop):
        vlist = hop.inputargs(Float)
        return hop.genop('float_neg', vlist, resulttype=Float)

    def rtype_pos(_, hop):
        vlist = hop.inputargs(Float)
        return vlist[0]

    def rtype_int(_, hop):
        vlist = hop.inputargs(Float)
        return hop.genop('cast_float_to_int', vlist, resulttype=Signed)

    rtype_float = rtype_pos

#
# _________________________ Conversions _________________________

class __extend__(pairtype(IntegerRepr, FloatRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        if r_from.lowleveltype == Unsigned and r_to.lowleveltype == Float:
            if debug: print 'explicit cast_uint_to_float'
            return llops.genop('cast_uint_to_float', [v], resulttype=Float)
        if r_from.lowleveltype == Signed and r_to.lowleveltype == Float:
            if debug: print 'explicit cast_int_to_float'
            return llops.genop('cast_int_to_float', [v], resulttype=Float)
        return NotImplemented

class __extend__(pairtype(BoolRepr, FloatRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        if r_from.lowleveltype == Bool and r_to.lowleveltype == Float:
            if debug: print 'explicit cast_bool_to_float'
            return llops.genop('cast_bool_to_float', [v], resulttype=Float)
        return NotImplemented

class __extend__(pairtype(PyObjRepr, FloatRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        if r_to.lowleveltype == Float:
            return llops.gencapicall('PyFloat_AsDouble', [v],
                                     resulttype=Float)
        return NotImplemented

class __extend__(pairtype(FloatRepr, PyObjRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        if r_from.lowleveltype == Float:
            return llops.gencapicall('PyFloat_FromDouble', [v],
                                     resulttype=pyobj_repr)
        return NotImplemented
