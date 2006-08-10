from pypy.conftest import gettestobjspace
from py.test import skip

class AppTest_AllDistinct(object):

    def setup_class(cls):
        cls.space = gettestobjspace('logic', usemodules=('_stackless', ))

        
    def test_instantiate(self):
        v1 = domain([1, 2], 'v1')
        v2 = domain([1, 2], 'v2')
        cstr = all_diff([v1, v2])
        variables = cstr.affected_variables()
        assert variables is not None
        assert len(variables) == 2
        assert cstr.knows_var(v1)
        assert cstr.knows_var(v2)

    def test_revise(self):
        v1 = domain([1, 2], 'v1')
        v2 = domain([1, 2], 'v2')
        cstr = all_diff([v1, v2])
        assert cstr.revise() == False # not entailed

        v3 = domain([1], 'v3')
        v4 = domain([2], 'v4')
        cstr = all_diff([v3, v4])
        assert cstr.revise() == True # entailed

        v5 = domain([1], 'v5')
        v6 = domain([1], 'v6')
        cstr = all_diff([v5, v6])
        raises(Exception, cstr.revise)

        v7 = domain([1, 2], 'v7')
        v8 = domain([1, 2], 'v8')
        cstr = all_diff([v2, v7, v8])
        raises(Exception, cstr.revise)

        v9 = domain([1], 'v9')
        v10= domain([1, 2], 'v10')
        cstr = all_diff([v9, v10])
        assert cstr.revise() == True
        assert domain_of(v10).get_values() == [2]

class AppTest_Expression(object):

    def setup_class(cls):
        cls.space = gettestobjspace('logic', usemodules=('_stackless', ))

    def test_instantiate(self):
        v1 = domain([1, 2], 'v1')
        cstr = make_expression([v1], '2*v1==2')
        assert str(cstr).startswith('<W_Expression object at')        

    def test_revise(self):
        v1 = domain([1, 2], 'v1')
        cstr = make_expression([v1], '2*v1==2')
        assert cstr.revise() == 0
        assert domain_of(v1).get_values() == [1]

