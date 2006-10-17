# Package initialisation
from pypy.interpreter.mixedmodule import MixedModule
import sys

class Module(MixedModule):
    applevel_name = '_socket'

    appleveldefs = {
        'error'      : 'app_socket.error',
        'herror'     : 'app_socket.herror',
        'gaierror'   : 'app_socket.gaierror',
        'timeout'    : 'app_socket.timeout',
    }

    interpleveldefs = {
        'SocketType':  'interp_socket.W_RSocket',
        'socket'    :  'interp_socket.W_RSocket',
    }

    def buildloaders(cls):
        from pypy.module.rsocket import ctypes_socket as _c 
        for name in """
            gethostbyname gethostbyname_ex gethostbyaddr gethostname
            getservbyname getservbyport getprotobyname
            fromfd socketpair
            ntohs ntohl htons htonl inet_aton inet_ntoa inet_pton inet_ntop
            getaddrinfo getnameinfo
            getdefaulttimeout setdefaulttimeout 
            """.split():
            
            Module.interpleveldefs[name] = 'interp_func.%s' % (name, )

        for constant, value in _c.constants.iteritems():
            Module.interpleveldefs[constant] = "space.wrap(%r)" % value
        super(Module, cls).buildloaders()
    buildloaders = classmethod(buildloaders)

#Module.interpleveldefs['has_ipv6'] = "space.wrap(%s)" % _socket.has_ipv6
