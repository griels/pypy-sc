from pypy.interpreter import baseobjspace, gateway, typedef

from pypy.objspace.cclp.misc import w, ClonableCoroutine
#from pypy.objspace.constraint.domain import W_FiniteDomain

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
    __str__ = __repr__


class W_Future(W_Var):
    "a read-only-by-its-consummer variant of logic. var"
    def __init__(w_self, space):
        W_Var.__init__(w_self, space)
        w_self._client = ClonableCoroutine.w_getcurrent(space)
        w("FUT", str(w_self))


class W_CVar(W_Var):
    def __init__(w_self, space, w_dom): #, w_name):
        assert isinstance(w_dom, W_FiniteDomain)
        W_Var.__init__(w_self, space)
        w_self.w_dom = w_dom
        #w_self.name = space.str_w(w_name)

    def name_w(w_self):
        return w_self.name

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

#-- Constraint ---------------------------------------------

## class W_Constraint(baseobjspace.Wrappable):
##     def __init__(self, object_space):
##         self._space = object_space

## W_Constraint.typedef = typedef.TypeDef(
##     "W_Constraint")


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
