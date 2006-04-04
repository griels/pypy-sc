from pypy.rpython.rmodel import Repr, inputconst
from pypy.rpython import extregistry
from pypy.rpython.lltypesystem import lltype
from pypy.annotation import model as annmodel
from pypy.rpython.rctypes.rmodel import CTypesValueRepr

from ctypes import POINTER, pointer, c_int

class PointerRepr(CTypesValueRepr):
    def __init__(self, rtyper, s_pointer, s_contents):
        self.s_pointer = s_pointer
        self.s_contents = s_contents
        self.ref_ctype = s_contents.knowntype
        self.r_contents = rtyper.getrepr(s_contents)
        ll_contents = lltype.Ptr(self.r_contents.c_data_type)

        super(PointerRepr, self).__init__(rtyper, s_pointer, ll_contents)

    def get_content_keepalives(self):
        "Return an extra keepalive field used for the pointer's contents."
        return [('keepalive_contents', self.r_contents.owner_lowleveltype)]

    def setkeepalive(self, llops, v_box, v_owner):
        inputargs = [v_box, inputconst(lltype.Void, 'keepalive_contents'),
                     v_owner]
        llops.genop('setfield', inputargs)

    def rtype_getattr(self, hop):
        s_attr = hop.args_s[1]
        assert s_attr.is_constant()
        assert s_attr.const == 'contents'
        v_ptr = hop.inputarg(self, 0)
        v_value = self.getvalue(hop.llops, v_ptr)
        return self.r_contents.allocate_instance_ref(hop.llops, v_value)

#def registerPointerType(ptrtype):
#    """Adds a new pointer type to the extregistry.
#
#    Since pointers can be created to primitive ctypes objects, arrays,
#    structs and structs are not predefined each new pointer type is
#    registered in the extregistry as it is identified.
#
#    The new pointers that are created have a "contents" attribute
#    which, when retrieved, in effect dereferences the pointer and
#    returns the referenced value.
#    """
#    def compute_result_annotation(s_self, s_arg):
#        return annmodel.SomeCTypesObject(ptrtype,
#                annmodel.SomeCTypesObject.OWNSMEMORY)
#
#    def specialize_call(hop):
#        raise RuntimeError('foo')
#
#    contentsType = annmodel.SomeCTypesObject(ptrtype._type_,
#                                    annmodel.SomeCTypesObject.MEMORYALIAS)
#
#    def get_repr(rtyper, s_pointer):
#        return PointerRepr(rtyper, s_pointer, contentsType)
#        
#    type_entry = extregistry.register_type(ptrtype,
#                            specialize_call=specialize_call,
#                            get_repr=get_repr)
#    type_entry.get_field_annotation = {'contents': contentsType}.__getitem__
#
#    return extregistry.register_value(ptrtype,
#                        compute_result_annotation=compute_result_annotation,
#                        specialize_call=specialize_call)
#
#def pointer_compute_annotation(metatype, the_type):
#    """compute the annotation of POINTER() calls to create a ctypes
#    pointer for the given type
#    """
#
#    def pointer_compute_result_annotation(s_arg):
#        """Called to compute the result annotation of
#        POINTER(<ctypes type>).  This happens to return a new
#        class which itself is treated as SomeBuiltin because when
#        called it creates a new pointer.
#
#        NOTE: To handle a myriad of possible pointer types, each
#              ctypes type that is passed to POINTER() calls is itself
#              registered if it isn't already.
#        """
#        ptrtype = POINTER(s_arg.const)
#
#        if not extregistry.is_registered_type(ptrtype):
#            entry = registerPointerType(ptrtype)
#        else:
#            entry = extregistry.lookup(ptrtype)
#
#        s_self = annmodel.SomeCTypesObject(ptrtype,
#                            annmodel.SomeCTypesObject.OWNSMEMORY)
#                        
#
#        return annmodel.SomeBuiltin(entry.compute_result_annotation,
#                s_self=s_self,
#                methodname=ptrtype.__name__)
#
#    # annotation of POINTER (not the call) is SomeBuitin which provides
#    # a way of computing the result annotation of POINTER(<ctypes type>)
#    return annmodel.SomeBuiltin(pointer_compute_result_annotation,
#                                methodname=the_type.__name__)
#
#def pointer_specialize_call(hop):
#    raise RuntimeError("foo")
#
# handles POINTER() calls
#value_entry = extregistry.register_value(POINTER,
#        compute_annotation=pointer_compute_annotation,
#        specialize_call=pointer_specialize_call)

def pointertype_compute_annotation(metatype, type):
    def compute_result_annotation(*arg_s):
        return annmodel.SomeCTypesObject(type,
                annmodel.SomeCTypesObject.OWNSMEMORY)
    return annmodel.SomeBuiltin(compute_result_annotation, 
                                methodname=type.__name__)

def pointertype_specialize_call(hop):
    r_ptr = hop.r_result
    v_result = r_ptr.allocate_instance(hop.llops)
    if len(hop.args_s):
        v_contentsbox, = hop.inputargs(r_ptr.r_contents)
        v_c_data = r_ptr.r_contents.get_c_data(hop.llops, v_contentsbox)
        v_owner = r_ptr.r_contents.get_c_data_owner(hop.llops, v_contentsbox)
        r_ptr.setvalue(hop.llops, v_result, v_c_data)
        r_ptr.setkeepalive(hop.llops, v_result, v_owner)
    return v_result

def pointerinstance_compute_annotation(type, instance):
    return annmodel.SomeCTypesObject(type,
            annmodel.SomeCTypesObject.OWNSMEMORY)

def pointerinstance_field_annotation(s_pointer, fieldname):
    assert fieldname == "contents"
    ptrtype = s_pointer.knowntype
    return annmodel.SomeCTypesObject(ptrtype._type_,
                                     annmodel.SomeCTypesObject.MEMORYALIAS)

def pointerinstance_get_repr(rtyper, s_pointer):
    s_contents = pointerinstance_field_annotation(s_pointer, "contents")
    return PointerRepr(rtyper, s_pointer, s_contents)

PointerType = type(POINTER(c_int))
extregistry.register_type(PointerType,
        compute_annotation=pointertype_compute_annotation,
        specialize_call=pointertype_specialize_call)

entry = extregistry.register_metatype(PointerType,
        compute_annotation=pointerinstance_compute_annotation,
        get_repr=pointerinstance_get_repr)
entry.get_field_annotation = pointerinstance_field_annotation

def pointerfn_compute_annotation(s_arg):
    assert isinstance(s_arg, annmodel.SomeCTypesObject)
    ctype = s_arg.knowntype
    result_ctype = POINTER(ctype)
    return annmodel.SomeCTypesObject(result_ctype,
                                     annmodel.SomeCTypesObject.OWNSMEMORY)

extregistry.register_value(pointer,
        compute_result_annotation=pointerfn_compute_annotation,
        # same rtyping for calling pointer() or calling a specific instance
        # of PointerType:
        specialize_call=pointertype_specialize_call)
