import os
from pypy.lib import _file 
from pypy.tool.udir import udir 
import py 

class TestFile: 
    def setup_method(self, method):
        self.fd = _file.file(__file__, 'r')

    def teardown_method(self, method):
        self.fd.close()
        
    def test_case_1(self):
        assert self.fd.tell() == 0

    def test_case_readonly(self):
        fn = str(udir.join('temptestfile'))
        f=_file.file(fn, 'w')
        assert f.name == fn
        assert f.mode == 'w'
        assert f.closed == False
        assert f.encoding == None # Fix when we find out what this is
        py.test.raises((TypeError, AttributeError), setattr, f, 'name', 42)

    def test_plain_read(self):
        data1 = self.fd.read()
        data2 = open(__file__, 'r').read()
        assert data1 == data2

    def test_readline(self):
        cpyfile = open(__file__, 'r')
        assert self.fd.readline() == cpyfile.readline()
        for i in range(-1, 10):
            assert self.fd.readline(i) == cpyfile.readline(i)

    def test_readlines(self):
        fn = str(udir.join('temptestfile'))
        lines = ['line%d\n' % i for i in range(10000)]
        f=_file.file(fn, 'w')
        f.writelines(lines)
        f.close()
        assert open(fn, 'r').readlines() == lines
        assert _file.file(fn, 'r').readlines() == lines
        somelines = _file.file(fn, 'r').readlines(20000)
        assert len(somelines) > 2000
        assert somelines == lines[:len(somelines)]
