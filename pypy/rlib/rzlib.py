from pypy.rpython.lltypesystem import rffi, lltype
from pypy.rpython.tool import rffi_platform

includes = ['zlib.h']
libraries = ['z']

constantnames = '''
    Z_OK  Z_STREAM_ERROR  Z_BUF_ERROR  Z_MEM_ERROR  Z_STREAM_END
    Z_DEFLATED  Z_DEFAULT_STRATEGY  Z_DEFAULT_COMPRESSION
    Z_NO_FLUSH  Z_FINISH
    MAX_WBITS  MAX_MEM_LEVEL
    '''.split()

class SimpleCConfig:
    """
    Definitions for basic types defined by zlib.
    """
    _includes_ = includes

    # XXX If Z_PREFIX was defined for the libz build, then these types are
    # named z_uInt, z_uLong, and z_Bytef instead.
    uInt = rffi_platform.SimpleType('uInt', rffi.UINT)
    uLong = rffi_platform.SimpleType('uLong', rffi.ULONG)
    Bytef = rffi_platform.SimpleType('Bytef', rffi.UCHAR)
    voidpf = rffi_platform.SimpleType('voidpf', rffi.VOIDP)

    ZLIB_VERSION = rffi_platform.DefinedConstantString('ZLIB_VERSION')

for _name in constantnames:
    setattr(SimpleCConfig, _name, rffi_platform.ConstantInteger(_name))

config = rffi_platform.configure(SimpleCConfig)
voidpf = config['voidpf']
uInt = config['uInt']
uLong = config['uLong']
Bytef = config['Bytef']
Bytefp = lltype.Ptr(lltype.Array(Bytef, hints={'nolength': True}))

ZLIB_VERSION = config['ZLIB_VERSION']

for _name in constantnames:
    globals()[_name] = config[_name]

# The following parameter is copied from zutil.h, version 0.95,
# according to CPython's zlibmodule.c
if MAX_MEM_LEVEL >= 8:
    DEF_MEM_LEVEL = 8
else:
    DEF_MEM_LEVEL = MAX_MEM_LEVEL

OUTPUT_BUFFER_SIZE = 32*1024


class ComplexCConfig:
    """
    Definitions of structure types defined by zlib and based on SimpleCConfig
    definitions.
    """
    _includes_ = includes

    z_stream = rffi_platform.Struct(
        'z_stream',
        [('next_in', Bytefp),
         ('avail_in', uInt),
         ('total_in', uLong),

         ('next_out', Bytefp),
         ('avail_out', uInt),
         ('total_out', uLong),

         ('msg', rffi.CCHARP),

         ('zalloc', lltype.Ptr(
                    lltype.FuncType([voidpf, uInt, uInt], voidpf))),
         ('zfree', lltype.Ptr(
                    lltype.FuncType([voidpf, voidpf], lltype.Void))),

         ('opaque', voidpf),

         ('data_type', rffi.INT),
         ('adler', uLong),
         ('reserved', uLong)
         ])

config = rffi_platform.configure(ComplexCConfig)
z_stream = config['z_stream']
z_stream_p = lltype.Ptr(z_stream)

def zlib_external(*a, **kw):
    kw['includes'] = includes
    kw['libraries'] = libraries
    return rffi.llexternal(*a, **kw)

_crc32 = zlib_external('crc32', [uLong, Bytefp, uInt], uLong)
_adler32 = zlib_external('adler32', [uLong, Bytefp, uInt], uLong)


# XXX I want to call deflateInit2, not deflateInit2_
_deflateInit2_ = zlib_external(
    'deflateInit2_',
    [z_stream_p, # stream
     rffi.INT, # level
     rffi.INT, # method
     rffi.INT, # window bits
     rffi.INT, # mem level
     rffi.INT, # strategy
     rffi.CCHARP, # version
     rffi.INT], # stream size
    rffi.INT)
_deflate = zlib_external('deflate', [z_stream_p, rffi.INT], rffi.INT)

_deflateEnd = zlib_external('deflateEnd', [z_stream_p], rffi.INT)

def _deflateInit2(stream, level, method, wbits, memlevel, strategy):
    size = rffi.sizeof(z_stream)
    result = _deflateInit2_(
        stream, level, method, wbits, memlevel, strategy, ZLIB_VERSION, size)
    return result

# ____________________________________________________________

CRC32_DEFAULT_START = 0

def crc32(string, start=CRC32_DEFAULT_START):
    """
    Compute the CRC32 checksum of the string, possibly with the given
    start value, and return it as a unsigned 32 bit integer.
    """
    bytes = rffi.str2charp(string)
    checksum = _crc32(start, rffi.cast(Bytefp, bytes), len(string))
    rffi.free_charp(bytes)
    return checksum


ADLER32_DEFAULT_START = 1

def adler32(string, start=ADLER32_DEFAULT_START):
    """
    Compute the Adler-32 checksum of the string, possibly with the given
    start value, and return it as a unsigned 32 bit integer.
    """
    bytes = rffi.str2charp(string)
    checksum = _adler32(start, rffi.cast(Bytefp, bytes), len(string))
    rffi.free_charp(bytes)
    return checksum

# ____________________________________________________________

class RZlibError(Exception):
    """Exception raised by failing operations in pypy.rlib.rzlib."""
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

    def fromstream(stream, err, while_doing):
        """Return a RZlibError with a message formatted from a zlib error
        code and stream.
        """
        if stream.c_msg:
            reason = rffi.charp2str(stream.c_msg)
        else:
            reason = ""
        if not reason and err == Z_MEM_ERROR:
            reason = "out of memory"
        if reason:
            delim = ": "
        else:
            delim = ""
        msg = "Error %d %s%s%s" % (err, while_doing, delim, reason)
        return RZlibError(msg)
    fromstream = staticmethod(fromstream)


def deflateInit(level=Z_DEFAULT_COMPRESSION, method=Z_DEFLATED,
                wbits=MAX_WBITS, memLevel=DEF_MEM_LEVEL,
                strategy=Z_DEFAULT_STRATEGY):
    """
    Allocate and return an opaque 'stream' object that can be used to
    compress data.
    """
    stream = lltype.malloc(z_stream, flavor='raw', zero=True)
    err = _deflateInit2(stream, level, method, wbits, memLevel, strategy)
    if err == Z_OK:
        return stream
    else:
        try:
            if err == Z_STREAM_ERROR:
                raise ValueError("Invalid initialization option")
            else:
                raise RZlibError.fromstream(stream, err,
                    "while creating compression object")
        finally:
            lltype.free(stream, flavor='raw')


def deflateEnd(stream):
    """
    Free the resources associated with the deflate stream.
    Note that this may raise RZlibError.
    """
    try:
        err = _deflateEnd(stream)
        if err != Z_OK:
            raise RZlibError.fromstream(stream, err,
                "while finishing compression")
    finally:
        lltype.free(stream, flavor='raw')


def compress(stream, data, flush=Z_NO_FLUSH):
    """
    Feed more data into a deflate stream.  Returns a string containing
    (a part of) the compressed data.  If flush != Z_NO_FLUSH, this also
    flushes the output data; see zlib.h or the documentation of the
    zlib module for the possible values of 'flush'.
    """
    # Warning, reentrant calls to the zlib with a given stream can cause it
    # to crash.  The caller of pypy.rlib.rzlib should use locks if needed.

    # Prepare the input buffer for the stream
    inbuf = lltype.malloc(rffi.CCHARP.TO, len(data), flavor='raw')
    try:
        for i in xrange(len(data)):
            inbuf[i] = data[i]
        stream.c_next_in = rffi.cast(Bytefp, inbuf)
        rffi.setintfield(stream, 'c_avail_in', len(data))

        # Prepare the output buffer
        outbuf = lltype.malloc(rffi.CCHARP.TO, OUTPUT_BUFFER_SIZE,
                               flavor='raw')
        try:
            # Strategy: we call deflate() to get as much output data as
            # fits in the buffer, then accumulate all output into a list
            # of characters 'result'.  We don't need to gradually
            # increase the output buffer size because there is no
            # quadratic factor.
            result = []

            while True:
                stream.c_next_out = rffi.cast(Bytefp, outbuf)
                rffi.setintfield(stream, 'c_avail_out', OUTPUT_BUFFER_SIZE)
                err = _deflate(stream, flush)
                if err == Z_OK or err == Z_STREAM_END:
                    # accumulate data into 'result'
                    avail_out = rffi.cast(lltype.Signed, stream.c_avail_out)
                    for i in xrange(OUTPUT_BUFFER_SIZE - avail_out):
                        result.append(outbuf[i])
                    # if the output buffer is full, there might be more data
                    # so we need to try again.  Otherwise, we're done.
                    if avail_out > 0:
                        break
                    # We're also done if we got a Z_STREAM_END (which should
                    # only occur when flush == Z_FINISH).
                    if err == Z_STREAM_END:
                        break
                elif err == Z_BUF_ERROR:
                    # We will only get Z_BUF_ERROR if the output buffer
                    # was full but there wasn't more output when we
                    # tried again, so it is not an error condition.
                    avail_out = rffi.cast(lltype.Signed, stream.c_avail_out)
                    assert avail_out == OUTPUT_BUFFER_SIZE
                    break
                else:
                    raise RZlibError.fromstream(stream, err,
                        "while compressing")
        finally:
            lltype.free(outbuf, flavor='raw')
    finally:
        lltype.free(inbuf, flavor='raw')

    assert not stream.c_avail_in, "not all input consumed by deflate()"
    return ''.join(result)
