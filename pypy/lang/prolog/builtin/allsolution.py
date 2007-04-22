import py
from pypy.lang.prolog.interpreter import engine, helper, term, error
from pypy.lang.prolog.builtin.register import expose_builtin

# ___________________________________________________________________
# finding all solutions to a goal

class FindallContinuation(engine.Continuation):
    def __init__(self, template):
        self.found = []
        self.template = template

    def call(self, engine):
        clone = self.template.getvalue(engine.heap)
        self.found.append(clone)
        raise error.UnificationFailed()

def impl_findall(engine, template, goal, bag):
    oldstate = engine.heap.branch()
    collector = FindallContinuation(template)
    try:
        engine.call(goal, collector)
    except error.UnificationFailed:
        engine.heap.revert(oldstate)
    result = term.Atom("[]")
    for i in range(len(collector.found) - 1, -1, -1):
        copy = collector.found[i]
        d = {}
        copy = copy.clone_compress_vars(d, engine.heap.maxvar())
        engine.heap.extend(len(d))
        result = term.Term(".", [copy, result])
    bag.unify(result, engine.heap)
expose_builtin(impl_findall, "findall", unwrap_spec=['raw', 'callable', 'raw'])
