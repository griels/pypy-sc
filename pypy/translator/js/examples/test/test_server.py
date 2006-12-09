
""" Server testing
"""

from pypy.translator.js.examples import server
from urllib import URLopener

class Handler(server.TestHandler):
    def index(self):
        return "xxx"
    index.exposed = True

def test_basic_startup():
    import thread
    # XXX: how to do this without threads?
    httpd = server.HTTPServer(('127.0.0.1', 21210), Handler)
    thread.start_new_thread(httpd.serve_forever, ())
    assert URLopener().open("http://127.0.0.1:21210/index").read() == "xxx"

