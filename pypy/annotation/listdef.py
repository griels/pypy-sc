from pypy.annotation.model import SomeObject, SomeImpossibleValue, unionof


class ListItem:

    def __init__(self, bookkeeper, s_value):
        self.s_value = s_value
        self.bookkeeper = bookkeeper
        self.itemof = {}  # set of all ListDefs using this ListItem
        self.read_locations = {}

    def merge(self, other):
        if self is not other:
            self.itemof.update(other.itemof)
            self.read_locations.update(other.read_locations)
            self.patch()    # which should patch all refs to 'other'
            self.generalize(other.s_value)

    def patch(self):
        for listdef in self.itemof:
            listdef.listitem = self

    def generalize(self, s_other_value):
        s_new_value = unionof(self.s_value, s_other_value)
        if s_new_value != self.s_value:
            self.s_value = s_new_value
            # reflow from all reading points
            for position_key in self.read_locations:
                self.bookkeeper.annotator.reflowfromposition(position_key)


class ListDef:
    """A list definition remembers how general the items in that particular
    list have to be.  Every list creation makes a new ListDef, and the union
    of two lists merges the ListItems that each ListDef stores."""

    def __init__(self, bookkeeper, s_item=SomeImpossibleValue()):
        self.listitem = ListItem(bookkeeper, s_item)
        self.listitem.itemof[self] = True
        self.bookkeeper = bookkeeper

    def read_item(self, position_key=None):
        if position_key is None:
            if self.bookkeeper is None:   # for tests
                from pypy.annotation.bookkeeper import getbookkeeper
                position_key = getbookkeeper().position_key
            else:
                position_key = self.bookkeeper.position_key
        self.listitem.read_locations[position_key] = True
        return self.listitem.s_value

    def same_as(self, other):
        return self.listitem is other.listitem

    def union(self, other):
        if (self.same_as(MOST_GENERAL_LISTDEF) or
            other.same_as(MOST_GENERAL_LISTDEF)):
            return MOST_GENERAL_LISTDEF   # without merging
        else:
            self.listitem.merge(other.listitem)
            return self

    def generalize(self, s_value):
        self.listitem.generalize(s_value)


MOST_GENERAL_LISTDEF = ListDef(None, SomeObject())
