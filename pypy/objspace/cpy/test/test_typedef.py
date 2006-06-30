import py
import py.test
from pypy.interpreter.error import OperationError
from pypy.interpreter.baseobjspace import Wrappable
from pypy.interpreter.typedef import TypeDef
from pypy.interpreter.typedef import interp_attrproperty, GetSetProperty
from pypy.interpreter.gateway import interp2app, ObjSpace, W_Root
from pypy.interpreter.function import BuiltinFunction
from pypy.objspace.cpy.ann_policy import CPyAnnotatorPolicy
from pypy.objspace.cpy.objspace import CPyObjSpace, W_Object
from pypy.translator.c.test.test_genc import compile


class W_MyType(Wrappable):
    def __init__(self, space, x=1):
        self.space = space
        self.x = x

    def multiply(self, w_y):
        space = self.space
        y = space.int_w(w_y)
        return space.wrap(self.x * y)

    def fget_x(space, self):
        return space.wrap(self.x)

    def fset_x(space, self, w_value):
        self.x = space.int_w(w_value)


def test_direct():
    W_MyType.typedef = TypeDef("MyType")
    space = CPyObjSpace()
    x = W_MyType(space)
    y = W_MyType(space)
    w_x = space.wrap(x)
    w_y = space.wrap(y)
    assert space.interp_w(W_MyType, w_x) is x
    assert space.interp_w(W_MyType, w_y) is y
    py.test.raises(OperationError, "space.interp_w(W_MyType, space.wrap(42))")


def test_get_blackbox():
    W_MyType.typedef = TypeDef("MyType")
    space = CPyObjSpace()

    def make_mytype():
        return space.wrap(W_MyType(space))
    fn = compile(make_mytype, [],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res = fn(expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType'


def test_get_blackboxes():
    py.test.skip("a bug with specialize:wrap?")
    W_MyType.typedef = TypeDef("MyType")

    class W_MyType2(Wrappable):
        def __init__(self, space, x=1):
            self.space = space
            self.x = x
    W_MyType2.typedef = TypeDef("MyType2")
    space = CPyObjSpace()

    def make_mytype(n):
        if n:
            return space.wrap(W_MyType2(space))
        else:
            return space.wrap(W_MyType(space))
    fn = compile(make_mytype, [int],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res = fn(1, expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType'
    res = fn(0, expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType2'


def test_blackbox():
    W_MyType.typedef = TypeDef("MyType")
    space = CPyObjSpace()

    def mytest(w_myobj):
        myobj = space.interp_w(W_MyType, w_myobj, can_be_None=True)
        if myobj is None:
            myobj = W_MyType(space)
            myobj.abc = 1
        myobj.abc *= 2
        w_myobj = space.wrap(myobj)
        w_abc = space.wrap(myobj.abc)
        return space.newtuple([w_myobj, w_abc])

    def fn(obj):
        w_obj = W_Object(obj)
        w_res = mytest(w_obj)
        return w_res.value
    fn.allow_someobjects = True

    fn = compile(fn, [object],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res, abc = fn(None, expected_extra_mallocs=1)
    assert abc == 2
    assert type(res).__name__ == 'MyType'

    res2, abc = fn(res, expected_extra_mallocs=1)
    assert abc == 4
    assert res2 is res

    res2, abc = fn(res, expected_extra_mallocs=1)
    assert abc == 8
    assert res2 is res

    res2, abc = fn(res, expected_extra_mallocs=1)
    assert abc == 16
    assert res2 is res


def test_class_attr():
    W_MyType.typedef = TypeDef("MyType",
                               hello = 7)
    space = CPyObjSpace()

    def make_mytype():
        return space.wrap(W_MyType(space))
    fn = compile(make_mytype, [],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res = fn(expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType'
    assert res.hello == 7
    assert type(res).hello == 7


def test_method():
    W_MyType.typedef = TypeDef("MyType",
                               multiply = interp2app(W_MyType.multiply))
    space = CPyObjSpace()
    assert space.int_w(W_MyType(space, 6).multiply(space.wrap(7))) == 42

    def make_mytype():
        return space.wrap(W_MyType(space, 123))
    fn = compile(make_mytype, [],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res = fn(expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType'
    assert res.multiply(3) == 369


def test_interp_attrproperty():
    W_MyType.typedef = TypeDef("MyType",
                               x = interp_attrproperty("x", W_MyType))
    space = CPyObjSpace()

    def mytest(w_myobj):
        myobj = space.interp_w(W_MyType, w_myobj, can_be_None=True)
        if myobj is None:
            myobj = W_MyType(space)
            myobj.x = 1
        myobj.x *= 2
        w_myobj = space.wrap(myobj)
        w_x = space.wrap(myobj.x)
        return space.newtuple([w_myobj, w_x])

    def fn(obj):
        w_obj = W_Object(obj)
        w_res = mytest(w_obj)
        return w_res.value
    fn.allow_someobjects = True

    fn = compile(fn, [object],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res, x = fn(None, expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType'
    assert x == 2
    assert res.x == 2

    res2, x = fn(res, expected_extra_mallocs=1)
    assert res2 is res
    assert x == 4
    assert res.x == 4


def test_getset():
    getset_x = GetSetProperty(W_MyType.fget_x, W_MyType.fset_x, cls=W_MyType)
    W_MyType.typedef = TypeDef("MyType",
                               x = getset_x)
    space = CPyObjSpace()

    def mytest(w_myobj):
        myobj = space.interp_w(W_MyType, w_myobj, can_be_None=True)
        if myobj is None:
            myobj = W_MyType(space)
            myobj.x = 1
        myobj.x *= 2
        w_myobj = space.wrap(myobj)
        w_x = space.wrap(myobj.x)
        return space.newtuple([w_myobj, w_x])

    def fn(obj):
        w_obj = W_Object(obj)
        w_res = mytest(w_obj)
        return w_res.value
    fn.allow_someobjects = True

    fn = compile(fn, [object],
                 annotatorpolicy = CPyAnnotatorPolicy(space))

    res, x = fn(None, expected_extra_mallocs=1)
    assert type(res).__name__ == 'MyType'
    assert x == 2
    assert res.x == 2
    res.x += 100
    assert res.x == 102

    res2, x = fn(res, expected_extra_mallocs=1)
    assert res2 is res
    assert x == 204
    assert res.x == 204
