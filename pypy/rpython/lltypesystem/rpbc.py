import types
import sys
from pypy.annotation.pairtype import pairtype, pair
from pypy.annotation import model as annmodel
from pypy.objspace.flow.model import Constant, Variable
from pypy.rpython.lltypesystem.lltype import \
     typeOf, Void, ForwardReference, Struct, Bool, \
     Ptr, malloc, nullptr
from pypy.rpython.rmodel import Repr, TyperError, inputconst, inputdesc
from pypy.rpython.rpbc import samesig,\
     commonbase, allattributenames, adjust_shape, \
     AbstractClassesPBCRepr, AbstractMethodsPBCRepr, OverriddenFunctionPBCRepr, \
     AbstractMultipleFrozenPBCRepr, MethodOfFrozenPBCRepr, \
     AbstractFunctionsPBCRepr
from pypy.rpython.lltypesystem import rclass
from pypy.tool.sourcetools import has_varargs

from pypy.rpython import callparse

def rtype_is_None(robj1, rnone2, hop, pos=0):
    if not isinstance(robj1.lowleveltype, Ptr):
        raise TyperError('is None of instance of the non-pointer: %r' % (robj1))           
    v1 = hop.inputarg(robj1, pos)
    return hop.genop('ptr_iszero', [v1], resulttype=Bool)
    
# ____________________________________________________________

class MultipleFrozenPBCRepr(AbstractMultipleFrozenPBCRepr):
    """Representation selected for multiple non-callable pre-built constants."""
    def __init__(self, rtyper, access_set):
        self.rtyper = rtyper
        self.access_set = access_set
        self.pbc_type = ForwardReference()
        self.lowleveltype = Ptr(self.pbc_type)
        self.pbc_cache = {}

    def _setup_repr(self):
        llfields = self._setup_repr_fields()
        self.pbc_type.become(Struct('pbc', *llfields))

    def create_instance(self):
        return malloc(self.pbc_type, immortal=True)

    def null_instance(self):
        return nullptr(self.pbc_type)

    def getfield(self, vpbc, attr, llops):
        mangled_name, r_value = self.fieldmap[attr]
        cmangledname = inputconst(Void, mangled_name)
        return llops.genop('getfield', [vpbc, cmangledname],
                           resulttype = r_value)

# ____________________________________________________________

class FunctionsPBCRepr(AbstractFunctionsPBCRepr):
    """Representation selected for a PBC of function(s)."""

    def setup_specfunc(self):
        fields = []
        for row in self.uniquerows:
            fields.append((row.attrname, row.fntype))
        return Ptr(Struct('specfunc', *fields))
        
    def create_specfunc(self):
        return malloc(self.lowleveltype.TO, immortal=True)

    def get_specfunc_row(self, llop, v, c_rowname, resulttype):
        return llop.genop('getfield', [v, c_rowname], resulttype=resulttype)
        
class MethodsPBCRepr(AbstractMethodsPBCRepr):
    """Representation selected for a PBC of the form {func: classdef...}.
    It assumes that all the methods come from the same name in a base
    classdef."""

    def rtype_simple_call(self, hop):
        return self.redispatch_call(hop, call_args=False)

    def rtype_call_args(self, hop):
        return self.redispatch_call(hop, call_args=True)

    def redispatch_call(self, hop, call_args):
        r_class = self.r_im_self.rclass
        mangled_name, r_func = r_class.clsfields[self.methodname]
        assert isinstance(r_func, (FunctionsPBCRepr,
                                   OverriddenFunctionPBCRepr))
        # s_func = r_func.s_pbc -- not precise enough, see
        # test_precise_method_call_1.  Build a more precise one...
        funcdescs = [desc.funcdesc for desc in hop.args_s[0].descriptions]
        s_func = annmodel.SomePBC(funcdescs)
        v_im_self = hop.inputarg(self, arg=0)
        v_cls = self.r_im_self.getfield(v_im_self, '__class__', hop.llops)
        v_func = r_class.getclsfield(v_cls, self.methodname, hop.llops)

        hop2 = self.add_instance_arg_to_hop(hop, call_args)
        opname = 'simple_call'
        if call_args:
            opname = 'call_args'

        hop2.v_s_insertfirstarg(v_func, s_func)   # insert 'function'
        # now hop2 looks like simple_call(function, self, args...)
        return hop2.dispatch(opname=opname)


# ____________________________________________________________


class ClassesPBCRepr(AbstractClassesPBCRepr):
    """Representation selected for a PBC of class(es)."""

    # no __init__ here, AbstractClassesPBCRepr.__init__ is good enough

    def rtype_simple_call(self, hop):
        return self.redispatch_call(hop, call_args=False)

    def rtype_call_args(self, hop):
        return self.redispatch_call(hop, call_args=True)

    def redispatch_call(self, hop, call_args):
        s_instance = hop.s_result
        r_instance = hop.r_result

        if self.lowleveltype is Void:
            # instantiating a single class
            assert isinstance(s_instance, annmodel.SomeInstance)
            classdef = hop.s_result.classdef
            v_instance = rclass.rtype_new_instance(hop.rtyper, classdef,
                                                   hop.llops)
            s_init = classdef.classdesc.s_read_attribute('__init__')
            v_init = Constant("init-func-dummy")   # this value not really used
        else:
            # instantiating a class from multiple possible classes
            from pypy.rpython.lltypesystem.rbuiltin import ll_instantiate
            vtypeptr = hop.inputarg(self, arg=0)
            access_set = self.get_access_set()
            r_class = self.get_class_repr()
            if '__init__' in access_set.attrs:
                s_init = access_set.attrs['__init__']
                v_init = r_class.getpbcfield(vtypeptr, access_set, '__init__',
                                             hop.llops)
            else:
                s_init = annmodel.s_ImpossibleValue
            v_inst1 = hop.gendirectcall(ll_instantiate, vtypeptr)
            v_instance = hop.genop('cast_pointer', [v_inst1],
                                   resulttype = r_instance)

        if isinstance(s_init, annmodel.SomeImpossibleValue):
            assert hop.nb_args == 1, ("arguments passed to __init__, "
                                      "but no __init__!")
        else:
            hop2 = self.replace_class_with_inst_arg(
                    hop, v_instance, s_instance, call_args)
            hop2.v_s_insertfirstarg(v_init, s_init)   # add 'initfunc'
            hop2.s_result = annmodel.s_None
            hop2.r_result = self.rtyper.getrepr(hop2.s_result)
            # now hop2 looks like simple_call(initfunc, instance, args...)
            hop2.dispatch()
        return v_instance

# ____________________________________________________________

##def rtype_call_memo(hop): 
##    memo_table = hop.args_v[0].value
##    if memo_table.s_result.is_constant():
##        return hop.inputconst(hop.r_result, memo_table.s_result.const)
##    fieldname = memo_table.fieldname 
##    assert hop.nb_args == 2, "XXX"  

##    r_pbc = hop.args_r[1]
##    assert isinstance(r_pbc, (MultipleFrozenPBCRepr, ClassesPBCRepr))
##    v_table, v_pbc = hop.inputargs(Void, r_pbc)
##    return r_pbc.getfield(v_pbc, fieldname, hop.llops)
