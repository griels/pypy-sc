from pypy.interpreter import eval, function, gateway
from pypy.interpreter.error import OperationError
from pypy.interpreter.typedef import TypeDef, GetSetProperty
from pypy.interpreter.typedef import attrproperty, attrproperty_w
from pypy.objspace.std.multimethod import MultiMethod, FailedToImplement

__all__ = ['StdTypeDef', 'newmethod', 'gateway',
           'GetSetProperty', 'attrproperty', 'attrproperty_w',
           'MultiMethod']


class StdTypeDef(TypeDef):

    def __init__(self, name, bases, **rawdict):
        TypeDef.__init__(self, name, **rawdict)
        self.bases = bases
        self.local_multimethods = []

    def registermethods(self, namespace):
        self.local_multimethods += hack_out_multimethods(namespace)

    def mro(self, space):
        assert len(self.bases) <= 1
        if self.bases:
            return [self] + self.bases[0].mro(space)
        else:
            return [self]

def newmethod(descr_new):
    # XXX make the result a staticmethod
    return gateway.interp2app(descr_new)

# ____________________________________________________________
#
# All the code below fishes from the multimethod registration tables
# the descriptors to put into the W_TypeObjects.
#

def buildtypeobject(typedef, space):
    # build a W_TypeObject from this StdTypeDef
    from pypy.objspace.std.typeobject import W_TypeObject

    w = space.wrap
    rawdict = typedef.rawdict.copy()

    if isinstance(typedef, StdTypeDef):
        # get all the sliced multimethods
        multimethods = slicemultimethods(space.__class__, typedef)
        for name, code in multimethods.items():
            # compute the slice and ignore the multimethod if empty
            if not code.computeslice(space):
                continue
            # create a Function around the sliced multimethod code
            fn = function.Function(space, code, defs_w=code.getdefaults(space))
            assert name not in rawdict, 'name clash: %s in %s_typedef' % (
                name, typedef.name)
            rawdict[name] = fn
        bases_w = [space.gettypeobject(basedef) for basedef in typedef.bases]
    else:
        from pypy.objspace.std.objecttype import object_typedef
        bases_w = [space.gettypeobject(object_typedef)]

    # wrap everything
    dict_w = {}
    for descrname, descrvalue in rawdict.items():
        dict_w[descrname] = w(descrvalue)

    return W_TypeObject(space, typedef.name, bases_w, dict_w, typedef)

def hack_out_multimethods(ns):
    result = []
    for value in ns.itervalues():
        if isinstance(value, MultiMethod):
            result.append(value)
    return result

def slicemultimethod(multimethod, typeclass, result):
    for i in range(len(multimethod.specialnames)):
        # each MultimethodCode embeds a multimethod
        name = multimethod.specialnames[i]
        if name in result:
            # conflict between e.g. __lt__ and
            # __lt__-as-reversed-version-of-__gt__
            code = result[name]
            if code.bound_position < i:
                continue
        mmframeclass = multimethod.extras.get('mmframeclass')
        if mmframeclass is None:
            if len(multimethod.specialnames) > 1:
                mmframeclass = SpecialMmFrame
            else:
                mmframeclass = MmFrame
        code = MultimethodCode(multimethod, mmframeclass, typeclass, i)
        result[name] = code

def slicemultimethods(spaceclass, typeclass):
    result = {}
    # import and slice all multimethods of the space.MM container
    for multimethod in hack_out_multimethods(spaceclass.MM.__dict__):
        slicemultimethod(multimethod, typeclass, result)
    # import all multimethods defined directly on the type without slicing
    for multimethod in typeclass.local_multimethods:
        slicemultimethod(multimethod, None, result)
    return result

class MultimethodCode(eval.Code):
    """A code object that invokes a multimethod."""
    
    def __init__(self, multimethod, framecls, typeclass, bound_position=0):
        eval.Code.__init__(self, multimethod.operatorsymbol)
        self.basemultimethod = multimethod
        self.typeclass = typeclass
        self.bound_position = bound_position
        self.framecls = framecls
        argnames = ['x%d'%(i+1) for i in range(multimethod.arity)]
        varargname = kwargname = None
        if multimethod.extras.get('varargs', False):
            varargname = 'args'
        if multimethod.extras.get('keywords', False):
            kwargname = 'keywords'
        self.sig = argnames, varargname, kwargname

    def computeslice(self, space):
        if self.typeclass is None:
            slice = self.basemultimethod
        else:
            slice = self.basemultimethod.slice(self.typeclass,
                                               self.bound_position)
        if slice.is_empty():
            return False
        else:
            self.mm = slice.get(space)
            return True

    def signature(self):
        return self.sig

    def getdefaults(self, space):
        return [space.wrap(x)
                for x in self.basemultimethod.extras.get('defaults', ())]

    def create_frame(self, space, w_globals, closure=None):
        return self.framecls(space, self)

class MmFrame(eval.Frame):
    def run(self):
        "Call the multimethod, raising a TypeError if not implemented."
        args = list(self.fastlocals_w)
        args.insert(0, args.pop(self.code.bound_position))
        w_result = self.code.mm(*args)
        # we accept a real None from operations with no return value
        if w_result is None:
            w_result = self.space.w_None
        return w_result

class SpecialMmFrame(eval.Frame):
    def run(self):
        "Call the multimethods, possibly returning a NotImplemented."
        args = list(self.fastlocals_w)
        args.insert(0, args.pop(self.code.bound_position))
        try:
            return self.code.mm.perform_call(args)
        except FailedToImplement, e:
            if e.args:
                raise OperationError(*e.args)
            else:
                return self.space.w_NotImplemented

