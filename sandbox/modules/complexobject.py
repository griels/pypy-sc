import re
import errno
import math
import types
import warnings


PREC_REPR = 0 # 17
PREC_STR = 0 # 12


class complex(object):
    """complex(real[, imag]) -> complex number

    Create a complex number from a real part and an optional imaginary part.
    This is equivalent to (real + imag*1j) where imag defaults to 0."""
    
    def __init__(self, real=0.0, imag=None):
        if type(real) == types.StringType and imag is not None:
            msg = "complex() can't take second arg if first is a string"
            raise TypeError, msg
        if type(imag) == types.StringType:
            msg = "complex() second arg can't be a string"
            raise TypeError, msg

        if type(real) in (types.StringType, types.UnicodeType):
            self.real, self.imag = self._makeComplexFromString(real)
        else:
            if imag is None:
               imag = 0.
            self.real = float(real)
            self.imag = float(imag)
        

    def _makeComplexFromString(self, string):
        pat = re.compile(" *([\+\-]?\d*\.?\d*)([\+\-]?\d*\.?\d*)[jJ] *")
        m = pat.match(string)
        x, y = m.groups()
        if len(y) == 1 and y in '+-':
            y = y + '1.0'
        x, y = map(float, [x, y])
        return x, y


    def __description(self, precision):
        sign = '+'
        if self.imag < 0.:
            sign = ''
        if self.real != 0.:
            format = "(%%%02dg%%s%%%02dgj)" % (precision, precision)
            args = (self.real, sign, self.imag)
        else:
            format = "%%%02dgj" % precision
            args = self.imag
        return format % args


    def __repr__(self):
        return self.__description(PREC_REPR)


    def __str__(self):
        return self.__description(PREC_STR)

        
    def __hash__(self):
        hashreal = hash(self.real)
        hashimag = hash(self.imag)

        # Note:  if the imaginary part is 0, hashimag is 0 now,
        # so the following returns hashreal unchanged.  This is
        # important because numbers of different types that
        # compare equal must have the same hash value, so that
        # hash(x + 0*j) must equal hash(x).

        combined = hashreal + 1000003 * hashimag
        if combined == -1:
            combined = -2

        return combined


    def __add__(self, other):
        real = self.real + other.real
        imag = self.imag + other.imag
        return complex(real, imag)


    def __sub__(self, other):
        real = self.real - other.real
        imag = self.imag - other.imag
        return complex(real, imag)


    def __mul__(self, other):
        if other.__class__ != complex:
            return complex(other*self.real, other*self.imag)

        real = self.real*other.real - self.imag*other.imag
        imag = self.real*other.imag + self.imag*other.real
        return complex(real, imag)


    def __div__(self, other):
        if other.__class__ != complex:
            return complex(self.real/other, self.imag/other)

        if other.real < 0:
            abs_breal = -other.real
        else: 
            abs_breal = other.real
      
        if other.imag < 0:
            abs_bimag = -other.imag
        else:
            abs_bimag = other.imag

        if abs_breal >= abs_bimag:
            # divide tops and bottom by other.real
            if abs_breal == 0.0:
                errnum = errno.EDOM
                real = imag = 0.0
            else:
                ratio = other.imag / other.real
                denom = other.real + other.imag * ratio
                real = (self.real + self.imag * ratio) / denom
                imag = (self.imag - self.real * ratio) / denom
        else:
            # divide tops and bottom by other.imag
            ratio = other.real / other.imag
            denom = other.real * ratio + other.imag
            assert other.imag != 0.0
            real = (self.real * ratio + self.imag) / denom
            imag = (self.imag * ratio - self.real) / denom

        return complex(real, imag)


    def __mod__(self, other):
        errnum = 0
        div = self/other # The raw divisor value.
        if errnum == errno.EDOM:
            raise ZeroDivisionError, "complex remainder"

        div.real = math.floor(div.real) # Use the floor of the real part.
        div.imag = 0.0
        mod = self - div*other

        if mod.__class__ == complex:
            return mod
        else:
            return complex(mod)


    def __divmod__(self, other):
        warnings.warn("complex divmod(), // and % are deprecated", DeprecationWarning)

        errnum = 0
        div = self/other #  The raw divisor value
        if errnum == errno.EDOM:
            raise ZeroDivisionError, "complex divmod()"

        div = complex(math.floor(div.real), 0.0)
        mod = self - div*other
        d = div # complex(div)
        m = mod # complex(mod)

        return d, m


    def __pow__(self, other):
        if other.__class__ != complex:
            other = complex(other, 0)
                    
        a, b = self, other

        if b.real == 0. and b.imag == 0.:
            real = 1.
            imag = 0.
        elif a.real == 0. and a.imag == 0.:
            if b.imag != 0. or b.real < 0.:
                errnum = errno.EDOM
            real = 0.
            imag = 0.
        else:
            vabs = math.hypot(a.real,a.imag)
            len = math.pow(vabs,b.real)
            at = math.atan2(a.imag, a.real)
            phase = at*b.real
            if b.imag != 0.0:
                len /= math.exp(at*b.imag)
                phase += b.imag*math.log(vabs)
            real = len*math.cos(phase)
            imag = len*math.sin(phase)

        return complex(real, imag)


    def __neg__(self):
        return complex(-self.real, -self.imag)


    def __pos__(self):
        return complex(self.real, self.imag)


    def __abs__(self):
        result = math.hypot(self.real, self.imag)
        return float(result)


    def __nonzero__(self):
        return self.real != 0.0 or self.imag != 0.0


    def __coerce__(self, other):
        typ = type(other)
        
        if typ is types.IntType:
            return self, complex(float(other))
        elif typ is types.LongType:
            return self, complex(float(other))
        elif typ is types.FloatType:
            return self, complex(other)
        elif other.__class__ == complex:
            return self, other

        raise TypeError, "number coercion failed"


    def __int__(self):
        raise TypeError, "can't convert complex to int; use e.g. int(abs(z))"


    def __long__(self):
        raise TypeError, "can't convert complex to long; use e.g. long(abs(z))"


    def __float__(self):
        raise TypeError, "can't convert complex to float; use e.g. float(abs(z))"


    def conjugate(self):
        return complex(self.real, -self.imag)


    def __lt__(self, other):
        raise TypeError, "cannot compare complex numbers using <, <=, >, >="

        
    def __le__(self, other):
        raise TypeError, "cannot compare complex numbers using <, <=, >, >="

        
    def __gt__(self, other):
        raise TypeError, "cannot compare complex numbers using <, <=, >, >="

        
    def __get__(self, other):
        raise TypeError, "cannot compare complex numbers using <, <=, >, >="


    def __ne__(self, other):
        if self.real != other.real:
            return 1
        if self.imag != other.imag:
            return 1
        return 0            


#    def __new__(self, ...):
#        pass

#    def __floordiv__(self, value):
#        pass


# test mod, coerce, divmod


# complex_subtype_from_c_complex
# PyComplex_FromCComplex
# complex_subtype_from_doubles
# PyComplex_FromDoubles
# PyComplex_RealAsDouble
# PyComplex_ImagAsDouble
# PyComplex_AsCComplex
# complex_dealloc
# complex_to_buf
# complex_print
# complex_classic_div
# complex_int_div
# complex_richcompare
# complex_subtype_from_string
# complex_new
