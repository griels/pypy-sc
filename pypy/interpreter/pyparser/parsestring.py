from pypy.interpreter import gateway
from pypy.interpreter.error import OperationError

def parsestr(space, encoding, s):
    # compiler.transformer.Transformer.decode_literal depends on what 
    # might seem like minor details of this function -- changes here 
    # must be reflected there.

    # we use ps as "pointer to s"
    # q is the virtual last char index of the string
    ps = 0
    quote = s[ps]
    rawmode = False
    unicode = False

    # string decoration handling
    o = ord(quote)
    isalpha = (o>=97 and o<=122) or (o>=65 and o<=90)
    if isalpha or quote == '_':
        if quote == 'u' or quote == 'U':
            ps += 1
            quote = s[ps]
            unicode = True
        if quote == 'r' or quote == 'R':
            ps += 1
            quote = s[ps]
            rawmode = True
    if quote != "'" and quote != '"':
        raise_app_valueerror(space,
                             'Internal error: parser passed unquoted literal')
    ps += 1
    q = len(s) - 1
    if s[q] != quote:
        raise_app_valueerror(space, 'Internal error: parser passed unmatched '
                                    'quotes in literal')
    if q-ps >= 4 and s[ps] == quote and s[ps+1] == quote:
        # triple quotes
        ps += 2
        if s[q-1] != quote or s[q-2] != quote:
            raise_app_valueerror(space, 'Internal error: parser passed '
                                        'unmatched triple quotes in literal')
        q -= 2

    if unicode: # XXX Py_UnicodeFlag is ignored for now
        if encoding is None or encoding == "iso-8859-1":
            buf = s
            bufp = ps
            bufq = q
            u = None
        else:
            # "\XX" may become "\u005c\uHHLL" (12 bytes)
            lis = [] # using a list to assemble the value
            end = q
            while ps < end:
                if s[ps] == '\\':
                    lis.append(s[ps])
                    ps += 1
                    if ord(s[ps]) & 0x80:
                        lis.append("u005c")
                if ord(s[ps]) & 0x80: # XXX inefficient
                    w, ps = decode_utf8(space, s, ps, end, "utf-16-be")
                    rn = len(w)
                    assert rn % 2 == 0
                    for i in range(0, rn, 2):
                        lis.append('\\u')
                        lis.append(hexbyte(ord(w[i])))
                        lis.append(hexbyte(ord(w[i+1])))
                else:
                    lis.append(s[ps])
                    ps += 1
            buf = ''.join(lis)
            bufp = 0
            bufq = len(buf)
        assert 0 <= bufp <= bufq
        w_substr = space.wrap(buf[bufp : bufq])
        if rawmode:
            w_v = PyUnicode_DecodeRawUnicodeEscape(space, w_substr)
        else:
            w_v = PyUnicode_DecodeUnicodeEscape(space, w_substr)
        return w_v

    need_encoding = (encoding is not None and
                     encoding != "utf-8" and encoding != "iso-8859-1")
    # XXX add strchr like interface to rtyper
    assert 0 <= ps <= q
    substr = s[ps : q]
    if rawmode or '\\' not in s[ps:]:
        if need_encoding:
            w_u = PyUnicode_DecodeUTF8(space, space.wrap(substr))
            #w_v = space.wrap(space.unwrap(w_u).encode(encoding)) this works
            w_v = PyUnicode_AsEncodedString(space, w_u, space.wrap(encoding))
            return w_v
        else:
            return space.wrap(substr)

    enc = None
    if need_encoding:
         enc = encoding
    v = PyString_DecodeEscape(space, substr, unicode, enc)
    return space.wrap(v)

def hexbyte(val):
    result = "%x" % val
    if len(result) == 1:
        result = "0" + result
    return result

def PyString_DecodeEscape(space, s, unicode, recode_encoding):
    """
    Unescape a backslash-escaped string. If unicode is non-zero,
    the string is a u-literal. If recode_encoding is non-zero,
    the string is UTF-8 encoded and should be re-encoded in the
    specified encoding.
    """
    lis = []
    ps = 0
    end = len(s)
    while ps < end:
        if s[ps] != '\\':
            # note that the C code has a label here.
            # the logic is the same.
            if recode_encoding and ord(s[ps]) & 0x80:
                w, ps = decode_utf8(space, s, ps, end, recode_encoding)
                # Append bytes to output buffer.
                lis.append(w)
            else:
                lis.append(s[ps])
                ps += 1
            continue
        ps += 1
        if ps == end:
            raise_app_valueerror(space, 'Trailing \\ in string')
        prevps = ps
        ch = s[ps]
        ps += 1
        # XXX This assumes ASCII!
        if ch == '\n':
            pass
        elif ch == '\\':
            lis.append('\\')
        elif ch == "'":
            lis.append("'")
        elif ch == '"':
            lis.append('"')
        elif ch == 'b':
            lis.append("\010")
        elif ch == 'f':
            lis.append('\014') # FF
        elif ch == 't':
            lis.append('\t')
        elif ch == 'n':
            lis.append('\n')
        elif ch == 'r':
            lis.append('\r')
        elif ch == 'v':
            lis.append('\013') # VT
        elif ch == 'a':
            lis.append('\007') # BEL, not classic C
        elif ch in '01234567':
            # Look for up to two more octal digits
            span = ps
            span += (span < end) and (s[span] in '01234567')
            span += (span < end) and (s[span] in '01234567')
            lis.append(chr(int(s[prevps : span], 8)))
            ps = span
        elif ch == 'x':
            if ps+2 <= end and isxdigit(s[ps]) and isxdigit(s[ps + 1]):
                lis.append(chr(int(s[ps : ps + 2], 16)))
                ps += 2
            else:
                raise_app_valueerror(space, 'invalid \\x escape')
            # ignored replace and ignore for now

        elif unicode and (ch == 'u' or ch == 'U' or ch == 'N'):
            raise_app_valueerror(space, 'Unicode escapes not legal '
                                        'when Unicode disabled')
        else:
            # this was not an escape, so the backslash
            # has to be added, and we start over in
            # non-escape mode.
            lis.append('\\')
            ps -= 1
            assert ps >= 0
            continue
            # an arbitry number of unescaped UTF-8 bytes may follow.

    buf = ''.join(lis)
    return buf


def isxdigit(ch):
    return (ch >= '0' and ch <= '9' or
            ch >= 'a' and ch <= 'f' or
            ch >= 'A' and ch <= 'F')

app = gateway.applevel(r'''
    def PyUnicode_DecodeUnicodeEscape(data):
        import _codecs
        return _codecs.unicode_escape_decode(data)[0]

    def PyUnicode_DecodeRawUnicodeEscape(data):
        import _codecs
        return _codecs.raw_unicode_escape_decode(data)[0]

    def PyUnicode_DecodeUTF8(data):
        import _codecs
        return _codecs.utf_8_decode(data)[0]

    def PyUnicode_AsEncodedString(data, encoding):
        import _codecs
        return _codecs.encode(data, encoding)
''')

PyUnicode_DecodeUnicodeEscape = app.interphook('PyUnicode_DecodeUnicodeEscape')
PyUnicode_DecodeRawUnicodeEscape = app.interphook('PyUnicode_DecodeRawUnicodeEscape')
PyUnicode_DecodeUTF8 = app.interphook('PyUnicode_DecodeUTF8')
PyUnicode_AsEncodedString = app.interphook('PyUnicode_AsEncodedString')

def decode_utf8(space, s, ps, end, encoding):
    assert ps >= 0
    pt = ps
    # while (s < end && *s != '\\') s++; */ /* inefficient for u".."
    while ps < end and ord(s[ps]) & 0x80:
        ps += 1
    w_u = PyUnicode_DecodeUTF8(space, space.wrap(s[pt : ps]))
    w_v = PyUnicode_AsEncodedString(space, w_u, space.wrap(encoding))
    v = space.str_w(w_v)
    return v, ps

def raise_app_valueerror(space, msg):
    raise OperationError(space.w_ValueError, space.wrap(msg))
