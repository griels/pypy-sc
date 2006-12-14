from pypy.rlib.rctypes.implementation import CTypeController, getcontroller
from pypy.rlib.rctypes import rctypesobject
from pypy.rpython.lltypesystem import lltype

from ctypes import ARRAY, c_int, c_char


ArrayType = type(ARRAY(c_int, 10))


class ArrayCTypeController(CTypeController):

    def __init__(self, ctype):
        CTypeController.__init__(self, ctype)
        self.itemcontroller = getcontroller(ctype._type_)
        self.length = ctype._length_
        self.knowntype = rctypesobject.RFixedArray(
            self.itemcontroller.knowntype,
            self.length)

    def new(self, *args_s):
        if len(args_s) > self.length:
            raise ValueError("too many arguments for an array of length %d" % (
                self.length,))
        obj = self.knowntype.allocate()
        if len(args_s) > 0:
            lst_s = list(args_s)
            for i in range(len(args_s)):
                self.setitem(obj, i, lst_s[i])
        return obj
    new._annspecialcase_ = 'specialize:arg(0)'

    def getitem(self, obj, i):
        itemobj = obj.ref(i)
        return self.itemcontroller.return_value(itemobj)
    getitem._annspecialcase_ = 'specialize:arg(0)'

    def setitem(self, obj, i, value):
        itemobj = obj.ref(i)
        self.itemcontroller.set_value(itemobj, value)
    setitem._annspecialcase_ = 'specialize:arg(0)'


ArrayCTypeController.register_for_metatype(ArrayType)
