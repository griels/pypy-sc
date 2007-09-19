
from pypy.annotation import model as annmodel
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.lltypesystem.lloperation import llop
from pypy.rpython.lltypesystem import ll2ctypes
from pypy.annotation.model import lltype_to_annotation
from pypy.tool.sourcetools import func_with_new_name
from pypy.rlib.objectmodel import Symbolic, CDefinedIntSymbolic
from pypy.rlib import rarithmetic
from pypy.rpython.rbuiltin import parse_kwds
from pypy.rpython.extregistry import ExtRegistryEntry
from pypy.rlib.unroll import unrolling_iterable
from pypy.tool.sourcetools import func_with_new_name
import os

class CConstant(Symbolic):
    """ A C-level constant, maybe #define, rendered directly.
    """
    def __init__(self, c_name, TP):
        self.c_name = c_name
        self.TP = TP

    def annotation(self):
        return lltype_to_annotation(self.TP)

    def lltype(self):
        return self.TP

def llexternal(name, args, result, _callable=None, sources=[], includes=[],
               libraries=[], include_dirs=[], sandboxsafe=False,
               canraise=False, stringpolicy='noauto', _nowrapper=False):
    """ String policies:
    autocast - automatically cast to ll_string, but don't delete it
    fullauto - automatically cast + delete is afterwards
    noauto - don't do anything

    WARNING: It's likely that in future we'll decide to use fullauto by
             default
    """
    ext_type = lltype.FuncType(args, result)
    if _callable is None:
        _callable = ll2ctypes.LL2CtypesCallable(ext_type)
    funcptr = lltype.functionptr(ext_type, name, external='C',
                                 sources=tuple(sources),
                                 includes=tuple(includes),
                                 libraries=tuple(libraries),
                                 include_dirs=tuple(include_dirs),
                                 _callable=_callable,
                                 _safe_not_sandboxed=sandboxsafe,
                                 _debugexc=True, # on top of llinterp
                                 canraise=canraise)
    if isinstance(_callable, ll2ctypes.LL2CtypesCallable):
        _callable.funcptr = funcptr

    if _nowrapper:
        return funcptr

    invoke_around_handlers = not sandboxsafe
    unrolling_arg_tps = unrolling_iterable(enumerate(args))
    def wrapper(*args):
        # XXX the next line is a workaround for the annotation bug
        # shown in rpython.test.test_llann:test_pbctype.  Remove it
        # when the test is fixed...
        assert isinstance(lltype.Signed, lltype.Number)
        real_args = ()
        if stringpolicy == 'fullauto':
            to_free = ()
        for i, tp in unrolling_arg_tps:
            ll_str = None
            if isinstance(tp, lltype.Number):
                real_args = real_args + (cast(tp, args[i]),)
            elif tp is lltype.Float:
                real_args = real_args + (float(args[i]),)
            elif tp is CCHARP and (stringpolicy == 'fullauto' or
                     stringpolicy == 'autocast'):
                s = args[i]
                if s is None:
                    ll_str = lltype.nullptr(CCHARP.TO)
                else:
                    ll_str = str2charp(s)
                real_args = real_args + (ll_str,)
            else:
                real_args = real_args + (args[i],)
            if stringpolicy == 'fullauto':
                if tp is CCHARP:
                    to_free = to_free + (ll_str,)
                else:
                    to_free = to_free + (None,)
        if invoke_around_handlers:
            before = aroundstate.before
            after = aroundstate.after
            if before: before()
            # NB. it is essential that no exception checking occurs after
            # the call to before(), because we don't have the GIL any more!
        result = funcptr(*real_args)
        if invoke_around_handlers:
            if after: after()
        if stringpolicy == 'fullauto':
            for i, tp in unrolling_arg_tps:
                if tp is CCHARP:
                    if to_free[i]:
                        lltype.free(to_free[i], flavor='raw')
        return result
    wrapper._always_inline_ = True
    # for debugging, stick ll func ptr to that
    wrapper._ptr = funcptr
    return func_with_new_name(wrapper, name)

AroundFnPtr = lltype.Ptr(lltype.FuncType([], lltype.Void))
class AroundState:
    def _freeze_(self):
        self.before = None    # or a regular RPython function
        self.after = None     # or a regular RPython function
        return False
aroundstate = AroundState()
aroundstate._freeze_()

# ____________________________________________________________

from pypy.rpython.tool.rfficache import platform

TYPES = []
for _name in 'short int long'.split():
    for name in (_name, 'unsigned ' + _name):
        TYPES.append(name)
TYPES += ['signed char', 'unsigned char',
          'long long', 'unsigned long long', 'size_t']
if os.name != 'nt':
    TYPES.append('mode_t')
    TYPES.append('pid_t')
else:
    MODE_T = lltype.Signed
    PID_T = lltype.Signed

def setup():
    """ creates necessary c-level types
    """
    result = []
    for name in TYPES:
        c_name = name
        if name.startswith('unsigned'):
            name = 'u' + name[9:]
            signed = False
        else:
            signed = (name != 'size_t')
        name = name.replace(' ', '')
        tp = platform.inttype(name.upper(), c_name, signed)
        globals()['r_' + name] = platform.numbertype_to_rclass[tp]
        globals()[name.upper()] = tp
        result.append(tp)
    return result

NUMBER_TYPES = setup()
platform.numbertype_to_rclass[lltype.Signed] = int     # avoid "r_long" for common cases
# ^^^ this creates at least the following names:
# --------------------------------------------------------------------
#        Type           RPython integer class doing wrap-around
# --------------------------------------------------------------------
#        SIGNEDCHAR     r_signedchar
#        UCHAR          r_uchar
#        SHORT          r_short
#        USHORT         r_ushort
#        INT            r_int
#        UINT           r_uint
#        LONG           r_long
#        ULONG          r_ulong
#        LONGLONG       r_longlong
#        ULONGLONG      r_ulonglong
#        SIZE_T         r_size_t
# --------------------------------------------------------------------

def CStruct(name, *fields, **kwds):
    """ A small helper to create external C structure, not the
    pypy one
    """
    hints = kwds.get('hints', {})
    hints = hints.copy()
    kwds['hints'] = hints
    hints['external'] = 'C'
    hints['c_name'] = name
    # Hack: prefix all attribute names with 'c_' to cope with names starting
    # with '_'.  The genc backend removes the 'c_' prefixes...
    c_fields = [('c_' + key, value) for key, value in fields]
    return lltype.Struct(name, *c_fields, **kwds)

def CStructPtr(*args, **kwds):
    return lltype.Ptr(CStruct(*args, **kwds))

def CFixedArray(tp, size):
    return lltype.FixedSizeArray(tp, size)

def CArray(tp):
    return lltype.Array(tp, hints={'nolength': True})
CArray._annspecialcase_ = 'specialize:memo'

def COpaque(name, hints=None, **kwds):
    if hints is None:
        hints = {}
    else:
        hints = hints.copy()
    hints['external'] = 'C'
    hints['c_name'] = name
    def lazy_getsize(result=[]):
        if not result:
            size = platform.sizeof(name, **kwds)
            result.append(size)
        return result[0]
    hints['getsize'] = lazy_getsize
    return lltype.OpaqueType(name, hints)

def COpaquePtr(*args, **kwds):
    return lltype.Ptr(COpaque(*args, **kwds))

def CExternVariable(TYPE, name):
    """Return a pair of functions - a getter and a setter - to access
    the given global C variable.
    """
    # XXX THIS IS ONLY A QUICK HACK TO MAKE IT WORK
    # In general, we need to re-think a few things to be more consistent,
    # e.g. what if a CStruct, COpaque or CExternVariable requires
    # some #include...
    assert not isinstance(TYPE, lltype.ContainerType)
    CTYPE = lltype.FixedSizeArray(TYPE, 1)
    c_variable_ref = CConstant('(&%s)' % (name,), lltype.Ptr(CTYPE))
    def getter():
        return c_variable_ref[0]
    def setter(newvalue):
        c_variable_ref[0] = newvalue
    return (func_with_new_name(getter, '%s_getter' % (name,)),
            func_with_new_name(setter, '%s_setter' % (name,)))

get_errno, set_errno = CExternVariable(lltype.Signed, 'errno')

# char, represented as a Python character
# (use SIGNEDCHAR or UCHAR for the small integer types)
CHAR = lltype.Char

# double  - XXX there is no support for the C type 'float' in the C backend yet
DOUBLE = lltype.Float

# void *   - for now, represented as char *
VOIDP = lltype.Ptr(lltype.Array(lltype.Char, hints={'nolength': True}))

# char *
CCHARP = lltype.Ptr(lltype.Array(lltype.Char, hints={'nolength': True}))

# int *
INTP = lltype.Ptr(lltype.Array(lltype.Signed, hints={'nolength': True}))

# double *
DOUBLEP = lltype.Ptr(lltype.Array(DOUBLE, hints={'nolength': True}))

# various type mapping
# str -> char*
def str2charp(s):
    """ str -> char*
    """
    array = lltype.malloc(CCHARP.TO, len(s) + 1, flavor='raw')
    for i in range(len(s)):
        array[i] = s[i]
    array[len(s)] = '\x00'
    return array

def free_charp(cp):
    lltype.free(cp, flavor='raw')

# char* -> str
# doesn't free char*
def charp2str(cp):
    l = []
    i = 0
    while cp[i] != '\x00':
        l.append(cp[i])
        i += 1
    return "".join(l)

# char**
CCHARPP = lltype.Ptr(lltype.Array(CCHARP, hints={'nolength': True}))

def liststr2charpp(l):
    """ list[str] -> char**, NULL terminated
    """
    array = lltype.malloc(CCHARPP.TO, len(l) + 1, flavor='raw')
    for i in range(len(l)):
        array[i] = str2charp(l[i])
    array[len(l)] = lltype.nullptr(CCHARP.TO)
    return array

def free_charpp(ref):
    """ frees list of char**, NULL terminated
    """
    i = 0
    while ref[i]:
        free_charp(ref[i])
        i += 1
    lltype.free(ref, flavor='raw')

cast = ll2ctypes.force_cast      # a forced, no-checking cast


def size_and_sign(tp):
    size = sizeof(tp)
    try:
        unsigned = not tp._type.SIGNED
    except AttributeError:
        if tp in [lltype.Char, lltype.Float, lltype.Signed] or\
               isinstance(tp, lltype.Ptr):
            unsigned = False
        else:
            unsigned = False
    return size, unsigned

def sizeof(tp):
    if isinstance(tp, lltype.FixedSizeArray):
        return sizeof(tp.OF) * tp.length
    if isinstance(tp, lltype.Struct):
        # the hint is present in structures probed by rffi_platform.
        size = tp._hints.get('size')
        if size is None:
            size = llmemory.sizeof(tp)    # a symbolic result in this case
        return size
    if isinstance(tp, lltype.Ptr):
        tp = ULONG     # XXX!
    if tp is lltype.Char:
        return 1
    if tp is lltype.Float:
        return 8
    assert isinstance(tp, lltype.Number)
    if tp is lltype.Signed:
        return ULONG._type.BITS/8
    return tp._type.BITS/8

# ********************** some helpers *******************

def make(STRUCT, **fields):
    """ Malloc a structure and populate it's fields
    """
    ptr = lltype.malloc(STRUCT, flavor='raw')
    for name, value in fields.items():
        setattr(ptr, name, value)
    return ptr

class MakeEntry(ExtRegistryEntry):
    _about_ = make

    def compute_result_annotation(self, s_type, **s_fields):
        TP = s_type.const
        if not isinstance(TP, lltype.Struct):
            raise TypeError("make called with %s instead of Struct as first argument" % TP)
        return annmodel.SomePtr(lltype.Ptr(TP))

    def specialize_call(self, hop, **fields):
        assert hop.args_s[0].is_constant()
        vlist = [hop.inputarg(lltype.Void, arg=0)]
        flags = {'flavor':'raw'}
        vlist.append(hop.inputconst(lltype.Void, flags))
        v_ptr = hop.genop('malloc', vlist, resulttype=hop.r_result.lowleveltype)
        hop.has_implicit_exception(MemoryError)   # record that we know about it
        hop.exception_is_here()
        for name, i in fields.items():
            name = name[2:]
            v_arg = hop.inputarg(hop.args_r[i], arg=i)
            v_name = hop.inputconst(lltype.Void, name)
            hop.genop('setfield', [v_ptr, v_name, v_arg])
        return v_ptr


def structcopy(pdst, psrc):
    """Copy all the fields of the structure given by 'psrc'
    into the structure given by 'pdst'.
    """
    copy_fn = _get_structcopy_fn(lltype.typeOf(pdst), lltype.typeOf(psrc))
    copy_fn(pdst, psrc)
structcopy._annspecialcase_ = 'specialize:ll'

def _get_structcopy_fn(PDST, PSRC):
    assert PDST == PSRC
    if isinstance(PDST.TO, lltype.Struct):
        STRUCT = PDST.TO
        fields = [(name, STRUCT._flds[name]) for name in STRUCT._names]
        unrollfields = unrolling_iterable(fields)

        def copyfn(pdst, psrc):
            for name, TYPE in unrollfields:
                if isinstance(TYPE, lltype.ContainerType):
                    structcopy(getattr(pdst, name), getattr(psrc, name))
                else:
                    setattr(pdst, name, getattr(psrc, name))

        return copyfn
    else:
        raise NotImplementedError('structcopy: type %r' % (PDST.TO,))
_get_structcopy_fn._annspecialcase_ = 'specialize:memo'


def setintfield(pdst, fieldname, value):
    """Maybe temporary: a helper to set an integer field into a structure,
    transparently casting between the various integer types.
    """
    STRUCT = lltype.typeOf(pdst).TO
    TSRC = lltype.typeOf(value)
    TDST = getattr(STRUCT, fieldname)
    assert isinstance(TSRC, lltype.Number)
    assert isinstance(TDST, lltype.Number)
    setattr(pdst, fieldname, cast(TDST, value))
setintfield._annspecialcase_ = 'specialize:ll_and_arg(1)'
