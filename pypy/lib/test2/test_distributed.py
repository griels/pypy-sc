
""" Controllers tests
"""

from pypy.conftest import gettestobjspace

class AppTestNoProxy(object):
    disabled = True
    def test_init(self):
        raises(ImportError, "import distributed")

class AppTestDistributed(object):
    def setup_class(cls):
        cls.space = gettestobjspace(**{"objspace.std.withtproxy": True})

    def test_init(self):
        import distributed
        distributed.proxy

    def test_protocol(self):
        from distributed import AbstractProtocol
        protocol = AbstractProtocol()
        for item in ("aaa", 3, u"aa", 344444444444444444L, 1.2, (1, "aa")):
            assert protocol.unwrap(protocol.wrap(item)) == item
        assert type(protocol.unwrap(protocol.wrap([1,2,3]))) is list
        assert type(protocol.unwrap(protocol.wrap({"a":3}))) is dict
        
        def f():
            pass
        
        assert type(protocol.unwrap(protocol.wrap(f))) is type(f)

    def test_protocol_run(self):
        l = [1,2,3]
        from distributed import LocalProtocol
        protocol = LocalProtocol()
        wrap = protocol.wrap
        unwrap = protocol.unwrap
        item = unwrap(wrap(l))
        assert len(item) == 3
        assert item[2] == 3
        item += [1,1,1]
        assert len(item) == 6
