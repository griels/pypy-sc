# Package initialisation
from pypy.interpreter.mixedmodule import MixedModule
import sys

class Module(MixedModule):
    appleveldefs = {
        'error'      : 'app_socket.error',
        'herror'     : 'app_socket.herror',
        'gaierror'   : 'app_socket.gaierror',
        'timeout'    : 'app_socket.timeout',
        'gethostbyname': 'app_socket.gethostbyname',
    }

    interpleveldefs = {
        'SocketType':  'interp_socket.Socket',
        'socket'    :  'interp_socket.Socket',
    }

    def buildloaders(cls):
        from pypy.rpython.rctypes.socketmodule import ctypes_socket as _c 
        for name in """
            gethostbyname_ex gethostbyaddr gethostname
            getservbyname getservbyport getprotobyname
            fromfd socketpair
            ntohs ntohl htons htonl inet_aton inet_ntoa inet_pton inet_ntop
            getaddrinfo getnameinfo
            getdefaulttimeout setdefaulttimeout 
            """.split():
            
            Module.interpleveldefs[name] = 'interp_socket.%s' % (name, )

        for constant, value in _c.constants.iteritems():
            Module.interpleveldefs[constant] = "space.wrap(%r)" % value
        super(Module, cls).buildloaders()
    buildloaders = classmethod(buildloaders)

#Module.interpleveldefs['has_ipv6'] = "space.wrap(%s)" % _socket.has_ipv6
