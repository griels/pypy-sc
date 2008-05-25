
from pypy.rlib.rzipfile import RZipFile
from pypy.tool.udir import udir
from zipfile import ZIP_STORED, ZIP_DEFLATED, ZipInfo, ZipFile
from pypy.rpython.test.tool import BaseRtypingTest, LLRtypeMixin, OORtypeMixin
import os
import time

class BaseTestRZipFile(BaseRtypingTest):

    def setup_class(cls):
        tmpdir = udir.ensure('zipimport_%s' % cls.__name__, dir=1)
        zipname = str(tmpdir.join("somezip.zip"))
        cls.zipname = zipname
        zipfile = ZipFile(zipname, "w", compression=cls.compression)
        cls.year = time.localtime(time.time())[0]
        zipfile.writestr("one", "stuff")
        zipfile.writestr("dir" + os.path.sep + "two", "otherstuff")
        zipfile.close()
    
    def test_rzipfile(self):
        zipname = self.zipname
        year = self.year
        compression = self.compression
        def one():
            rzip = RZipFile(zipname, "r", compression)
            info = rzip.getinfo('one')
            return (info.date_time[0] == year and
                    rzip.read('one') == 'stuff')

        assert one()
        assert self.interpret(one, [])

class TestRZipFile(BaseTestRZipFile, LLRtypeMixin):
    compression = ZIP_STORED

class TestRZipFileCompressed(BaseTestRZipFile, LLRtypeMixin):
    compression = ZIP_DEFLATED