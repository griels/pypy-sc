import threading

from constraint import FiniteDomain


#----------- Exceptions ---------------------------------
class VariableException(Exception):
    def __init__(self, name):
        self.name = name

class AlreadyInStore(VariableException):
    def __str__(self):
        return "%s already in store" % self.name

class NotAVariable(VariableException):
    def __str__(self):
        return "%s is not a variable" % self.name

#----------- Variables ----------------------------------
class EqSet(set):
    """An equivalence set for variables"""

##     def __str__(self):
##         if len(self) == 0:
##             return ''
##         for var in self:
##             '='.join(var.name)

class NoValue:
    pass

class Var(object):
    """Single-assignment variable"""

    def __init__(self, name, cs):
        if name in cs.names:
            raise AlreadyInStore(name)
        self.name = name
        # the creation-time (top-level) space
        self.cs = cs
        # top-level 'commited' binding
        self._val = NoValue
        # domains in multiple spaces
        self._doms = {cs : FiniteDomain([])}
        # when updated in a 'transaction', keep track
        # of our initial value (for abort cases)
        self.previous = None
        self.changed = False
        # a condition variable for concurrent access
        self.value_condition = threading.Condition()

    # for consumption by the global cs

    def _is_bound(self):
        return not isinstance(self._val, EqSet) \
               and self._val != NoValue

    # atomic unification support

    def _commit(self):
        self.changed = False

    def _abort(self):
        self.val = self.previous
        self.changed = False

    # value accessors
    def _set_val(self, val):
        self.value_condition.acquire()
        if self.cs.in_transaction:
            if not self.changed:
                self.previous = self._val
                self.changed = True
        self._val = val
        self.value_condition.notifyAll()
        self.value_condition.release()
        
    def _get_val(self):
        return self._val
    val = property(_get_val, _set_val)

    def __str__(self):
        if self.is_bound():
            return "%s = %s" % (self.name, self.val)
        return "%s" % self.name

    def __repr__(self):
        return self.__str__()

    def __eq__(self, thing):
        return isinstance(thing, Var) \
               and self.name == thing.name

    def __hash__(self):
        return self.name.__hash__()

    def bind(self, val):
        """top-level space bind"""
        self.cs.bind(self, val)

    is_bound = _is_bound

    #-- domain setter/getter is per space
    def cs_set_dom(self, cs, dom):
        self._doms[cs] = dom

    def cs_get_dom(self, cs):
        self._doms.setdefault(cs, FiniteDomain([]))
        return self._doms[cs]

    #-- Dataflow ops with concurrent semantics ------
    # should be used by threads that want to block on
    # unbound variables

    def get(self):
        """Make threads wait on the variable
           being bound in the top-level space
        """
        try:
            self.value_condition.acquire()
            while not self._is_bound():
                self.value_condition.wait()
            return self.val
        finally:
            self.value_condition.release()


#-- stream stuff -----------------------------

from Queue import Queue

class StreamUserBug(Exception):
    pass

class Stream(Queue):
    """a stream is potentially unbounded list
       of messages, i.e a list whose tail is
       an unbound dataflow variable
    """

    def __init__(self, size=5, stuff=None):
        self.elts = stuff
        self.idx = 0
        Queue.__init__(self, size)

    def get(self):
        if self.elts is None:
            Queue.get(self)
        else:
            try:
                v = self.elts[self.idx]
                self.idx += 1
                return v
            except IndexError:
                self.idx = 0
                return self.get()

    def put(self, elt):
        if self.elts is None:
            Queue.put(self, elt)
        else:
            raise NoImplemented
