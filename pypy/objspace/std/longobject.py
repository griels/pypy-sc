import sys, operator
from pypy.objspace.std.objspace import *
from pypy.objspace.std.intobject import W_IntObject
from pypy.objspace.std.floatobject import W_FloatObject
from pypy.objspace.std.noneobject import W_NoneObject
from pypy.rpython.rarithmetic import intmask, r_uint, LONG_MASK
from pypy.rpython.rarithmetic import LONG_BIT

import math

# the following describe a plain digit
SHIFT = int(LONG_BIT // 2) #- 1
MASK = int((1 << SHIFT) - 1)

# masks for normal signed integer
SIGN_BIT = LONG_BIT-1
SIGN_MASK = r_uint(1) << SIGN_BIT
NONSIGN_MASK = ~SIGN_MASK

# masks for half-word access
SHORT_BIT = LONG_BIT // 2
SHORT_MASK = int((1 << SHORT_BIT) - 1)

# XXX some operations below return one of their input arguments
#     without checking that it's really of type long (and not a subclass).

class W_LongObject(W_Object):
    """This is a reimplementation of longs using a list of r_uints."""
    # All functions that still rely on the underlying Python's longs are marked
    # with YYYYYY
    from pypy.objspace.std.longtype import long_typedef as typedef
    
    def __init__(w_self, space, digits, sign=0):
        W_Object.__init__(w_self, space)
        if isinstance(digits, long):  #YYYYYY
            digits, sign = args_from_long(digits)
        w_self.digits = digits
        w_self.sign = sign
        assert len(w_self.digits)

    def longval(self): #YYYYYY
        l = 0
        for d in self.digits[::-1]:
            l = l << LONG_BIT
            l += long(d)
        return l * self.sign

    def unwrap(w_self): #YYYYYY
        return w_self.longval()

    def _normalize(self):
        if len(self.digits) == 0:
            self.sign = 0
            self.digits = [r_uint(0)]
            return
        i = len(self.digits) - 1
        while i != 0 and self.digits[i] == 0:
            self.digits.pop(-1)
            i -= 1
        if len(self.digits) == 1 and self.digits[0] == 0:
            self.sign = 0

    def _getshort(self, index):
        a = self.digits[index // 2]
        if index % 2 == 0:
            return a & SHORT_MASK
        else:
            return a >> SHORT_BIT

    def _setshort(self, index, short):
        a = self.digits[index // 2]
        assert isinstance(short, r_uint)
        # note that this is possibly one bit more than a digit
        assert short & SHORT_MASK == short
        if index % 2 == 0:
            self.digits[index // 2] = ((a >> SHORT_BIT) << SHORT_BIT) + short
        else:
            self.digits[index // 2] = (a & SHORT_MASK) + (short << SHORT_BIT)


registerimplementation(W_LongObject)

# bool-to-long
def delegate_Bool2Long(w_bool):
    return W_LongObject(w_bool.space, [r_uint(w_bool.boolval)],
                        int(w_bool.boolval))

# int-to-long delegation
def delegate_Int2Long(w_intobj):
    if w_intobj.intval < 0:
        sign = -1
    elif w_intobj.intval > 0:
        sign = 1
    else:
        sign = 0
    digits = [r_uint(abs(w_intobj.intval))]
    return W_LongObject(w_intobj.space, digits, sign)

# long-to-float delegation
def delegate_Long2Float(w_longobj):
    try:
        return W_FloatObject(w_longobj.space, _AsDouble(w_longobj))
    except OverflowError:
        raise OperationError(w_longobj.space.w_OverflowError,
                             w_longobj.space.wrap("long int too large to convert to float"))


# long__Long is supposed to do nothing, unless it has
# a derived long object, where it should return
# an exact one.
def long__Long(space, w_long1):
    if space.is_w(space.type(w_long1), space.w_long):
        return w_long1
    digits = w_long1.digits
    sign = w_long1.sign
    return W_LongObject(space, digits, sign)

def long__Int(space, w_intobj):
    if w_intobj.intval < 0:
        sign = -1
    elif w_intobj.intval > 0:
        sign = 1
    else:
        sign = 0
    return W_LongObject(space, [r_uint(abs(w_intobj.intval))], sign)

def int__Long(space, w_value):
    if len(w_value.digits) == 1:
        if w_value.digits[0] & SIGN_MASK == 0:
            return space.newint(int(w_value.digits[0]) * w_value.sign)
        elif w_value.sign == -1 and w_value.digits[0] & NONSIGN_MASK == 0:
            return space.newint(intmask(w_value.digits[0]))
    #subtypes of long are converted to long!
    return long__Long(space, w_value)

def float__Long(space, w_longobj):
    try:
        return space.newfloat(_AsDouble(w_longobj))
    except OverflowError:
        raise OperationError(space.w_OverflowError,
                             space.wrap("long int too large to convert to float"))

def long__Float(space, w_floatobj):
    return _FromDouble(space, w_floatobj.floatval)

def int_w__Long(space, w_value):
    if len(w_value.digits) == 1:
        if  w_value.digits[0] & SIGN_MASK == 0:
            return int(w_value.digits[0]) * w_value.sign
        elif w_value.sign == -1 and w_value.digits[0] & NONSIGN_MASK == 0:
            return intmask(w_value.digits[0])
    raise OperationError(space.w_OverflowError,
                         space.wrap("long int too large to convert to int"))

def uint_w__Long(space, w_value):
    if w_value.sign == -1:
        raise OperationError(space.w_ValueError, space.wrap(
            "cannot convert negative integer to unsigned int"))
    x = r_uint(0)
    i = len(w_value.digits) * 2 - 1
    while i >= 0:
        prev = x
        x = (x << SHIFT) + v._getshort(i)
        if (x >> SHIFT) != prev:
            raise OperationError(space.w_OverflowError, space.wrap(
                "long int too large to convert to unsigned int"))
    return x

def repr__Long(space, w_long):
    return space.wrap(_format(w_long, 10, True))

def str__Long(space, w_long):
    return space.wrap(_format(w_long, 10, False))

def eq__Long_Long(space, w_long1, w_long2):
    if (w_long1.sign != w_long2.sign or
        len(w_long1.digits) != len(w_long2.digits)):
        return space.newbool(False)
    i = 0
    ld = len(w_long1.digits)
    while i < ld:
        if w_long1.digits[i] != w_long2.digits[i]:
            return space.newbool(False)
        i += 1
    return space.newbool(True)

def lt__Long_Long(space, w_long1, w_long2):
    if w_long1.sign > w_long2.sign:
        return space.newbool(False)
    if w_long1.sign < w_long2.sign:
        return space.newbool(True)
    ld1 = len(w_long1.digits)
    ld2 = len(w_long2.digits)
    if ld1 > ld2:
        if w_long2.sign > 0:
            return space.newbool(False)
        else:
            return space.newbool(True)
    elif ld1 < ld2:
        if w_long2.sign > 0:
            return space.newbool(True)
        else:
            return space.newbool(False)
    i = ld1 - 1
    while i >= 0:
        d1 = w_long1.digits[i]
        d2 = w_long2.digits[i]
        if d1 < d2:
            if w_long2.sign > 0:
                return space.newbool(True)
            else:
                return space.newbool(False)
        elif d1 > d2:
            if w_long2.sign > 0:
                return space.newbool(False)
            else:
                return space.newbool(True)
        i -= 1
    return space.newbool(False)

def hash__Long(space,w_value): #YYYYYY
    ## %reimplement%
    # real Implementation should be taken from _Py_HashDouble in object.c
    return space.wrap(hash(w_value.longval()))

# coerce
def coerce__Long_Long(space, w_long1, w_long2):
    return space.newtuple([w_long1, w_long2])


def add__Long_Long(space, w_long1, w_long2):
    if w_long1.sign < 0:
        if w_long2.sign < 0:
            result = _x_add(w_long1, w_long2)
            if result.sign != 0:
                result.sign = -result.sign
        else:
            result = _x_sub(w_long2, w_long1)
    else:
        if w_long2.sign < 0:
            result = _x_sub(w_long1, w_long2)
        else:
            result = _x_add(w_long1, w_long2)
    result._normalize()
    return result

def sub__Long_Long(space, w_long1, w_long2):
    if w_long1.sign < 0:
        if w_long2.sign < 0:
            result = _x_sub(w_long1, w_long2)
        else:
            result = _x_add(w_long1, w_long2)
        result.sign = -result.sign
    else:
        if w_long2.sign < 0:
            result = _x_add(w_long1, w_long2)
        else:
            result = _x_sub(w_long1, w_long2)
    result._normalize()
    return result

def mul__Long_Long(space, w_long1, w_long2):
    result = _x_mul(w_long1, w_long2)
    result.sign = w_long1.sign * w_long2.sign
    return result

def truediv__Long_Long(space, w_long1, w_long2):
    div = _long_true_divide(w_long1, w_long2)
    return space.newfloat(div)

def floordiv__Long_Long(space, w_long1, w_long2):
    div, mod = _l_divmod(w_long1, w_long2)
    return div

def div__Long_Long(space, w_long1, w_long2):
    return floordiv__Long_Long(space, w_long1, w_long2)

def mod__Long_Long(space, w_long1, w_long2):
    div, mod = _l_divmod(w_long1, w_long2)
    return mod

def divmod__Long_Long(space, w_long1, w_long2):
    div, mod = _l_divmod(w_long1, w_long2)
    return space.newtuple([div, mod])

# helper for pow()  #YYYYYY: still needs longval if second argument is negative
def _impl_long_long_pow(space, lv, lw, lz=None):
    if lw.sign < 0:
        if lz is not None:
            raise OperationError(space.w_TypeError,
                             space.wrap("pow() 2nd argument "
                 "cannot be negative when 3rd argument specified"))
        return space.pow(space.newfloat(float(lv.longval())),
                         space.newfloat(float(lw.longval())),
                         space.w_None)
    if lz is not None:
        if lz.sign == 0:
            raise OperationError(space.w_ValueError,
                                    space.wrap("pow() 3rd argument cannot be 0"))
    result = W_LongObject(space, [r_uint(1)], 1)
    if lw.sign == 0:
        if lz is not None:
            result = mod__Long_Long(space, result, lz)
        return result
    if lz is not None:
        temp = mod__Long_Long(space, lv, lz)
    else:
        temp = lv
    i = 0
    #Treat the most significant digit specially to reduce multiplications
    while i < len(lw.digits) - 1:
        j = 0
        m = r_uint(1)
        di = lw.digits[i]
        while j < LONG_BIT:
            if di & m:
                result = mul__Long_Long(space, result, temp)
            temp = mul__Long_Long(space, temp, temp)
            if lz is not None:
                result = mod__Long_Long(space, result, lz)
                temp = mod__Long_Long(space, temp, lz)
            m = m << 1
            j += 1
        i += 1
    m = r_uint(1) << (LONG_BIT - 1)
    highest_set_bit = LONG_BIT
    j = LONG_BIT - 1
    di = lw.digits[i]
    while j >= 0:
        if di & m:
            highest_set_bit = j
            break
        m = m >> 1
        j -= 1
    assert highest_set_bit != LONG_BIT, "long not normalized"
    j = 0
    m = r_uint(1)
    while j <= highest_set_bit:
        if di & m:
            result = mul__Long_Long(space, result, temp)
        temp = mul__Long_Long(space, temp, temp)
        if lz is not None:
            result = mod__Long_Long(space, result, lz)
            temp = mod__Long_Long(space, temp, lz)
        m = m << 1
        j += 1
    if lz:
        result = mod__Long_Long(space, result, lz)
    return result


def pow__Long_Long_Long(space, w_long1, w_long2, w_long3):
    return _impl_long_long_pow(space, w_long1, w_long2, w_long3)

def pow__Long_Long_None(space, w_long1, w_long2, w_long3):
    return _impl_long_long_pow(space, w_long1, w_long2, None)

def neg__Long(space, w_long1):
    return W_LongObject(space, w_long1.digits[:], -w_long1.sign)

def pos__Long(space, w_long):
    return long__Long(space, w_long)

def abs__Long(space, w_long):
    return W_LongObject(space, w_long.digits[:], abs(w_long.sign))

def nonzero__Long(space, w_long):
    return space.newbool(w_long.sign != 0)

def invert__Long(space, w_long): #Implement ~x as -(x + 1)
    w_lpp = add__Long_Long(space, w_long, W_LongObject(space, [r_uint(1)], 1))
    return neg__Long(space, w_lpp)

def lshift__Long_Long(space, w_long1, w_long2):
    if w_long2.sign < 0:
        raise OperationError(space.w_ValueError,
                             space.wrap("negative shift count"))
    elif w_long2.sign == 0:
        return w_long1
    try:
        b = int_w__Long(space, w_long2)
    except OverflowError:   # b too big
        raise OperationError(space.w_OverflowError,
                             space.wrap("shift count too large"))
    wordshift = b // LONG_BIT
    remshift = r_uint(b) % LONG_BIT
    oldsize = len(w_long1.digits)
    newsize = oldsize + wordshift
    if remshift != 0:
        newsize += 1
    w_result = W_LongObject(space, [r_uint(0)] * newsize, w_long1.sign)
    rightshift = LONG_BIT - remshift
    LOWER_MASK = (r_uint(1) << r_uint(rightshift)) - 1
    UPPER_MASK = ~LOWER_MASK
    accum = r_uint(0)
    i = wordshift
    j = 0
    while j < oldsize:
        digit = w_long1.digits[j]
        w_result.digits[i] = (accum | (digit << remshift))
        accum = (digit & UPPER_MASK) >> rightshift
        i += 1
        j += 1
    if remshift:
        w_result.digits[i] = accum
    else:
        assert not accum
    w_result._normalize()
    return w_result

def rshift__Long_Long(space, w_long1, w_long2):
    if w_long2.sign < 0:
        raise OperationError(space.w_ValueError,
                             space.wrap("negative shift count"))
    elif w_long2.sign == 0:
        return w_long1
    if w_long1.sign == -1:
        w_a1 = invert__Long(space, w_long1)
        w_a2 = rshift__Long_Long(space, w_a1, w_long2)
        return invert__Long(space, w_a2)
    try:
        b = int_w__Long(space, w_long2)
    except OverflowError:   # b too big # XXX maybe just return 0L instead?
        raise OperationError(space.w_OverflowError,
                             space.wrap("shift count too large"))
    wordshift = b // LONG_BIT
    remshift = r_uint(b) % LONG_BIT
    oldsize = len(w_long1.digits)
    newsize = oldsize - wordshift
    if newsize <= 0:
        return W_LongObject(space, [r_uint(0)], 0)
    w_result = W_LongObject(space, [r_uint(0)] * newsize, 1)
    leftshift = LONG_BIT - remshift
    LOWER_MASK = (r_uint(1) << r_uint(remshift)) - 1
    UPPER_MASK = ~LOWER_MASK
    accum = r_uint(0)
    i = newsize - 1
    j = oldsize - 1
    while i >= 0:
        digit = w_long1.digits[j]
        w_result.digits[i] = (accum | (digit >> remshift))
        accum = (digit & LOWER_MASK) << leftshift
        i -= 1
        j -= 1
    w_result._normalize()
    return w_result

def and__Long_Long(space, w_long1, w_long2):
    return _bitwise(w_long1, '&', w_long2)

def xor__Long_Long(space, w_long1, w_long2):
    return _bitwise(w_long1, '^', w_long2)

def or__Long_Long(space, w_long1, w_long2):
    return _bitwise(w_long1, '|', w_long2)

def oct__Long(space, w_long1):
    return space.wrap(_format(w_long1, 8, True))

def hex__Long(space, w_long1):
    return space.wrap(_format(w_long1, 16, True))

def getnewargs__Long(space, w_long1):
    return space.newtuple([W_LongObject(space, w_long1.digits, w_long1.sign)])


register_all(vars())

# register implementations of ops that recover int op overflows

# binary ops
for opname in ['add', 'sub', 'mul', 'div', 'floordiv', 'truediv', 'mod', 'divmod', 'lshift']:
    exec compile("""
def %(opname)s_ovr__Int_Int(space, w_int1, w_int2):
    w_long1 = delegate_Int2Long(w_int1)
    w_long2 = delegate_Int2Long(w_int2)
    return %(opname)s__Long_Long(space, w_long1, w_long2)
""" % {'opname': opname}, '', 'exec')

    getattr(StdObjSpace.MM, opname).register(globals()['%s_ovr__Int_Int' %opname], W_IntObject, W_IntObject, order=1)

# unary ops
for opname in ['neg', 'abs']:
    exec """
def %(opname)s_ovr__Int(space, w_int1):
    w_long1 = delegate_Int2Long(w_int1)
    return %(opname)s__Long(space, w_long1)
""" % {'opname': opname}

    getattr(StdObjSpace.MM, opname).register(globals()['%s_ovr__Int' %opname], W_IntObject, order=1)

# pow
def pow_ovr__Int_Int_None(space, w_int1, w_int2, w_none3):
    w_long1 = delegate_Int2Long(w_int1)
    w_long2 = delegate_Int2Long(w_int2)
    return pow__Long_Long_None(space, w_long1, w_long2, w_none3)

def pow_ovr__Int_Int_Long(space, w_int1, w_int2, w_long3):
    w_long1 = delegate_Int2Long(w_int1)
    w_long2 = delegate_Int2Long(w_int2)
    return pow__Long_Long_Long(space, w_long1, w_long2, w_long3)

StdObjSpace.MM.pow.register(pow_ovr__Int_Int_None, W_IntObject, W_IntObject, W_NoneObject, order=1)
StdObjSpace.MM.pow.register(pow_ovr__Int_Int_Long, W_IntObject, W_IntObject, W_LongObject, order=1)


# Helper Functions
def args_from_long(l): #YYYYYY
    if l < 0:
        sign = -1
    elif l > 0:
        sign = 1
    else:
        sign = 0
    l = abs(l)
    digits = []
    i = 0
    while l:
        digits.append(r_uint(l & LONG_MASK))
        l = l >> LONG_BIT
    if sign == 0:
        digits = [r_uint(0)]
    return digits, sign


def _x_add(a, b):
    """ Add the absolute values of two long integers. """
    size_a = len(a.digits) * 2
    size_b = len(b.digits) * 2

    # Ensure a is the larger of the two:
    if size_a < size_b:
        a, b = b, a
        size_a, size_b = size_b, size_a
    z = W_LongObject(a.space, [r_uint(0)] * (len(a.digits) + 1), 1)
    i = 0
    carry = r_uint(0)
    while i < size_b:
        carry += a._getshort(i) + b._getshort(i)
        z._setshort(i, carry & MASK)
        carry >>= SHIFT
        i += 1
    while i < size_a:
        carry += a._getshort(i)
        z._setshort(i, carry & MASK)
        carry >>= SHIFT
        i += 1
    z._setshort(i, carry)
    z._normalize()
    return z

def _x_sub(a, b):
    """ Subtract the absolute values of two integers. """
    size_a = len(a.digits) * 2
    size_b = len(b.digits) * 2
    sign = 1
    borrow = 0

    # Ensure a is the larger of the two:
    if size_a < size_b:
        sign = -1
        a,b=b, a
        size_a, size_b = size_b, size_a
    elif size_a == size_b:
        # Find highest digit where a and b differ:
        i = size_a - 1
        while i >= 0 and a._getshort(i) == b._getshort(i):
            i -= 1
        if i < 0:
            return W_LongObject(a.space, [r_uint(0)], 0)
        if a._getshort(i) < b._getshort(i):
            sign = -1
            a, b = b, a
        size_a = size_b = i+1
    digitpairs = (size_a + 1) // 2
    z = W_LongObject(a.space, [r_uint(0)] * digitpairs, 1)
    i = 0
    while i < size_b:
        # The following assumes unsigned arithmetic
        # works modulo 2**N for some N>SHIFT.
        borrow = a._getshort(i) - b._getshort(i) - borrow
        z._setshort(i, borrow & MASK)
        borrow >>= SHIFT
        borrow &= 1 # Keep only one sign bit
        i += 1
    while i < size_a:
        borrow = a._getshort(i) - borrow
        z._setshort(i, borrow & MASK)
        borrow >>= SHIFT
        borrow &= 1 # Keep only one sign bit
        i += 1
    assert borrow == 0
    if sign < 0:
        z.sign = -1
    z._normalize()
    return z


#Multiply the absolute values of two longs
def _x_mul(a, b):
    size_a = len(a.digits) * 2
    size_b = len(b.digits) * 2
    z = W_LongObject(a.space, [r_uint(0)] * ((size_a + size_b) // 2), 1)
    i = 0
    while i < size_a:
        carry = r_uint(0)
        f = a._getshort(i)
        j = 0
        while j < size_b:
            carry += z._getshort(i + j) + b._getshort(j) * f
            z._setshort(i + j, carry & MASK)
            carry = carry >> SHIFT
            j += 1
        while carry != 0:
            assert i + j < size_a + size_b
            carry += z._getshort(i + j)
            z._setshort(i + j, carry & MASK)
            carry = carry >> SHIFT
            j += 1
        i += 1
    z._normalize()
    return z

def _inplace_divrem1(pout, pin, n, size=0):
    """
    Divide long pin by non-zero digit n, storing quotient
    in pout, and returning the remainder. It's OK for pin == pout on entry.
    """
    rem = r_uint(0)
    assert n > 0 and n <= MASK
    if not size:
        size = len(pin.digits) * 2
    size -= 1
    while size >= 0:
        rem = (rem << SHIFT) + pin._getshort(size)
        hi = rem // n
        pout._setshort(size, hi)
        rem -= hi * n
        size -= 1
    return rem

def _divrem1(a, n):
    """
    Divide a long integer by a digit, returning both the quotient
    and the remainder as a tuple.
    The sign of a is ignored; n should not be zero.
    """
    assert n > 0 and n <= MASK
    size = len(a.digits)
    z = W_LongObject(a.space, [r_uint(0)] * size, 1)
    rem = _inplace_divrem1(z, a, n)
    z._normalize()
    return z, rem

def _muladd1(a, n, extra):
    """Multiply by a single digit and add a single digit, ignoring the sign.
    """
    digitpairs = len(a.digits)
    size_a = digitpairs * 2
    if a._getshort(size_a-1) == 0:
        size_a -= 1
    z = W_LongObject(a.space, [r_uint(0)] * (digitpairs+1), 1)
    carry = extra
    for i in range(size_a):
        carry += a._getshort(i) * n
        z._setshort(i, carry & MASK)
        carry >>= SHIFT
    i += 1
    z._setshort(i, carry)
    z._normalize()
    return z

# for the carry in _x_divrem, we need something that can hold
# two digits plus a sign.
# for the time being, we here implement such a 33 bit number just
# for the purpose of the division.
# In the long term, it might be considered to implement the
# notation of a "double anything" unsigned type, which could
# be used recursively to implement longs of any size.

class r_suint(object):
    # we do not inherit from r_uint, because we only
    # support a few operations for our purpose
    def __init__(self, value=0):
        if isinstance(value, r_suint):
            self.value = value.value
            self.sign = value.sign
        else:
            self.value = r_uint(value)
            self.sign = -(value < 0)

    def longval(self):
        if self.sign:
            return -long(-self.value)
        else:
            return long(self.value)
        
    def __repr__(self):
        return repr(self.longval())

    def __str__(self):
        return str(self.longval())

    def __iadd__(self, other):
        hold = self.value
        self.value += other
        self.sign ^= - ( (other < 0) != (self.value < hold) )
        return self

    def __add__(self, other):
        res = r_suint(self)
        res += other
        return res

    def __isub__(self, other):
        hold = self.value
        self.value -= other
        self.sign ^= - ( (other < 0) != (self.value > hold) )
        return self

    def __sub__(self, other):
        res = r_suint(self)
        res -= other
        return res

    def __irshift__(self, n):
        self.value >>= n
        if self.sign:
            self.value += r_uint(LONG_MASK) << (LONG_BIT - n)
        return self

    def __rshift__(self, n):
        res = r_suint(self)
        res >>= n
        return res

    def __ilshift__(self, n):
        self.value <<= n
        return self

    def __lshift__(self, n):
        res = r_suint(self)
        res <<= n
        return res

    def __and__(self, mask):
        # only used to get bits from the value
        return self.value & mask

    def __eq__(self, other):
        if not isinstance(other,r_suint):
            other = r_suint(other)
        return self.sign == other.sign and self.value == other.value

def _x_divrem(v1, w1):
    size_w = len(w1.digits) * 2
    # hack for the moment:
    # find where w1 is really nonzero
    if w1._getshort(size_w-1) == 0:
        size_w -= 1
    d = (MASK+1) // (w1._getshort(size_w-1) + 1)
    v = _muladd1(v1, d, r_uint(0))
    w = _muladd1(w1, d, r_uint(0))
    size_v = len(v.digits) * 2
    if v._getshort(size_v-1) == 0:
        size_v -= 1
    size_w = len(w.digits) * 2
    if w._getshort(size_w-1) == 0:
        size_w -= 1
    assert size_v >= size_w and size_w > 1 # Assert checks by div()

    size_a = size_v - size_w + 1
    digitpairs = (size_a + 1) // 2
    a = W_LongObject(v.space, [r_uint(0)] * digitpairs, 1)

    j = size_v
    k = size_a - 1
    while k >= 0:
        if j >= size_v:
            vj = r_uint(0)
        else:
            vj = v._getshort(j)
        carry = r_suint(0) # note: this must hold two digits and a sign!

        if vj == w._getshort(size_w-1):
            q = r_uint(MASK)
        else:
            q = ((vj << SHIFT) + v._getshort(j-1)) // w._getshort(size_w-1)

        # notabene!
        # this check needs a signed two digits result
        # or we get an overflow.
        while (w._getshort(size_w-2) * q >
                ((
                    r_suint(vj << SHIFT) # this one dominates
                    + v._getshort(j-1)
                    - long(q) * long(w._getshort(size_w-1))
                                ) << SHIFT)
                + v._getshort(j-2)):
            q -= 1
        i = 0
        while i < size_w and i+k < size_v:
            z = w._getshort(i) * q
            zz = z >> SHIFT
            carry += v._getshort(i+k) + (zz << SHIFT)
            carry -= z
            if hasattr(carry, 'value'):
                v._setshort(i+k, r_uint(carry.value & MASK))
            else:
                v._setshort(i+k, r_uint(carry & MASK))
            carry >>= SHIFT
            carry -= zz
            i += 1

        if i+k < size_v:
            carry += v._getshort(i+k)
            v._setshort(i+k, r_uint(0))

        if carry == 0:
            a._setshort(k, q & MASK)
        else:
            ##!!assert carry == -1
            a._setshort(k, (q-1) & MASK)

            carry = r_suint(0)
            i = 0
            while i < size_w and i+k < size_v:
                carry += v._getshort(i+k) + w._getshort(i)
                v._setshort(i+k, r_uint(carry.value) & MASK)
                carry >>= SHIFT
                i += 1
        j -= 1
        k -= 1

    a._normalize()
    rem, _ = _divrem1(v, d)
    return a, rem


def _divrem(a, b):
    """ Long division with remainder, top-level routine """
    size_a = len(a.digits) * 2
    size_b = len(b.digits) * 2
    if a._getshort(size_a-1) == 0:
        size_a -= 1
    if b._getshort(size_b-1) == 0:
        size_b -= 1

    if b.sign == 0:
        raise OperationError(a.space.w_ZeroDivisionError,
                             a.space.wrap("long division or modulo by zero"))

    if (size_a < size_b or
        (size_a == size_b and
         a._getshort(size_a-1) < b._getshort(size_b-1))):
        # |a| < |b|
        z = W_LongObject(a.space, [r_uint(0)], 0)
        rem = a
        return z, rem
    if size_b == 1:
        z, urem = _divrem1(a, b._getshort(0))
        rem = W_LongObject(a.space, [urem], int(urem != 0))
    else:
        z, rem = _x_divrem(a, b)
    # Set the signs.
    # The quotient z has the sign of a*b;
    # the remainder r has the sign of a,
    # so a = b*z + r.
    if a.sign != b.sign:
        z.sign = - z.sign
    if a.sign < 0 and rem.sign != 0:
        rem.sign = - rem.sign
    return z, rem

# ______________ conversions to double _______________

def _AsScaledDouble(v):
    """
    NBITS_WANTED should be > the number of bits in a double's precision,
    but small enough so that 2**NBITS_WANTED is within the normal double
    range.  nbitsneeded is set to 1 less than that because the most-significant
    Python digit contains at least 1 significant bit, but we don't want to
    bother counting them (catering to the worst case cheaply).

    57 is one more than VAX-D double precision; I (Tim) don't know of a double
    format with more precision than that; it's 1 larger so that we add in at
    least one round bit to stand in for the ignored least-significant bits.
    """
    NBITS_WANTED = 57
    multiplier = float(1 << SHIFT)
    if v.sign == 0:
        return 0.0, 0
    i = len(v.digits) * 2 - 1
    if v._getshort(i) == 0:
        i -= 1
    sign = v.sign
    x = float(v._getshort(i))
    nbitsneeded = NBITS_WANTED - 1
    # Invariant:  i Python digits remain unaccounted for.
    while i > 0 and nbitsneeded > 0:
        i -= 1
        x = x * multiplier + float(v._getshort(i))
        nbitsneeded -= SHIFT
    # There are i digits we didn't shift in.  Pretending they're all
    # zeroes, the true value is x * 2**(i*SHIFT).
    exponent = i
    assert x > 0.0
    return x * sign, exponent

def isinf(x):
    return x != 0.0 and x / 2 == x

##def ldexp(x, exp):
##    assert type(x) is float
##    lb1 = LONG_BIT - 1
##    multiplier = float(r_uint(1) << lb1)
##    while exp >= lb1:
##        x *= multiplier
##        exp -= lb1
##    if exp:
##        x *= float(r_uint(1) << exp)
##    return x

# note that math.ldexp checks for overflows,
# while the C ldexp is not guaranteed to do.
# XXX make sure that we don't ignore this!

def _AsDouble(v):
    """ Get a C double from a long int object. """
    x, e = _AsScaledDouble(v)
    if e <= sys.maxint / SHIFT:
        x = math.ldexp(x, e * SHIFT)
        #if not isinf(x):
        # this is checked by math.ldexp
        return x
    raise OverflowError # can't say "long int too large to convert to float"

def _long_true_divide(a, b):
    try:
        ad, aexp = _AsScaledDouble(a)
        bd, bexp = _AsScaledDouble(b)
        if bd == 0.0:
            raise OperationError(a.space.w_ZeroDivisionError,
                                 a.space.wrap("long division or modulo by zero"))

        # True value is very close to ad/bd * 2**(SHIFT*(aexp-bexp))
        ad /= bd   # overflow/underflow impossible here
        aexp -= bexp
        if aexp > sys.maxint / SHIFT:
            raise OverflowError
        elif aexp < -(sys.maxint / SHIFT):
            return 0.0 # underflow to 0
        ad = math.ldexp(ad, aexp * SHIFT)
        ##if isinf(ad):   # ignore underflow to 0.0
        ##    raise OverflowError
        # math.ldexp checks and raises
        return ad
    except OverflowError:
        raise OperationError(a.space.w_OverflowError,
                             a.space.wrap("long/long too large for a float"))


def _FromDouble(space, dval):
    """ Create a new long int object from a C double """
    neg = 0
    if isinf(dval):
        raise OperationError(space.w_OverflowError,
                             space.wrap("cannot convert float infinity to long"))
    if dval < 0.0:
        neg = 1
        dval = -dval
    frac, expo = math.frexp(dval) # dval = frac*2**expo; 0.0 <= frac < 1.0
    if expo <= 0:
        return W_LongObject(space, [r_uint(0)], 0)
    ndig = (expo-1) // SHIFT + 1 # Number of 'digits' in result
    digitpairs = (ndig + 1) // 2
    v = W_LongObject(space, [r_uint(0)] * digitpairs, 1)
    frac = math.ldexp(frac, (expo-1) % SHIFT + 1)
    for i in range(ndig-1, -1, -1):
        bits = int(frac)
        v._setshort(i, r_uint(bits))
        frac -= float(bits)
        frac = math.ldexp(frac, SHIFT)
    if neg:
        v.sign = -1
    return v

def _l_divmod(v, w):
    """
    The / and % operators are now defined in terms of divmod().
    The expression a mod b has the value a - b*floor(a/b).
    The _divrem function gives the remainder after division of
    |a| by |b|, with the sign of a.  This is also expressed
    as a - b*trunc(a/b), if trunc truncates towards zero.
    Some examples:
      a   b   a rem b     a mod b
      13  10   3           3
     -13  10  -3           7
      13 -10   3          -7
     -13 -10  -3          -3
    So, to get from rem to mod, we have to add b if a and b
    have different signs.  We then subtract one from the 'div'
    part of the outcome to keep the invariant intact.
    """
    div, mod = _divrem(v, w)
    if mod.sign * w.sign == -1:
        mod = add__Long_Long(v.space, mod, w)
        one = W_LongObject(v.space, [r_uint(1)], 1)
        div = sub__Long_Long(v.space, div, one)
    return div, mod


def _format(a, base, addL):
    """
    Convert a long int object to a string, using a given conversion base.
    Return a string object.
    If base is 8 or 16, add the proper prefix '0' or '0x'.
    """
    size_a = len(a.digits) * 2
    if a._getshort(size_a-1) == 0:
        size_a -= 1

    assert base >= 2 and base <= 36

    sign = False

    # Compute a rough upper bound for the length of the string
    i = base
    bits = 0
    while i > 1:
        bits += 1
        i >>= 1
    i = 5 + int(bool(addL)) + (size_a*LONG_BIT + bits-1) // bits
    s = [chr(0)] * i
    p = i
    if addL:
        p -= 1
        s[p] = 'L'
    if a.sign < 0:
        sign = True

    if a.sign == 0:
        p -= 1
        s[p] = '0'
    elif (base & (base - 1)) == 0:
        # JRH: special case for power-of-2 bases
        accum = r_uint(0)
        accumbits = 0  # # of bits in accum 
        basebits = 1   # # of bits in base-1
        i = base
        while 1:
            i >>= 1
            if i <= 1:
                break
            basebits += 1

        for i in range(size_a):
            accum |= a._getshort(i) << accumbits
            accumbits += SHIFT
            assert accumbits >= basebits
            while 1:
                cdigit = accum & (base - 1)
                if cdigit < 10:
                    cdigit += ord('0')
                else:
                    cdigit += ord('A') - 10
                assert p > 0
                p -= 1
                s[p] = chr(cdigit)
                accumbits -= basebits
                accum >>= basebits
                if i < size_a - 1:
                    if accumbits < basebits:
                        break
                else:
                    if accum <= 0:
                        break
    else:
        # Not 0, and base not a power of 2.  Divide repeatedly by
        # base, but for speed use the highest power of base that
        # fits in a digit.
        size = size_a
        pin = a # just for similarity to C source which uses the array
        # powbase <- largest power of base that fits in a digit.
        powbase = base  # powbase == base ** power
        power = 1
        while 1:
            newpow = powbase * r_uint(base)
            if newpow >> SHIFT:  # doesn't fit in a digit
                break
            powbase = newpow
            power += 1

        # Get a scratch area for repeated division.
        digitpairs = (size + 1) // 2
        scratch = W_LongObject(a.space, [r_uint(0)] * digitpairs, 1)

        # Repeatedly divide by powbase.
        while 1:
            ntostore = power
            rem = _inplace_divrem1(scratch, pin, powbase, size)
            pin = scratch  # no need to use a again
            if pin._getshort(size - 1) == 0:
                size -= 1

            # Break rem into digits.
            assert ntostore > 0
            while 1:
                nextrem = rem // base
                c = rem - nextrem * base
                assert p > 0
                if c < 10:
                    c += ord('0')
                else:
                    c += ord('A') - 10
                p -= 1
                s[p] = chr(c)
                rem = nextrem
                ntostore -= 1
                # Termination is a bit delicate:  must not
                # store leading zeroes, so must get out if
                # remaining quotient and rem are both 0.
                if not (ntostore and (size or rem)):
                    break
            if size == 0:
                break

    if base == 8:
        if size_a != 0:
            p -= 1
            s[p] = '0'
    elif base == 16:
        p -= 1
        s[p] ='x'
        p -= 1
        s[p] = '0'
    elif base != 10:
        p -= 1
        s[p] = '#'
        p -= 1
        s[p] = chr(ord('0') + base % 10)
        if base > 10:
            p -= 1
            s[p] = chr(ord('0') + base // 10)
    if sign:
        p -= 1
        s[p] = '-'

    if p == 0:
        return ''.join(s)
    else:
        return ''.join(s[p:])


def _bitwise(a, op, b): # '&', '|', '^'
    """ Bitwise and/or/xor operations """

    if a.sign < 0:
        a = invert__Long(a.space, a)
        maska = r_uint(MASK)
    else:
        maska = r_uint(0)
    if b.sign < 0:
        b = invert__Long(b.space, b)
        maskb = r_uint(MASK)
    else:
        maskb = r_uint(0)

    negz = 0
    if op == '^':
        if maska != maskb:
            maska ^= MASK
            negz = -1
    elif op == '&':
        if maska and maskb:
            op = '|'
            maska ^= MASK
            maskb ^= MASK
            negz = -1
    elif op == '|':
        if maska or maskb:
            op = '&'
            maska ^= MASK
            maskb ^= MASK
            negz = -1

    # JRH: The original logic here was to allocate the result value (z)
    # as the longer of the two operands.  However, there are some cases
    # where the result is guaranteed to be shorter than that: AND of two
    # positives, OR of two negatives: use the shorter number.  AND with
    # mixed signs: use the positive number.  OR with mixed signs: use the
    # negative number.  After the transformations above, op will be '&'
    # iff one of these cases applies, and mask will be non-0 for operands
    # whose length should be ignored.

    size_a = len(a.digits) * 2
    if a._getshort(size_a - 1) == 0:
        size_a -= 1
    size_b = len(b.digits) * 2
    if b._getshort(size_b - 1) == 0:
        size_b -= 1
    if op == '&':
        if maska:
            size_z = size_b
        else:
            if maskb:
                size_z = size_a
            else:
                size_z = min(size_a, size_b)
    else:
        size_z = max(size_a, size_b)

    digitpairs = (size_z + 1) // 2
    z = W_LongObject(a.space, [r_uint(0)] * digitpairs, 1)

    for i in range(size_z):
        if i < size_a:
            diga = a._getshort(i) ^ maska
        else:
            diga = maska
        if i < size_b:
            digb = b._getshort(i) ^ maskb
        else:
            digb = maskb
        if op == '&':
            z._setshort(i, diga & digb)
        elif op == '|':
            z._setshort(i, diga | digb)
        elif op == '^':
            z._setshort(i, diga ^ digb)

    z._normalize()
    if negz == 0:
        return z
    return invert__Long(z.space, z)
