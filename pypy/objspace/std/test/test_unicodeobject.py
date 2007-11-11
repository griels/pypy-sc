import sys


class AppTestUnicodeStringStdOnly:
    def test_compares(self):
        assert u'a' == 'a'
        assert 'a' == u'a'
        assert not u'a' == 'b'
        assert not 'a'  == u'b'
        assert u'a' != 'b'
        assert 'a'  != u'b'
        assert not (u'a' == 5)
        assert u'a' != 5
        assert u'a' < 5 or u'a' > 5

class AppTestUnicodeString:
    def test_addition(self):
        def check(a, b):
            assert a == b
            assert type(a) == type(b)
        check(u'a' + 'b', u'ab')
        check('a' + u'b', u'ab')

    def test_join(self):
        def check(a, b):
            assert a == b
            assert type(a) == type(b)
        check(', '.join([u'a']), u'a')
        check(', '.join(['a', u'b']), u'a, b')
        check(u', '.join(['a', 'b']), u'a, b')

    if sys.version_info >= (2,3):
        def test_contains_ex(self):
            assert u'' in 'abc'
            assert u'bc' in 'abc'
            assert 'bc' in 'abc'
        pass   # workaround for inspect.py bug in some Python 2.4s

    def test_contains(self):
        assert u'a' in 'abc'
        assert 'a' in u'abc'

    def test_splitlines(self):
        assert u''.splitlines() == []
        assert u''.splitlines(1) == []
        assert u'\n'.splitlines() == [u'']
        assert u'a'.splitlines() == [u'a']
        assert u'one\ntwo'.splitlines() == [u'one', u'two']
        assert u'\ntwo\nthree'.splitlines() == [u'', u'two', u'three']
        assert u'\n\n'.splitlines() == [u'', u'']
        assert u'a\nb\nc'.splitlines(1) == [u'a\n', u'b\n', u'c']
        assert u'\na\nb\n'.splitlines(1) == [u'\n', u'a\n', u'b\n']

    def test_zfill(self):
        assert u'123'.zfill(2) == u'123'
        assert u'123'.zfill(3) == u'123'
        assert u'123'.zfill(4) == u'0123'
        assert u'123'.zfill(6) == u'000123'
        assert u'+123'.zfill(2) == u'+123'
        assert u'+123'.zfill(3) == u'+123'
        assert u'+123'.zfill(4) == u'+123'
        assert u'+123'.zfill(5) == u'+0123'
        assert u'+123'.zfill(6) == u'+00123'
        assert u'-123'.zfill(3) == u'-123'
        assert u'-123'.zfill(4) == u'-123'
        assert u'-123'.zfill(5) == u'-0123'
        assert u''.zfill(3) == u'000'
        assert u'34'.zfill(1) == u'34'
        assert u'34'.zfill(4) == u'0034'

    def test_split(self):
        assert u"".split() == []
        assert u"".split(u'x') == ['']
        assert u" ".split() == []
        assert u"a".split() == [u'a']
        assert u"a".split(u"a", 1) == [u'', u'']
        assert u" ".split(u" ", 1) == [u'', u'']
        assert u"aa".split(u"a", 2) == [u'', u'', u'']
        assert u" a ".split() == [u'a']
        assert u"a b c".split() == [u'a',u'b',u'c']
        assert u'this is the split function'.split() == [u'this', u'is', u'the', u'split', u'function']
        assert u'a|b|c|d'.split(u'|') == [u'a', u'b', u'c', u'd']
        assert 'a|b|c|d'.split(u'|') == [u'a', u'b', u'c', u'd']
        assert u'a|b|c|d'.split('|') == [u'a', u'b', u'c', u'd']
        assert u'a|b|c|d'.split(u'|', 2) == [u'a', u'b', u'c|d']
        assert u'a b c d'.split(None, 1) == [u'a', u'b c d']
        assert u'a b c d'.split(None, 2) == [u'a', u'b', u'c d']
        assert u'a b c d'.split(None, 3) == [u'a', u'b', u'c', u'd']
        assert u'a b c d'.split(None, 4) == [u'a', u'b', u'c', u'd']
        assert u'a b c d'.split(None, 0) == [u'a b c d']
        assert u'a  b  c  d'.split(None, 2) == [u'a', u'b', u'c  d']
        assert u'a b c d '.split() == [u'a', u'b', u'c', u'd']
        assert u'a//b//c//d'.split(u'//') == [u'a', u'b', u'c', u'd']
        assert u'endcase test'.split(u'test') == [u'endcase ', u'']
        raises(ValueError, u'abc'.split, '')
        raises(ValueError, u'abc'.split, u'')
        raises(ValueError, 'abc'.split, u'')

    def test_rsplit(self):
        assert u"".rsplit() == []
        assert u" ".rsplit() == []
        assert u"a".rsplit() == [u'a']
        assert u"a".rsplit(u"a", 1) == [u'', u'']
        assert u" ".rsplit(u" ", 1) == [u'', u'']
        assert u"aa".rsplit(u"a", 2) == [u'', u'', u'']
        assert u" a ".rsplit() == [u'a']
        assert u"a b c".rsplit() == [u'a',u'b',u'c']
        assert u'this is the rsplit function'.rsplit() == [u'this', u'is', u'the', u'rsplit', u'function']
        assert u'a|b|c|d'.rsplit(u'|') == [u'a', u'b', u'c', u'd']
        assert u'a|b|c|d'.rsplit('|') == [u'a', u'b', u'c', u'd']
        assert 'a|b|c|d'.rsplit(u'|') == [u'a', u'b', u'c', u'd']
        assert u'a|b|c|d'.rsplit(u'|', 2) == [u'a|b', u'c', u'd']
        assert u'a b c d'.rsplit(None, 1) == [u'a b c', u'd']
        assert u'a b c d'.rsplit(None, 2) == [u'a b', u'c', u'd']
        assert u'a b c d'.rsplit(None, 3) == [u'a', u'b', u'c', u'd']
        assert u'a b c d'.rsplit(None, 4) == [u'a', u'b', u'c', u'd']
        assert u'a b c d'.rsplit(None, 0) == [u'a b c d']
        assert u'a  b  c  d'.rsplit(None, 2) == [u'a  b', u'c', u'd']
        assert u'a b c d '.rsplit() == [u'a', u'b', u'c', u'd']
        assert u'a//b//c//d'.rsplit(u'//') == [u'a', u'b', u'c', u'd']
        assert u'endcase test'.rsplit(u'test') == [u'endcase ', u'']
        raises(ValueError, u'abc'.rsplit, u'')
        raises(ValueError, u'abc'.rsplit, '')
        raises(ValueError, 'abc'.rsplit, u'')

    def test_center(self):
        s=u"a b"
        assert s.center(0) == u"a b"
        assert s.center(1) == u"a b"
        assert s.center(2) == u"a b"
        assert s.center(3) == u"a b"
        assert s.center(4) == u"a b "
        assert s.center(5) == u" a b "
        assert s.center(6) == u" a b  "
        assert s.center(7) == u"  a b  "
        assert s.center(8) == u"  a b   "
        assert s.center(9) == u"   a b   "
        assert u'abc'.center(10) == u'   abc    '
        assert u'abc'.center(6) == u' abc  '
        assert u'abc'.center(3) == u'abc'
        assert u'abc'.center(2) == u'abc'
        assert u'abc'.center(5, u'*') == u'*abc*'    # Python 2.4
        assert u'abc'.center(5, '*') == u'*abc*'     # Python 2.4
        raises(TypeError, u'abc'.center, 4, u'cba')

    def test_title(self):
        assert u"brown fox".title() == u"Brown Fox"
        assert u"!brown fox".title() == u"!Brown Fox"
        assert u"bROWN fOX".title() == u"Brown Fox"
        assert u"Brown Fox".title() == u"Brown Fox"
        assert u"bro!wn fox".title() == u"Bro!Wn Fox"

    def test_istitle(self):
        assert u"".istitle() == False
        assert u"!".istitle() == False
        assert u"!!".istitle() == False
        assert u"brown fox".istitle() == False
        assert u"!brown fox".istitle() == False
        assert u"bROWN fOX".istitle() == False
        assert u"Brown Fox".istitle() == True
        assert u"bro!wn fox".istitle() == False
        assert u"Bro!wn fox".istitle() == False
        assert u"!brown Fox".istitle() == False
        assert u"!Brown Fox".istitle() == True
        assert u"Brow&&&&N Fox".istitle() == True
        assert u"!Brow&&&&n Fox".istitle() == False
        
    def test_capitalize(self):
        assert u"brown fox".capitalize() == u"Brown fox"
        assert u' hello '.capitalize() == u' hello '
        assert u'Hello '.capitalize() == u'Hello '
        assert u'hello '.capitalize() == u'Hello '
        assert u'aaaa'.capitalize() == u'Aaaa'
        assert u'AaAa'.capitalize() == u'Aaaa'

    def test_rjust(self):
        s = u"abc"
        assert s.rjust(2) == s
        assert s.rjust(3) == s
        assert s.rjust(4) == u" " + s
        assert s.rjust(5) == u"  " + s
        assert u'abc'.rjust(10) == u'       abc'
        assert u'abc'.rjust(6) == u'   abc'
        assert u'abc'.rjust(3) == u'abc'
        assert u'abc'.rjust(2) == u'abc'
        assert u'abc'.rjust(5, u'*') == u'**abc'    # Python 2.4
        assert u'abc'.rjust(5, '*') == u'**abc'     # Python 2.4
        raises(TypeError, u'abc'.rjust, 5, u'xx')

    def test_ljust(self):
        s = u"abc"
        assert s.ljust(2) == s
        assert s.ljust(3) == s
        assert s.ljust(4) == s + u" "
        assert s.ljust(5) == s + u"  "
        assert u'abc'.ljust(10) == u'abc       '
        assert u'abc'.ljust(6) == u'abc   '
        assert u'abc'.ljust(3) == u'abc'
        assert u'abc'.ljust(2) == u'abc'
        assert u'abc'.ljust(5, u'*') == u'abc**'    # Python 2.4
        assert u'abc'.ljust(5, '*') == u'abc**'     # Python 2.4
        raises(TypeError, u'abc'.ljust, 6, u'')

    def test_replace(self):
        assert u'one!two!three!'.replace(u'!', '@', 1) == u'one@two!three!'
        assert u'one!two!three!'.replace('!', u'') == u'onetwothree'
        assert u'one!two!three!'.replace(u'!', u'@', 2) == u'one@two@three!'
        assert u'one!two!three!'.replace('!', '@', 3) == u'one@two@three@'
        assert u'one!two!three!'.replace(u'!', '@', 4) == u'one@two@three@'
        assert u'one!two!three!'.replace('!', u'@', 0) == u'one!two!three!'
        assert u'one!two!three!'.replace(u'!', u'@') == u'one@two@three@'
        assert u'one!two!three!'.replace('x', '@') == u'one!two!three!'
        assert u'one!two!three!'.replace(u'x', '@', 2) == u'one!two!three!'
        assert u'abc'.replace('', u'-') == u'-a-b-c-'
        assert u'abc'.replace(u'', u'-', 3) == u'-a-b-c'
        assert u'abc'.replace('', '-', 0) == u'abc'
        assert u''.replace(u'', '') == u''
        assert u''.replace('', u'a') == u'a'
        assert u'abc'.replace(u'ab', u'--', 0) == u'abc'
        assert u'abc'.replace('xy', '--') == u'abc'
        assert u'123'.replace(u'123', '') == u''
        assert u'123123'.replace('123', u'') == u''
        assert u'123x123'.replace(u'123', u'') == u'x'

    def test_strip(self):
        s = u" a b "
        assert s.strip() == u"a b"
        assert s.rstrip() == u" a b"
        assert s.lstrip() == u"a b "
        assert u'xyzzyhelloxyzzy'.strip(u'xyz') == u'hello'
        assert u'xyzzyhelloxyzzy'.lstrip('xyz') == u'helloxyzzy'
        assert u'xyzzyhelloxyzzy'.rstrip(u'xyz') == u'xyzzyhello'


    def test_long_from_unicode(self):
        assert long(u'12345678901234567890') == 12345678901234567890
        assert int(u'12345678901234567890') == 12345678901234567890

    def test_int_from_unicode(self):
        assert int(u'12345') == 12345

    def test_float_from_unicode(self):
        assert float(u'123.456e89') == float('123.456e89')

    def test_repr(self):
        for ustr in [u"", u"a", u"'", u"\'", u"\"", u"\t", u"\\", u'',
                     u'a', u'"', u'\'', u'\"', u'\t', u'\\', u"'''\"",
                     unichr(19), unichr(2), u'\u1234', u'\U00101234']:
            assert eval(repr(ustr)) == ustr
            
    def test_getnewargs(self):
        class X(unicode):
            pass
        x = X(u"foo\u1234")
        a = x.__getnewargs__()
        assert a == (u"foo\u1234",)
        assert type(a[0]) is unicode

    def test_call_unicode(self):
        assert unicode() == u''
        assert unicode(None) == u'None'
        assert unicode(123) == u'123'
        assert unicode([2, 3]) == u'[2, 3]'

    def test_call_unicode(self):
        skip("does not work")
        class X:
            def __unicode__(self):
                return u'x'

        try:
            unicode(X(), 'ascii')
        except TypeError, t:
            assert 'need string or buffer' in str(t)
        else:
            raise Exception("DID NOT RAISE")

    def test_startswith(self):
        assert u'ab'.startswith(u'ab') is True
        assert u'ab'.startswith(u'a') is True
        assert u'ab'.startswith(u'') is True
        assert u'x'.startswith(u'a') is False
        assert u'x'.startswith(u'x') is True
        assert u''.startswith(u'') is True
        assert u''.startswith(u'a') is False
        assert u'x'.startswith(u'xx') is False
        assert u'y'.startswith(u'xx') is False

    def test_startswith_more(self):
        assert u'ab'.startswith(u'a', 0) is True
        assert u'ab'.startswith(u'a', 1) is False
        assert u'ab'.startswith(u'b', 1) is True
        assert u'abc'.startswith(u'bc', 1, 2) is False
        assert u'abc'.startswith(u'c', -1, 4) is True

    def test_startswith_tuples(self):
        assert u'hello'.startswith((u'he', u'ha'))
        assert not u'hello'.startswith((u'lo', u'llo'))
        assert u'hello'.startswith((u'hellox', u'hello'))
        assert not u'hello'.startswith(())
        assert u'helloworld'.startswith((u'hellowo', u'rld', u'lowo'), 3)
        assert not u'helloworld'.startswith((u'hellowo', u'ello', u'rld'), 3)
        assert u'hello'.startswith((u'lo', u'he'), 0, -1)
        assert not u'hello'.startswith((u'he', u'hel'), 0, 1)
        assert u'hello'.startswith((u'he', u'hel'), 0, 2)
        raises(TypeError, u'hello'.startswith, (42,))
    
    def test_endswith(self):
        assert u'ab'.endswith(u'ab') is True
        assert u'ab'.endswith(u'b') is True
        assert u'ab'.endswith(u'') is True
        assert u'x'.endswith(u'a') is False
        assert u'x'.endswith(u'x') is True
        assert u''.endswith(u'') is True
        assert u''.endswith(u'a') is False
        assert u'x'.endswith(u'xx') is False
        assert u'y'.endswith(u'xx') is False

    def test_endswith_more(self):
        assert u'abc'.endswith(u'ab', 0, 2) is True
        assert u'abc'.endswith(u'bc', 1) is True
        assert u'abc'.endswith(u'bc', 2) is False
        assert u'abc'.endswith(u'b', -3, -1) is True

    def test_endswith_tuple(self):
        assert not u'hello'.endswith((u'he', u'ha'))
        assert u'hello'.endswith((u'lo', u'llo'))
        assert u'hello'.endswith((u'hellox', u'hello'))
        assert not u'hello'.endswith(())
        assert u'helloworld'.endswith((u'hellowo', u'rld', u'lowo'), 3)
        assert not u'helloworld'.endswith((u'hellowo', u'ello', u'rld'), 3, -1)
        assert u'hello'.endswith((u'hell', u'ell'), 0, -1)
        assert not u'hello'.endswith((u'he', u'hel'), 0, 1)
        assert u'hello'.endswith((u'he', u'hell'), 0, 4)
        raises(TypeError, u'hello'.endswith, (42,))

    def test_expandtabs(self):
        assert u'abc\rab\tdef\ng\thi'.expandtabs() ==    u'abc\rab      def\ng       hi'
        assert u'abc\rab\tdef\ng\thi'.expandtabs(8) ==   u'abc\rab      def\ng       hi'
        assert u'abc\rab\tdef\ng\thi'.expandtabs(4) ==   u'abc\rab  def\ng   hi'
        assert u'abc\r\nab\tdef\ng\thi'.expandtabs(4) == u'abc\r\nab  def\ng   hi'
        assert u'abc\rab\tdef\ng\thi'.expandtabs() ==    u'abc\rab      def\ng       hi'
        assert u'abc\rab\tdef\ng\thi'.expandtabs(8) ==   u'abc\rab      def\ng       hi'
        assert u'abc\r\nab\r\ndef\ng\r\nhi'.expandtabs(4) == u'abc\r\nab\r\ndef\ng\r\nhi'

        s = u'xy\t'
        assert s.expandtabs() =='xy      '
        
        s = u'\txy\t'
        assert s.expandtabs() =='        xy      '
        assert s.expandtabs(1) ==' xy '
        assert s.expandtabs(2) =='  xy  '
        assert s.expandtabs(3) =='   xy '
        
        assert u'xy'.expandtabs() =='xy'
        assert u''.expandtabs() ==''

    def test_translate(self):
        assert u'bbbc' == u'abababc'.translate({ord('a'):None})
        assert u'iiic' == u'abababc'.translate({ord('a'):None, ord('b'):ord('i')})
        assert u'iiix' == u'abababc'.translate({ord('a'):None, ord('b'):ord('i'), ord('c'):u'x'})
        assert u'<i><i><i>c' == u'abababc'.translate({ord('a'):None, ord('b'):u'<i>'})
        assert u'c' == u'abababc'.translate({ord('a'):None, ord('b'):u''})
        assert u'xyyx' == u'xzx'.translate({ord('z'):u'yy'})

        raises(TypeError, u'hello'.translate)
        raises(TypeError, u'abababc'.translate, {ord('a'):''})

    def test_unicode_form_encoded_object(self):
        assert unicode('x', 'utf-8') == u'x'
        assert unicode('x', 'utf-8', 'strict') == u'x'
        
    def test_unicode_startswith_tuple(self):
        assert u'xxx'.startswith(('x', 'y', 'z'), 0)
        assert u'xxx'.endswith(('x', 'y', 'z'), 0)

    def test_missing_cases(self):
        # some random cases, which are discovered to not be tested during annotation
        assert u'xxx'[1:1] == u''
