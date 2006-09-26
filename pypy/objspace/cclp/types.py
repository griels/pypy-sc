from pypy.interpreter import baseobjspace, gateway, typedef
from pypy.interpreter.error import OperationError

from pypy.objspace.cclp.misc import w, ClonableCoroutine, get_current_cspace

W_Root = baseobjspace.W_Root

#-- Variables types ----------------------------------------

class W_Var(W_Root):
    def __init__(w_self, space):
        # ring of aliases or bound value
        w_self.w_bound_to = w_self
        w_self.entails = {}
        # byneed flag
        w_self.needed = False

    def __repr__(w_self):
        if isinstance(w_self.w_bound_to, W_Var):
            return '<?@%s>' % prettyfy_id(id(w_self))
        return '<%s@%s>' % (w_self.w_bound_to,
                            prettyfy_id(id(w_self)))

    def _same_as(w_self, w_var):
        assert isinstance(w_var, W_Var)
        return w_self is w_var
    __str__ = __repr__


class W_Future(W_Var):
    "a read-only-by-its-consummer variant of logic. var"
    def __init__(w_self, space):
        W_Var.__init__(w_self, space)
        w_self._client = ClonableCoroutine.w_getcurrent(space)
        w("FUT", str(w_self))


class W_CVar(W_Var):
    def __init__(self, space, w_dom, w_name):
        assert isinstance(w_dom, W_AbstractDomain)
        W_Var.__init__(self, space)
        self.w_dom = w_dom
        self.name = space.str_w(w_name)
        self.w_nam = w_name
        cspace = get_current_cspace(space)
        if cspace is None:
            w("-- WARNING : you are instanciating a constraint var in the top-level space")
        else:
            cspace.register_var(self)

    def name_w(self):
        return self.name

    def w_name(self):
        return self.w_nam

def domain_of(space, w_v):
    assert isinstance(w_v, W_CVar)
    return w_v.w_dom
app_domain_of = gateway.interp2app(domain_of)

#-- Exception types ----------------------------------------

class W_FailedValue(W_Root):
    """wraps an exception raised in some coro, to be re-raised in
       some dependant coro sometime later
    """
    def __init__(w_self, exc):
        w_self.exc = exc

class ConsistencyError(Exception): pass

class Solution(Exception): pass

#-- Constraint ---------------------------------------------

class W_Constraint(baseobjspace.Wrappable):
    def __init__(self, object_space):
        self._space = object_space

W_Constraint.typedef = typedef.TypeDef("W_Constraint")

class W_AbstractDomain(baseobjspace.Wrappable):
    """Implements the functionnality related to the changed flag.
    Can be used as a starting point for concrete domains"""

    def __init__(self, space):
        self._space = space
        self._changed = W_Var(self._space)

    def give_synchronizer(self):
        pass

    def get_values(self):
        pass

    def size(self):
        pass

W_AbstractDomain.typedef = typedef.TypeDef("W_AbstractDomain")

class W_AbstractDistributor(baseobjspace.Wrappable):

    def __init__(self, space, fanout):
        assert isinstance(fanout, int)
        self._space = space
        self._fanout = fanout
        self._cspace = get_current_cspace(space)

W_AbstractDistributor.typedef = typedef.TypeDef("W_AbstractDistributor")


#-- Misc ---------------------------------------------------

def deref(space, w_var):
    "gets the value/next alias of a variable"
    assert isinstance(w_var, W_Var)
    return w_var.w_bound_to

def aliases(space, w_var):
    """return the aliases of a var, including itself"""
    assert isinstance(w_var, W_Var)
    assert isinstance(w_var.w_bound_to, W_Var)
    al = []
    w_curr = w_var
    while 1:
        w_next = w_curr.w_bound_to
        assert isinstance(w_next, W_Var)
        al.append(w_curr)
        if space.is_true(space.is_nb_(w_next, w_var)):
            break
        w_curr = w_next
    return al

def prettyfy_id(an_int):
    "gets the 3 lower digits of an int"
    assert isinstance(an_int, int)
    a_str = str(an_int)
    l = len(a_str) - 1
    return a_str[l-3:l]
