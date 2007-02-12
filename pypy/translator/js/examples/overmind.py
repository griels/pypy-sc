#!/usr/bin/env python
""" This is script which collects all the demos and
run them when needed
"""

from pypy.translator.js.lib import server
from pypy.translator.js.lib.support import callback
from pypy.rpython.extfunc import _callable
from pypy.rpython.ootypesystem.bltregistry import described
from pypy.translator.js.main import rpython2javascript

import os
import py

FUNCTION_LIST = ['launch_console']
tempdir = py.test.ensuretemp("infos")
TIMEOUT = 100

def launch_console_in_new_process():
    from pypy.translator.js.examples import pythonconsole
    httpd = server.start_server(server_address=('', 0),
                        handler=pythonconsole.RequestHandler, timeout=TIMEOUT,
                        port_file=tempdir.join("console_pid"),
                        fork=True, server=pythonconsole.Server)
    pythonconsole.httpd = httpd
    port = int(tempdir.join("console_pid").read())
    return port

class ExportedMethods(server.ExportedMethods):
    @callback(retval=int)
    def launch_console(self):
        """ Note that we rely here on threads not being invoked,
        if we want to make this multiplayer, we need additional locking
        XXX
        """
        return launch_console_in_new_process()
    
exported_methods = ExportedMethods()

def js_source(function_list):
    import over_client
    return rpython2javascript(over_client, FUNCTION_LIST)

class Handler(server.Handler):
    static_dir = str(py.path.local(__file__).dirpath().join("data"))
    index = server.Static()
    exported_methods = exported_methods

    def source_js(self):
        if hasattr(self.server, 'source'):
            source = self.server.source
        else:
            source = js_source(FUNCTION_LIST)
            self.server.source = source
        return "text/javascript", source
    source_js.exposed = True

if __name__ == '__main__':
    server.start_server(handler=Handler)
