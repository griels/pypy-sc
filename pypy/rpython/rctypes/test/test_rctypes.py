import py.test

def setup_module(mod):
    try:
        import ctypes
    except ImportError:
        py.test.skip("this test needs ctypes installed")
    else:
        import sys
        from pypy.rpython.rctypes.interface import cdll, c_char_p, c_int
        if sys.platform == 'win32':
            mylib = cdll.LoadLibrary('msvcrt.dll')
        elif sys.platform == 'linux2':
            mylib = cdll.LoadLibrary('libc.so.6')
        else:
            py.test.skip("don't know how to load the c lib for %s" % 
                    sys.platform)

        atoi = mylib.atoi
        atoi.restype = c_int
        atoi.argstype = [c_char_p]
        def o_atoi(a):
           return atoi(a)
        mod.o_atoi = o_atoi


class Test_rctypes:

    from pypy.annotation.annrpython import RPythonAnnotator
    
    def test_simple(self):


        res = o_atoi('42')   
        assert res == 42 

    def inprogress_test_annotate_simple(self):
        a = self.RPythonAnnotator()
        s = a.build_types(o_atoi, [str])
        # result should be an integer
        assert s.knowntype == int
