from pypy.objspace.std import StdObjSpace 
from pypy.tool.udir import udir
import py
import socket, sys

def setup_module(mod): 
    mod.space = StdObjSpace(usemodules=['_socket'])
    mod.w_socket = space.appexec([], "(): import _socket as m; return m")
    
def test_gethostname():
    host = space.appexec([w_socket], "(_socket): return _socket.gethostname()")
    assert space.unwrap(host) == socket.gethostname()

def test_gethostbyname():
    host = "localhost"
    ip = space.appexec([w_socket, space.wrap(host)],
                       "(_socket, host): return _socket.gethostbyname(host)")
    assert space.unwrap(ip) == socket.gethostbyname(host)

def test_gethostbyname_ex():
    host = "localhost"
    ip = space.appexec([w_socket, space.wrap(host)],
                       "(_socket, host): return _socket.gethostbyname_ex(host)")
    assert isinstance(space.unwrap(ip), tuple)
    assert space.unwrap(ip) == socket.gethostbyname_ex(host)

def test_gethostbyaddr():
    host = "localhost"
    ip = space.appexec([w_socket, space.wrap(host)],
                       "(_socket, host): return _socket.gethostbyaddr(host)")
    assert space.unwrap(ip) == socket.gethostbyaddr(host)
    host = "127.0.0.1"
    ip = space.appexec([w_socket, space.wrap(host)],
                       "(_socket, host): return _socket.gethostbyaddr(host)")
    assert space.unwrap(ip) == socket.gethostbyaddr(host)

def test_getservbyname():
    name = "smtp"
    # 2 args version
    port = space.appexec([w_socket, space.wrap(name)],
                        "(_socket, name): return _socket.getservbyname(name, 'tcp')")
    assert space.unwrap(port) == 25
    # 1 arg version
    if sys.version_info < (2, 4):
        py.test.skip("getservbyname second argument is not optional before python 2.4")
    port = space.appexec([w_socket, space.wrap(name)],
                        "(_socket, name): return _socket.getservbyname(name)")
    assert space.unwrap(port) == 25

def test_getservbyport():
    if sys.version_info < (2, 4):
        py.test.skip("getservbyport does not exist before python 2.4")
    port = 25
    # 2 args version
    name = space.appexec([w_socket, space.wrap(port)],
                         "(_socket, port): return _socket.getservbyport(port, 'tcp')")
    assert space.unwrap(name) == "smtp"
    name = space.appexec([w_socket, space.wrap(port)],
                         """(_socket, port):
                         try:
                             return _socket.getservbyport(port, 42)
                         except TypeError:
                             return 'OK'
                         """)
    assert space.unwrap(name) == 'OK' 
    # 1 arg version
    name = space.appexec([w_socket, space.wrap(port)],
                         "(_socket, port): return _socket.getservbyport(port)")
    assert space.unwrap(name) == "smtp"

def test_getprotobyname():
    name = "tcp"
    num = space.appexec([w_socket, space.wrap(name)],
                        "(_socket, name): return _socket.getprotobyname(name)")
    assert space.unwrap(num) == socket.IPPROTO_TCP
    

def test_has_ipv6():
    res = space.appexec([w_socket], "(_socket): return _socket.has_ipv6")
    assert space.unwrap(res) == socket.has_ipv6

