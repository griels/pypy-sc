import autopath
from pypy.objspace.flow.model import Constant, Block, Link, Variable, traverse
from pypy.objspace.flow.model import flatten
from pypy.interpreter.argument import Arguments
from pypy.translator.simplify import simplify_graph
from pypy.objspace.flow import FlowObjSpace 
from pypy.objspace.flow import objspace

import os
import operator
is_operator = getattr(operator, 'is_', operator.eq) # it's not there 2.2

class TestFlowObjSpace:
    def setup_class(cls): 
        cls.space = FlowObjSpace() 

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

    def all_operations(self, graph):
        result = {}
        def visit(node):
            if isinstance(node, Block):
                for op in node.operations:
                    result.setdefault(op.opname, 0)
                    result[op.opname] += 1
        traverse(visit, graph)
        return result

    #__________________________________________________________
    def nothing():
        pass

    def test_nothing(self):
        x = self.codetest(self.nothing)
        assert len(x.startblock.exits) == 1
        link, = x.startblock.exits
        assert link.target == x.returnblock
        self.show(x)

    #__________________________________________________________
    def simplefunc(x):
        return x+1

    def test_simplefunc(self):
        graph = self.codetest(self.simplefunc)
        assert self.all_operations(graph) == {'add': 1}

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
    def loop(x):
        x = abs(x)
        while x:
            x = x - 1

    def test_loop(self):
        graph = self.codetest(self.loop)
        assert self.all_operations(graph) == {'abs': 1,
                                              'is_true': 1,
                                              'sub': 1}

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
    def const_pow():
        return 2 ** 5

    def test_const_pow(self):
        x = self.codetest(self.const_pow)
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
        simplify_graph(x)
        self.show(x)
        def cannot_reach_exceptblock(link):
            if isinstance(link, Link):
                assert link.target is not x.exceptblock
        traverse(cannot_reach_exceptblock, x)

    #__________________________________________________________
    def implicitException_int_and_id(x):
        try:
            return int(x) + id(x)
        except TypeError:   # not captured by the flow graph!
            return 0

    def test_implicitException_int_and_id(self):
        x = self.codetest(self.implicitException_int_and_id)
        simplify_graph(x)
        self.show(x)
        assert len(x.startblock.exits) == 1
        assert x.startblock.exits[0].target is x.returnblock

    #__________________________________________________________
    def implicitException_os_stat(x):
        try:
            return os.stat(x)
        except OSError:   # *captured* by the flow graph!
            return 0

    def test_implicitException_os_stat(self):
        x = self.codetest(self.implicitException_os_stat)
        simplify_graph(x)
        self.show(x)
        assert len(x.startblock.exits) == 3
        d = {}
        for link in x.startblock.exits:
            d[link.exitcase] = True
        assert d == {None: True, OSError: True, Exception: True}

    #__________________________________________________________
    def reraiseKeyError(dic):
        try:
            x = dic[5]
        except KeyError:
            raise

    def test_reraiseKeyError(self):
        x = self.codetest(self.reraiseKeyError)
        simplify_graph(x)
        self.show(x)
        found_KeyError = []
        def only_raise_KeyError(link):
            if isinstance(link, Link):
                if link.target is x.exceptblock:
                    assert link.args[0] == Constant(KeyError)
                    found_KeyError.append(link)
        traverse(only_raise_KeyError, x)
        assert found_KeyError

    #__________________________________________________________
    def reraiseAnything(dic):
        try:
            dic[5]
        except:
            raise

    def test_reraiseAnything(self):
        x = self.codetest(self.reraiseAnything)
        simplify_graph(x)
        self.show(x)
        found = {}
        def find_exceptions(link):
            if isinstance(link, Link):
                if link.target is x.exceptblock:
                    assert isinstance(link.args[0], Constant)
                    found[link.args[0].value] = True
        traverse(find_exceptions, x)
        assert found == {KeyError: True, IndexError: True}

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
        simplify_graph(x)
        ops = x.startblock.operations
        assert len(ops) == 2
        assert ops[0].opname == 'simple_call'
        assert ops[0].args == [Constant(IndexError)]
        assert ops[1].opname == 'type'
        assert ops[1].args == [ops[0].result]
        assert x.startblock.exits[0].args == [ops[1].result, ops[0].result]
        assert x.startblock.exits[0].target is x.exceptblock

    #__________________________________________________________
    def raise2(msg):
        raise IndexError, msg
    
    def test_raise2(self):
        x = self.codetest(self.raise2)
        self.show(x)
        # XXX can't check the shape of the graph, too complicated...

    #__________________________________________________________
    def raise3(msg):
        raise IndexError(msg)
    
    def test_raise3(self):
        x = self.codetest(self.raise3)
        self.show(x)
        # XXX can't check the shape of the graph, too complicated...

    #__________________________________________________________
    def raise4(stuff):
        raise stuff
    
    def test_raise4(self):
        x = self.codetest(self.raise4)
        self.show(x)

    #__________________________________________________________
    def raisez(z, tb):
        raise z.__class__,z, tb

    def test_raisez(self):
        x = self.codetest(self.raisez)
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
    
    def specialcases(x):
        operator.lt(x,3)
        operator.le(x,3)
        operator.eq(x,3)
        operator.ne(x,3)
        operator.gt(x,3)
        operator.ge(x,3)
        is_operator(x,3)
        operator.__lt__(x,3)
        operator.__le__(x,3)
        operator.__eq__(x,3)
        operator.__ne__(x,3)
        operator.__gt__(x,3)
        operator.__ge__(x,3)
        # the following ones are constant-folded
        operator.eq(2,3)
        operator.__gt__(2,3)
    
    def test_specialcases(self):
        x = self.codetest(self.specialcases)
        from pypy.translator.simplify import join_blocks
        join_blocks(x)
        assert len(x.startblock.operations) == 13
        for op in x.startblock.operations:
            assert op.opname in ['lt', 'le', 'eq', 'ne',
                                       'gt', 'ge', 'is_']
            assert len(op.args) == 2
            assert op.args[1].value == 3

    #__________________________________________________________
    def jump_target_specialization(x):
        if x:
            n = 5
        else:
            n = 6
        return n*2

    def test_jump_target_specialization(self):
        x = self.codetest(self.jump_target_specialization)
        self.show(x)
        def visitor(node):
            if isinstance(node, Block):
                for op in node.operations:
                    assert op.opname != 'mul', "mul should have disappeared"
        traverse(visitor, x)

    #__________________________________________________________
    def highly_branching_example(a,b,c,d,e,f,g,h,i,j):
        if a:
            x1 = 1
        else:
            x1 = 2
        if b:
            x2 = 1
        else:
            x2 = 2
        if c:
            x3 = 1
        else:
            x3 = 2
        if d:
            x4 = 1
        else:
            x4 = 2
        if e:
            x5 = 1
        else:
            x5 = 2
        if f:
            x6 = 1
        else:
            x6 = 2
        if g:
            x7 = 1
        else:
            x7 = 2
        if h:
            x8 = 1
        else:
            x8 = 2
        if i:
            x9 = 1
        else:
            x9 = 2
        if j:
            x10 = 1
        else:
            x10 = 2
        return (x1, x2, x3, x4, x5, x6, x7, x8, x9, x10)

    def test_highly_branching_example(self):
        x = self.codetest(self.highly_branching_example)
        self.show(x)
        assert len(flatten(x)) < 60   # roughly 20 blocks + 30 links

    #__________________________________________________________
    def test_unfrozen_user_class1(self):
        class C:
            def __nonzero__(self):
                return True
        c = C()
        def f():
            if c:
                return 1
            else:
                return 2
        graph = self.codetest(f)

        results = []
        def visit(link):
            if isinstance(link, Link):
                if link.target == graph.returnblock:
                    results.extend(link.args)
        traverse(visit, graph)
        assert len(results) == 2

    def test_unfrozen_user_class2(self):
        class C:
            def __add__(self, other):
                return 4
        c = C()
        d = C()
        def f():
            return c+d
        graph = self.codetest(f)

        results = []
        def visit(link):
            if isinstance(link, Link):
                if link.target == graph.returnblock:
                    results.extend(link.args)
        traverse(visit, graph)
        assert not isinstance(results[0], Constant)

    def test_frozen_user_class1(self):
        class C:
            def __nonzero__(self):
                return True
            def _freeze_(self):
                return True
        c = C()
        def f():
            if c:
                return 1
            else:
                return 2

        graph = self.codetest(f)

        results = []
        def visit(link):
            if isinstance(link, Link):
                if link.target == graph.returnblock:
                    results.extend(link.args)
        traverse(visit, graph)
        assert len(results) == 1

    def test_frozen_user_class2(self):
        class C:
            def __add__(self, other):
                return 4
            def _freeze_(self):
                return True
        c = C()
        d = C()
        def f():
            return c+d
        graph = self.codetest(f)

        results = []
        def visit(link):
            if isinstance(link, Link):
                if link.target == graph.returnblock:
                    results.extend(link.args)
        traverse(visit, graph)
        assert results == [Constant(4)]

    def test_const_star_call(self):
        def g(a=1,b=2,c=3):
            pass
        def f():
            return g(1,*(2,3))
        graph = self.codetest(f)
        call_args = []
        def visit(block):
            if isinstance(block, Block):
                for op in block.operations:
                    if op.opname == "call_args":
                        call_args.append(op)
        traverse(visit, graph)
        assert not call_args
        


DATA = {'x': 5,
        'y': 6}

def user_defined_function():
    pass


def test_extract_cell_content():
    class Strange(object):
        def __cmp__(self, other):
            assert False, "should not be called"
    strange = Strange()
    def f():
        return strange
    res = objspace.extract_cell_content(f.func_closure[0])
    assert res is strange
