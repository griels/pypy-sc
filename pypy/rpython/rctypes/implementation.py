"""
The rctypes implementaion is contained here.
"""

import sys
import ctypes
from ctypes import *
from ctypes import _FUNCFLAG_CDECL
if sys.platform == "win32":
    from ctypes import _FUNCFLAG_STDCALL
from pypy.annotation.model import SomeInteger, SomeCTypesObject, \
        SomeString, SomeFloat
from pypy.rpython.lltypesystem.lltype import Signed, SignedLongLong, \
        Unsigned, UnsignedLongLong, Char, Float, Ptr, GcStruct, \
        Void
from pypy.rpython.rmodel import Repr, IntegerRepr, inputconst
from pypy.rpython.error import TyperError
from pypy.annotation.pairtype import pairtype


# ctypes_annotation_list contains various attributes that
# are used by the pypy annotation.

ctypes_annotation_list = [
    (c_char,          Char,             None),
    (c_byte,          Signed,           None),
    (c_ubyte,         Unsigned,         None),
    (c_short,         Signed,           None),
    (c_ushort,        Unsigned,         None),
    (c_int,           Signed,           None),
    (c_uint,          Unsigned,         None),
    (c_long,          Signed,           None),
    (c_ulong,         Unsigned,         None),
    (c_longlong,      SignedLongLong,   None),
    (c_ulonglong,     UnsignedLongLong, None),
    (c_float,         Float,            None),
    (c_double,        Float,            None),
    (c_char_p,        None, 
            staticmethod(lambda ll_type, arg_name:"RPyString_AsString(%s)" % arg_name)),
    (POINTER(c_char), None, 
            staticmethod(lambda ll_type, arg_name:"RPyString_AsString(%s)" % arg_name)),
]

def create_ctypes_annotations():
    """
    create_ctypes_annotation creates a map between
    ctypes, annotation types and low level types.
    For convenience, an existing map from low level types to
    annotation types is used ('ll_to_annotation_map').
    """

    from pypy.annotation.model import ll_to_annotation_map
    for the_type, ll_type, wrap_arg in ctypes_annotation_list:
        the_type.annotator_type = ll_to_annotation_map.get(ll_type)
        the_type.ll_type = ll_type
        if wrap_arg is not None:
            the_type.wrap_arg = wrap_arg
            the_type.default_memorystate = SomeCTypesObject.OWNSMEMORY
        else:
            # !!!! attention !!!!
            # the basic c_types need some annotation information
            # at the moment that are exactly the types that have
            # no 'wrap_arg'. This might change in the future
            the_type.compute_result_annotation = classmethod(lambda cls, s_arg:SomeCTypesObject(cls))
            the_type.default_memorystate = SomeCTypesObject.NOMEMORY

create_ctypes_annotations()

class FunctionPointerTranslation(object):

        def compute_result_annotation(self, *args_s):
            """
            Answer the annotation of the external function's result
            """
            # TODO: Check whteher teh function returns a pointer
            # an correct teh memory state appropriately
            try:
                return self.restype.annotator_type
            except AttributeError:
                return SomeCTypesObject(self.restype)

        def __hash__(self):
            return id(self)

        def specialize(self, hop):
            return hop.llops.gencapicall(self.__name__, hop.args_v,
                         resulttype=self.restype.ll_type, _callable=None,
                         convert_params=self.convert_params) 

        def convert_params(self, backend, param_info_list):
            assert "c" == backend.lower()
            assert self.argtypes is not None
            answer = []
            for ctype_type, (ll_type, arg_name) in zip(self.argtypes, param_info_list):
                if ll_type == ctype_type.ll_type:
                    answer.append(arg_name)
                else:
                    answer.append(ctype_type.wrap_arg(ll_type, arg_name))
            return answer
#
#class CtypesBasicTypeInstantiationTranslation( FunctionPointerTranslation ):
#
#    compute_result_annotation = classmethod(
#            FunctionPointerTranslation.compute_result_annotation)
#
    
class RStructureMeta(type(Structure)):
    def __new__(mta,name,bases,clsdict):
        _fields = clsdict.get('_fields_',None)
        _adict = {}
        if _fields is not None:
            for attr, atype in _fields:
                _adict[attr] = atype
        clsdict['_fields_def_'] = _adict

        return super(RStructureMeta,mta).__new__(mta, name, bases, clsdict)

class RStructure(Structure):

    __metaclass__ = RStructureMeta

    default_memorystate = SomeCTypesObject.OWNSMEMORY

    def compute_annotation(cls):
        return SomeCTypesObject(cls)
    compute_annotation = classmethod(compute_annotation)

    def specialize( cls, highLevelOperation ):
        ctypesStructureType = highLevelOperation.r_result.lowleveltype  
        return highLevelOperation.llops.genop(
                "malloc", [ inputconst( Void, ctypesStructureType ) ],
                highLevelOperation.r_result )
    specialize = classmethod(specialize)

    def compute_result_annotation(cls, *args_s):
        """
        Answer the result annotation of calling 'cls'.
        """
        return SomeCTypesObject(cls,SomeCTypesObject.OWNSMEMORY)
    compute_result_annotation = classmethod(compute_result_annotation)

    def createLowLevelRepresentation( rtyper, annotationObject ):
        """
        Answer the correspondending low level object.
        """
        if annotationObject.memorystate == annotationObject.OWNSMEMORY:
            return CtypesMemoryOwningStructureRepresentation( 
                    rtyper, annotationObject )
        elif annotationObject.memorystate == annotationObject.MEMORYALIAS:
            return CtypesMemoryAliasStructureRepresentation(
                    rtyper, annotationObject )
        else:
            raise TyperError( "Unkown memory state in %r" % annotationObject )
    createLowLevelRepresentation = staticmethod( createLowLevelRepresentation )


class RByrefObj(object):

    default_memorystate = SomeCTypesObject.MEMORYALIAS

    def __init__(self):
        self.__name__ = 'RByrefObj'

    def compute_result_annotation(cls, s_arg):
        """
        Answer the result annotation of calling 'byref'.
        """
        return SomeCTypesObject(POINTER(s_arg.knowntype))

    compute_result_annotation = classmethod(compute_result_annotation)

    def __call__(self,obj):
        return byref(obj)

RByref = RByrefObj()


def RPOINTER(cls):
    answer = POINTER(cls)

    def compute_result_annotation(cls, s_arg):
        """
        Answer the result annotation of calling 'cls'.
        """
        assert answer is cls
        try:
            memorystate = s_arg.memorystate
        except AttributeError:
            memorystate = None
        return SomeCTypesObject(cls, memorystate)
    answer.compute_result_annotation = classmethod(compute_result_annotation)

    def createLowLevelRepresentation( rtyper, annotationObject ):
        """
        Create a lowlevel representation for the pointer.
        """
        return CtypesPointerRepresentation( rtyper, annotationObject )
    answer.createLowLevelRepresentation = staticmethod(
            createLowLevelRepresentation )

    def specialize( cls, highLevelOperation ): 
        #d#print "specialize:", cls, highLevelOperation
        ctypesStructureType = highLevelOperation.r_result.lowleveltype  
        answer = highLevelOperation.llops.genop(
                "malloc", [ inputconst( Void, ctypesStructureType ) ],
                highLevelOperation.r_result )
        highLevelOperation.genop(
                "setfield",
                [ "contents",
                    highLevelOperation.inputarg( highLevelOperation.args_r[ 0 ], 0 ) ],
                    highLevelOperation.r_result )
        return answer
    answer.specialize = classmethod( specialize )

    # We specialcased accessing pointers be getting their contents attribute
    # because we can't use the memory state from 'cls'.
    # So the obvious way to do it is obsolete (#o#).
    answer._fields_def_ = {"contents": cls}

    # XXX Think about that twice and think about obsoleting
    # the obsoletion above
    answer.default_memorystate = None
    return answer


class RCDLL(CDLL):
    """
    This is the restricted version of ctypes' CDLL class.
    """

    class _CdeclFuncPtr(FunctionPointerTranslation, CDLL._CdeclFuncPtr):
        """
        A simple extension of ctypes function pointers that
        implements a simple interface to the anotator.
        """
        _flags_ = _FUNCFLAG_CDECL



if sys.platform == "win32":
    class RWinDLL(WinDLL):
        """
        This is the restricted version of ctypes' WINDLL class
        """

        class _StdcallFuncPtr(FunctionPointerTranslation, WinDLL._StdcallFuncPtr):
            """
            A simple extension of ctypes function pointers that
            implements a simple interface to the anotator.
            """
            _flags_ = _FUNCFLAG_STDCALL

def RARRAY(typ,length):
    answer = ARRAY(typ,length)
    def compute_result_annotation(cls, *arg_s):
        """
        Answer the result annotation of calling 'cls'.
        """
        assert answer is cls
        return SomeCTypesObject(cls, SomeCTypesObject.OWNSMEMORY)
    answer.compute_result_annotation = classmethod(compute_result_annotation)
    return answer


class AbstractCtypesRepresentation( Repr ):
    """
    The abstract base class of all ctypes low level representations.
    """


class AbstractCtypesStructureRepresentation( AbstractCtypesRepresentation ):
    """
    The abstract base class of ctypes structures' low level representation.
    """

    def __init__( self, rtyper, annotationObject ):
        # XXX This .ll_type may not work for pointers or structures
        # containg structures
        fields = [ ( name, ctypesType.ll_type )
                        for name, ctypesType in annotationObject.knowntype._fields_ ]
        self.lowleveltype = Ptr(
                GcStruct( 
                    'CtypesStructure_%s' %
                    annotationObject.knowntype.__name__, *fields ) )

    def rtype_setattr( self, highLevelOperation ):
        highLevelOperation.genop( 
                "setfield", 
                highLevelOperation.inputargs(
                    *highLevelOperation.args_r[ :3 ] ) )

    def rtype_getattr( self, highLevelOperation ):
        return highLevelOperation.genop( 
                "getfield", 
                highLevelOperation.inputargs(
                    *highLevelOperation.args_r[ :2 ] ),
                highLevelOperation.r_result )


class CtypesMemoryOwningStructureRepresentation( AbstractCtypesStructureRepresentation ):
    """
    The lowlevel representation of a ctypes structure that owns its memory.
    """


class CtypesMemoryAliasStructureRepresentation( AbstractCtypesStructureRepresentation ):
    """
    The lowlevel representation of a ctypes structure that is an alias to
    someone else's memory.
    """


class CtypesPointerRepresentation( AbstractCtypesRepresentation ):
    """
    The lowlevel representation of a cytpes pointer.
    """

    def __init__( self, rtyper, annotationObject ):
        self.lowleveltype = Ptr(
                GcStruct(
                    'CtypesPointer_%s' % annotationObject.knowntype.__name__,
                    ( "contents",
                      rtyper.getrepr(
                        annotationObject.knowntype._type_.compute_annotation() ).lowleveltype ) ) )

    def rtype_getattr( self, highLevelOperation ):
        return highLevelOperation.genop( 
                "getfield", 
                highLevelOperation.inputargs(
                    *highLevelOperation.args_r[ :2 ] ),
                highLevelOperation.r_result )

        
class __extend__( SomeCTypesObject ):
    def rtyper_makerepr( self, rtyper ):
        return self.knowntype.createLowLevelRepresentation( rtyper, self )
        
    def rtyper_makekey( self ):
        return self.__class__, self.knowntype, self.memorystate


class __extend__( pairtype( CtypesPointerRepresentation, IntegerRepr ) ):
    def rtype_getitem( ( self, integer ), highLevelOperation ):
        print "rtype_getitem:", integer
        return highLevelOperation.genop( 
                "getfield", 
                "contents",
                highLevelOperation.r_result )

