# First cut at representing Oz dataflow variable

import threading

#----------- Exceptions ---------------------------------
class VariableException(Exception):
    def __init__(self, name):
        self.name = name

class NotAVariable(VariableException):
    def __str__(self):
        return "%s is not a variable" % self.name

class AlreadyExists(VariableException):
    def __str__(self):
        return "%s already exists" % self.name

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

    def __init__(self, name, store):
        if name in store.names:
            raise AlreadyExists(name)
        self.name = name
        self.store = store
        # top-level 'commited' binding
        self._val = NoValue
        # when updated in a 'transaction', keep track
        # of our initial value (for abort cases)
        self.previous = None
        self.changed = False
        # a condition variable for concurrent access
        self.mutex = threading.Lock()
        self.value_condition = threading.Condition(self.mutex)

    # for consumption by the global store

    def _is_bound(self):
        return not isinstance(self._val, EqSet) \
               and self._val != NoValue

    # 'transaction' support

    def _commit(self):
        self.changed = False

    def _abort(self):
        self.val = self.previous
        self.changed = False

    # value accessors
    def _set_val(self, val):
        self.value_condition.acquire()
        if self.store.in_transaction:
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

    #---- Concurrent public ops --------------------------

    def is_bound(self):
        self.mutex.acquire()
        res = self._is_bound()
        self.mutex.release()
        return res

    # should be used by threads that want to block on
    # unbound variables
    def get(self):
        try:
            self.value_condition.acquire()
            while not self._is_bound():
                self.value_condition.wait()
            return self.val
        finally:
            self.value_condition.release()
