# Application level implementation of string formatting.

# There's some insane stuff in here.  Blame CPython.  Please.

# Known problems:
# (1) rounding isn't always right (see comments in _float_formatting).
# (2) something goes wrong in the f_alt case of %g handling.
# (3) it's really, really slow.
import sys

class _Flags(object):
    def __repr__(self):
        return "<%s>"%(', '.join([f for f in self.__dict__
                                  if f[0] == 'f' and getattr(self, f)]),)
    f_ljust = 0
    f_sign = 0
    f_blank = 0
    f_alt = 0
    f_zero = 0


def value_next(valueiter):
    try:
        return valueiter.next()
    except StopIteration:
        raise TypeError('not enough arguments for format string')


def peel_num(c, fmtiter, valueiter):
    if c == '*':
        v = value_next(valueiter)
        if not isinstance(v, int):
            raise TypeError, "* wants int"
        return fmtiter.next(), v
    n = ''
    while c in '0123456789':
        n += c
        c = fmtiter.next()
    if n:
        return c, int(n)
    else:
        return c, 0


def peel_flags(c, fmtiter):
    flags = _Flags()
    while 1:
        if c == '-':
            flags.f_ljust = True
        elif c == '+':
            flags.f_sign = True
        elif c == ' ':
            flags.f_blank = True
        elif c == '#':
            flags.f_alt = True
        elif c == '0':
            flags.f_zero = True
        else:
            break
        c = fmtiter.next()
    return c, flags


def parse_fmt(fmtiter, valueiter, valuedict):
    """return (char, flags, width, prec, value)
    partially consumes fmtiter & valueiter"""
    c = fmtiter.next()
    value = None
    gotvalue = False
    if c == '(':
        n = ''
        pcount = 1
        while 1:
            c = fmtiter.next()
            if c == ')':
                pcount -= 1
                if pcount == 0:
                    break
            elif c == '(':
                pcount += 1
            n += c
        value = valuedict[n]
        gotvalue = True
        c = fmtiter.next()
    c, flags = peel_flags(c, fmtiter)
    c, width = peel_num(c, fmtiter, valueiter)
    if c == '.':
        c, prec = peel_num(fmtiter.next(), fmtiter, valueiter)
    else:
        prec = None
    if c in 'hlL':
        c = fmtiter.next()
    if width and width < 0:
        # this can happen with *-args
        flags.f_ljust = True
        width = -width
    if not gotvalue:
        if c == '%':
            # did YOU realize that "%4%"%() == '   %'??
            value = '%'
            c = 's'
        else:
            value = value_next(valueiter)
    return (c, flags, width, prec, value)


class NeedUnicodeFormattingError(Exception):
    pass

class Formatter(object):
    def __init__(self, char, flags, width, prec, value):
        self.char = char
        self.flags = flags
        self.width = width
        self.prec = prec
        self.value = value

    def numeric_preprocess(self, v):
        # negative zeroes?
        # * mwh giggles, falls over
        # still, if we can recognize them, here's the place to do it.
        import math
        if v < 0 or v == 0 and isinstance(v, float) and math.atan2(0, v) != 0:
            sign = '-'
            v = -v
        else:
            if self.flags.f_sign:
                sign = '+'
            elif self.flags.f_blank:
                sign = ' '
            else:
                sign = ''
        return v, sign

    def numeric_postprocess(self, r, sign, prefix=""):
        assert self.char in 'iduoxXeEfFgG'
        padchar = ' '
        if self.flags.f_zero:
            padchar = '0'
        if self.width is not None:
            p = self.width - len(r) - len(sign) -len(prefix)
            if self.flags.f_ljust:
                r = sign + prefix + r + ' '*p
            else:
                if self.flags.f_zero:
                    r = sign+prefix+padchar*p + r
                else:
                    r = padchar*p + sign + prefix + r
        else:
            r = sign + prefix + r
        return r

    def format(self):
        raise NotImplementedError

    def std_wp(self, r):
        assert self.char not in 'iduoxXeEfFgG'
        if self.prec is not None:
            r = r[:self.prec]
        if self.width is not None:
            p = self.width - len(r)
            if self.flags.f_ljust:
                r = r + ' '*p
            else:
                r = ' '*p + r
        return r


def funcFormatter(*funcs):
    """NOT_RPYTHON"""
    class _F(Formatter):
        def format(self):
            r = self.value
            for f in funcs:
                r = f(r)
            return self.std_wp(r)
    return _F


def maybe_int(value):
    try:
        inter = value.__int__
    except AttributeError:
        raise TypeError, "int argument required"
    return inter()


def maybe_float(value):
    try:
        floater = value.__float__
    except AttributeError:
        raise TypeError, "float argument required"
    return floater()


# isinf isn't too hard...
def isinf(v):
    return v != 0 and v*2.0 == v

# To get isnan, working x-platform and both on 2.3 and 2.4, is a
# horror.  I think this works (for reasons I don't really want to talk
# about), and probably when implemented on top of pypy, too.
def isnan(v):
    return v != v*1.0 or (v == 1.0 and v == 2.0)

from _float_formatting import flonum2digits

class FloatFormatter(Formatter):
    def eDigits(self, ds):
        ds = ds[:self.prec + 1] + ['0'] * (self.prec + 1 - len(ds))
        if self.prec > 0 or self.flags.f_alt:
            ds[1:1] = ['.']
        return ''.join(ds)

    def fDigits(self, ds, k):
        p = max(self.prec, 0)
        if 0 < k < len(ds):
            if len(ds) - k < p:
                ds.extend(['0'] * (p - (len(ds) - k)))
            else:
                ds = ds[:p + k]
            ds[k:k] = ['.']
        elif k <= 0:
            ds[0:0] = ['0']*(-k)
            ds = ds[:p]
            ds.extend(['0'] * (p - len(ds)))
            ds[0:0]= ['0', '.']
        elif k >= len(ds):
            ds.extend((k-len(ds))*['0'] + ['.'] + ['0']*p)
        return ''.join(ds)

    def format(self):
        v = maybe_float(self.value)
        if isnan(v):
            return 'nan'
        elif isinf(v):
            return 'inf'
        v, sign = self.numeric_preprocess(v)
        if self.prec is None:
            self.prec = 6
        r = self._format(v)
        return self.numeric_postprocess(r, sign)

    def _formatd(self, kind, v):
        import __builtin__
        return __builtin__._formatd(self.flags.f_alt, self.prec, kind, v)

class FloatFFormatter(FloatFormatter):
    def _format(self, v):
        if v/1e25 > 1e25:
            return FloatGFormatter('g', self.flags, self.width,
                                   self.prec, self.value).format()
        return self._formatd('f', v)
        #ds, k = flonum2digits(v)
        #digits = self.fDigits(ds, k)
        #if  not self.flags.f_alt:
        #    digits = digits.rstrip('.')
        #return digits

# system specific formatting. Linux does 3, Windows does 4...
# XXX this works only when we use geninterp!
if 0:
    _x = `1.2e34`
    _EF = len(_x) - _x.rindex('+')
    del _x
else:
    _EF = 3


class FloatEFormatter(FloatFormatter):
    def _format(self, v):
        return self._formatd('e', v)
        #ds, k = flonum2digits(v)
        #digits = self.eDigits(ds)
        #return "%%s%%c%%+0%dd" % _EF %(digits, self.char, k-1)


class FloatGFormatter(FloatFormatter):
    # The description of %g in the Python documentation lies
    # in a variety of minor ways.
    # Gah, this still isn't quite right in the f_alt case.
    # (One has to wonder who might care).
    def _format(self, v):
        return self._formatd('g', v)
        ## the following is btw. correct for marshal, now:
        #ds, k = flonum2digits(v)
        #ds = ds[:self.prec] # XXX rounding!
        #if -4 < k <= self.prec:
        #    if k < 0:
        #        self.prec -= k # grow prec for extra zeros
        #    digits = self.fDigits(ds, k)
        #    if not self.flags.f_alt:
        #        digits = digits.rstrip('0').rstrip('.')
        #    r = digits
        #else:
        #    digits = self.eDigits(ds)
        #    if not self.flags.f_alt:
        #        digits = digits.rstrip('0').rstrip('.')
        #    r = "%%se%%+0%dd" % _EF %(digits, k-1)
        #return r


class HexFormatter(Formatter):
    # NB: this has 2.4 semantics wrt. negative values
    def format(self):
        v, sign = self.numeric_preprocess(maybe_int(self.value))
        r = hex(v)[2:]
        if r[-1]=="L":
            # workaround weird behavior of CPython's hex
            r = r[:-1].lower()
        if self.prec is not None and len(r) < self.prec:
            r = '0'*(self.prec - len(r)) + r
        if self.flags.f_alt:
            prefix = '0x'
        else:
            prefix = ''
        if self.char == 'X':
            r = r.upper()
            prefix = prefix.upper()
        return self.numeric_postprocess(r, sign, prefix)


class OctFormatter(Formatter):
    # NB: this has 2.4 semantics wrt. negative values
    def format(self):
        v, sign = self.numeric_preprocess(maybe_int(self.value))
        r = oct(v)
        if r[-1] == "L":
            r = r[:-1]
        if v and not self.flags.f_alt:
            r = r[1:]
        if self.prec is not None and len(r) < self.prec:
            r = '0'*(self.prec - len(r)) + r
        return self.numeric_postprocess(r, sign)


class IntFormatter(Formatter):
    # NB: this has 2.4 semantics wrt. negative values (for %u)
    def format(self):
        v, sign = self.numeric_preprocess(maybe_int(self.value))
        r = str(v)
        if self.prec is not None and len(r) < self.prec:
            r = '0'*(self.prec - len(r)) + r
        return self.numeric_postprocess(r, sign)


class CharFormatter(Formatter):
    def format(self):
        if isinstance(self.value, str):
            v = self.value
            if len(v) != 1:
                raise TypeError, "%c requires int or char"
        
        elif isinstance(self.value, unicode):
            raise NeedUnicodeFormattingError
        else:
            i = maybe_int(self.value)
            if not 0 <= i <= 255:
                raise OverflowError("OverflowError: unsigned byte "
                                    "integer is greater than maximum")
            v = chr(i)
        self.prec = None
        return self.std_wp(v)

class StringFormatter(Formatter):
    def format(self):
        if isinstance(self.value, unicode):
            raise NeedUnicodeFormattingError
        return self.std_wp(str(self.value))



str_format_registry = {
    'd':IntFormatter,
    'i':IntFormatter,
    'o':OctFormatter,
    'u':IntFormatter,
    'x':HexFormatter,
    'X':HexFormatter,
    'e':FloatEFormatter,
    'E':FloatEFormatter,
    'f':FloatFFormatter,
    'F':FloatFFormatter,
    'g':FloatGFormatter,
    'G':FloatGFormatter,
    'c':CharFormatter,
    's':StringFormatter,
    'r':funcFormatter(repr),
    # this *can* get accessed, by e.g. '%()4%'%{'':1}.
    # The usual %% case has to be handled specially as it
    # doesn't consume a value.
    '%':funcFormatter(lambda x:'%'),
    }
    
class UnicodeStringFormatter(Formatter):
    def format(self):
        if isinstance(self.value, unicode):
            return self.std_wp(self.value)
        if hasattr(self.value,'__unicode__'):
            return self.std_wp(self.value.__unicode__())
        return self.std_wp(str(self.value))

class UnicodeCharFormatter(Formatter):
    def format(self):
        if isinstance(self.value, unicode):
            v = self.value
            if len(v) != 1:
                raise TypeError, "%c requires int or unicode char"
        elif isinstance(self.value, str):
            v = unicode(self.value)
            if len(v) != 1:
                raise TypeError, "%c requires int or unicode char"
        else:
            i = maybe_int(self.value)
            if not 0 <= i <= sys.maxunicode:
                raise OverflowError("OverflowError: unsigned byte "
                                    "integer is greater than maximum")
            v = unichr(i)
        self.prec = None
        return self.std_wp(v)

unicode_format_registry = {
    u'd':IntFormatter,
    u'i':IntFormatter,
    u'o':OctFormatter,
    u'u':IntFormatter,
    u'x':HexFormatter,
    u'X':HexFormatter,
    u'e':FloatEFormatter,
    u'E':FloatEFormatter,
    u'f':FloatFFormatter,
    u'F':FloatFFormatter,
    u'g':FloatGFormatter,
    u'G':FloatGFormatter,
    u'c':UnicodeCharFormatter,
    u's':UnicodeStringFormatter,
    u'r':funcFormatter(repr),
    # this *can* get accessed, by e.g. '%()4%'%{'':1}.
    # The usual %% case has to be handled specially as it
    # doesn't consume a value.
    u'%':funcFormatter(lambda x:u'%'),
    }
    

del funcFormatter # don't irritate flow space

class FmtIter(object):
    def __init__(self, fmt):
        self.fmt = fmt
        self.i = 0

    def __iter__(self):
        return self

    def next(self):
        try:
            c = self.fmt[self.i]
        except IndexError:
            raise StopIteration
        self.i += 1
        return c

    def skip_to_fmt(self):
        i = self.i
        j = self.fmt.find('%', i)
        if j < 0:
            self.i = len(self.fmt)
            return self.fmt[i:]
        else:
            self.i = j
            return self.fmt[i:j]


def format(fmt, values, valuedict=None, do_unicode=False):
    if do_unicode:
        format_registry = unicode_format_registry
    else:
        format_registry = str_format_registry
        
    fmtiter = FmtIter(fmt)
    valueiter = iter(values)
    r = []
    try:
        for c in fmtiter:
            if c == '%':
                t = parse_fmt(fmtiter, valueiter, valuedict)
                try:
                    f = format_registry[t[0]]
                except KeyError:
                    char = t[0]
                    if isinstance(char, unicode):
                        char = char.encode(sys.getdefaultencoding(), 'replace')
                    raise ValueError("unsupported format character "
                                     "'%s' (0x%x) at index %d"
                                     % (char, ord(t[0]), fmtiter.i - 1))
                # Trying to translate this using the flow space.
                # Currently, star args give a problem there,
                # so let's be explicit about the args:
                # r.append(f(*t).format())
                char, flags, width, prec, value = t
                try:
                    r.append(f(char, flags, width, prec, value).format())
                except NeedUnicodeFormattingError:
                    # Switch to using the unicode formatters and retry.
                    do_unicode = True
                    format_registry = unicode_format_registry
                    f = format_registry[t[0]]
                    r.append(f(char, flags, width, prec, value).format())
 
            else:
                # efficiency hack:
                r.append(c + fmtiter.skip_to_fmt())
    except StopIteration:
        raise ValueError, "incomplete format"
    try:
        valueiter.next()
    except StopIteration:
        pass
    else:
        if valuedict is None:
            raise TypeError('not all arguments converted '
                            'during string formatting')
    if do_unicode:
        return u''.join(r)
    return ''.join(r)

