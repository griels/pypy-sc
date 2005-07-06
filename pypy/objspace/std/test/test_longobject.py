import autopath
import sys
from random import random, randint
from pypy.objspace.std import longobject as lobj
from pypy.objspace.std.objspace import FailedToImplement
from pypy.rpython.rarithmetic import r_uint
from pypy.interpreter.error import OperationError

objspacename = 'std'

def gen_signs(l):
    for s in l:
        if s == 0:
            yield s
        else:
            yield s
            yield -s


class TestW_LongObject:

    def test_add(self):
        x = 123456789123456789000000L
        y = 123858582373821923936744221L
        for i in [-1, 1]:
            for j in [-1, 1]:
                f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x * i))
                f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y * j))
                result = lobj.add__Long_Long(self.space, f1, f2)
                assert result.longval() == x * i + y * j

    def test_sub(self):
        x = 12378959520302182384345L 
        y = 88961284756491823819191823L
        for i in [-1, 1]:
            for j in [-1, 1]:
                f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x * i))
                f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y * j))
                result = lobj.sub__Long_Long(self.space, f1, f2)
                assert result.longval() == x * i - y * j

    def test_subzz(self):
        w_l0 = lobj.W_LongObject(self.space, [r_uint(0)])
        assert self.space.sub(w_l0, w_l0).longval() == 0

    def test_mul(self):
        x = -1238585838347L
        y = 585839391919233L
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
        result = lobj.mul__Long_Long(self.space, f1, f2)
        assert result.longval() == x * y

    def test__inplace_divrem1(self):
        # signs are not handled in the helpers!
        x = 1238585838347L
        y = 3
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = r_uint(y)
        remainder = lobj._inplace_divrem1(f1, f1, f2)
        assert (f1.longval(), remainder) == divmod(x, y)

    def test__divrem1(self):
        # signs are not handled in the helpers!
        x = 1238585838347L
        y = 3
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = r_uint(y)
        div, rem = lobj._divrem1(f1, f2)
        assert (div.longval(), rem) == divmod(x, y)

    def test__muladd1(self):
        x = 1238585838347L
        y = 3
        z = 42
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = r_uint(y)
        f3 = r_uint(z)
        prod = lobj._muladd1(f1, f2, f3)
        assert prod.longval() == x * y + z

    def test__x_divrem(self):
        x = 12345678901234567890L
        for i in range(100):
            y = long(randint(0, 1 << 30))
            y <<= 30
            y += randint(0, 1 << 30)
            f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
            f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
            div, rem = lobj._x_divrem(f1, f2)
            assert div.longval(), rem.longval() == divmod(x, y)

    def test__divrem(self):
        x = 12345678901234567890L
        for i in range(100):
            y = long(randint(0, 1 << 30))
            y <<= 30
            y += randint(0, 1 << 30)
            for sx, sy in (1, 1), (1, -1), (-1, -1), (-1, 1):
                sx *= x
                sy *= y
                f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(sx))
                f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(sy))
                div, rem = lobj._x_divrem(f1, f2)
                assert div.longval(), rem.longval() == divmod(sx, sy)

    def test__AsDouble(self):
        x = 12345678901234567890L ** 10
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        d = lobj._AsDouble(f1)
        assert d == float(x)
        x = x ** 100
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        assert raises(OverflowError, lobj._AsDouble, f1)

    def test__FromDouble(self):
        x = 1234567890.1234567890
        f1 = lobj._FromDouble(self.space, x)
        y = lobj._AsDouble(f1)
        assert f1.longval() == long(x)
        # check overflow
        x = 12345.6789e10000000000000000000000000000
        try:
            lobj._FromDouble(self.space, x)
        except OperationError, e:
            assert e.w_type is self.space.w_OverflowError

    def test_eq(self):
        x = 5858393919192332223L
        y = 585839391919233111223311112332L
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(-x))
        f3 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
        assert self.space.is_true(lobj.eq__Long_Long(self.space, f1, f1))
        assert self.space.is_true(lobj.eq__Long_Long(self.space, f2, f2))
        assert self.space.is_true(lobj.eq__Long_Long(self.space, f3, f3))
        assert not self.space.is_true(lobj.eq__Long_Long(self.space, f1, f2))
        assert not self.space.is_true(lobj.eq__Long_Long(self.space, f1, f3))

    def test_lt(self):
        val = [0, 0x111111111111, 0x111111111112, 0x111111111112FFFF]
        for x in gen_signs(val):
            for y in gen_signs(val):
                f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
                f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
                assert (x < y) ==  self.space.is_true(
                    lobj.lt__Long_Long(self.space, f1, f2))

    def test_int_conversion(self):
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(12332))
        f2 = lobj.delegate_Int2Long(self.space.newint(12332))
        assert f2.longval() == f1.longval()
        assert lobj.int__Long(self.space, f2).intval == 12332
        assert lobj.int_w__Long(self.space, f2) == 12332
        assert lobj.long__Int(self.space, self.space.wrap(42)).longval() == 42
        assert lobj.long__Int(self.space, self.space.wrap(-42)).longval() == -42

        u = lobj.uint_w__Long(self.space, f2)
        assert u == 12332
        assert isinstance(u, r_uint)

    def test_conversions(self):
        space = self.space
        for v in (0, 1, -1, sys.maxint, -sys.maxint-1):
            assert lobj.W_LongObject(self.space, *lobj.args_from_long(v)).longval() == v
            w_v = space.newint(v)
            for w_lv in (lobj.long__Int(space, w_v), lobj.delegate_Int2Long(w_v)):
                assert w_lv.longval() == v
                assert lobj.int_w__Long(space, w_lv) == v
                assert space.is_true(space.isinstance(lobj.int__Long(space, w_lv), space.w_int))            
                assert space.eq_w(lobj.int__Long(space, w_lv), w_v)

                if v>=0:
                    u = lobj.uint_w__Long(space, w_lv)
                    assert u == v
                    assert isinstance(u, r_uint)
                else:
                    space.raises_w(space.w_ValueError, lobj.uint_w__Long, space, w_lv)

        w_toobig_lv1 = lobj.W_LongObject(space, *lobj.args_from_long(sys.maxint+1))
        assert w_toobig_lv1.longval() == sys.maxint+1
        w_toobig_lv2 = lobj.W_LongObject(space, *lobj.args_from_long(sys.maxint+2))
        assert w_toobig_lv2.longval() == sys.maxint+2
        w_toobig_lv3 = lobj.W_LongObject(space, *lobj.args_from_long(-sys.maxint-2))
        assert w_toobig_lv3.longval() == -sys.maxint-2        

        for w_lv in (w_toobig_lv1, w_toobig_lv2, w_toobig_lv3):            
            space.raises_w(space.w_OverflowError, lobj.int_w__Long, space, w_lv)
            assert space.is_true(space.isinstance(lobj.int__Long(space, w_lv), space.w_long))

        w_lmaxuint = lobj.W_LongObject(space, *lobj.args_from_long(2*sys.maxint+1))
        w_toobig_lv4 = lobj.W_LongObject(space, *lobj.args_from_long(2*sys.maxint+2))        

        u = lobj.uint_w__Long(space, w_lmaxuint)
        assert u == 2*sys.maxint+1
        assert isinstance(u, r_uint)
        
        space.raises_w(space.w_ValueError, lobj.uint_w__Long, space, w_toobig_lv3)       
        space.raises_w(space.w_OverflowError, lobj.uint_w__Long, space, w_toobig_lv4)



    def test_pow_lll(self):
        x = 10L
        y = 2L
        z = 13L
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
        f3 = lobj.W_LongObject(self.space, *lobj.args_from_long(z))
        v = lobj.pow__Long_Long_Long(self.space, f1, f2, f3)
        assert v.longval() == pow(x, y, z)
        f1, f2, f3 = [lobj.W_LongObject(self.space, *lobj.args_from_long(i))
                      for i in (10L, -1L, 42L)]
        self.space.raises_w(self.space.w_TypeError,
                            lobj.pow__Long_Long_Long,
                            self.space, f1, f2, f3)
        f1, f2, f3 = [lobj.W_LongObject(self.space, *lobj.args_from_long(i))
                      for i in (10L, 5L, 0L)]
        self.space.raises_w(self.space.w_ValueError,
                            lobj.pow__Long_Long_Long,
                            self.space, f1, f2, f3)

    def test_pow_lln(self):
        x = 10L
        y = 2L
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
        v = lobj.pow__Long_Long_None(self.space, f1, f2, self.space.w_None)
        assert v.longval() == x ** y

    def test_normalize(self):
        f1 = lobj.W_LongObject(self.space, [lobj.r_uint(1), lobj.r_uint(0)], 1)
        f1._normalize()
        assert len(f1.digits) == 1
        f0 = lobj.W_LongObject(self.space, [lobj.r_uint(0)], 0)
        assert self.space.is_true(
            self.space.eq(lobj.sub__Long_Long(self.space, f1, f1), f0))

    def test_invert(self):
        x = 3 ** 40
        f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
        f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(-x))
        r1 = lobj.invert__Long(self.space, f1)
        r2 = lobj.invert__Long(self.space, f2)
        assert r1.longval() == -(x + 1)
        assert r2.longval() == -(-x + 1)

    def test_shift(self):
        negative = lobj.W_LongObject(self.space, *lobj.args_from_long(-23))
        big = lobj.W_LongObject(self.space, *lobj.args_from_long(2L ** 100L))
        for x in gen_signs([3L ** 30L, 5L ** 20L, 7 ** 300, 0L, 1L]):
            f1 = lobj.W_LongObject(self.space, *lobj.args_from_long(x))
            self.space.raises_w(self.space.w_ValueError,
                                lobj.lshift__Long_Long, self.space, f1,
                                negative)
            self.space.raises_w(self.space.w_ValueError,
                                lobj.rshift__Long_Long, self.space, f1,
                                negative)                                
            self.space.raises_w(self.space.w_OverflowError,
                                lobj.lshift__Long_Long, self.space, f1,
                                big)
            self.space.raises_w(self.space.w_OverflowError,
                                lobj.rshift__Long_Long, self.space, f1,
                                big)                                
            for y in [0L, 1L, 32L, 2304L, 11233L, 3 ** 9]:
                f2 = lobj.W_LongObject(self.space, *lobj.args_from_long(y))
                res1 = lobj.lshift__Long_Long(self.space, f1, f2).longval()
                res2 = lobj.rshift__Long_Long(self.space, f1, f2).longval()
                assert res1 == x << y
                assert res2 == x >> y

class AppTestLong:
    def test_add(self):
        assert int(123L + 12443L) == 123 + 12443
        assert -20 + 2 + 3L + True == -14L

    def test_sub(self):
        assert int(58543L - 12332L) == 58543 - 12332
        assert 237123838281233L * 12 == 237123838281233L * 12L

    def test_mul(self):
        assert 363L * 2 ** 40 == 363L << 40

    def test_truediv(self):
        exec "from __future__ import division; a = 31415926L / 10000000L"
        assert a == 3.1415926

    def test_floordiv(self):
        a = 31415926L // 10000000L
        assert a == 3L

    def test_conversion(self):
        class long2(long):
            pass
        x = long2(1L<<100)
        y = int(x)
        assert type(y) == long

    def test_pow(self):
        assert pow(0L, 0L, 1L) == 0L

    def test_getnewargs(self):
        assert  0L .__getnewargs__() == (0L,)
        assert  (-1L) .__getnewargs__() == (-1L,)

    def test_divmod(self):
        def check_division(x, y):
            q, r = divmod(x, y)
            pab, pba = x*y, y*x
            assert pab == pba
            assert q == x//y
            assert r == x%y
            assert x == q*y + r
            if y > 0:
                assert 0 <= r < y
            else:
                assert y < r <= 0
        for x in [-1L, 0L, 1L, 2L ** 100 - 1, -2L ** 100 - 1]:
            for y in [-105566530L, -1L, 1L, 1034522340L]:
                continue
                print "checking division for %s, %s" % (x, y)
                check_division(x, y)
        # special case from python tests:
        s1 = 33
        s2 = 2
        x = 16565645174462751485571442763871865344588923363439663038777355323778298703228675004033774331442052275771343018700586987657790981527457655176938756028872904152013524821759375058141439
        x >>= s1*16
        y = 10953035502453784575
        y >>= s2*16
        x = 0x3FE0003FFFFC0001FFFL
        y = 0x9800FFC1L
        print "special case"
        check_division(x, y)
        raises(ZeroDivisionError, "x // 0L")

    def test_format(self):
        assert repr(12345678901234567890) == '12345678901234567890L'
        assert str(12345678901234567890) == '12345678901234567890'
        assert hex(0x1234567890ABCDEFL) == '0x1234567890ABCDEFL'
        assert oct(01234567012345670L) == '01234567012345670L'

    def test_bits(self):
        assert 0xAAAAAAAAL | 0x55555555L == 0xFFFFFFFFL
        assert 0xAAAAAAAAL & 0x55555555L == 0x00000000L
        assert 0xAAAAAAAAL ^ 0x55555555L == 0xFFFFFFFFL
        assert -0xAAAAAAAAL | 0x55555555L == -0xAAAAAAA9L
        assert 0xAAAAAAAAL | 0x555555555L == 0x5FFFFFFFFL
        assert 0xAAAAAAAAL & 0x555555555L == 0x000000000L
        assert 0xAAAAAAAAL ^ 0x555555555L == 0x5FFFFFFFFL
