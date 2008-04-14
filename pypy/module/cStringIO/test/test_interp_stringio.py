
from pypy.conftest import gettestobjspace

import os, sys, py


class AppTestcStringIO:
    def setup_class(cls):
        space = gettestobjspace(usemodules=('cStringIO',))
        cls.space = space
        cls.w_write_many_expected_result = space.wrap(''.join(
            [chr(i) for j in range(10) for i in range(253)]))
        cls.w_StringIO = space.appexec([], """():
            import cStringIO
            return cStringIO.StringIO
        """)

    def test_simple(self):
        f = self.StringIO()
        f.write('hello')
        f.write(' world')
        assert f.getvalue() == 'hello world'

    def test_write_many(self):
        f = self.StringIO()
        for j in range(10):
            for i in range(253):
                f.write(chr(i))
        expected = ''.join([chr(i) for j in range(10) for i in range(253)])
        assert f.getvalue() == expected

    def test_seek(self):
        f = self.StringIO()
        f.write('0123')
        f.write('456')
        f.write('789')
        f.seek(4)
        f.write('AB')
        assert f.getvalue() == '0123AB6789'
        f.seek(-2, 2)
        f.write('CDE')
        assert f.getvalue() == '0123AB67CDE'
        f.seek(2, 0)
        f.seek(5, 1)
        f.write('F')
        assert f.getvalue() == '0123AB6FCDE'

    def test_write_beyond_end(self):
        f = self.StringIO()
        f.seek(20, 1)
        assert f.tell() == 20
        f.write('X')
        assert f.getvalue() == '\x00' * 20 + 'X'

    def test_tell(self):
        f = self.StringIO()
        f.write('0123')
        f.write('456')
        assert f.tell() == 7
        f.seek(2)
        for i in range(3, 20):
            f.write('X')
            assert f.tell() == i
        assert f.getvalue() == '01XXXXXXXXXXXXXXXXX'

    def test_read(self):
        f = self.StringIO()
        assert f.read() == ''
        f.write('0123')
        f.write('456')
        assert f.read() == ''
        assert f.read(5) == ''
        assert f.tell() == 7
        f.seek(1)
        assert f.read() == '123456'
        assert f.tell() == 7
        f.seek(1)
        assert f.read(12) == '123456'
        assert f.tell() == 7
        f.seek(1)
        assert f.read(2) == '12'
        assert f.read(1) == '3'
        assert f.tell() == 4
        f.seek(0)
        assert f.read() == '0123456'
        assert f.tell() == 7
        f.seek(0)
        assert f.read(7) == '0123456'
        assert f.tell() == 7
        f.seek(15)
        assert f.read(2) == ''
        assert f.tell() == 15

    def test_reset(self):
        from cStringIO import StringIO
        f = StringIO()
        f.write('foobar')
        f.reset()
        res = f.read()
        assert res == 'foobar'

    def test_close(self):
        from cStringIO import StringIO
        f = StringIO()
        assert not f.closed
        f.close()
        raises(ValueError, f.write, 'hello')
        raises(ValueError, f.getvalue)
        raises(ValueError, f.read, 0)
        raises(ValueError, f.seek, 0)
        assert f.closed
        f.close()
        assert f.closed
