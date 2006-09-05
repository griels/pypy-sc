from pypy.annotation.policy import AnnotatorPolicy
from pypy.jit.timeshifter.test.test_timeshift import TimeshiftingTests

P_OOPSPEC = AnnotatorPolicy()
P_OOPSPEC.novirtualcontainer = True
P_OOPSPEC.oopspec = True
P_OOPSPEC.exceptiontransform = False # XXX for now, needs to make ptr_ne/eq
                                     # not force things


class TestVList(TimeshiftingTests):

    def test_vlist(self):
        def ll_function():
            lst = []
            lst.append(12)
            return lst[0]
        res = self.timeshift(ll_function, [], [], policy=P_OOPSPEC)
        assert res == 12
        self.check_insns({})

    def test_enter_block(self):
        def ll_function(flag):
            lst = []
            lst.append(flag)
            lst.append(131)
            if flag:
                return lst[0]
            else:
                return lst[1]
        res = self.timeshift(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 6
        self.check_insns({'int_is_true': 1})
        res = self.timeshift(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 131
        self.check_insns({'int_is_true': 1})

    def test_merge(self):
        def ll_function(flag):
            lst = []
            if flag:
                lst.append(flag)
            else:
                lst.append(131)
            return lst[-1]
        res = self.timeshift(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 6
        self.check_insns({'int_is_true': 1})
        res = self.timeshift(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 131
        self.check_insns({'int_is_true': 1})

    def test_replace(self):
        def ll_function(flag):
            lst = []
            if flag:
                lst.append(12)
            else:
                lst.append(131)
            return lst[-1]
        res = self.timeshift(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 12
        self.check_insns({'int_is_true': 1})
        res = self.timeshift(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 131
        self.check_insns({'int_is_true': 1})

    def test_force(self):
        def ll_function(n):
            lst = []
            lst.append(n)
            if n:
                lst.append(12)
            return lst[-1]
        res = self.timeshift(ll_function, [6], [], policy=P_OOPSPEC)
        assert res == 12
        res = self.timeshift(ll_function, [0], [], policy=P_OOPSPEC)
        assert res == 0
