from pypy.annotation import model as annmodel
from pypy.rpython import extregistry
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.rctypes.rmodel import CTypesValueRepr

import ctypes


CFuncPtrType = type(ctypes.CFUNCTYPE(None))

def cfuncptrtype_compute_annotation(type, instance):

    def compute_result_annotation(*args_s):
        """
        Answer the annotation of the external function's result
        """
        result_ctype = instance.restype
        s_result = annmodel.SomeCTypesObject(result_ctype,
                                         annmodel.SomeCTypesObject.OWNSMEMORY)
        return s_result.return_annotation()

    return annmodel.SomeBuiltin(compute_result_annotation, 
        methodname=instance.__name__)

def cfuncptrtype_specialize_call(hop):
    # this is necessary to get the original function pointer when specializing
    # the metatype
    assert hop.spaceop.opname == "simple_call"
    cfuncptr = hop.spaceop.args[0].value
    fnname = cfuncptr.__name__

    args_r = []
    for ctype in cfuncptr.argtypes:
        s_arg = annmodel.SomeCTypesObject(ctype,
                              annmodel.SomeCTypesObject.MEMORYALIAS)
        r_arg = hop.rtyper.getrepr(s_arg)
        args_r.append(r_arg)

    vlist = hop.inputargs(*args_r)
    unwrapped_args_v = []
    ARGTYPES = []
    for r_arg, v in zip(args_r, vlist):
        if isinstance(r_arg, CTypesValueRepr):
            # ValueRepr case
            unwrapped_args_v.append(r_arg.getvalue(hop.llops, v))
            ARGTYPES.append(r_arg.ll_type)
        else:
            # RefRepr case -- i.e. the function argument that we pass by
            # value is e.g. a complete struct; we pass a pointer to it
            # in the low-level graphs and it's up to the back-end to
            # generate the correct dereferencing
            unwrapped_args_v.append(r_arg.get_c_data(hop.llops, v))
            ARGTYPES.append(r_arg.c_data_type)
    s_res = annmodel.SomeCTypesObject(cfuncptr.restype,
                                      annmodel.SomeCTypesObject.OWNSMEMORY)
    r_res = hop.rtyper.getrepr(s_res)

    ll_func = getattr(cfuncptr, 'llinterp_friendly_version', None)
    includes = getattr(cfuncptr, 'includes', ())
    v_result = hop.llops.gencapicall(fnname, unwrapped_args_v,
                                     resulttype = r_res.ll_type,
                                     _callable = ll_func,
                                     includes = includes)
    # XXX hack! hack! temporary! I promize!
    FUNCTYPE = lltype.FuncType(ARGTYPES, r_res.ll_type)
    last_op = hop.llops[-1]
    assert last_op.opname == 'direct_call'
    last_op.args[0].concretetype = lltype.Ptr(FUNCTYPE)
    last_op.args[0].value._set_TYPE(last_op.args[0].concretetype)
    last_op.args[0].value._set_T(FUNCTYPE)
    last_op.args[0].value._obj._TYPE = FUNCTYPE

    return v_result

extregistry.register_metatype(CFuncPtrType, 
    compute_annotation=cfuncptrtype_compute_annotation,
    specialize_call=cfuncptrtype_specialize_call)
