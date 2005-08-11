import struct

class GCError(Exception):
    pass

class FREED_OBJECT(object):
    def __getattribute__(self, attr):
        raise GCError("trying to access freed object")
    def __setattribute__(self, attr, value):
        raise GCError("trying to access freed object")


def free_non_gc_object(obj):
    assert getattr(obj.__class__, "_raw_allocate_", False), "trying to free regular object"
    obj.__dict__ = {}
    obj.__class__ = FREED_OBJECT

