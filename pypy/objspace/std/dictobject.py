"""
Reviewed 03-06-22
All common dictionary methods are correctly implemented,
tested, and complete. The only missing feature is support
for order comparisons.
"""

from pypy.objspace.std.objspace import *
from pypy.interpreter import gateway

from pypy.rpython.rarithmetic import r_uint

class Entry:
    def __init__(self):
        self.hash = r_uint(0)
        self.w_key = None
        self.w_value = None
    def __repr__(self):
        return '<Entry %r,%r,%r>'%(self.hash, self.w_key, self.w_value)

class W_DictObject(W_Object):
    from pypy.objspace.std.dicttype import dict_typedef as typedef

    def __init__(w_self, space, list_pairs_w):
        W_Object.__init__(w_self, space)
        
        w_self.used = 0
        w_self.data = []
        w_self.resize(len(list_pairs_w)*2)
        w_self.w_dummy = space.newlist([])
        for w_k, w_v in list_pairs_w:
            w_self.insert(w_self.hash(w_k), w_k, w_v)
        
    def __repr__(w_self):
        """ representation for debugging purposes """
        return "%s(%s)" % (w_self.__class__.__name__, w_self.data)

    def hash(w_self, w_obj):
        space = w_self.space
        return r_uint(space.int_w(space.hash(w_obj)))

    def insert(self, h, w_key, w_value):
        entry = self.lookdict(h, w_key)
        if entry.w_value is None:
            self.used += 1
            entry.hash = h
            entry.w_key = w_key
            entry.w_value = w_value
        else:
            entry.w_value = w_value

    def resize(self, minused):
        newsize = 4
        while newsize < minused:
            newsize *= 2
        od = self.data

        self.used = 0
        self.data = [Entry() for i in range(newsize)]
        for entry in od:
            if entry.w_value is not None:
                self.insert(entry.hash, entry.w_key, entry.w_value)

    def lookdict(self, lookup_hash, w_lookup):
        assert isinstance(lookup_hash, r_uint)
        space = self.space
        data = self.data
        mask = len(data) - 1   # len(data) is expected to be a power of 2
        i = lookup_hash & mask

        entry = data[i]
        if entry.w_key is None or space.is_w(w_lookup, entry.w_key):
            return entry
        if entry.w_key is self.w_dummy:
            freeslot = entry
        else:
            if entry.hash == lookup_hash and space.eq_w(entry.w_key, w_lookup):
                if self.data is not data:
                    # the eq_w() modified the dict sufficiently to have it
                    # switch to another table.  Can't return 'entry', which
                    # belongs to the old table.  Start over...
                    return self.lookdict(lookup_hash, w_lookup)
                return entry
            freeslot = None

        perturb = lookup_hash
        while 1:
            i = (i << 2) + i + perturb + 1
            entry = data[i & mask]
            if entry.w_key is None:
                if freeslot:
                    return freeslot
                else:
                    return entry
            if entry.hash == lookup_hash and entry.w_key is not self.w_dummy \
                   and space.eq_w(entry.w_key, w_lookup):
                if self.data is not data:
                    # the eq_w() modified the dict sufficiently to have it
                    # switch to another table.  Can't return 'entry', which
                    # belongs to the old table.  Start over...
                    return self.lookdict(lookup_hash, w_lookup)
                return entry
            if entry.w_key is self.w_dummy and freeslot is None:
                freeslot = entry
            perturb >>= 5

    def unwrap(w_dict):
        space = w_dict.space
        result = {}
        for entry in w_dict.data:
            if entry.w_value is not None:
                # XXX generic mixed types unwrap
                result[space.unwrap(entry.w_key)] = space.unwrap(entry.w_value)
        return result

registerimplementation(W_DictObject)


def init__Dict(space, w_dict, __args__):
    w_src, w_kwds = __args__.parse('dict',
                          (['seq_or_map'], None, 'kwargs'), # signature
                          [W_DictObject(space, [])])        # default argument
    dict_clear__Dict(space, w_dict)
    # XXX do dict({...}) with dict_update__Dict_Dict()
    try:
        space.getattr(w_src, space.wrap("keys"))
    except OperationError:
        list_of_w_pairs = space.unpackiterable(w_src)
        for w_pair in list_of_w_pairs:
            pair = space.unpackiterable(w_pair)
            if len(pair)!=2:
                raise OperationError(space.w_ValueError,
                             space.wrap("dict() takes a sequence of pairs"))
            w_k, w_v = pair
            setitem__Dict_ANY_ANY(space, w_dict, w_k, w_v)
    else:
        if space.is_true(w_src):
            from pypy.objspace.std.dicttype import dict_update__ANY_ANY
            dict_update__ANY_ANY(space, w_dict, w_src)
    if space.is_true(w_kwds):
        space.call_method(w_dict, 'update', w_kwds)

def getitem__Dict_ANY(space, w_dict, w_lookup):
    entry = w_dict.lookdict(w_dict.hash(w_lookup), w_lookup)
    if entry.w_value is not None:
        return entry.w_value
    else:
        raise OperationError(space.w_KeyError, w_lookup)

def setitem__Dict_ANY_ANY(space, w_dict, w_newkey, w_newvalue):
    w_dict.insert(w_dict.hash(w_newkey), w_newkey, w_newvalue)
    if 2*w_dict.used > len(w_dict.data):
        w_dict.resize(2*w_dict.used)

def delitem__Dict_ANY(space, w_dict, w_lookup):
    entry = w_dict.lookdict(w_dict.hash(w_lookup), w_lookup)
    if entry.w_value is not None:
        w_dict.used -= 1
        entry.w_key = w_dict.w_dummy
        entry.w_value = None
    else:
        raise OperationError(space.w_KeyError, w_lookup)
    
def len__Dict(space, w_dict):
    return space.wrap(w_dict.used)

def contains__Dict_ANY(space, w_dict, w_lookup):
    entry = w_dict.lookdict(w_dict.hash(w_lookup), w_lookup)
    return space.newbool(entry.w_value is not None)

dict_has_key__Dict_ANY = contains__Dict_ANY

def iter__Dict(space, w_dict):
    return W_DictIter_Keys(space, w_dict)

def eq__Dict_Dict(space, w_left, w_right):
    if space.is_true(space.is_(w_left, w_right)):
        return space.w_True

    if w_left.used != w_right.used:
        return space.w_False
    for entry in w_left.data:
        w_val = entry.w_value
        if w_val is None:
            continue
        rightentry = w_right.lookdict(entry.hash, entry.w_key)
        if rightentry.w_value is None:
            return space.w_False
        if not space.eq_w(w_val, rightentry.w_value):
            return space.w_False
    return space.w_True

def characterize(space, adata, w_b):
    """ (similar to CPython) 
    returns the smallest key in adata for which b's value is different or absent and this value """
    w_smallest_diff_a_key = None
    w_its_value = None
    for entry in adata:
        w_val = entry.w_value
        if w_val is None:
            continue
        w_key = entry.w_key
        if w_smallest_diff_a_key is None or space.is_true(space.lt(w_key, w_smallest_diff_a_key)):
            b_entry = w_b.lookdict(entry.hash, w_key)
            if b_entry.w_value is None:
                w_its_value = w_val
                w_smallest_diff_a_key = w_key
            else:
                if not space.eq_w(w_val, b_entry.w_value):
                    w_its_value = w_val
                    w_smallest_diff_a_key = w_key
    return w_smallest_diff_a_key, w_its_value

def lt__Dict_Dict(space, w_left, w_right):
    # Different sizes, no problem
    if w_left.used < w_right.used:
        return space.w_True
    if w_left.used > w_right.used:
        return space.w_False

    # Same size
    w_leftdiff, w_leftval = characterize(space, w_left.data, w_right)
    if w_leftdiff is None:
        return space.w_False
    w_rightdiff, w_rightval = characterize(space, w_right.data, w_left)
    w_res = space.w_False
    if w_rightdiff is not None:
        w_res = space.lt(w_leftdiff, w_rightdiff)
    if space.is_w(w_res, space.w_False) and space.eq_w(w_leftdiff, w_rightdiff) and w_rightval is not None:
        w_res = space.lt(w_leftval, w_rightval)
    return w_res


def hash__Dict(space,w_dict):
    raise OperationError(space.w_TypeError,space.wrap("dict objects are unhashable"))

def dict_copy__Dict(space, w_self):
    return W_DictObject(space, [(entry.w_key,entry.w_value)
                                for entry in w_self.data
                                if entry.w_value is not None])

def dict_items__Dict(space, w_self):
    return space.newlist([ space.newtuple([entry.w_key,entry.w_value])
                           for entry in w_self.data
                           if entry.w_value is not None])

def dict_keys__Dict(space, w_self):
    return space.newlist([ entry.w_key
                           for entry in w_self.data
                           if entry.w_value is not None])

def dict_values__Dict(space, w_self):
    return space.newlist([ entry.w_value
                           for entry in w_self.data
                           if entry.w_value is not None])

def dict_iteritems__Dict(space, w_self):
    return W_DictIter_Items(space, w_self)

def dict_iterkeys__Dict(space, w_self):
    return W_DictIter_Keys(space, w_self)

def dict_itervalues__Dict(space, w_self):
    return W_DictIter_Values(space, w_self)

def dict_clear__Dict(space, w_self):
    w_self.data = [Entry()]
    w_self.used = 0

def dict_get__Dict_ANY_ANY(space, w_dict, w_lookup, w_default):
    entry = w_dict.lookdict(w_dict.hash(w_lookup), w_lookup)
    if entry.w_value is not None:
        return entry.w_value
    else:
        return w_default

app = gateway.applevel('''
    def dictrepr(currently_in_repr, d):
        # Now we only handle one implementation of dicts, this one.
        # The fix is to move this to dicttype.py, and do a
        # multimethod lookup mapping str to StdObjSpace.str
        # This cannot happen until multimethods are fixed. See dicttype.py
            dict_id = id(d)
            if dict_id in currently_in_repr:
                return '{...}'
            currently_in_repr[dict_id] = 1
            try:
                items = []
                for k, v in d.iteritems():
                    items.append(repr(k) + ": " + repr(v))
                return "{" +  ', '.join(items) + "}"
            finally:
                try:
                    del currently_in_repr[dict_id]
                except:
                    pass
''', filename=__file__)

dictrepr = app.interphook("dictrepr")

def repr__Dict(space, w_dict):
    if w_dict.used == 0:
        return space.wrap('{}')
    w_currently_in_repr = space.getexecutioncontext()._py_repr
    return dictrepr(space, w_currently_in_repr, w_dict)


# ____________________________________________________________
# Iteration

class W_DictIterObject(W_Object):
    from pypy.objspace.std.dicttype import dictiter_typedef as typedef

    def __init__(w_self, space, w_dictobject):
        W_Object.__init__(w_self, space)
        w_self.w_dictobject = w_dictobject
        w_self.len = w_dictobject.used
        w_self.pos = 0
        w_self.datapos = 0

    def return_entry(w_self, entry):
        raise NotImplementedError

registerimplementation(W_DictIterObject)

class W_DictIter_Keys(W_DictIterObject):
    def return_entry(w_self, entry):
        return entry.w_key

class W_DictIter_Values(W_DictIterObject):
    def return_entry(w_self, entry):
        return entry.w_value

class W_DictIter_Items(W_DictIterObject):
    def return_entry(w_self, entry):
        return w_self.space.newtuple([entry.w_key, entry.w_value])


def iter__DictIterObject(space, w_dictiter):
    return w_dictiter

def next__DictIterObject(space, w_dictiter):
    w_dict = w_dictiter.w_dictobject
    if w_dict is not None:
        if w_dictiter.len != w_dict.used:
            w_dictiter.len = -1   # Make this error state sticky
            raise OperationError(space.w_RuntimeError,
                     space.wrap("dictionary changed size during iteration"))
        # look for the next entry
        i = w_dictiter.datapos
        data = w_dict.data
        while i < len(data):
            entry = data[i]
            i += 1
            if entry.w_value is not None:
                w_dictiter.pos += 1
                w_dictiter.datapos = i
                return w_dictiter.return_entry(entry)
        # no more entries
        w_dictiter.w_dictobject = None
    raise OperationError(space.w_StopIteration, space.w_None)

def len__DictIterObject(space, w_dictiter):
    w_dict = w_dictiter.w_dictobject
    if w_dict is None or w_dictiter.len == -1 :
        return space.wrap(0)
    return space.wrap(w_dictiter.len - w_dictiter.pos)
# ____________________________________________________________

from pypy.objspace.std import dicttype
register_all(vars(), dicttype)
