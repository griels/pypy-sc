import autopath

from pypy.objspace.std.multimethod import *

BoundMultiMethod.ASSERT_BASE_TYPE = object


objspacename = 'std'

class X:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return '<X %r>' % self.value

def from_y_to_x(space, yinstance):
    return X(yinstance)

from_y_to_x.result_class = X
from_y_to_x.priority = 2

def from_x_to_str(space, xinstance):
    #if xinstance.value:
    return w('!' + repr(xinstance.value))
    #else:
    #    return []

from_x_to_str.result_class = str
from_x_to_str.priority = 2


class Y:
    def __init__(self, value):
        self.value = value
    def __repr__(self):
        return '<Y %r>' % self.value
    def __nonzero__(self):
        return self.value != 666


def add_x_x(space, x1, x2):
    return "add_x_x", x1, x2

def add_x_y(space, x1, y2):
    if x1.value < 0:
        raise FailedToImplement(ValueError, 'not good')
    return "add_x_y", x1, y2

def add_y_y(space, y1, y2):
    return "add_y_y", y1, y2

def add_string_string(space, x, y):
    return "add_string_string", x, y

def add_int_string(space, x, y):
    return "add_int_string", x, y

def add_int_any(space, y1, o2):
    return "add_int_any", y1, o2

class FakeObjSpace:
    add = MultiMethod('+', 2, [])
    add.register(add_x_x,           X,   X)
    add.register(add_x_y,           X,   Y)
    add.register(add_y_y,           Y,   Y)
    add.register(add_string_string, str, str)
    add.register(add_int_string,    int, str)
    add.register(add_int_any,       int, object)

    delegate = DelegateMultiMethod()
    delegate.register(from_y_to_x,    Y)
    delegate.register(from_x_to_str,  X)
    
    def wrap(self, x):
        return '<wrapped %r>' % (x,)
    w_TypeError = 'w_TypeError'

##def w(x, cache={}):
##    if type(x) in cache:
##        Stub = cache[type(x)]
##    else:
##        Stub = type(type(x))('%s_stub' % type(x).__name__, (type(x),), {})
##        Stub.dispatchclass = Stub
##        cache[type(x)] = Stub
##    return Stub(x)

##X.dispatchclass = X
##Y.dispatchclass = Y

def w(x):
    return x


class TestMultiMethod:
    def setup_method(self,method):
        # only run when testing stdobjectspace 
        #XXX removed: self.space
        self.space = FakeObjSpace()

    def test_non_delegate(self):
        space = self.space
        
        r = space.add(X(2), X(5))
        assert repr(r) == "('add_x_x', <X 2>, <X 5>)"
        
        r = space.add(X(3), Y(4))
        assert repr(r) == "('add_x_y', <X 3>, <Y 4>)"

        r = space.add(Y(0), Y(20))
        assert repr(r) == "('add_y_y', <Y 0>, <Y 20>)"

        r = space.add(w(-3), w([7,6,5]))
        assert repr(r) == "('add_int_any', -3, [7, 6, 5])"

        r = space.add(w(5), w("test"))
        assert repr(r) == "('add_int_string', 5, 'test')"

        r = space.add(w("x"), w("y"))
        assert repr(r) == "('add_string_string', 'x', 'y')"
        
    def test_delegate_y_to_x(self):
        space = self.space
        r = space.add(Y(-1), X(7))
        assert repr(r) == "('add_x_x', <X <Y -1>>, <X 7>)"
        
        r = space.add(Y(1), X(7))
        assert repr(r) == "('add_x_x', <X <Y 1>>, <X 7>)"
        
        r = space.add(X(-3), Y(20))
        assert repr(r) == "('add_x_x', <X -3>, <X <Y 20>>)"
       
    def test_no_operation_defined(self):
        space = self.space
        raises(OperationError, space.add, w([3]), w(4))
        raises(OperationError, space.add, w(3.0), w('bla'))
        #raises(OperationError, space.add, X(0), w("spam"))
        #raises(OperationError, space.add, Y(666), w("egg"))

    def test_delegate_x_to_str(self):
        space = self.space
        r = space.add(X(42), w("spam"))
        assert repr(r) == "('add_string_string', '!42', 'spam')"

        r = space.add(Y(20), w("egg"))
        assert repr(r) == "('add_string_string', '!<Y 20>', 'egg')"
