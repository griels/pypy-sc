from pypy.interpreter.baseobjspace import OperationError


class FailedToImplement(Exception):
    "Signals the dispatcher to try harder."

class W_ANY:
    "Placeholder to allow dispatch on any value."


class MultiMethod(object):

    def __init__(self, operatorsymbol, arity):
        "MultiMethod dispatching on the first 'arity' arguments."
        self.arity = arity
        self.operatorsymbol = operatorsymbol
        self.dispatch_table = {}

    def register(self, function, *types):
        if types in self.dispatch_table:
            raise error, "we already got an implementation for %r %r" % (
                self.operatorsymbol, types)
        self.dispatch_table[types] = function

    def __get__(self, space, cls):
        if space is None:
            return self  # <-------------------------- Hack
        return BoundMultiMethod(space, self)

    def buildchoices(self, types):
        """Build a list of all possible combinations of delegated types,
        sorted by cost."""
        result = []
        self.internal_buildchoices(types, (), (), result)
        result.sort()
        return result

    def internal_buildchoices(self, initialtypes,
                              currenttypes, currentdelegators, result):
        if len(currenttypes) == self.arity:
            try:
                function = self.dispatch_table[currenttypes]
            except KeyError:
                pass
            else:
                result.append((currentdelegators, function))
        else:
            nexttype = initialtypes[len(currenttypes)]
            self.internal_buildchoices(initialtypes, currenttypes + (nexttype,),
                                       currentdelegators + (None,), result)
            delegators = getattr(nexttype, "delegate_once", {})
            for othertype, delegator in delegators.items():
                self.internal_buildchoices(initialtypes,
                                           currenttypes + (othertype,),
                                           currentdelegators + (delegator,),
                                           result)


class BoundMultiMethod:

    def __init__(self, space, multimethod):
        self.space = space
        self.multimethod = multimethod

    def __call__(self, *args):
        if len(args) < self.multimethod.arity:
            raise TypeError, ("multimethod needs at least %d arguments" %
                              self.multimethod.arity)
        dispatchargs = args[:self.multimethod.arity]
        extraargs    = args[self.multimethod.arity:]
        initialtypes = tuple([a.__class__ for a in dispatchargs])
        choicelist = self.multimethod.buildchoices(initialtypes)
        firstfailure = None
        for delegators, function in choicelist:
            newargs = []
            for delegator, arg in zip(delegators, args):
                if delegator is not None:
                    arg = delegator(self.space, arg)
                newargs.append(arg)
            newargs = tuple(newargs) + extraargs
            try:
                return function(self.space, *newargs)
            except FailedToImplement, e:
                # we got FailedToImplement, record the first such error
                if firstfailure is None:
                    firstfailure = e
        if firstfailure is None:
            if len(initialtypes) <= 1:
                plural = ""
            else:
                plural = "s"
            typenames = [t.__name__ for t in initialtypes]
            message = "unsupported operand type%s for %s: %s" % (
                plural, self.multimethod.operatorsymbol,
                ', '.join(typenames))
            w_value = self.space.wrap(message)
            raise OperationError(self.space.w_TypeError, w_value)
        else:
            raise e


class error(Exception):
    "Thrown to you when you do something wrong with multimethods."
