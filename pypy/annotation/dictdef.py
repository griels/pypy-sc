from pypy.annotation.model import SomeObject, SomeImpossibleValue
from pypy.annotation.model import SomeInteger, SomeBool, unionof
from pypy.annotation.listdef import ListItem


class DictKey(ListItem):
    custom_eq_hash = False
    pending_emulated_calls = ()

    def patch(self):
        for dictdef in self.itemof:
            dictdef.dictkey = self

    def merge(self, other):
        if self is not other:
            assert self.custom_eq_hash == other.custom_eq_hash, (
                "mixing plain dictionaries with r_dict()")
            ListItem.merge(self, other)
            if self.custom_eq_hash:
                self.update_rdict_annotations(other.s_rdict_eqfn,
                                              other.s_rdict_hashfn,
                                              other=other)

    def generalize(self, s_other_value):
        updated = ListItem.generalize(self, s_other_value)
        if self.custom_eq_hash and (updated or self.pending_emulated_calls):
            self.emulate_rdict_calls()
        return updated

    def update_rdict_annotations(self, s_eqfn, s_hashfn, other=None):
        if not self.custom_eq_hash:
            self.custom_eq_hash = True
        else:
            s_eqfn = unionof(s_eqfn, self.s_rdict_eqfn)
            s_hashfn = unionof(s_hashfn, self.s_rdict_hashfn)
        self.s_rdict_eqfn = s_eqfn
        self.s_rdict_hashfn = s_hashfn
        self.emulate_rdict_calls(other=other)

    def emulate_rdict_calls(self, other=None):
        # hackish: cannot emulate a call if we are not currently handling
        # an operation
        # (e.g. a link or a prebuilt constant coming from somewhere,
        # as in rpython.test.test_objectmodel.test_rtype_constant_r_dicts)
        if not hasattr(self.bookkeeper, 'position_key'):
            self.pending_emulated_calls += (other,)
            return

        myeq = (self, 'eq')
        myhash = (self, 'hash')
        replace_othereq = []
        replace_otherhash = []
        for other in self.pending_emulated_calls + (other,):
            if other:
                replace_othereq.append((other, 'eq'))
                replace_otherhash.append((other, 'hash'))
        self.pending_emulated_calls = ()

        s_key = self.s_value
        s1 = self.bookkeeper.emulate_pbc_call(myeq, self.s_rdict_eqfn, [s_key, s_key],
                                              replace=replace_othereq)
        assert SomeBool().contains(s1), (
            "the custom eq function of an r_dict must return a boolean"
            " (got %r)" % (s1,))
        s2 = self.bookkeeper.emulate_pbc_call(myhash, self.s_rdict_hashfn, [s_key],
                                              replace=replace_otherhash)
        assert SomeInteger().contains(s2), (
            "the custom hash function of an r_dict must return an integer"
            " (got %r)" % (s2,))


class DictValue(ListItem):
    def patch(self):
        for dictdef in self.itemof:
            dictdef.dictvalue = self


class DictDef:
    """A dict definition remembers how general the keys and values in that
    particular dict have to be.  Every dict creation makes a new DictDef,
    and the union of two dicts merges the DictKeys and DictValues that each
    DictDef stores."""

    def __init__(self, bookkeeper, s_key = SomeImpossibleValue(),
                                 s_value = SomeImpossibleValue()):
        self.dictkey = DictKey(bookkeeper, s_key)
        self.dictkey.itemof[self] = True
        self.dictvalue = DictValue(bookkeeper, s_value)
        self.dictvalue.itemof[self] = True
        self.bookkeeper = bookkeeper

    def read_key(self, position_key=None):
        if position_key is None:
            if self.bookkeeper is None:   # for tests
                from pypy.annotation.bookkeeper import getbookkeeper
                position_key = getbookkeeper().position_key
            else:
                position_key = self.bookkeeper.position_key
        self.dictkey.read_locations[position_key] = True
        if self.dictkey.pending_emulated_calls:
            self.dictkey.emulate_rdict_calls()
        return self.dictkey.s_value

    def read_value(self, position_key=None):
        if position_key is None:
            if self.bookkeeper is None:   # for tests
                from pypy.annotation.bookkeeper import getbookkeeper
                position_key = getbookkeeper().position_key
            else:
                position_key = self.bookkeeper.position_key
        self.dictvalue.read_locations[position_key] = True
        return self.dictvalue.s_value

    def same_as(self, other):
        return (self.dictkey is other.dictkey and
                self.dictvalue is other.dictvalue)

    def union(self, other):
        if (self.same_as(MOST_GENERAL_DICTDEF) or
            other.same_as(MOST_GENERAL_DICTDEF)):
            return MOST_GENERAL_DICTDEF   # without merging
        else:
            self.dictkey.merge(other.dictkey)
            self.dictvalue.merge(other.dictvalue)
            return self

    def generalize_key(self, s_key):
        self.dictkey.generalize(s_key)

    def generalize_value(self, s_value):
        self.dictvalue.generalize(s_value)

    def __repr__(self):
        return '<{%r: %r}>' % (self.dictkey.s_value, self.dictvalue.s_value)


MOST_GENERAL_DICTDEF = DictDef(None, SomeObject(), SomeObject())
