# Oz unification in Python 2.4
# within a single assignment store
# crude and buggy ...

#TODO :
# * ensure that the store is intact after a failure
#   (maybe with some anti-bind ops)
# * provide a way to copy the store to a fresh one
#   (clone operator)
# After reading more of the "book", I see some more ops
# are needed for the store to be part of a computation
# space ...

#----------- Variables ----------------------------------
class EqSet(frozenset):
    """An equivalence set for variables"""
    pass

class Var(object):

    def __init__(self, name, store):
        self.name = name
        self.store = store
        store.add_unbound(self)

    def __str__(self):
        if self in self.store.bound.keys():
            return "%s = %s" % (self.name,
                                self.store.bound[self])
        return "%s" % self.name

    def __repr__(self):
        return self.__str__()

    def __eq__(self, thing):
        return type(thing) == Var and self.name == thing.name

    def __hash__(self):
        return self.name.__hash__()

def var(name):
    return Var(name, _store)

#----------- Store Exceptions ----------------------------
class VariableException(Exception):
    def __init__(self, name):
        self.name = name

class UnboundVariable(VariableException):
    def __str__(self):
        return "%s has no value yet" % self.name

class AlreadyBound(VariableException):
    def __str__(self):
        return "%s is already bound" % self.name

class AlreadyInStore(VariableException):
    def __str__(self):
        return "%s already in store" % self.name

class UnificationFailure(Exception):
    def __init__(self, var1, var2):
        self.var1, self.var2 = (var1, var2)
    def __str__(self):
        return "%s %s can't be unified" % (self.var1,
                                           self.var2)

class Circularity(UnificationFailure):
    def __str__(self):
        return "cycle : % %s not unifiable" % (self.var1,
                                               self.var2)
               
#----------- Variable Exceptions-------------------------
class NotAVariable(VariableException):
    def __str__(self):
        return "%s is not a variable" % self.name

#----------- Store ------------------------------------
class Store(object):
    """The Store consists of a set of k variables
       x1,...,xk that are partitioned as follows: 
       * set of unbound variables that are equal
         (also called equivalence sets of variables).
         The variables in each set are equal to each
         other but not to any other variables.
       * variables bound to a number, record or procedure
         (also called determined variables)."""
    
    def __init__(self):
        # set of all known vars
        # var->equivalence set mapping for unbound vars
        # set of equisets (clusters of unbound variables)
        # var->objects bindings
        self.vars = set()
        self.equisets = {}
        self.unbound = set()
        self.bound = {}
        # memoizer for unify (avoids infinite loops when
        # one wants to unify vars with cycles)
        self.unify_memo = set()

    def add_unbound(self, var):
        # register globally
        if var in self.vars:
            raise AlreadyInStore(var.name)
        print "adding %s to the store" % var
        self.vars.add(var)
        # put into new singleton equiv. set
        eqset = EqSet([var])
        self.equisets[var] = eqset
        self.unbound.add(eqset)

    #-- BIND -------------------------------------------

    def bind(self, var, val):
        """1. (unbound)Variable/(unbound)Variable or
           2. (unbound)Variable/(bound)Variable or
           3. (unbound)Variable/Value binding
        """
        assert(isinstance(var, Var) and (var in self.vars))
        if var == val:
            return
        if self._both_are_vars(var, val):
            if self._both_are_bound(var, val):
                raise AlreadyBound(var.name)
            if self.bound.has_key(var): # 2.
                self.bind(val, var)
            elif self.bound.has_key(val): # 2.
                self._bind(self.equisets[var],
                           self.bound[val])
            else: # 1. 
                self._merge(self.equisets[var],
                            self.equisets[val])
        else: # 3.
            if self.bound.has_key(var):
                raise AlreadyBound(var.name)
            self._bind(self.equisets[var], val)

    def _both_are_vars(self, v1, v2):
        try:
            return v1 in self.vars and v2 in self.vars
        except:
            return False

    def _both_are_bound(self, v1, v2):
        return self.bound.has_key(v1) and \
               self.bound.has_key(v2)

    def _bind(self, eqs, val):
        print "variable - value binding : %s %s" % (eqs, val)
        # bind all vars in the eqset to obj
        for name in eqs:
            del self.equisets[name]
            self.bound[name] = val
        self.unbound.remove(eqs)

    def _merge(self, eqs1, eqs2):
        print "unbound variables binding : %s %s" % (eqs1, eqs2)
        if eqs1 == eqs2: return
        # merge two equisets into one
        neweqs = eqs1 | eqs2
        # let's reassign everybody to eqs1
        for name in neweqs:
            self.equisets[name] = neweqs
        self.unbound.remove(eqs1)
        self.unbound.remove(eqs2)
        self.unbound.add(neweqs)

    #-- UNIFY ------------------------------------------

    def unify(self, x, y):
        #FIXME in case of failure, the store state is not
        #      properly restored ...
        print "unify %s with %s" % (x,y)
        # do the memoization work
        if (x,y) in self.unify_memo: raise Circularity(x,y)
        self.unify_memo.add((x, y))
        # dispatch to the apropriate unifier
        try:
            if x not in self.bound and y not in self.bound:
                if x != y:
                    if type(x) is Var:
                        self.bind(x,y)
                    else:
                        self.bind(y,x)
            elif x in self.bound and y in self.bound:
                self._unify_bound(x,y)
            elif x in self.bound:
                self.bind(x,y)
            else:
                self.bind(y,x)
        except AlreadyBound:
            raise UnificationFailure(x, y)
        
    def _unify_bound(self, x, y):
        print "unify bound %s %s" % (x, y)
        vx, vy = (self.bound[x], self.bound[y])
        if not _unifiable(vx, vy): raise UnificationFailure(x, y)
        elif type(vx) in [list, set] and isinstance(vy, type(vx)):
            self._unify_iterable(x, y)
        elif type(vx) is dict and isinstance(vy, type(vx)):
            self._unify_mapping(x, y)
        else:
            raise UnificationFailure(x, y)

    def _unify_iterable(self, x, y):
        print "unify sequences %s %s" % (x, y)
        vx, vy = (self.bound[x], self.bound[y])
        idx, top = (0, len(vx))
        while (idx < top):
            self.unify(vx[idx], vy[idx])
            idx += 1

    def _unify_mapping(self, x, y):
        print "unify mappings %s %s" % (x, y)
        vx, vy = (self.bound[x], self.bound[y])
        for xk in vx.keys():
            self.unify(vx[xk], vy[xk])

#-- Unifiability checks---------------------------------------
#--
#-- quite costly & could be merged back in unify
#-- FIXME : memoize _iterable

def _iterable(thing):
    return type(thing) in [list, set]

def _mapping(thing):
    return type(thing) is dict
        
def _unifiable(term1, term2):
    """Checks wether two terms can be unified"""
    print "unifiable ? %s %s" % (term1, term2)
    if _iterable(term1):
        if _iterable(term2):
            return _iter_unifiable(term1, term2)
        return False
    if _mapping(term1) and _mapping(term2):
        return _mapping_unifiable(term1, term2)
    if not(isinstance(term1, Var) or isinstance(term2, Var)):
        return term1 == term2 # same 'atomic' object
    return True
        
def _iter_unifiable(c1, c2):
   """Checks wether two iterables can be unified"""
   print "unifiable sequences ? %s %s" % (c1, c2)
   if len(c1) != len(c2): return False
   idx, top = (0, len(c1))
   while(idx < top):
       if not _unifiable(c1[idx], c2[idx]):
           return False
       idx += 1
   return True

def _mapping_unifiable(m1, m2):
    """Checks wether two mappings can be unified"""
    print "unifiable mappings ? %s %s" % (m1, m2)
    if len(m1) != len(m2): return False
    if m1.keys() != m2.keys(): return False
    v1, v2 = (m1.items(), m2.items())
    v1.sort()
    v2.sort()
    return _iter_unifiable([e[1] for e in v1],
                           [e[1] for e in v2])

#-- Some utilities -----------------------------------------------
#--
#-- the global store
_store = Store()

#-- global accessor functions
def bind(var, val):
    return _store.bind(var, val)

def unify(var1, var2):
    return _store.unify(var1, var2)

def bound():
    return _store.bound.keys()

def unbound():
    res = []
    for cluster in _store.unbound:
        res.append('='.join([str(var) for var in cluster]))
    return res
