"""Marshal module written in Python.

This doesn't marshal code objects, but supports everything else.
Performance or careful error checking is not an issue.

"""

import StringIO
import string
from types import *
try:
    import new
except ImportError:
    new = None

TYPE_NULL     = '0'
TYPE_NONE     = 'N'
TYPE_FALSE    = 'F'
TYPE_TRUE     = 'T'
TYPE_STOPITER = 'S'
TYPE_ELLIPSIS = '.'
TYPE_INT      = 'i'
TYPE_INT64    = 'I'
TYPE_FLOAT    = 'f'
TYPE_COMPLEX  = 'x'
TYPE_LONG     = 'l'
TYPE_STRING   = 's'
TYPE_INTERNED = 't'
TYPE_STRINGREF= 'R'
TYPE_TUPLE    = '('
TYPE_LIST     = '['
TYPE_DICT     = '{'
TYPE_CODE     = 'c'
TYPE_UNKNOWN  = '?'
TYPE_UNICODE  = 'u'
TYPE_UNKNOWN  = '?'
TYPE_SET      = '<'
TYPE_FROZENSET= '>'

class Marshaller:

    dispatch = {}

    def __init__(self, f):
        self.f = f

    def dump(self, x):
        self.dispatch[type(x)](self, x)

    def w_long64(self, x):
        self.w_long(x)
        self.w_long(x>>32)

    def w_long(self, x):
        write = self.f.write
        write(chr((x)     & 0xff))
        write(chr((x>> 8) & 0xff))
        write(chr((x>>16) & 0xff))
        write(chr((x>>24) & 0xff))

    def w_short(self, x):
        write = self.f.write
        write(chr((x)     & 0xff))
        write(chr((x>> 8) & 0xff))

    def dump_none(self, x):
        self.f.write(TYPE_NONE)
    dispatch[NoneType] = dump_none

    def dump_bool(self, x):
        if x:
            self.f.write(TYPE_TRUE)
        else:
            self.f.write(TYPE_FALSE)
    dispatch[bool] = dump_bool

    def dump_stopiter(self, x):
        assert x is StopIteration
        self.f.write(TYPE_STOPITER)
    dispatch[type(StopIteration)] = dump_stopiter

    def dump_ellipsis(self, x):
        self.f.write(TYPE_ELLIPSIS)
    
    try:
        dispatch[EllipsisType] = dump_ellipsis
    except NameError:
        pass

    def dump_int(self, x):
        y = x>>31
        if y and y != -1:
            self.f.write(TYPE_INT64)
            self.w_long64(x)
        else:
            self.f.write(TYPE_INT)
            self.w_long(x)
    dispatch[IntType] = dump_int

    def dump_long(self, x):
        self.f.write(TYPE_LONG)
        sign = 1
        if x < 0:
            sign = -1
            x = -x
        digits = []
        while x:
            digits.append(x & 0x7FFF)
            x = x>>15
        self.w_long(len(digits) * sign)
        for d in digits:
            self.w_short(d)
    dispatch[LongType] = dump_long

    def dump_float(self, x):
        write = self.f.write
        write(TYPE_FLOAT)
        s = `x`
        write(chr(len(s)))
        write(s)
    dispatch[FloatType] = dump_float

    def dump_complex(self, x):
        write = self.f.write
        write(TYPE_COMPLEX)
        s = `x.real`
        write(chr(len(s)))
        write(s)
        s = `x.imag`
        write(chr(len(s)))
        write(s)
    try:
        dispatch[ComplexType] = dump_complex
    except NameError:
        pass

    def dump_string(self, x):
        # XXX we can't check for interned strings, yet,
        # so we (for now) never create TYPE_INTERNED or TYPE_STRINGREF
        self.f.write(TYPE_STRING)
        self.w_long(len(x))
        self.f.write(x)
    dispatch[StringType] = dump_string

    def dump_unicode(self, x):
        self.f.write(TYPE_UNICODE)
        s = x.encode('utf8')
        self.w_long(len(s))
        self.f.write(s)
    dispatch[UnicodeType] = dump_unicode

    def dump_tuple(self, x):
        self.f.write(TYPE_TUPLE)
        self.w_long(len(x))
        for item in x:
            self.dump(item)
    dispatch[TupleType] = dump_tuple

    def dump_list(self, x):
        self.f.write(TYPE_LIST)
        self.w_long(len(x))
        for item in x:
            self.dump(item)
    dispatch[ListType] = dump_list

    def dump_dict(self, x):
        self.f.write(TYPE_DICT)
        for key, value in x.items():
            self.dump(key)
            self.dump(value)
        self.f.write(TYPE_NULL)
    dispatch[DictionaryType] = dump_dict

    def dump_code(self, x):
        self.f.write(TYPE_CODE)
        self.w_long(x.co_argcount)
        self.w_long(x.co_nlocals)
        self.w_long(x.co_stacksize)
        self.w_long(x.co_flags)
        self.dump(x.co_code)
        self.dump(x.co_consts)
        self.dump(x.co_names)
        self.dump(x.co_varnames)
        self.dump(x.co_freevars)
        self.dump(x.co_cellvars)
        self.dump(x.co_filename)
        self.dump(x.co_name)
        self.w_long(x.co_firstlineno)
        self.dump(x.co_lnotab)
    try:
        dispatch[CodeType] = dump_code
    except NameError:
        pass


class NULL:
    pass

class Unmarshaller:

    dispatch = {}

    def __init__(self, f):
        self.f = f
        self._stringtable = []

    def load(self):
        c = self.f.read(1)
        if not c:
            raise EOFError
        return self.dispatch[c](self)

    def r_short(self):
        read = self.f.read
        lo = ord(read(1))
        hi = ord(read(1))
        x = lo | (hi<<8)
        if x & 0x8000:
            x = x - 0x10000
        return x

    def r_long(self):
        read = self.f.read
        a = ord(read(1))
        b = ord(read(1))
        c = ord(read(1))
        d = ord(read(1))
        x = a | (b<<8) | (c<<16) | (d<<24)
        if d & 0x80 and x > 0:
            x = -((1L<<32) - x)
        return x

    def r_long64(self):
        read = self.f.read
        a = ord(read(1))
        b = ord(read(1))
        c = ord(read(1))
        d = ord(read(1))
        e = long(ord(read(1)))
        f = long(ord(read(1)))
        g = long(ord(read(1)))
        h = long(ord(read(1)))
        x = a | (b<<8) | (c<<16) | (d<<24)
        x = x | (e<<32) | (f<<40) | (g<<48) | (h<<56)
        if h & 0x80 and x > 0:
            x = -((1L<<64) - x)
        return x

    def load_null(self):
        return NULL
    dispatch[TYPE_NULL] = load_null

    def load_none(self):
        return None
    dispatch[TYPE_NONE] = load_none

    def load_true(self):
        return True
    dispatch[TYPE_TRUE] = load_true

    def load_false(self):
        return False
    dispatch[TYPE_FALSE] = load_false

    def load_stopiter(self):
        return StopIteration
    dispatch[TYPE_STOPITER] = load_stopiter

    def load_ellipsis(self):
        return Ellipsis
    dispatch[TYPE_ELLIPSIS] = load_ellipsis

    def load_int(self):
        return self.r_long()
    dispatch[TYPE_INT] = load_int

    def load_int64(self):
        return self.r_long64()
    dispatch[TYPE_INT64] = load_int64

    def load_long(self):
        size = self.r_long()
        sign = 1
        if size < 0:
            sign = -1
            size = -size
        x = 0L
        for i in range(size):
            d = self.r_short()
            x = x | (d<<(i*15L))
        return x * sign
    dispatch[TYPE_LONG] = load_long

    def load_float(self):
        n = ord(self.f.read(1))
        s = self.f.read(n)
        return string.atof(s)
    dispatch[TYPE_FLOAT] = load_float

    def load_complex(self):
        n = ord(self.f.read(1))
        s = self.f.read(n)
        real = float(s)
        n = ord(self.f.read(1))
        s = self.f.read(n)
        imag = float(s)
        return complex(real, imag)
    dispatch[TYPE_COMPLEX] = load_complex

    def load_string(self):
        n = self.r_long()
        return self.f.read(n)
    dispatch[TYPE_STRING] = load_string

    def load_interned(self):
        n = self.r_long()
        ret = intern(self.f.read(n))
        self._stringtable.append(ret)
        return ret
    dispatch[TYPE_INTERNED] = load_interned

    def load_stringref(self):
        n = self.r_long()
        return self._stringtable[n]
    dispatch[TYPE_STRINGREF] = load_stringref

    def load_unicode(self):
        n = self.r_long()
        s = self.f.read(n)
        ret = s.decode('utf8')
        return ret
    dispatch[TYPE_UNICODE] = load_unicode

    def load_tuple(self):
        return tuple(self.load_list())
    dispatch[TYPE_TUPLE] = load_tuple

    def load_list(self):
        n = self.r_long()
        list = []
        for i in range(n):
            list.append(self.load())
        return list
    dispatch[TYPE_LIST] = load_list

    def load_dict(self):
        d = {}
        while 1:
            key = self.load()
            if key is NULL:
                break
            value = self.load()
            d[key] = value
        return d
    dispatch[TYPE_DICT] = load_dict

    def load_code(self):
        argcount = self.r_long()
        nlocals = self.r_long()
        stacksize = self.r_long()
        flags = self.r_long()
        code = self.load()
        consts = self.load()
        names = self.load()
        varnames = self.load()
        freevars = self.load()
        cellvars = self.load()
        filename = self.load()
        name = self.load()
        firstlineno = self.r_long()
        lnotab = self.load()
        if not new:
            raise RuntimeError, "can't unmarshal code objects; no 'new' module"
        return new.code(argcount, nlocals, stacksize, flags, code, consts,
                        names, varnames, filename, name, firstlineno, lnotab,
                        freevars, cellvars)
    dispatch[TYPE_CODE] = load_code


def dump(x, f):
    Marshaller(f).dump(x)

def load(f):
    return Unmarshaller(f).load()

def dumps(x):
    f = StringIO.StringIO()
    dump(x, f)
    return f.getvalue()

def loads(s):
    f = StringIO.StringIO(s)
    return load(f)
