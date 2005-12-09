import autopath
import py
import _socket
from pypy.translator.c.test.test_genc import compile
from pypy.translator.translator import Translator

def setup_module(mod):
    import pypy.module._socket.rpython.exttable   # for declare()/declaretype()

def test_htonl():
    # This just checks that htons etc. are their own inverse,
    # when looking at the lower 16 or 32 bits.
    def fn1(n):
        return _socket.htonl(n)
    def fn2(n):
        return _socket.ntohl(n)
    def fn3(n):
        return _socket.ntohs(n)
    def fn4(n):
        return _socket.htons(n)
    sizes = {compile(fn1, [int]): 32, compile(fn2, [int]): 32,
             compile(fn4, [int]): 16, compile(fn3, [int]): 16}
    for func, size in sizes.items():
        mask = (1L<<size) - 1
        # Don't try with 'long' values: type conversion is done
        # at the interp level, not at the C level
        for i in (0, 1, 0xffff, 2, 0x01234567, 0x76543210):
            print func, hex(i&mask)
            assert i & mask == func(func(i&mask)) & mask

def test_gethostname():
    def does_stuff():
        return _socket.gethostname()
    f1 = compile(does_stuff, [])
    res = f1()
    assert res == _socket.gethostname()


def test_gethostbyname():
    def does_stuff(host):
        return _socket.gethostbyname(host)
    f1 = compile(does_stuff, [str])
    res = f1("localhost")
    assert res == _socket.gethostbyname("localhost")

def test_getaddrinfo():
    py.test.skip("segfaulting on linux right now")
    import pypy.module._socket.rpython.exttable   # for declare()/declaretype()
    from pypy.module._socket.rpython import rsocket
    def does_stuff(host, port):
        addr = rsocket.getaddrinfo(host, port, 0, 0, 0, 0)
        result = []
        while True: 
            info = addr.nextinfo()
            if info[0] == 0:
                break
            result.append("(%d, %d, %d, '%s', ('%s', %d))" %
                          (info[0],info[1],info[2],info[3],info[4],info[5]))
        addr.free()
        return str(result)
    f1 = compile(does_stuff, [str, str])
    res = f1("localhost", "25")
    assert eval(res) == _socket.getaddrinfo("localhost", "25")

def test_newsocket_annotation():
    from pypy.module._socket.rpython import rsocket
    def does_stuff():
        return rsocket.newsocket(_socket.AF_INET, _socket.SOCK_STREAM, 0)
    t = Translator(does_stuff)
    a = t.annotate([])
    assert a.gettype(t.graphs[0].getreturnvar()) == int

def test_newsocket():
    from pypy.module._socket.rpython import rsocket
    def does_stuff():
        return rsocket.newsocket(_socket.AF_INET, _socket.SOCK_STREAM, 0)
    f1 = compile(does_stuff, [])
    res = f1()
    assert isinstance(res, (int, long))

def test_newsocket_error():
    from pypy.module._socket.rpython import rsocket
    tests = [
        (1001, _socket.SOCK_STREAM, 0),
        (_socket.AF_INET, 555555, 0),
    ]
    def does_stuff(family, type, protocol):
        return rsocket.newsocket(family, type, protocol)
    f1 = compile(does_stuff, [int, int, int])
    for args in tests:
        py.test.raises(OSError, f1, *args)

def test_connect():
    import os
    from pypy.module._socket.rpython import rsocket
    def does_stuff():
        fd = rsocket.newsocket(_socket.AF_INET, _socket.SOCK_STREAM, 0)
        # XXX need to think of a test without connecting to outside servers
        rsocket.connect(fd, "codespeak.net", 80)
        sockname = rsocket.getpeername(fd)
        os.close(fd)
        return sockname[1]
    f1 = compile(does_stuff, [])
    res = f1()
    assert res == 80
