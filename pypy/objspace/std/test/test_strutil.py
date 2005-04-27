import autopath
from pypy.objspace.std.strutil import *

objspacename = 'std'

class TestStrUtil:

    def test_string_to_int(self):
        space = self.space
        cases = [('0', 0),
                 ('1', 1),
                 ('9', 9),
                 ('10', 10),
                 ('09', 9),
                 ('0000101', 101),    # not octal unless base 0 or 8
                 ('5123', 5123),
                 (' 0', 0),
                 ('0  ', 0),
                 (' \t \n   32313  \f  \v   \r  \n\r    ', 32313),
                 ('+12', 12),
                 ('-5', -5),
                 ('- 5', -5),
                 ('+ 5', 5),
                 ('  -123456789 ', -123456789),
                 ]
        for s, expected in cases:
            assert string_to_int(space, s) == expected
            assert string_to_w_long(space, s).longval() == expected

    def test_string_to_int_base(self):
        space = self.space        
        cases = [('111', 2, 7),
                 ('010', 2, 2),
                 ('102', 3, 11),
                 ('103', 4, 19),
                 ('107', 8, 71),
                 ('109', 10, 109),
                 ('10A', 11, 131),
                 ('10a', 11, 131),
                 ('10f', 16, 271),
                 ('10F', 16, 271),
                 ('0x10f', 16, 271),
                 ('0x10F', 16, 271),
                 ('10z', 36, 1331),
                 ('10Z', 36, 1331),
                 ('12',   0, 12),
                 ('015',  0, 13),
                 ('0x10', 0, 16),
                 ('0XE',  0, 14),
                 ('0',    0, 0),
                 ('0x',   0, 0),    # according to CPython so far
                 ('0X',   0, 0),    #     "           "
                 ('0x',  16, 0),    #     "           "
                 ('0X',  16, 0),    #     "           "
                 ]
        for s, base, expected in cases:
            assert string_to_int(space, s, base) == expected
            assert string_to_int(space, '+'+s, base) == expected
            assert string_to_int(space, '-'+s, base) == -expected
            assert string_to_int(space, s+'\n', base) == expected
            assert string_to_int(space, '  +'+s, base) == expected
            assert string_to_int(space, '-'+s+'  ', base) == -expected

    def test_string_to_int_error(self):
        space = self.space
        cases = ['0x123',    # must use base 0 or 16
                 ' 0X12 ',
                 '',
                 '++12',
                 '+-12',
                 '-+12',
                 '--12',
                 '12a6',
                 '12A6',
                 'f',
                 'Z',
                 '.',
                 '@',
                 ]
        for s in cases:
            raises(ParseStringError, string_to_int, space, s)
            raises(ParseStringError, string_to_int, space, '  '+s)
            raises(ParseStringError, string_to_int, space, s+'  ')
            raises(ParseStringError, string_to_int, space, '+'+s)
            raises(ParseStringError, string_to_int, space, '-'+s)

    def test_string_to_int_overflow(self):
        space = self.space
        raises(ParseStringOverflowError, string_to_int, space,'1891234174197319')

    def test_string_to_int_base_error(self):
        space = self.space        
        cases = [('1', 1),
                 ('1', 37),
                 ('a', 0),
                 ('9', 9),
                 ('0x123', 7),
                 ('145cdf', 15),
                 ('12', 37),
                 ('12', 98172),
                 ('12', -1),
                 ('12', -908),
                 ('12.3', 10),
                 ('12.3', 13),
                 ('12.3', 16),
                 ]
        for s, base in cases:
            raises(ParseStringError, string_to_int, space, s, base)
            raises(ParseStringError, string_to_int, space, '  '+s, base)
            raises(ParseStringError, string_to_int, space, s+'  ', base)
            raises(ParseStringError, string_to_int, space, '+'+s, base)
            raises(ParseStringError, string_to_int, space, '-'+s, base)

    def test_string_to_w_long(self):
        space = self.space
        assert string_to_w_long(space, '123L').longval() == 123
        assert string_to_w_long(space, '123L  ').longval() == 123
        raises(ParseStringError, string_to_w_long, space, 'L')
        raises(ParseStringError, string_to_w_long, space, 'L  ')
        assert string_to_w_long(space, '123L', 4).longval() == 27
        assert string_to_w_long(space, '123L', 30).longval() == 27000 + 1800 + 90 + 21
        assert string_to_w_long(space, '123L', 22).longval() == 10648 + 968 + 66 + 21
        assert string_to_w_long(space, '123L', 21).longval() == 441 + 42 + 3
        assert string_to_w_long(space, '1891234174197319').longval() == 1891234174197319
