from pypy.translator.cl.buildcl import make_cl_func, generate_cl_func

def test_simple():
    class C:
        pass
    def new_get_set():
        obj = C()
        obj.answer = 42
        return obj.answer
    cl_new_get_set = make_cl_func(new_get_set)
    assert cl_new_get_set() == 42

def test_inc():
    class IntHolder:
        def __init__(self, number):
            self.number = number
        def inc(self):
            self.number += 1
        def get(self):
            return self.number
    def inc(number):
        obj = IntHolder(number)
        obj.inc()
        return obj.get()
    cl_inc = make_cl_func(inc, [int])
    assert cl_inc(5) == 6

def test_inherit():
    class Foo:
        pass
    class Bar(Foo):
        pass
    def check_inheritance():
        obj = Bar()
    code = generate_cl_func(check_inheritance)
    print code
    assert code.count("defclass") == 2

def test_isinstance():
    class Foo:
        pass
    class Bar(Foo):
        pass
    class Baz(Foo):
        pass
    def check_isinstance(flag):
        if flag:
            obj = Bar()
        else:
            obj = Baz()
        return isinstance(obj, Bar)
    cl_check_isinstance = make_cl_func(check_isinstance, [bool])
    assert cl_check_isinstance(True) == True

def test_list_length():
    def list_length_one(number):
        lst = [number]
        return len(lst)
    cl_list_length_one = make_cl_func(list_length_one, [int])
    assert cl_list_length_one(0) == 1

def test_list_get():
    def list_and_get(number):
        lst = [number]
        return lst[0]
    cl_list_and_get = make_cl_func(list_and_get, [int])
    assert cl_list_and_get(1985) == 1985
