"""
Plain Python definition of the builtin functions related to run-time
program introspection.
"""

import sys

def globals():
    "Return the dictionary containing the current scope's global variables."
    return sys._getframe(0).f_globals

def locals():
    """Return a dictionary containing the current scope's local variables.
Note that this may be the real dictionary of local variables, or a copy."""
    return sys._getframe(0).f_locals

def _caller_locals(): 
    return sys._getframe(0).f_locals 

def _recursive_issubclass(cls, klass_or_tuple):
    if cls is klass_or_tuple:
        return True
    for base in getattr(cls, '__bases__', ()):
        if _recursive_issubclass(base, klass_or_tuple):
            return True
    return False

def _issubclass(cls, klass_or_tuple, check_cls, depth):
    if depth == 0:
        # XXX overzealous test compliance hack
        raise RuntimeError,"maximum recursion depth excedeed"
    if _issubtype(type(klass_or_tuple), tuple):
        for klass in klass_or_tuple:
            if _issubclass(cls, klass, True, depth-1):
                return True
        return False
    try:
        return _issubtype(cls, klass_or_tuple)
    except TypeError:
        if check_cls and not hasattr(cls, '__bases__'):
            raise TypeError, "arg 1 must be a class or type"
        if not hasattr(klass_or_tuple, '__bases__'):
            raise TypeError, "arg 2 must be a class or type or a tuple thereof"
        return _recursive_issubclass(cls, klass_or_tuple)

def issubclass(cls, klass_or_tuple):
    """Check whether a class 'cls' is a subclass (i.e., a derived class) of
another class.  When using a tuple as the second argument, check whether
'cls' is a subclass of any of the classes listed in the tuple."""
    import sys
    return _issubclass(cls, klass_or_tuple, True, sys.getrecursionlimit())

def isinstance(obj, klass_or_tuple):
    """Check whether an object is an instance of a class (or of a subclass
thereof).  When using a tuple as the second argument, check whether 'obj'
is an instance of any of the classes listed in the tuple."""
    if issubclass(type(obj), klass_or_tuple):
        return True
    try:
        objcls = obj.__class__
    except AttributeError:
        return False
    else:
        import sys
        return (objcls is not type(obj) and
                _issubclass(objcls, klass_or_tuple, False, sys.getrecursionlimit()))


def vars(*obj):
    """Return a dictionary of all the attributes currently bound in obj.  If
    called with no argument, return the variables bound in local scope."""

    if len(obj) == 0:
        return _caller_locals()
    elif len(obj) != 1:
        raise TypeError, "vars() takes at most 1 argument."
    else:
        try:
            return obj[0].__dict__
        except AttributeError:
            raise TypeError, "vars() argument must have __dict__ attribute"

def hasattr(obj, attr):
    """Check whether the object has an attribute with the given name."""
    try:
        getattr(obj, attr)
        return True
    except TypeError:
        # if 'attr' was not a string or unicode, let the TypeError through,
        # else eat it
        if isinstance(attr, basestring):
            return False
        else:
            raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        return False

# Replaced by the interp-level helper space.callable(): 
##def callable(ob):
##    import __builtin__ # XXX this is insane but required for now for geninterp
##    for c in type(ob).__mro__:
##        if '__call__' in c.__dict__:
##            if isinstance(ob, __builtin__._instance): # old style instance!
##                return getattr(ob, '__call__', None) is not None
##            return True
##    else:
##        return False

def dir(*args):
    """dir([object]) -> list of strings

    Return an alphabetized list of names comprising (some of) the attributes
    of the given object, and of attributes reachable from it:

    No argument:  the names in the current scope.
    Module object:  the module attributes.
    Type or class object:  its attributes, and recursively the attributes of
        its bases.
    Otherwise:  its attributes, its class's attributes, and recursively the
        attributes of its class's base classes.
    """
    if len(args) > 1:
        raise TypeError("dir expected at most 1 arguments, got %d"
                        % len(args))
    if len(args) == 0:
        local_names = _caller_locals().keys() # 2 stackframes away
        if not isinstance(local_names, list):
            raise TypeError("expected locals().keys() to be a list")
        local_names.sort()
        return local_names

    import types

    obj = args[0]

    if isinstance(obj, types.ModuleType):
        try:
            result = obj.__dict__.keys()
            if not isinstance(result, list):
                raise TypeError("expected __dict__.keys() to be a list")
            result.sort()
            return result
        except AttributeError:
            return []

    elif isinstance(obj, (types.TypeType, types.ClassType)):
        #Don't look at __class__, as metaclass methods would be confusing.
        result = _classdir(obj).keys()
        result.sort()
        return result

    else: #(regular item)
        Dict = {}
        try:
            Dict.update(obj.__dict__)
        except AttributeError: pass
        try:
            Dict.update(_classdir(obj.__class__))
        except AttributeError: pass

        ## Comment from object.c:
        ## /* Merge in __members__ and __methods__ (if any).
        ## XXX Would like this to go away someday; for now, it's
        ## XXX needed to get at im_self etc of method objects. */
        for attr in ['__members__','__methods__']:
            try:
                for item in getattr(obj, attr):
                    if isinstance(item, types.StringTypes):
                        Dict[item] = None
            except (AttributeError, TypeError): pass

        result = Dict.keys()
        result.sort()
        return result

def _classdir(klass):
    """Return a dict of the accessible attributes of class/type klass.

    This includes all attributes of klass and all of the
    base classes recursively.

    The values of this dict have no meaning - only the keys have
    meaning.  
    """
    Dict = {}
    try:
        Dict.update(klass.__dict__)
    except AttributeError: pass 
    try:
        # XXX - Use of .__mro__ would be suggested, if the existance
        #   of that attribute could be guarranted.
        bases = klass.__bases__
    except AttributeError: pass
    else:
        try:
            #Note that since we are only interested in the keys,
            #  the order we merge classes is unimportant
            for base in bases:
                Dict.update(_classdir(base))
        except TypeError: pass
    return Dict
