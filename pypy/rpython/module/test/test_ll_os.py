import os
from pypy.tool.udir import udir
from pypy.tool.pytest.modcheck import skipimporterror
from pypy.translator.c.test.test_genc import compile

from pypy.rpython import extregistry
from pypy.rpython.lltypesystem.module.ll_os import Implementation as impl
import sys
import py

def getllimpl(fn):
    return extregistry.lookup(fn).lltypeimpl

def test_access():
    filename = str(udir.join('test_access.txt'))
    fd = file(filename, 'w')
    fd.close()

    for mode in os.R_OK, os.W_OK, os.X_OK, os.R_OK | os.W_OK | os.X_OK:
        result = getllimpl(os.access)(filename, mode)
        assert result == os.access(filename, mode)


def test_getcwd():
    data = getllimpl(os.getcwd)()
    assert data == os.getcwd()

def test_strerror():
    data = impl.ll_os_strerror(2)
    assert impl.from_rstr(data) == os.strerror(2)

def test_system():
    filename = str(udir.join('test_system.txt'))
    arg = impl.to_rstr('python -c "print 1+1" > %s' % filename)
    data = impl.ll_os_system(arg)
    assert data == 0
    assert file(filename).read().strip() == '2'
    os.unlink(filename)

def test_putenv_unsetenv():
    filename = str(udir.join('test_putenv.txt'))
    arg = impl.to_rstr('abcdefgh=12345678')
    impl.ll_os_putenv(arg)
    cmd = '''python -c "import os; print os.environ['abcdefgh']" > %s''' % filename
    os.system(cmd)
    f = file(filename)
    result = f.read().strip()
    assert result == '12345678'
    f.close()
    os.unlink(filename)
    posix = __import__(os.name)
    if hasattr(posix, "unsetenv"):
        impl.ll_os_unsetenv(impl.to_rstr("abcdefgh"))
        cmd = '''python -c "import os; print repr(os.getenv('abcdefgh'))" > %s''' % filename
        os.system(cmd)
        f = file(filename)
        result = f.read().strip()
        assert result == 'None'
        f.close()
        os.unlink(filename)

test_src = """
import os
from pypy.tool.udir import udir
#from pypy.rpython.module.ll_os import 

def test_environ():
    count = 0
    while 1:
        l
        if not impl.ll_os_environ(count):
            break
        count += 1
    channel.send(count == len(os.environ.keys()))
test_environ()
"""

def test_environ():
    import py
    py.test.skip("Test hangs, should be rewritten to new-style")
    gw = py.execnet.PopenGateway()
    chan = gw.remote_exec(py.code.Source(test_src))
    res = chan.receive()
    assert res
    chan.close()

def test_opendir_readdir():
    dirname = str(udir)
    rsdirname = impl.to_rstr(dirname)
    result = []
    DIR = impl.ll_os_opendir(rsdirname)
    try:
        while True:
            nextentry = impl.ll_os_readdir(DIR)
            if not nextentry:   # null pointer check
                break
            result.append(impl.from_rstr(nextentry))
    finally:
        impl.ll_os_closedir(DIR)
    assert '.' in result
    assert '..' in result
    result.remove('.')
    result.remove('..')
    result.sort()
    compared_with = os.listdir(dirname)
    compared_with.sort()
    assert result == compared_with

class ExpectTestOs:
    def setup_class(cls):
        if not hasattr(os, 'ttyname'):
            py.test.skip("no ttyname")
        py.test.skip("XXX get_errno() does not work with ll2ctypes")
    
    def test_ttyname(self):
        import os
        import py
        from pypy.rpython.test.test_llinterp import interpret

        def ll_to_string(s):
            return ''.join(s.chars)
        
        def f(num):
            try:
                return os.ttyname(num)
            except OSError:
                return ''

        assert ll_to_string(interpret(f, [0])) == f(0)
        assert ll_to_string(interpret(f, [338])) == ''
