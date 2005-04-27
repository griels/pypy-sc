

class AppTest_Descroperation:

    def test_getslice(self):
        class Sq(object):
            def __getslice__(self, start, stop):
                return (start, stop)
            def __getitem__(self, key):
                return "booh"
            def __len__(self):
                return 100

        sq = Sq()

        assert sq[1:3] == (1,3)
        import sys
        assert sq[1:] == (1, sys.maxint)
        assert sq[:3] == (0, 3)
        assert sq[:] == (0, sys.maxint)
        # negative indices
        assert sq[-1:3] == (99, 3)
        assert sq[1:-3] == (1, 97)
        assert sq[-1:-3] == (99, 97)

    def test_setslice(self):
        class Sq(object):
            def __setslice__(self, start, stop, sequence):
                ops.append((start, stop, sequence))
            def __setitem__(self, key, value):
                raise AssertionError, key
            def __len__(self):
                return 100

        sq = Sq()
        ops = []
        sq[-5:3] = 'hello'
        sq[12:] = 'world'
        sq[:-1] = 'spam'
        sq[:] = 'egg'

        import sys
        assert ops == [
            (95, 3,          'hello'),
            (12, sys.maxint, 'world'),
            (0,  99,         'spam'),
            (0,  sys.maxint, 'egg'),
            ]

    def test_delslice(self):
        class Sq(object):
            def __delslice__(self, start, stop):
                ops.append((start, stop))
            def __delitem__(self, key):
                raise AssertionError, key
            def __len__(self):
                return 100

        sq = Sq()
        ops = []
        del sq[5:-3]
        del sq[-12:]
        del sq[:1]
        del sq[:]

        import sys
        assert ops == [
            (5,   97),
            (88,  sys.maxint),
            (0,   1),
            (0,   sys.maxint),
            ]

    def test_ipow(self):
        x = 2
        x **= 5
        assert x == 32
