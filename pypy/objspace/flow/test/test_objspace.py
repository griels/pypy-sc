import autopath
from pypy.tool import testit
from pypy.objspace.flow.model import Constant


class TestFlowObjSpace(testit.TestCase):
    def setUp(self):
        self.space = testit.objspace('flow')

    def codetest(self, func):
        import inspect
        try:
            func = func.im_func
        except AttributeError:
            pass
        #name = func.func_name
        graph = self.space.build_flow(func)
        graph.source = inspect.getsource(func)
        return graph

    def reallyshow(self, x):
        x.show()
        #import os
        #from pypy.translator.tool.make_dot import make_dot
        #dest = make_dot(x.name, x)
        #os.system('gv %s' % str(dest))

    def show(self, x):
        pass   # or   self.reallyshow(x)

    #__________________________________________________________
    def nothing():
        pass

    def test_nothing(self):
        x = self.codetest(self.nothing)
        self.assertEquals(len(x.startblock.exits), 1)
        link, = x.startblock.exits
        self.assertEquals(link.target, x.returnblock)
        self.show(x)

    #__________________________________________________________
    def simplebranch(i, j):
        if i < 0:
            return i
        return j

    def test_simplebranch(self):
        x = self.codetest(self.simplebranch)
        self.show(x)

    #__________________________________________________________
    def ifthenelse(i, j):
        if i < 0:
            i = j
        return g(i) + 1
    
    def test_ifthenelse(self):
        x = self.codetest(self.simplebranch)
        self.show(x)

    #__________________________________________________________
    def print_(i):
        print i
    
    def test_print(self):
        x = self.codetest(self.print_)
        self.show(x)

    #__________________________________________________________
    def while_(i):
        while i > 0:
            i = i - 1

    def test_while(self):
        x = self.codetest(self.while_)
        self.show(x)

    #__________________________________________________________
    def union_easy(i):
        if i:
            pass
        else:
            i = 5
        return i

    def test_union_easy(self):
        x = self.codetest(self.union_easy)
        self.show(x)

    #__________________________________________________________
    def union_hard(i):
        if i:
            i = 5
        return i
    
    def test_union_hard(self):
        x = self.codetest(self.union_hard)
        self.show(x)

    #__________________________________________________________
    def while_union(i):
        total = 0
        while i > 0:
            total += i
            i = i - 1
        return total
    
    def test_while_union(self):
        x = self.codetest(self.while_union)
        self.show(x)

    #__________________________________________________________
    def simple_for(lst):
        total = 0
        for i in lst:
            total += i
        return total
    
    def test_simple_for(self):
        x = self.codetest(self.simple_for)
        self.show(x)

    #__________________________________________________________
    def nested_whiles(i, j):
        s = ''
        z = 5
        while z > 0:
            z = z - 1
            u = i
            while u < j:
                u = u + 1
                s = s + '.'
            s = s + '!'
        return s

    def test_nested_whiles(self):
        x = self.codetest(self.nested_whiles)
        self.show(x)

    #__________________________________________________________
    def break_continue(x):
        result = []
        i = 0
        while 1:
            i = i + 1
            try:
                if i&1:
                    continue
                if i >= x:
                    break
            finally:
                result.append(i)
            i = i + 1
        return result

    def test_break_continue(self):
        x = self.codetest(self.break_continue)
        self.show(x)

    #__________________________________________________________
    def unpack_tuple(lst):
        a, b, c = lst

    def test_unpack_tuple(self):
        x = self.codetest(self.unpack_tuple)
        self.show(x)

    #__________________________________________________________
    def reverse_3(lst):
        try:
            a, b, c = lst
        except:
            return 0, 0, 0
        else:
            return c, b, a

    def test_reverse_3(self):
        x = self.codetest(self.reverse_3)
        self.show(x)

    #__________________________________________________________
    def finallys(lst):
        x = 1
        try:
            x = 2
            try:
                x = 3
                a, = lst
                x = 4
            except KeyError:
                return 5
            except ValueError:
                return 6
            b, = lst
            x = 7
        finally:
            x = 8
        return x

    def test_finallys(self):
        x = self.codetest(self.finallys)
        self.show(x)

    #__________________________________________________________
    def implicitIndexError(lst):
        try:
            x = lst[5]
        except IndexError:
            return 'catch'
        return lst[3]   # not caught

    def test_implicitIndexError(self):
        x = self.codetest(self.implicitIndexError)
        self.show(x)

    #__________________________________________________________
    def freevar(self, x):
        def adder(y):
            return x+y
        return adder

    def test_freevar(self):
        x = self.codetest(self.freevar(3))
        self.show(x)

    #__________________________________________________________
    def raise1(msg):
        raise IndexError
    
    def test_raise1(self):
        x = self.codetest(self.raise1)
        self.show(x)
        assert len(x.startblock.operations) == 0
        assert x.startblock.exits[0].args == [
            Constant(IndexError),
            Constant(None)]         # no normalization
        assert x.startblock.exits[0].target is x.exceptblock

    #__________________________________________________________
    def raise2(msg):
        raise IndexError, msg
    
    def test_raise2(self):
        x = self.codetest(self.raise2)
        self.show(x)
        assert len(x.startblock.operations) == 0
        assert x.startblock.exits[0].args == [
            Constant(IndexError),
            x.startblock.inputargs[0]]
        assert x.startblock.exits[0].target is x.exceptblock

    #__________________________________________________________
    def raise3(msg):
        raise IndexError(msg)
    
    def test_raise3(self):
        x = self.codetest(self.raise3)
        self.show(x)
        assert len(x.startblock.operations) == 1
        assert x.startblock.operations[0].opname == 'simple_call'
        assert list(x.startblock.operations[0].args) == [
            Constant(IndexError),
            x.startblock.inputargs[0]]
        assert x.startblock.exits[0].args == [
            Constant(IndexError),
            x.startblock.operations[0].result]
        assert x.startblock.exits[0].target is x.exceptblock

    #__________________________________________________________
    def raise4(stuff):
        raise stuff
    
    def test_raise4(self):
        x = self.codetest(self.raise4)
        self.show(x)

    #__________________________________________________________
    def raise_and_catch_1(exception_instance):
        try:
            raise exception_instance
        except IndexError:
            return -1
        return 0
    
    def test_raise_and_catch_1(self):
        x = self.codetest(self.raise_and_catch_1)
        self.show(x)

    #__________________________________________________________
    def catch_simple_call():
        try:
            user_defined_function()
        except IndexError:
            return -1
        return 0
    
    def test_catch_simple_call(self):
        x = self.codetest(self.catch_simple_call)
        self.show(x)

    #__________________________________________________________
    def dellocal():
        x = 1
        del x
        for i in range(10):
            pass
    
    def test_dellocal(self):
        x = self.codetest(self.dellocal)
        self.show(x)

    #__________________________________________________________
    def globalconstdict(name):
        x = DATA['x']
        z = DATA[name]
        return x, z
    
    def test_globalconstdict(self):
        x = self.codetest(self.globalconstdict)
        self.show(x)

    #__________________________________________________________
    def specialcases():
        import operator
        operator.lt(2,3)
        operator.le(2,3)
        operator.eq(2,3)
        operator.ne(2,3)
        operator.gt(2,3)
        operator.ge(2,3)
        operator.is_(2,3)
        operator.__lt__(2,3)
        operator.__le__(2,3)
        operator.__eq__(2,3)
        operator.__ne__(2,3)
        operator.__gt__(2,3)
        operator.__ge__(2,3)
    
    def test_specialcases(self):
        x = self.codetest(self.specialcases)
        self.assertEquals(len(x.startblock.operations), 13)
        for op in x.startblock.operations:
            self.assert_(op.opname in ['lt', 'le', 'eq', 'ne',
                                       'gt', 'ge', 'is_'])
            self.assertEquals(len(op.args), 2)
            self.assertEquals(op.args[0].value, 2)
            self.assertEquals(op.args[1].value, 3)

DATA = {'x': 5,
        'y': 6}

def user_defined_function():
    pass

if __name__ == '__main__':
    testit.main()
