"""Flow Graph Transformation

The difference between simplification and transformation is that
transformation may introduce new space operation.
"""

import types
from pypy.objspace.flow.model import SpaceOperation
from pypy.annotation.model import SomeValue
from pypy.translator.annrpython import CannotSimplify

# XXX: Lots of duplicated codes. Fix this!

# [a] * b
# -->
# c = newlist(a)
# d = mul(c, int b)
# -->
# d = alloc_and_set(b, a)

def transform_allocate(self):
    """Transforms [a] * b to alloc_and_set(b, a) where b is int."""
    for block in self.annotated:
        operations = block.operations[:]
        n_op = len(operations)
        for i in range(0, n_op-1):
            op1 = operations[i]
            op2 = operations[i+1]
            if (op1.opname == 'newlist' and
                len(op1.args) == 1 and
                op2.opname == 'mul' and
                op1.result is op2.args[0] and
                self.gettype(op2.args[1]) is int):
                new_op = SpaceOperation('alloc_and_set',
                                        (op2.args[1], op1.args[0]),
                                        op2.result)
                block.operations[i+1:i+2] = [new_op]

# a[b:c]
# -->
# d = newslice(b, c, None)
# e = getitem(a, d)
# -->
# e = getslice(a, b, c)

def transform_slice(self):
    """Transforms a[b:c] to getslice(a, b, c)."""
    for block in self.annotated:
        operations = block.operations[:]
        n_op = len(operations)
        for i in range(0, n_op-1):
            op1 = operations[i]
            op2 = operations[i+1]
            if (op1.opname == 'newslice' and
                self.gettype(op1.args[2]) is types.NoneType and
                op2.opname == 'getitem' and
                op1.result is op2.args[1]):
                new_op = SpaceOperation('getslice',
                                        (op2.args[0], op1.args[0], op1.args[1]),
                                        op2.result)
                block.operations[i+1:i+2] = [new_op]

# a(*b)
# -->
# c = newtuple(*b)
# d = newdict()
# e = call(function a, c, d)
# -->
# e = simple_call(a, *b)

def transform_simple_call(self):
    """Transforms call(a, (...), {}) to simple_call(a, ...)"""
    for block in self.annotated:
        known_vars = block.inputargs[:]
        operations = []
        for op in block.operations:
            try:
                if op.opname != 'call':
                    raise CannotSimplify
                varargs_cell = self.binding(op.args[1])
                varkwds_cell = self.binding(op.args[2])
                arg_cells = self.decode_simple_call(varargs_cell,
                                                    varkwds_cell)
                if arg_cells is None:
                    raise CannotSimplify

                args = [self.reverse_binding(known_vars, c) for c in arg_cells]
                args.insert(0, op.args[0])
                new_ops = [SpaceOperation('simple_call', args, op.result)]
                
            except CannotSimplify:
                new_ops = [op]

            for op in new_ops:
                operations.append(op)
                known_vars.append(op.result)

        block.operations = operations

def transform_graph(ann):
    """Apply set of transformations available."""
    transform_allocate(ann)
    transform_slice(ann)
    transform_simple_call(ann)
