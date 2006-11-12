import py
from pypy.lang.prolog.interpreter.parsing import parse_file, TermBuilder
from pypy.lang.prolog.interpreter import engine, helper, term, error
from pypy.lang.prolog.builtin.register import expose_builtin

# ___________________________________________________________________
# control predicates

def impl_fail(engine):
    raise error.UnificationFailed()
expose_builtin(impl_fail, "fail", unwrap_spec=[])

def impl_true(engine):
    pass
expose_builtin(impl_true, "true", unwrap_spec=[])

def impl_repeat(engine, continuation):
    while 1:
        try:
            return continuation.call(engine)
        except error.UnificationFailed:
            pass
expose_builtin(impl_repeat, "repeat", unwrap_spec=[], handles_continuation=True)

def impl_cut(engine, continuation):
    raise error.CutException(continuation)
expose_builtin(impl_cut, "!", unwrap_spec=[],
               handles_continuation=True)

class AndContinuation(engine.Continuation):
    def __init__(self, next_call, continuation):
        self.next_call = next_call
        self.continuation = continuation

    def call(self, engine):
        next_call = self.next_call.dereference(engine.frame)
        if isinstance(next_call, term.Var):
            error.throw_instantiation_error()
        if not isinstance(next_call, term.Callable):
            error.throw_type_error('callable', next_call)
        return engine.call(next_call, self.continuation)

def impl_and(engine, call1, call2, continuation):
    if not isinstance(call2, term.Var) and not isinstance(call2, term.Callable):
        error.throw_type_error('callable', call2)
    and_continuation = AndContinuation(call2, continuation)
    return engine.call(call1, and_continuation)
expose_builtin(impl_and, ",", unwrap_spec=["callable", "raw"],
               handles_continuation=True)

def impl_or(engine, call1, call2, continuation):
    oldstate = engine.frame.branch()
    try:
        return engine.call(call1, continuation)
    except error.UnificationFailed:
        engine.frame.revert(oldstate)
    return engine.call(call2, continuation)

expose_builtin(impl_or, ";", unwrap_spec=["callable", "callable"],
               handles_continuation=True)

def impl_not(engine, call):
    try:
        try:
            engine.call(call)
        except error.CutException, e:
            engine.continue_after_cut(e.continuation)
    except error.UnificationFailed:
        return None
    raise error.UnificationFailed()
expose_builtin(impl_not, ["not", "\\+"], unwrap_spec=["callable"])

def impl_if(engine, if_clause, then_clause, continuation):
    oldstate = engine.frame.branch()
    try:
        engine.call(if_clause)
    except error.UnificationFailed:
        engine.frame.revert(oldstate)
        raise
    return engine.call(helper.ensure_callable(then_clause), continuation)
expose_builtin(impl_if, "->", unwrap_spec=["callable", "raw"],
               handles_continuation=True)

