"""Snippets for translation

This module holds various snippets, to be used by translator
unittests.

TODO, or sanxiyn's plan:

Each snippet should know about suitable arguments to test it.
(Otherwise, there's a duplcation!) Should the result also be
stored? It can computed by CPython if we don't store it.

In case of typed translation test, we can give input_arg_types
by actually trying type() on arguments.

Each unittest should define a list of functions which it is able
to translate correctly, and import the list for tests. When
a translator can handle more, simply adding a function to the
list should suffice.

But for now, none of the above applies.
"""

# we define the starting types in the snippet 
# function's default arguments.  the following
# definitions denote to the "test-generator"
# the possible types that can be passed to
# the specific snippet. 
numtype = (int, float, ) 
anytype = (int, float, str)
seqtype = (list, tuple) 

def if_then_else(cond=anytype, x=anytype, y=anytype):
    if cond:
        return x
    else:
        return y

def my_gcd(a=numtype, b=numtype):
    r = a % b
    while r:
        a = b
        b = r
        r = a % b
    return b

def is_perfect_number(n=int):
    div = 1
    sum = 0
    while div < n:
        if n % div == 0:
            sum += div
        div += 1
    return n == sum

def my_bool(x=int):
    return not not x

def two_plus_two():
    """Array test"""
    array = [0] * 3
    array[0] = 2
    array[1] = 2
    array[2] = array[0] + array[1]
    return array[2]

def sieve_of_eratosthenes():
    """Sieve of Eratosthenes
    
    This one is from an infamous benchmark, "The Great Computer
    Language Shootout".

    URL is: http://www.bagley.org/~doug/shootout/
    """
    flags = [True] * (8192+1)
    count = 0
    i = 2
    while i <= 8192:
        if flags[i]:
            k = i + i
            while k <= 8192:
                flags[k] = False
                k = k + i
            count = count + 1
        i = i + 1
    return count

def simple_func(i=numtype):
    return i + 1

def while_func(i=numtype):
    total = 0
    while i > 0:
        total = total + i
        i = i - 1
    return total

def nested_whiles(i=int, j=int):
    s = ''
    z = 5
    while z > 0:
        z = z - 1
        u = i
        while u < j:
            u = u + 1
            s = s + '.'
        s = s + '!'
    return s

def poor_man_range(i=int): 
    lst = []
    while i > 0:
        i = i - 1
        lst.append(i)
    lst.reverse()
    return lst

def poor_man_rev_range(i=int): 
    lst = []
    while i > 0:
        i = i - 1
        lst += [i]
    return lst

def simple_id(x=anytype): 
    return x

def branch_id(cond=anytype, a=anytype, b=anytype):
    while 1:
        if cond:
            return a
        else:
            return b

def builtinusage():
    return pow(2, 2)

def yast(lst=seqtype):
    total = 0
    for z in lst:
        total = total + z
    return total

def time_waster(n=int):
    """Arbitrary test function"""
    i = 0
    x = 1
    while i < n:
        j = 0
        while j <= i:
            j = j + 1
            x = x + (i & j)
        i = i + 1
    return x

def half_of_n(n=int):
    """Slice test"""
    i = 0
    lst = range(n)
    while lst:
        lst = lst[1:-1]
        i = i + 1
    return i

def int_id(x=int):
    i = 0
    while i < x:
        i = i + 1
    return i

def greet(target=str):
    """String test"""
    hello = "hello"
    return hello + target

def choose_last():
    """For loop test"""
    set = ["foo", "bar", "spam", "egg", "python"]
    for choice in set:
        pass
    return choice

def poly_branch(x=int):
    if x:
        y = [1,2,3]
    else:
        y = ['a','b','c']

    z = y
    return z*2

def s_and(x=anytype, y=anytype):
    if x and y:
        return 'yes'
    else:
        return 'no'

def break_continue(x=numtype):
    result = []
    i = 0
    while 1:
        i = i + 1
        try:
            if i&1:
                continue
            if i >= x:
                break
        finally:
            result.append(i)
        i = i + 1
    return result

def reverse_3(lst=seqtype):
    try:
        a, b, c = lst
    except:
        return 0, 0, 0
    return c, b, a

def finallys(lst=seqtype):
    x = 1
    try:
        x = 2
        try:
            x = 3
            a, = lst
            x = 4
        except KeyError:
            return 5
        except ValueError:
            return 6
        b, = lst
        x = 7
    finally:
        x = 8
    return x

def factorial(n=int):
    if n <= 1:
        return 1
    else:
        return n * factorial(n-1)

def factorial2(n=int):   # analysed in a different order
    if n > 1:
        return n * factorial(n-1)
    else:
        return 1

def _append_five(lst): 
    lst += [5]

def call_five():
    a = []
    _append_five(a)
    return a

# INHERITANCE / CLASS TESTS  
class C(object): pass

def build_instance():
    c = C()
    return c

def set_attr():
    c = C()
    c.a = 1
    c.a = 2
    return c.a

def merge_setattr(x):
    if x:
        c = C()
        c.a = 1
    else:
        c = C()
    return c.a

class D(C): pass
class E(C): pass

def inheritance1():
    d = D()
    d.stuff = ()
    e = E()
    e.stuff = -12
    e.stuff = 3
    lst = [d, e]
    return d.stuff, e.stuff


def inheritance2():
    d = D()
    d.stuff = (-12, -12)
    e = E()
    e.stuff = (3, "world")
    return _getstuff(d), _getstuff(e)

class F:
    pass
class G(F):
    def m(self, x):
        return self.m2(x)
    def m2(self, x):
        return D(), x
class H(F):
    def m(self, y):
        self.attr = 1
        return E(), y

def knownkeysdict(b=anytype):
    if b:
        d = {'a': 0}
        d['b'] = b
        d['c'] = 'world'
    else:
        d = {'b': -123}
    return d['b']

def prime(n=int):
    return len([i for i in range(1,n+1) if n%i==0]) == 2

class A0:
    pass
class A1(A0):
    clsattr = 123
class A2(A1):
    clsattr = 456
class A3(A2):
    clsattr = 789
class A4(A3):
    pass
class A5(A0):
    clsattr = 101112

def classattribute(flag=int):
    if flag == 1:
        x = A1()
    elif flag == 2:
        x = A2()
    elif flag == 3:
        x = A3()
    elif flag == 4:
        x = A4()
    else:
        x = A5()
    return x.clsattr


class Z:
    def my_method(self):
        return self.my_attribute

class WithInit:
    def __init__(self, n):
        self.a = n

class WithMoreInit(WithInit):
    def __init__(self, n, m):
        WithInit.__init__(self, n)
        self.b = m

def simple_method(v=anytype):
    z = Z()
    z.my_attribute = v
    return z.my_method()

def with_init(v=int):
    z = WithInit(v)
    return z.a

def with_more_init(v=int, w=bool):
    z = WithMoreInit(v, w)

global_z = Z()
global_z.my_attribute = 42

def global_instance():
    return global_z.my_method()


def powerset(setsize=int):
    """Powerset

    This one is from a Philippine Pythonista Hangout, an modified
    version of Andy Sy's code.
    
    list.append is modified to list concatenation, and powerset
    is pre-allocated and stored, instead of printed.
    
    URL is: http://lists.free.net.ph/pipermail/python/2002-November/
    """
    set = range(setsize)
    maxcardinality = pow(2, setsize)
    bitmask = 0L
    powerset = [None] * maxcardinality
    ptr = 0
    while bitmask < maxcardinality:
        bitpos = 1L
        index = 0
        subset = []
        while bitpos < maxcardinality:
            if bitpos & bitmask:
                subset = subset + [set[index]]
            index += 1
            bitpos <<= 1
        powerset[ptr] = subset
        ptr += 1
        bitmask += 1
    return powerset

# --------------------(Currently) Non runnable Functions ---------------------

def _somebug1(n=int):
    l = []
    v = l.append
    while n:
        l[7] = 5 # raises an exception 
        break 
    return v

def _inheritance_nonrunnable():
    d = D()
    d.stuff = (-12, -12)
    e = E()
    e.stuff = (3, "world")
    return C().stuff

# --------------------(Currently) Non compillable Functions ---------------------

def _attrs():
    def b(): pass
    b.f = 4
    b.g = 5
    return b.f + b.g

def _getstuff(x):
    return x.stuff

def _methodcall1(cond):
    if cond:
        x = G()
    else:
        x = H()
    return x.m(42)

