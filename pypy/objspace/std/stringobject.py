from pypy.objspace.std.objspace import *
from intobject   import W_IntObject
from sliceobject import W_SliceObject
from listobject import W_ListObject
from instmethobject import W_InstMethObject
from pypy.interpreter.extmodule import make_builtin_func


applicationfile = StdObjSpace.AppFile(__name__)

class W_StringObject(W_Object):
    def __init__(w_self, space, str):
        W_Object.__init__(w_self, space)
        w_self.value = str
    def __repr__(w_self):
        """ representation for debugging purposes """
        return "%s(%r)" % (w_self.__class__.__name__, w_self.value)
    def nonzero(w_self):
        return W_IntObject(w_self.space, w_self.value != 0)
    def hash(w_self):
        return W_IntObject(w_self, hash(w_self.value))

    def join(w_self, w_list):
        firstelem = 1
        res = ""
        for w_item in w_list.wrappeditems:
            if firstelem:
                res = w_item.value    
                firstelem = 0
            else:
                res = res + w_self.value + w_item.value
        return W_StringObject(w_self.space, res)

    def split(w_self, w_by=None):
        res = []
        inword = 0
        for ch in w_self.value:
            if ch==w_by.value or w_by is None and ch.isspace():
                if inword:
                    inword = 0
                elif w_by is not None:
                    res.append('')
            else:
                if inword:
                    res[-1] += ch
                else:
                    res.append(ch)
                    inword = 1
        for i in range(len(res)):
            res[i] = W_StringObject(w_self.space, res[i])
        return W_ListObject(w_self.space, res)

def getattr_str(space, w_list, w_attr):
    if space.is_true(space.eq(w_attr, space.wrap('join'))):
        w_builtinfn = make_builtin_func(space, W_StringObject.join)
        return W_InstMethObject(space, w_list, w_builtinfn)
    elif space.is_true(space.eq(w_attr, space.wrap('split'))):
        w_builtinfn = make_builtin_func(space, W_StringObject.split)
        return W_InstMethObject(space, w_list, w_builtinfn)
    raise FailedToImplement(space.w_AttributeError)

StdObjSpace.getattr.register(getattr_str, W_StringObject, W_ANY)


def str_unwrap(space, w_str):
    return w_str.value

StdObjSpace.unwrap.register(str_unwrap, W_StringObject)

def str_str_lt(space, w_str1, w_str2):
    i = w_str1.value
    j = w_str2.value
    return space.newbool( i < j )
StdObjSpace.lt.register(str_str_lt, W_StringObject, W_StringObject)

def str_str_le(space, w_str1, w_str2):
    i = w_str1.value
    j = w_str2.value
    return space.newbool( i <= j )
StdObjSpace.le.register(str_str_le, W_StringObject, W_StringObject)

def str_str_eq(space, w_str1, w_str2):
    i = w_str1.value
    j = w_str2.value
    return space.newbool( i == j )
StdObjSpace.eq.register(str_str_eq, W_StringObject, W_StringObject)

def str_str_ne(space, w_str1, w_str2):
    i = w_str1.value
    j = w_str2.value
    return space.newbool( i != j )
StdObjSpace.ne.register(str_str_ne, W_StringObject, W_StringObject)

def str_str_gt(space, w_str1, w_str2):
    i = w_str1.value
    j = w_str2.value
    return space.newbool( i > j )
StdObjSpace.gt.register(str_str_gt, W_StringObject, W_StringObject)

def str_str_ge(space, w_str1, w_str2):
    i = w_str1.value
    j = w_str2.value
    return space.newbool( i >= j )
StdObjSpace.ge.register(str_str_ge, W_StringObject, W_StringObject)


def getitem_str_int(space, w_str, w_int):
    return W_StringObject(space, w_str.value[w_int.intval])

StdObjSpace.getitem.register(getitem_str_int, 
                             W_StringObject, W_IntObject)

def getitem_str_slice(space, w_str, w_slice):
    return applicationfile.call(space, "getitem_string_slice", [w_str, w_slice])

StdObjSpace.getitem.register(getitem_str_slice, 
                                W_StringObject, W_SliceObject)

def add_str_str(space, w_left, w_right):
    return W_StringObject(space, w_left.value + w_right.value)

StdObjSpace.add.register(add_str_str, W_StringObject, W_StringObject)

def mod_str_ANY(space, w_left, w_right):
    notImplemented
 
def mod_str_tuple(space, w_format, w_args):
    notImplemented

def len_str(space, w_str):
    return space.wrap(len(w_str.value))

StdObjSpace.len.register(len_str, W_StringObject)

def str_str(space, w_str):
    return w_str

StdObjSpace.str.register(str_str, W_StringObject)
