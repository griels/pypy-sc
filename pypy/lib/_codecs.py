"""

   _codecs -- Provides access to the codec registry and the builtin
              codecs.

   This module should never be imported directly. The standard library
   module "codecs" wraps this builtin module for use within Python.

   The codec registry is accessible via:

     register(search_function) -> None

     lookup(encoding) -> (encoder, decoder, stream_reader, stream_writer)

   The builtin Unicode codecs use the following interface:

     <encoding>_encode(Unicode_object[,errors='strict']) -> 
         (string object, bytes consumed)

     <encoding>_decode(char_buffer_obj[,errors='strict']) -> 
        (Unicode object, bytes consumed)

   <encoding>_encode() interfaces also accept non-Unicode object as
   input. The objects are then converted to Unicode using
   PyUnicode_FromObject() prior to applying the conversion.

   These <encoding>s are available: utf_8, unicode_escape,
   raw_unicode_escape, unicode_internal, latin_1, ascii (7-bit),
   mbcs (on win32).


Written by Marc-Andre Lemburg (mal@lemburg.com).

Copyright (c) Corporation for National Research Initiatives.

"""
from unicodecodec import *

#/* --- Registry ----------------------------------------------------------- */
codec_search_path = []
codec_search_cache = {}

def codec_register( search_function ):
    """register(search_function)
    
    Register a codec search function. Search functions are expected to take
    one argument, the encoding name in all lower case letters, and return
    a tuple of functions (encoder, decoder, stream_reader, stream_writer).
    """

    if callable(search_function):
        codec_search_path.append(search_function)

register = codec_register

def codec_lookup(encoding):
    """lookup(encoding) -> (encoder, decoder, stream_reader, stream_writer)
    Looks up a codec tuple in the Python codec registry and returns
    a tuple of functions.
    """
    
    result = codec_search_cache.get(encoding,None)
    if not result:
        for search in codec_search_path:
            result=search(encoding)
            if result :
                codec_search_cache[encoding] = result 
                break
    return result

lookup = codec_lookup

def encode(v, encoding='defaultencoding',errors='strict'):
    """encode(obj, [encoding[,errors]]) -> object
    
    Encodes obj using the codec registered for encoding. encoding defaults
    to the default encoding. errors may be given to set a different error
    handling scheme. Default is 'strict' meaning that encoding errors raise
    a ValueError. Other possible values are 'ignore', 'replace' and
    'xmlcharrefreplace' as well as any other name registered with
    codecs.register_error that can handle ValueErrors.
    """
    
    encoder = lookup(encoding)[0]
    if encoder :
        res = encoder(v,errors)
    return res[0]

def decode(obj,encoding='defaultencoding',errors='strict'):
    """decode(obj, [encoding[,errors]]) -> object

    Decodes obj using the codec registered for encoding. encoding defaults
    to the default encoding. errors may be given to set a different error
    handling scheme. Default is 'strict' meaning that encoding errors raise
    a ValueError. Other possible values are 'ignore' and 'replace'
    as well as any other name registerd with codecs.register_error that is
    able to handle ValueErrors.
    """
    decoder = lookup(encoding)[1]
    if decoder:
        res = decoder(obj,errors)
    else:
        raise LookupError("No such encoding")
    return res[0]

def latin_1_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeLatin1(obj,len(obj),errors)
    return res, len(res)
# XXX MBCS codec might involve ctypes ?
def mbcs_decode():
    """None
    """
    pass

def readbuffer_encode( obj,errors='strict'):
    """None
    """
    res = str(obj)
    return res,len(res)

def escape_encode( obj,errors='strict'):
    """None
    """
    s = repr(obj)
    v = s[1:-1]
    return v,len(v)

def utf_8_decode( data,errors='strict',final=None):
    """None
    """
    res = PyUnicode_DecodeUTF8Stateful(data, len(data), errors, final)
    return res,len(res)

def raw_unicode_escape_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeRawUnicodeEscape(data, len(data), errors)
    return res,len(res)

def utf_7_decode( data,errors='strict'):
    """None
    """
    unistr = PyUnicode_DecodeUTF7(data,errors='strict')
    return unistr,len(unistr)
# XXX unicode_escape_encode
def unicode_escape_encode( obj,errors='strict'):
    """None
    """
    pass
# XXX latin_1_decode
def latin_1_decode( data,errors='strict'):
    """None
    """
    pass
# XXX utf_16_decode
def utf_16_decode( data,errors='strict'):
    """None
    """
    pass

def unicode_escape_decode( data,errors='strict'):
    """None
    """
    unistr = PyUnicode_DecodeUnicodeEscape(data,len(data),errors)
    return unistr,len(unistr)


def ascii_decode( data,errors='strict'):
    """None
    """
    res = PyUnicode_DecodeASCII(data,len(data),errors)
    return res,len(res)

def charmap_encode(obj,errors='strict',mapping='latin-1'):
    """None
    """
    res = PyUnicode_EncodeCharmap(obj,len(obj),mapping,errors)
    return res,len(res)

def unicode_internal_encode( obj,errors='strict'):
    """None
    """
    if type(obj) == unicode:
        return obj, len(obj)
    else:
        return PyUnicode_FromUnicode(obj,size),size
# XXX utf_16_ex_decode
def utf_16_ex_decode( data,errors='strict'):
    """None
    """
    pass
# XXX escape_decode Check if this is right
def escape_decode(data,errors='strict'):
    """None
    """
    return data,len(data)

def charbuffer_encode( obj,errors='strict'):
    """None
    """
    res = str(obj)
    return res,len(res)

def charmap_decode( data,errors='strict',mapping=None):
    """None
    """
    res = PyUnicode_DecodeCharmap(data, len(data), mapping, errors)
    return res,len(res)


def utf_7_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF7(obj,len(obj),0,0,errors)
    return res,len(res)

def mbcs_encode( obj,errors='strict'):
    """None
    """
    return (PyUnicode_EncodeMBCS(
			       PyUnicode_AS_UNICODE(obj), 
			       PyUnicode_GET_SIZE(obj),
			       errors),
		    PyUnicode_GET_SIZE(obj));
    

def ascii_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeASCII(obj,len(obj),errors)
    return res,len(res)
##(PyUnicode_EncodeASCII(
##			       PyUnicode_AS_UNICODE(obj), 
##			       PyUnicode_GET_SIZE(obj),
##			       errors),
##                PyUnicode_GET_SIZE(obj))

def utf_16_encode( obj,errors='strict'):
    """None
    """
    u = PyUnicode_EncodeUTF16(obj,len(obj),errors)
    return u,len(u)

def raw_unicode_escape_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeRawUnicodeEscape(obj,len(obj))
    return res,len(res)

def utf_8_encode( obj,errors='strict'):
    """None
    """
    res = PyUnicode_EncodeUTF8(obj,len(obj),errors)
    return res,len(res)
# XXX utf_16_le_encode
def utf_16_le_encode( obj,errors='strict'):
    """None
    """
    pass
# XXX utf_16_be_encode
def utf_16_be_encode( obj,errors='strict'):
    """None
    """
    pass

def unicode_internal_decode( unistr,errors='strict'):
    """None
    """
    if type(unistr) == unicode:
        return unistr,len(unistr)
    else:
        return unicode(unistr),len(unistr)
# XXX utf_16_le_decode
def utf_16_le_decode( data,errors='strict'):
    """None
    """
    pass
# XXX utf_16_be_decode
def utf_16_be_decode( data,errors='strict'):
    """None
    """
    pass

def strict_errors(exc):
    if isinstance(exc,Exception):
        raise exc
    else:
        raise TypeError("codec must pass exception instance")
    
def ignore_errors(exc):
    if isinstance(exc,(UnicodeEncodeError,UnicodeDecodeError,UnicodeTranslateError)):
        return u'',exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%exc)

Py_UNICODE_REPLACEMENT_CHARACTER = u"\ufffd"

def replace_errors(exc):
    if isinstance(exc,UnicodeEncodeError):
        return u'?'*(exc.end-exc.start),exc.end
    elif isinstance(exc,(UnicodeTranslateError,UnicodeDecodeError)):
        return Py_UNICODE_REPLACEMENT_CHARACTER*(exc.end-exc.start),exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%exc)

def xmlcharrefreplace_errors(exc):
    if isinstance(exc,UnicodeEncodeError):
        res = []
        for ch in exc.object[exc.start:exc.end]:
            res += '&#'
            res += str(ord(ch))
            res += ';'
        return u''.join(res),exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%type(exc))
    
def backslashreplace_errors(exc):
    if isinstance(exc,UnicodeEncodeError):
        p=[]
        for c in exc.object[exc.start:exc.end]:
            p.append('\\')
            oc = ord(c)
            if (oc >= 0x00010000):
                p.append('U')
                p.append("%.8x" % ord(c))
            elif (oc >= 0x100):
                p.append('u')
                p.append("%.4x" % ord(c))
            else:
                p.append('x')
                p.append("%.2x" % ord(c))
        return u''.join(p),exc.end
    else:
        raise TypeError("don't know how to handle %.400s in error callback"%type(exc))

register_error("strict",strict_errors)
register_error("ignore",ignore_errors)
register_error("replace",replace_errors)
register_error("xmlcharrefreplace",xmlcharrefreplace_errors)
register_error("backslashreplace",backslashreplace_errors)