import struct
from pypy.module.struct import standardfmttable as std
from pypy.rpython.tool import rffi_platform
from pypy.rpython.lltypesystem import lltype, rffi
from pypy.rlib.rarithmetic import r_singlefloat
from pypy.translator.tool.cbuild import ExternalCompilationInfo

native_is_bigendian = struct.pack("=i", 1) == struct.pack(">i", 1)

native_fmttable = {
    'x': std.standard_fmttable['x'],
    'c': std.standard_fmttable['c'],
    's': std.standard_fmttable['s'],
    'p': std.standard_fmttable['p'],
    }

# ____________________________________________________________

double_buf = lltype.malloc(rffi.DOUBLEP.TO, 1, flavor='raw', immortal=True)
float_buf = lltype.malloc(rffi.FLOATP.TO, 1, flavor='raw', immortal=True)

def pack_double(fmtiter):
    doubleval = fmtiter.accept_float_arg()
    double_buf[0] = doubleval
    p = rffi.cast(rffi.CCHARP, double_buf)
    for i in range(sizeof_double):
        fmtiter.result.append(p[i])

def unpack_double(fmtiter):
    input = fmtiter.read(sizeof_double)
    p = rffi.cast(rffi.CCHARP, double_buf)
    for i in range(sizeof_double):
        p[i] = input[i]
    doubleval = double_buf[0]
    fmtiter.appendobj(doubleval)

def pack_float(fmtiter):
    doubleval = fmtiter.accept_float_arg()
    floatval = r_singlefloat(doubleval)
    float_buf[0] = floatval
    p = rffi.cast(rffi.CCHARP, float_buf)
    for i in range(sizeof_float):
        fmtiter.result.append(p[i])

def unpack_float(fmtiter):
    input = fmtiter.read(sizeof_float)
    p = rffi.cast(rffi.CCHARP, float_buf)
    for i in range(sizeof_float):
        p[i] = input[i]
    floatval = float_buf[0]
    doubleval = float(floatval)
    fmtiter.appendobj(doubleval)

# ____________________________________________________________
#
# Use rffi_platform to get the native sizes and alignments from the C compiler

def setup():
    INSPECT = {'b': 'signed char',
               'h': 'signed short',
               'i': 'signed int',
               'l': 'signed long',
               'q': 'signed long long',
               'B': 'unsigned char',
               'H': 'unsigned short',
               'I': 'unsigned int',
               'L': 'unsigned long',
               'Q': 'unsigned long long',
               'P': 'char *',
               'f': 'float',
               'd': 'double',
               }

    pre_include_lines = []
    for fmtchar, ctype in INSPECT.items():
        pre_include_lines += ("""
            struct about_%s {
                char pad;
                %s field;
            };
        """ % (fmtchar, ctype)).split("\n")

    class CConfig:
        _compilation_info_ = ExternalCompilationInfo(
            pre_include_lines = pre_include_lines
        )

    for fmtchar, ctype in INSPECT.items():
        setattr(CConfig, fmtchar, rffi_platform.Struct(
            "struct about_%s" % (fmtchar,),
            [('field', lltype.FixedSizeArray(rffi.CHAR, 1))]))

    cConfig = rffi_platform.configure(CConfig)

    for fmtchar, ctype in INSPECT.items():
        S = cConfig[fmtchar]
        alignment = rffi.offsetof(S, 'c_field')
        size = rffi.sizeof(S.c_field)
        signed = 'a' <= fmtchar <= 'z'

        if fmtchar == 'f':
            pack = pack_float
            unpack = unpack_float
        elif fmtchar == 'd':
            pack = pack_double
            unpack = unpack_double
        else:
            cpython_checks_range = fmtchar in 'bBhH'
            pack = std.make_int_packer(size, signed, cpython_checks_range)
            unpack = std.make_int_unpacker(size, signed)

        native_fmttable[fmtchar] = {'size': size,
                                    'alignment': alignment,
                                    'pack': pack,
                                    'unpack': unpack}

setup()

sizeof_double = native_fmttable['d']['size']
sizeof_float  = native_fmttable['f']['size']
