from pypy.jit.hintannotator.annotator import HintAnnotatorPolicy
from pypy.jit.timeshifter.test.test_portal import PortalTest, P_OOPSPEC
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython.lltypesystem.rvirtualizable import VABLERTIPTR
from pypy.rlib.objectmodel import hint
import py

S = lltype.GcStruct('s', ('a', lltype.Signed), ('b', lltype.Signed))
PS = lltype.Ptr(S)

XY = lltype.GcForwardReference()
GETTER = lambda STRUC: lltype.Ptr(lltype.FuncType([lltype.Ptr(STRUC)],
                                                  lltype.Signed))
SETTER = lambda STRUC: lltype.Ptr(lltype.FuncType([lltype.Ptr(STRUC),
                                                  lltype.Signed],
                                                 lltype.Void))

def getset(name):
    def get(obj):
        access = obj.vable_access
        if access:
            return getattr(access, 'get_'+name)(obj)
        else:
            return getattr(obj, name)
    get.oopspec = 'vable.get_%s(obj)' % name
    def set(obj, value):
        access = obj.vable_access
        if access:
            return getattr(access, 'set_'+name)(obj, value)
        else:
            return setattr(obj, name, value)
    set.oopspec = 'vable.set_%s(obj, value)' % name
    return get, set

XP = lltype.GcForwardReference()
PGETTER = lambda XP: lltype.Ptr(lltype.FuncType([lltype.Ptr(XP)], PS))
PSETTER = lambda XP: lltype.Ptr(lltype.FuncType([lltype.Ptr(XP), PS],
                                   lltype.Void))

XY_ACCESS = lltype.Struct('xy_access',
                          ('get_x', GETTER(XY)),
                          ('set_x', SETTER(XY)),
                          ('get_y', GETTER(XY)),
                          ('set_y', SETTER(XY)),
                          hints = {'immutable': True},
                          adtmeths = {'redirected_fields': ('x', 'y')}
                          )


XP_ACCESS = lltype.Struct('xp_access',
                          ('get_x', GETTER(XP)),
                          ('set_x', SETTER(XP)),
                          ('get_p', PGETTER(XP)),
                          ('set_p', PSETTER(XP)),
                          hints = {'immutable': True},
                          adtmeths = {'redirected_fields': ('x', 'p')}
                          )

XY.become(lltype.GcStruct('xy',
                          ('vable_base', llmemory.Address),
                          ('vable_rti', VABLERTIPTR),
                          ('vable_access', lltype.Ptr(XY_ACCESS)),
                          ('x', lltype.Signed),
                          ('y', lltype.Signed),
                          hints = {'virtualizable': True},
                          adtmeths = {'ACCESS': XY_ACCESS},
              ))

E = lltype.GcStruct('e', ('xy', lltype.Ptr(XY)),
                         ('w',  lltype.Signed))
xy_get_x, xy_set_x = getset('x')
xy_get_y, xy_set_y = getset('y')


XP.become(lltype.GcStruct('xp',
                          ('vable_base', llmemory.Address),
                          ('vable_rti', VABLERTIPTR),                     
                          ('vable_access', lltype.Ptr(XP_ACCESS)),
                          ('x', lltype.Signed),
                          ('p', PS),
                          hints = {'virtualizable': True},
                          adtmeths = {'ACCESS': XP_ACCESS},
              ))
xp_get_x, xp_set_x = getset('x')
xp_get_p, xp_set_p = getset('p')

E2 = lltype.GcStruct('e', ('xp', lltype.Ptr(XP)),
                         ('w',  lltype.Signed))

PQ = lltype.GcForwardReference()
PQ_ACCESS = lltype.Struct('pq_access',
                          ('get_p', PGETTER(PQ)),
                          ('set_p', PSETTER(PQ)),
                          ('get_q', PGETTER(PQ)),
                          ('set_q', PSETTER(PQ)),
                          hints = {'immutable': True},
                          adtmeths = {'redirected_fields': ('p', 'q')}
                          )

PQ.become(lltype.GcStruct('pq',
                          ('vable_base', llmemory.Address),
                          ('vable_rti', VABLERTIPTR),                     
                          ('vable_access', lltype.Ptr(PQ_ACCESS)),
                          ('p', PS),
                          ('q', PS),
                          hints = {'virtualizable': True},
                          adtmeths = {'ACCESS': PQ_ACCESS},
              ))
pq_get_p, pq_set_p = getset('p')
pq_get_q, pq_set_q = getset('q')

E3 = lltype.GcStruct('e', ('pq', lltype.Ptr(PQ)),
                         ('w',  lltype.Signed))



class StopAtXPolicy(HintAnnotatorPolicy):
    def __init__(self, *funcs):
        HintAnnotatorPolicy.__init__(self, novirtualcontainer=True,
                                     oopspec=True)
        self.funcs = funcs

    def look_inside_graph(self, graph):
        try:
            if graph.func in self.funcs:
                return False
        except AttributeError:
            pass
        return True


class TestVirtualizableExplicit(PortalTest):

    def test_simple(self):
   
        def f(xy):
            x = xy_get_x(xy)
            y = xy_get_y(xy)
            return x+y

        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            return f(xy)

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0)
        residual_graph = self.get_residual_graph()
        assert len(residual_graph.startblock.inputargs) == 3
        assert ([v.concretetype for v in residual_graph.startblock.inputargs] ==
                [lltype.Ptr(XY), lltype.Signed, lltype.Signed])

    def test_simple_set(self):
   
        def f(xy):
            x = xy_get_x(xy)
            xy_set_y(xy, 1)
            y = xy_get_y(xy)
            return x+y

        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            return f(xy)

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 21
        self.check_insns(getfield=0)
        residual_graph = self.get_residual_graph()
        assert len(residual_graph.startblock.inputargs) == 3
        assert ([v.concretetype for v in residual_graph.startblock.inputargs] ==
                [lltype.Ptr(XY), lltype.Signed, lltype.Signed])

    def test_set_effect(self):

        def f(xy):
           x = xy_get_x(xy)
           xy_set_y(xy, 3)
           y = xy_get_y(xy)
           return x+y

        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            v = f(xy)
            return v + xy.y

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 26
        self.check_insns(getfield=0)
        residual_graph = self.get_residual_graph()
        assert len(residual_graph.startblock.inputargs) == 3
        assert ([v.concretetype for v in residual_graph.startblock.inputargs] ==
                [lltype.Ptr(XY), lltype.Signed, lltype.Signed])

    def test_simple_escape(self):
   
        def f(e, xy):
            xy_set_y(xy, 3)
            e.xy = xy
            return 0

        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            e = lltype.malloc(E)
            f(e, xy)
            return e.xy.x+e.xy.y

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 23
        self.check_insns(getfield=0)
        residual_graph = self.get_residual_graph()
        assert len(residual_graph.startblock.inputargs) == 4
        assert ([v.concretetype for v in residual_graph.startblock.inputargs] ==
                [lltype.Ptr(E), lltype.Ptr(XY), lltype.Signed, lltype.Signed])

    def test_simple_return_it(self):
        def f(which, xy1, xy2):
            xy_set_y(xy1, 3)
            xy_set_y(xy2, 7)
            if which == 1:
                return xy1
            else:
                return xy2

        def main(which, x, y):
            xy1 = lltype.malloc(XY)
            xy1.vable_access = lltype.nullptr(XY_ACCESS)
            xy2 = lltype.malloc(XY)
            xy2.vable_access = lltype.nullptr(XY_ACCESS)
            xy1.x = x
            xy1.y = y
            xy2.x = y
            xy2.y = x
            xy = f(which, xy1, xy2)
            assert xy is xy1 or xy is xy2
            return xy.x+xy.y

        res = self.timeshift_from_portal(main, f, [1, 20, 22],
                                         policy=P_OOPSPEC)
        assert res == 23
        self.check_insns(getfield=0)

    def test_simple_construct_no_escape(self):
   
        def f(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            x = xy_get_x(xy)
            y = xy_get_y(xy)
            return x+y

        def main(x, y):
            return f(x, y)

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0)

    def test_simple_construct_escape(self):
   
        def f(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            x = xy_get_x(xy)
            y = xy_get_y(xy)            
            return xy

        def main(x, y):
            xy = f(x, y)
            return xy.x+xy.y

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0)

    def test_simple_with_struct(self):
   
        def f(xp):
            x = xp_get_x(xp)
            p = xp_get_p(xp)
            return x+p.a+p.b

        def main(x, a, b):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            s = lltype.malloc(S)
            s.a = a
            s.b = b
            xp.p = s
            return f(xp)

        res = self.timeshift_from_portal(main, f, [20, 10, 12],
                                         policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=2)    

    def test_simple_with_setting_struct(self):
   
        def f(xp, s):
            xp_set_p(xp, s)
            x = xp_get_x(xp)
            p = xp_get_p(xp)
            p.b = p.b*2
            return x+p.a+p.b

        def main(x, a, b):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            s = lltype.malloc(S)
            s.a = a
            s.b = b
            v = f(xp, s)
            return v+xp.p.b

        res = self.timeshift_from_portal(main, f, [20, 10, 3],
                                         policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=3)

    def test_simple_with_setting_new_struct(self):
   
        def f(xp, a, b):
            s = lltype.malloc(S)
            s.a = a
            s.b = b
            xp_set_p(xp, s)            
            p = xp_get_p(xp)
            p.b = p.b*2
            x = xp_get_x(xp)
            return x+p.a+p.b

        def main(x, a, b):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            v = f(xp, a, b)
            return v+xp.p.b

        res = self.timeshift_from_portal(main, f, [20, 10, 3],
                                         policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0, malloc=1)


    def test_simple_constr_with_setting_new_struct(self):
   
        def f(x, a, b):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            s = lltype.malloc(S)
            s.a = a
            s.b = b            
            xp_set_p(xp, s)            
            p = xp_get_p(xp)
            p.b = p.b*2
            x = xp_get_x(xp)
            return xp

        def main(x, a, b):
            xp = f(x, a, b)
            return xp.x+xp.p.a+xp.p.b+xp.p.b

        res = self.timeshift_from_portal(main, f, [20, 10, 3],
                                         policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0, malloc=2)

    def test_simple_read(self):
   
        def f(e):
            xy = e.xy
            xy_set_y(xy, 3)
            return xy_get_x(xy)*2

        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            e = lltype.malloc(E)
            e.xy = xy
            v = f(e)
            return v + e.xy.x+e.xy.y

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 63
        self.check_insns(getfield=3)

    def test_simple_escape_through_vstruct(self):
   
        def f(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            e = lltype.malloc(E)
            e.xy = xy
            y = xy_get_y(xy)
            newy = 2*y
            xy_set_y(xy, newy)
            return e

        def main(x, y):
            e = f(x, y)
            return e.xy.x+e.xy.y

        res = self.timeshift_from_portal(main, f, [20, 11], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0, malloc=2)

    def test_late_residual_red_call(self):
        def g(e):
            xy = e.xy
            y = xy_get_y(xy)
            e.w = y

        def f(e):
            hint(None, global_merge_point=True)
            xy = e.xy
            y = xy_get_y(xy)
            newy = 2*y
            xy_set_y(xy, newy)
            if y:
                dummy = 0
            else:
                dummy = 1
            g(e)
            return dummy
            
        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            e = lltype.malloc(E)
            e.xy = xy
            f(e)
            return e.w

        res = self.timeshift_from_portal(main, f, [0, 21],
                                         policy=StopAtXPolicy(g))
        assert res == 42

    def test_residual_red_call(self):
        def g(e):
            xy = e.xy
            y = xy_get_y(xy)
            e.w = y        

        def f(e):
            hint(None, global_merge_point=True)
            xy = e.xy
            y = xy_get_y(xy)
            newy = 2*y
            xy_set_y(xy, newy)
            g(e)
            return xy.x
            
        def main(x, y):
            xy = lltype.malloc(XY)
            xy.vable_access = lltype.nullptr(XY_ACCESS)
            xy.x = x
            xy.y = y
            e = lltype.malloc(E)
            e.xy = xy
            v = f(e)
            return v+e.w

        res = self.timeshift_from_portal(main, f, [2, 20],
                                         policy=StopAtXPolicy(g))
        assert res == 42

    def test_force_in_residual_red_call(self):

        def g(e):
            xp = e.xp
            p = xp_get_p(xp)
            x = xp_get_x(xp)
                
            e.w = p.a + p.b + x

        def f(e, a, b):
            hint(None, global_merge_point=True)
            xp = e.xp
            s = lltype.malloc(S)
            s.a = a
            s.b = b

            xp_set_p(xp, s)

            x = xp_get_x(xp)
            newx = 2*x
            xp_set_x(xp, newx)
            g(e)            
            return xp.x
            
        def main(a, b, x):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            xp.p = lltype.nullptr(S)
            e = lltype.malloc(E2)
            e.xp = xp
            f(e, a, b)
            return e.w

        res = self.timeshift_from_portal(main, f, [2, 20, 10],
                                         policy=StopAtXPolicy(g))
        assert res == 42

    def test_force_multiple_reads_residual_red_call(self):
        def g(e):
            xp = e.xp
            p1 = xp_get_p(xp)
            p2 = xp_get_p(xp)
            e.w = int(p1 == p2)

        def f(e, a, b):
            hint(None, global_merge_point=True)
            xp = e.xp
            s = lltype.malloc(S)
            s.a = a
            s.b = b            
            xp_set_p(xp, s)
            
            x = xp_get_x(xp)
            newx = 2*x
            xp_set_x(xp, newx)
            g(e)            
            return xp.x
            
        def main(a, b, x):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            xp.p = lltype.nullptr(S)
            e = lltype.malloc(E2)
            e.xp = xp
            f(e, a, b)
            return e.w

        res = self.timeshift_from_portal(main, f, [2, 20, 10],
                                         policy=StopAtXPolicy(g))
        assert res == 1


    def test_force_unaliased_residual_red_call(self):

        def g(e):
            pq = e.pq
            p = pq_get_p(pq)
            q = pq_get_q(pq)
            e.w = int(p != q)

        def f(e, a, b):
            hint(None, global_merge_point=True)
            pq = e.pq
            s = lltype.malloc(S)
            s.a = a
            s.b = b
            pq_set_p(pq, s)
            s = lltype.malloc(S)
            s.a = a
            s.b = b            
            pq_set_q(pq, s)
            g(e)            
            return pq.p.a
            
        
        def main(a, b, x):
            pq = lltype.malloc(PQ)
            pq.vable_access = lltype.nullptr(PQ_ACCESS)
            pq.p = lltype.nullptr(S)
            pq.q = pq.p
            e = lltype.malloc(E3)
            e.pq = pq
            f(e, a, b)
            return e.w

        res = self.timeshift_from_portal(main, f, [2, 20, 10],
                                         policy=StopAtXPolicy(g))
        assert res == 1

    def test_force_aliased_residual_red_call(self):

        def g(e):
            pq = e.pq
            p = pq_get_p(pq)
            q = pq_get_q(pq)
            e.w = int(p == q)

        def f(e, a, b):
            hint(None, global_merge_point=True)            
            pq = e.pq
            s = lltype.malloc(S)
            s.a = a
            s.b = b
            pq_set_p(pq, s)
            pq_set_q(pq, s)
            g(e)            
            return pq.p.a
                    
        def main(a, b, x):
            pq = lltype.malloc(PQ)
            pq.vable_access = lltype.nullptr(PQ_ACCESS)
            pq.p = lltype.nullptr(S)
            pq.q = pq.p
            e = lltype.malloc(E3)
            e.pq = pq
            f(e, a, b)
            return e.w

        res = self.timeshift_from_portal(main, f, [2, 20, 10],
                                         policy=StopAtXPolicy(g))
        assert res == 1

    def test_force_in_residual_red_call_with_more_use(self):
        def g(e):
            xp = e.xp
            p = xp_get_p(xp)
            x = xp_get_x(xp)
            e.w = p.a + p.b + x
            p.b, p.a = p.a, p.b

        def f(e, a, b):
            hint(None, global_merge_point=True)
            xp = e.xp
            s = lltype.malloc(S)
            s.a = a
            s.b = b
            xp_set_p(xp, s)

            x = xp_get_x(xp)
            newx = 2*x
            xp_set_x(xp, newx)
            g(e)
            s.a = s.a*7
            s.b = s.b*5
            return xp.x
            
        def main(a, b, x):
            xp = lltype.malloc(XP)
            xp.vable_access = lltype.nullptr(XP_ACCESS)
            xp.x = x
            xp.p = lltype.nullptr(S)
            e = lltype.malloc(E2)
            e.xp = xp
            f(e, a, b)
            return e.w + xp.p.a + xp.p.b

        res = self.timeshift_from_portal(main, f, [2, 20, 10],
                                         policy=StopAtXPolicy(g))
        assert res == 42 + 140 + 10


class TestVirtualizableImplicit(PortalTest):

    def test_simple(self):

        class XY(object):
            _virtualizable_ = True
            
            def __init__(self, x, y):
                self.x = x
                self.y = y
   
        def f(xy):
            return xy.x+xy.y

        def main(x, y):
            xy = XY(x, y)
            return f(xy)

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0)

    def test_simple_inheritance(self):

        class X(object):
            _virtualizable_ = True
            
            def __init__(self, x):
                self.x = x

        class XY(X):

            def __init__(self, x, y):
                X.__init__(self, x)
                self.y = y
   
        def f(xy):
            return xy.x+xy.y

        def main(x, y):
            X(0)
            xy = XY(x, y)
            return f(xy)

        res = self.timeshift_from_portal(main, f, [20, 22], policy=P_OOPSPEC)
        assert res == 42
        self.check_insns(getfield=0)

    def test_simple_interpreter_with_frame(self):
        class Log:
            acc = 0
        log = Log()
        class Frame(object):
            _virtualizable_ = True
            def __init__(self, code, acc, y):
                self.code = code
                self.pc = 0
                self.acc = acc
                self.y = y

            def run(self):
                self.plus_minus(self.code)
                return self.acc

            def plus_minus(self, s):
                n = len(s)
                pc = 0
                while pc < n:
                    hint(None, global_merge_point=True)
                    self.pc = pc
                    op = s[pc]
                    op = hint(op, concrete=True)
                    if op == '+':
                        self.acc += self.y
                    elif op == '-':
                        self.acc -= self.y
                    elif op == 'd':
                        self.debug()
                    pc += 1
                return 0

            def debug(self):
                log.acc = self.acc
            
        def main(x, y):
            code = '+d+-+'
            f = Frame(code, x, y)
            return f.run(), log.acc
        
        res = self.timeshift_from_portal(main, Frame.plus_minus.im_func,
                            [0, 2],
                            policy=StopAtXPolicy(Frame.debug.im_func))

        assert res.item0 == 4
        assert res.item1 == 2
        calls = self.count_direct_calls()
        call_count = sum([count for graph, count in calls.iteritems()
                          if not graph.name.startswith('rpyexc_')])
        assert call_count == 3
