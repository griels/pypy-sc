import autopath
import py
import os.path, subprocess, sys
import _socket
from pypy.translator.c.test.test_genc import compile
from pypy.translator.translator import Translator

HOST = "localhost"
PORT = 8037

def setup_module(mod):
    import pypy.module._socket.rpython.exttable   # for declare()/declaretype()
    serverpath = os.path.join(autopath.pypydir, "module/_socket/test/echoserver.py")
    mod.process = subprocess.Popen([sys.executable, serverpath])

def teardown_module(mod):
    import telnetlib
    tn = telnetlib.Telnet(HOST, PORT)
    tn.write("shutdown\n")
    tn.close()
    del tn
    del mod.process

def test_connect():
    import os
    from pypy.module._socket.rpython import rsocket
    def does_stuff():
        fd = rsocket.newsocket(_socket.AF_INET, _socket.SOCK_STREAM, 0)
        rsocket.connect(fd, (HOST, PORT, 0, 0))
        sockname = rsocket.getpeername(fd)
        os.close(fd)
        return sockname[1]
    f1 = compile(does_stuff, [])
    res = f1()
    assert res == PORT
