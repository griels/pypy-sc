import math

from pypy.interpreter.error import OperationError
from pypy.interpreter.baseobjspace import Wrappable
from pypy.interpreter import baseobjspace, typedef, gateway
from pypy.interpreter.gateway import interp2app

from pypy.objspace.std.intobject import W_IntObject

from pypy.objspace.constraint.computationspace import W_Distributor

def arrange_domains(cs, variables):
    """build a data structure from var to dom
       that satisfies distribute & friends"""
    new_doms = {}
    for var in variables:
        new_doms[var] = cs.dom(var).copy()
    return new_doms


class W_AbstractDistributor(W_Distributor):
    """_distribute is left unimplemented."""

    def __init__(self, objspace, fanout):
        W_Distributor.__init__(objspace, fanout)

    def w_fanout(self):
        return self._space.newint(self._fanout)

    def _find_smallest_domain(self, w_cs):
        """returns the variable having the smallest domain.
        (or one of such varibles if there is a tie)
        """
        vars_ = [var for var, dom in w_cs.var_dom.items()
                 if dom.size() > 1]
        assert len(vars_) > 0
        best = vars_[0]
        for var in vars_:
            if w_cs.var_dom[var].size() < w_cs.var_dom[best].size():
                best = var
        return best

    def w_distribute(self, w_cs, w_choice):
        assert isinstance(w_choice, W_IntObject)
        self.distribute(w_cs, self._space.int_w(w_choice) -1)

    def distribute(self, w_cs, choice_w):
        variable = self.find_distribution_variable(w_cs)
        domain = w_cs.w_dom(variable)
        self._do_distribute(w_cs, domain, choice_w)
        for const in w_cs.dependant_constraints(variable):
            w_cs.to_check[const] = True

    def find_distribution_variable(self, w_cs):
        return self._find_smallest_domain(w_cs)
    
    def _do_distribute(self, w_cs, domain, choice):
        """remove values from domain depending on choice"""
        raise NotImplementedError

W_Distributor.typedef = typedef.TypeDef("W_AbstractDistributor",
    W_Distributor.typedef,
    fanout = interp2app(W_AbstractDistributor.w_fanout),
    distribute = interp2app(W_AbstractDistributor.w_distribute))
    
        
class W_NaiveDistributor(W_AbstractDistributor):
    """distributes domains by splitting the smallest domain in 2 new domains
    The first new domain has a size of one,
    and the second has all the other values"""

    def __init__(self, object_space, fanout):
        # default fanout is 2, see make_naive_distributor
        W_Distributor.__init__(self, object_space, fanout)
        
    def _do_distribute(self, w_cs, domain, choice):
        values = domain.get_values()
        #assert len(values) > 0
        if choice == 0:
            domain.remove_values(values[1:])
        else:
            domain.w_remove_value(values[0])

W_NaiveDistributor.typedef = typedef.TypeDef(
    "W_NaiveDistributor",
    W_AbstractDistributor.typedef)

def make_naive_distributor(object_space, fanout=2):
    if not isinstance(fanout, int):
        raise OperationError(object_space.w_RuntimeError,
                             object_space.wrap("fanout must be a positive integer"))
    return object_space.wrap(W_NaiveDistributor(object_space, fanout))
app_make_naive_distributor = interp2app(make_naive_distributor,
                                        unwrap_spec = [baseobjspace.ObjSpace, int])


class W_SplitDistributor(W_AbstractDistributor):
    """distributes domains by splitting the smallest domain in
    nb_subspaces equal parts or as equal as possible.
    If nb_subspaces is 0, then the smallest domain is split in
    domains of size 1"""
    
    def __init__(self, object_space, fanout):
        # default fanout is 3, see make_split_distributor
        W_Distributor.__init__(self, object_space, fanout)

    def _subdomains(self, w_cs):
        """returns the min number of partitions
           for a domain to be distributed"""
        to_split = self._find_smallest_domain(w_cs)
        if self._fanout > 0:
            return min(self._fanout,
                       w_cs.w_dom(to_split).size()) 
        else:
            return w_cs.w_dom(to_split).size() 

    def _do_distribute(self, w_cs, domain, choice):
        values = domain.get_values()
        nb_elts = max(1, len(values)*1./self._subdomains(w_cs))
        start, end = (int(math.floor(choice * nb_elts)),
                      int(math.floor((choice + 1) * nb_elts)))
        domain.remove_values(values[:start])
        domain.remove_values(values[end:])

def make_split_distributor(object_space, fanout=3):
    if not isinstance(fanout, int):
        raise OperationError(object_space.w_RuntimeError,
                             object_space.wrap("fanout must be a positive integer"))
    return object_space.wrap(W_SplitDistributor(object_space, fanout))
app_make_split_distributor = interp2app(make_split_distributor,
                                        unwrap_spec = [baseobjspace.ObjSpace, int])


class W_DichotomyDistributor(W_SplitDistributor):
    """distributes domains by splitting the smallest domain in
    two equal parts or as equal as possible"""
    def __init__(self, object_space, w_fanout):
        W_SplitDistributor.__init__(self, object_space, w_fanout)

def make_dichotomy_distributor(object_space):
    return make_split_distributor(object_space, 2)
app_make_dichotomy_distributor = interp2app(make_dichotomy_distributor)
