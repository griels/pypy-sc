from pypy.conftest import gettestobjspace

class AppTest_Stackless:

    def setup_class(cls):
        space = gettestobjspace(usemodules=('_stackless',))
        cls.space = space

    def x_test_one(self):
        import stackless

        print stackless.__file__
        t = stackless.tasklet()
        t.demo()
        class A(stackless.tasklet):
            def __init__(self, name):
                self.name = name
            def __new__(subtype, *args):
                return stackless.tasklet.__new__(subtype)
        x = A("heinz")
        x.demo()
        print x.name

    def test_simple(self):
        import stackless
        stackless.__init()

        rlist = []

        def f():
            rlist.append('f')

        def g():
            rlist.append('g')
            stackless.schedule()

        def main():
            rlist.append('m')
            cg = stackless.tasklet(g)()
            cf = stackless.tasklet(f)()
            stackless.run()
            rlist.append('m')

        main()

        assert stackless.getcurrent() is stackless.main_tasklet
        assert rlist == 'm g f m'.split()

    def test_with_channel(self):
        import stackless
        stackless.__init()

        rlist = []
        def f(outchan):
            for i in range(10):
                rlist.append('s%s' % i)
                outchan.send(i)
            outchan.send(-1)

        def g(inchan):
            while 1:
                val = inchan.receive()
                if val == -1:
                    break
                rlist.append('r%s' % val)

        ch = stackless.channel()
        t1 = stackless.tasklet(f)(ch)
        t2 = stackless.tasklet(g)(ch)

        stackless.run()

        assert len(rlist) == 20
        for i in range(10):
            (s,r), rlist = rlist[:2], rlist[2:]
            assert s == 's%s' % i
            assert r == 'r%s' % i

    def test_counter(self):
        import random
        import stackless
        stackless.__init()

        numbers = range(20)
        random.shuffle(numbers)

        def counter(n, ch):
            for i in xrange(n):
                stackless.schedule()
            ch.send(n)

        ch = stackless.channel()
        for each in numbers:
            stackless.tasklet(counter)(each, ch)

        stackless.run()

        rlist = []
        while ch.balance:
            rlist.append(ch.receive())

        numbers.sort()
        assert rlist == numbers
