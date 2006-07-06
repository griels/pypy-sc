""" blttest - some tests of builtin stuff
"""

import py

from pypy.rpython.ootypesystem.bltregistry import BasicExternal
from pypy.translator.js.test.runtest import compile_function

def check_source_contains(compiled_function, pattern):
    import re
    
    source = compiled_function.js.tmpfile.open().read()
    return re.search(pattern, source)

# check rendering _dom.get_document()
def test_simple_builtin():
    from pypy.translator.js.modules._dom import get_document
    def test_document_call():
        return get_document().getElementById("some_id")
    
    fn = compile_function(test_document_call, [])
    assert check_source_contains(fn, "= document")
    assert check_source_contains(fn, ".getElementById")

# check rendering transparent proxy
#def test_simple_proxy():
    
