import types

class SomeValue:
    pass

def debugname(someval, _seen = {}):
    """ return a simple name for a SomeValue. """
    try:
        return _seen[id(someval)]
    except KeyError:
        if not _seen:
            for name, value in globals().items():
                if isinstance(value, SomeValue):
                    _seen[id(value)] = name
            return debugname(someval)
        name = "X%d" % len(seen)
        _seen[id(someval)] = name
        return name

class Predicate:
    def __init__(self, name, arity):
        self.name = name
        self.arity = arity
    def __getitem__(self, args):
        if self.arity == 1:
            args = (args,)
        return Annotation(self, *args)
    def __str__(self):
        return self.name

class ConstPredicate(Predicate):
    def __init__(self, value):
        Predicate.__init__(self, 'const%s' % value, 1)
        self.value = value
    def __eq__(self, other):
        return self.__class__ is other.__class__ and self.value == other.value
    def __ne__(self, other):
        return not (self == other)
    def __hash__(self):
        return hash(self.value)

class ann:
    add = Predicate('add', 3)
    snuff = Predicate('snuff', 2)   # for testing, to remove :-)
    constant = ConstPredicate
    type = Predicate('type', 2)
    immutable = Predicate('immutable', 1)

class Annotation:
    """An Annotation asserts something about SomeValues.  
       It is a Predicate applied to some arguments. """
    
    def __init__(self, predicate, *args):
        self.predicate = predicate      # the operation or predicate
        self.args      = list(args)     # list of SomeValues
        assert len(args) == predicate.arity
        # note that for predicates that are simple operations like
        # op.add, the result is stored as the last argument.
        for someval in args:
            assert someval is Ellipsis or isinstance(someval, SomeValue)  # bug catcher

    def copy(self, renameargs={}):
        args = [renameargs.get(arg, arg) for arg in self.args]
        return Annotation(self.predicate, *args)

    def __repr__(self):
        return "Annotation(%s, %s)" % (
                self.predicate, ", ".join(map(repr, self.args)))


immutable_types = {
    int: 'int',
    long: 'long',
    tuple: 'tuple',
    str: 'str',
    bool: 'bool',
    types.FunctionType: 'function',
    }

# a conventional value for representing 'all Annotations match this one' 
blackholevalue = SomeValue()

# a few values representing 'any value of the given type'
# the following loops creates intvalue, strvalue, etc.
basicannotations = []
for _type, _name in immutable_types.items():
    _val = globals()['%svalue' % _name] = SomeValue()
    _tval = SomeValue()
    basicannotations.append(ann.type[_val, _tval])
    basicannotations.append(ann.constant(_type)[_tval])
    basicannotations.append(ann.immutable[_val])
