"""
This file defines the 'subset' SomeValue classes.

An instance of a SomeValue class stands for a Python object that has some
known properties, for example that is known to be a list of non-negative
integers.  Each instance can be considered as an object that is only
'partially defined'.  Another point of view is that each instance is a
generic element in some specific subset of the set of all objects.

"""

# Old terminology still in use here and there:
#    SomeValue means one of the SomeXxx classes in this file.
#    Cell is an instance of one of these classes.
#
# Think about cells as potato-shaped circles in a diagram:
#    ______________________________________________________
#   / SomeObject()                                         \
#  /   ___________________________          ______________  \
#  |  / SomeInteger(nonneg=False) \____    / SomeString() \  \
#  | /     __________________________  \   |              |  |
#  | |    / SomeInteger(nonneg=True) \ |   |      "hello" |  |
#  | |    |   0    42       _________/ |   \______________/  |
#  | \ -3 \________________/           /                     |
#  \  \                     -5   _____/                      /
#   \  \________________________/              3.1416       /
#    \_____________________________________________________/
#


from types import ClassType, BuiltinFunctionType, FunctionType
from pypy.annotation.pairtype import pair, extendabletype


class SomeObject:
    """The set of all objects.  Each instance stands
    for an arbitrary object about which nothing is known."""
    __metaclass__ = extendabletype
    knowntype = object
    def __eq__(self, other):
        return (self.__class__ is other.__class__ and
                self.__dict__  == other.__dict__)
    def __ne__(self, other):
        return not (self == other)
    def __repr__(self):
        kwds = ', '.join(['%s=%r' % item for item in self.__dict__.items()])
        return '%s(%s)' % (self.__class__.__name__, kwds)
    def contains(self, other):
        return self == other or pair(self, other).union() == self
    def is_constant(self):
        return hasattr(self, 'const')

class SomeInteger(SomeObject):
    "Stands for an object which is known to be an integer."
    knowntype = int
    def __init__(self, nonneg=False):
        self.nonneg = nonneg

class SomeBool(SomeInteger):
    "Stands for true or false."
    knowntype = bool
    nonneg = True
    def __init__(self):
        pass

class SomeString(SomeObject):
    "Stands for an object which is known to be a string."
    knowntype = str

class SomeList(SomeObject):
    "Stands for a homogenous list of any length."
    knowntype = list
    def __init__(self, factories, s_item=SomeObject()):
        self.factories = factories
        self.s_item = s_item     # general enough for any element

class SomeTuple(SomeObject):
    "Stands for a tuple of known length."
    knowntype = tuple
    def __init__(self, items):
        self.items = tuple(items)   # tuple of s_xxx elements

class SomeClass(SomeObject):
    "Stands for a user-defined class object."
    # only used when the class object is loaded in a variable
    knowntype = ClassType
    def __init__(self, cls):
        self.cls = cls

class SomeInstance(SomeObject):
    "Stands for an instance of a (user-defined) class."
    def __init__(self, classdef):
        self.classdef = classdef
        self.knowntype = classdef.cls
        self.revision = classdef.revision

class SomeBuiltin(SomeObject):
    "Stands for a built-in function or method with special-cased analysis."
    knowntype = BuiltinFunctionType  # == BuiltinMethodType
    def __init__(self, analyser):
        self.analyser = analyser

class SomeFunction(SomeObject):
    "Stands for a Python function (or some function out of a list)."
    knowntype = FunctionType
    def __init__(self, funcs):
        self.funcs = funcs   # set of functions that this one may be

class SomeImpossibleValue(SomeObject):
    """The empty set.  Instances are placeholders for objects that
    will never show up at run-time, e.g. elements of an empty list."""


def immutablevalue(x):
    "The most precise SomeValue instance that contains the immutable value x."
    if isinstance(bool, type) and isinstance(x, bool):
        result = SomeBool()
    elif isinstance(x, int):
        result = SomeInteger(nonneg = x>=0)
    elif isinstance(x, str):
        result = SomeString()
    elif isinstance(x, tuple):
        result = SomeTuple(items = [immutablevalue(e) for e in x])
    elif x in BUILTIN_FUNCTIONS:
        result = SomeBuiltin(BUILTIN_FUNCTIONS[x])
    elif isinstance(x, (type, ClassType)) and x.__module__ != '__builtin__':
        result = SomeClass(x)
    elif isinstance(x, FunctionType):
        result = SomeFunction({x: True})
    else:
        result = SomeObject()
    result.const = x
    return result

def valueoftype(t):
    "The most precise SomeValue instance that contains all objects of type t."
    if isinstance(bool, type) and issubclass(t, bool):
        return SomeBool()
    elif issubclass(t, int):
        return SomeInteger()
    elif issubclass(t, str):
        return SomeString()
    elif issubclass(t, list):
        return SomeList(factories={})
    else:
        return SomeObject()

def decode_simple_call(s_args, s_kwds):
    s_nbargs = s_args.len()
    if not s_nbargs.is_constant():
        return None
    nbargs = s_nbargs.const
    arglist = [pair(s_args, immutablevalue(j)).getitem()
               for j in range(nbargs)]
##        nbkwds = self.heap.get(ANN.len, varkwds_cell)
##        if nbkwds != 0:
##            return None  # XXX deal with dictionaries with constant keys
    return arglist


# ____________________________________________________________
# internal

def setunion(d1, d2):
    "Union of two sets represented as dictionaries."
    d = d1.copy()
    d.update(d2)
    return d

def set(it):
    "Turn an iterable into a set."
    d = {}
    for x in it:
        d[x] = True
    return d

def missing_operation(cls, name):
    def default_op(*args):
        #print '* warning, no type available for %s(%s)' % (
        #    name, ', '.join([repr(a) for a in args]))
        return SomeObject()
    setattr(cls, name, default_op)

# this has the side-effect of registering the unary and binary operations
from pypy.annotation.unaryop  import UNARY_OPERATIONS
from pypy.annotation.binaryop import BINARY_OPERATIONS
from pypy.annotation.builtin  import BUILTIN_FUNCTIONS
