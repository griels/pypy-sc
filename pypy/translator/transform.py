"""Flow Graph Transformation

The difference between simplification and transformation is that
transformation may introduce new space operation.
"""

import types
from pypy.objspace.flow.model import SpaceOperation
from pypy.objspace.flow.model import Variable, Constant, Block, Link
from pypy.translator.annrpython import CannotSimplify
from pypy.annotation import model as annmodel

# XXX: Lots of duplicated codes. Fix this!

# ----------------------------------------------------------------------
# The 'call_args' operation is the strangest one.  The meaning of its
# arguments is as follows:
#
#      call_args(<callable>, <shape>, <arg0>, <arg1>, <arg2>...)
#
# The shape must be a constant object, which describes how the remaining
# arguments are regrouped.  The class pypy.interpreter.argument.Arguments
# has a method 'fromshape(shape, list-of-args)' that reconstructs a complete
# Arguments instance from this information.  Don't try to interpret the
# shape anywhere else, but for reference, it is a 3-tuple:
# (number-of-pos-arg, tuple-of-keyword-names, flag-presence-of-*-arg)
# ----------------------------------------------------------------------

# [a] * b
# -->
# c = newlist(a)
# d = mul(c, int b)
# -->
# d = alloc_and_set(b, a)

def fully_annotated_blocks(self):
    """Ignore blocked blocks."""
    for block, is_annotated in self.annotated.iteritems():
        if is_annotated:
            yield block

def transform_allocate(self):
    """Transforms [a] * b to alloc_and_set(b, a) where b is int."""
    for block in fully_annotated_blocks(self):
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
    for block in fully_annotated_blocks(self):
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

## REMOVED: now FlowObjSpace produces 'call_args' operations only
##def transform_simple_call(self):
##    """Transforms call(a, (...), {}) to simple_call(a, ...)"""
##    for block in self.annotated:
##        known_vars = block.inputargs[:]
##        operations = []
##        for op in block.operations:
##            try:
##                if op.opname != 'call':
##                    raise CannotSimplify
##                varargs_cell = self.binding(op.args[1])
##                varkwds_cell = self.binding(op.args[2])
##                arg_cells = self.decode_simple_call(varargs_cell,
##                                                    varkwds_cell)
##                if arg_cells is None:
##                    raise CannotSimplify

##                args = [self.reverse_binding(known_vars, c) for c in arg_cells]
##                args.insert(0, op.args[0])
##                new_ops = [SpaceOperation('simple_call', args, op.result)]
                
##            except CannotSimplify:
##                new_ops = [op]

##            for op in new_ops:
##                operations.append(op)
##                known_vars.append(op.result)

##        block.operations = operations

def transform_dead_op_vars(self):
    """Remove dead operations and variables that are passed over a link
    but not used in the target block."""
    # the set of operations that can safely be removed (no side effects)
    CanRemove = {'newtuple': True,
                 'newlist': True,
                 'newdict': True,
                 'is_': True, 
                 'is_true': True}
    read_vars = {}  # set of variables really used
    variable_flow = {}  # map {Var: list-of-Vars-it-depends-on}
    
    # compute variable_flow and an initial read_vars
    for block in self.annotated:
        # figure out which variables are ever read
        for op in block.operations:
            if op.opname not in CanRemove:  # mark the inputs as really needed
                for arg in op.args:
                    read_vars[arg] = True
            else:
                # if CanRemove, only mark dependencies of the result
                # on the input variables
                deps = variable_flow.setdefault(op.result, [])
                deps.extend(op.args)

        if isinstance(block.exitswitch, Variable):
            read_vars[block.exitswitch] = True

        if block.exits:
            for link in block.exits:
                if link.target not in self.annotated:
                    for arg, targetarg in zip(link.args, link.target.inputargs):
                        read_vars[arg] = True
                        read_vars[targetarg] = True
                else:
                    for arg, targetarg in zip(link.args, link.target.inputargs):
                        deps = variable_flow.setdefault(targetarg, [])
                        deps.append(arg)
        else:
            # return and except blocks implicitely use their input variable(s)
            for arg in block.inputargs:
                read_vars[arg] = True
        # an input block's inputargs should not be modified, even if some
        # of the function's input arguments are not actually used
        if block.isstartblock:
            for arg in block.inputargs:
                read_vars[arg] = True

    # flow read_vars backwards so that any variable on which a read_vars
    # depends is also included in read_vars
    pending = list(read_vars)
    for var in pending:
        for prevvar in variable_flow.get(var, []):
            if prevvar not in read_vars:
                read_vars[prevvar] = True
                pending.append(prevvar)

    for block in self.annotated:

        # look for removable operations whose result is never used
        for i in range(len(block.operations)-1, -1, -1):
            op = block.operations[i]
            if op.result not in read_vars: 
                if op.opname in CanRemove: 
                    del block.operations[i]
                elif op.opname == 'simple_call': 
                    # XXX we want to have a more effective and safe 
                    # way to check if this operation has side effects
                    # ... 
                    if op.args and isinstance(op.args[0], Constant):
                        func = op.args[0].value
                        if func is isinstance:
                            del block.operations[i]

        # look for output variables never used
        # warning: this must be completely done *before* we attempt to
        # remove the corresponding variables from block.inputargs!
        # Otherwise the link.args get out of sync with the
        # link.target.inputargs.
        for link in block.exits:
            assert len(link.args) == len(link.target.inputargs)
            for i in range(len(link.args)-1, -1, -1):
                if link.target.inputargs[i] not in read_vars:
                    del link.args[i]
            # the above assert would fail here

    for block in self.annotated:
        # look for input variables never used
        # The corresponding link.args have already been all removed above
        for i in range(len(block.inputargs)-1, -1, -1):
            if block.inputargs[i] not in read_vars:
                del block.inputargs[i]

# expands the += operation between lists into a basic block loop.
#    a = inplace_add(b, c)
# becomes the following graph:
#
#  clen = len(c)
#  growlist(b, clen)     # ensure there is enough space for clen new items
#        |
#        |  (pass all variables to next block, plus i=0)
#        V
#  ,--> z = lt(i, clen)
#  |    exitswitch(z):
#  |     |          |        False
#  |     | True     `------------------>  ...sequel...
#  |     V
#  |    x = getitem(c, i)
#  |    fastappend(b, x)
#  |    i1 = add(i, 1)
#  |     |
#  `-----'  (pass all variables, with i=i1)
#
##def transform_listextend(self):
##    allblocks = list(self.annotated)
##    for block in allblocks:
##        for j in range(len(block.operations)):
##            op = block.operations[j]
##            if op.opname != 'inplace_add':
##                continue
##            a = op.result
##            b, c = op.args
##            s_list = self.bindings.get(b)
##            if not isinstance(s_list, annmodel.SomeList):
##                continue

##            # new variables
##            clen  = Variable()
##            i     = Variable()
##            i1    = Variable()
##            z     = Variable()
##            x     = Variable()
##            dummy = Variable()
##            self.setbinding(clen,  annmodel.SomeInteger(nonneg=True))
##            self.setbinding(i,     annmodel.SomeInteger(nonneg=True))
##            self.setbinding(i1,    annmodel.SomeInteger(nonneg=True))
##            self.setbinding(z,     annmodel.SomeBool())
##            self.setbinding(x,     s_list.s_item)
##            self.setbinding(dummy, annmodel.SomeImpossibleValue())

##            sequel_operations = block.operations[j+1:]
##            sequel_exitswitch = block.exitswitch
##            sequel_exits      = block.exits

##            del block.operations[j:]
##            block.operations += [
##                SpaceOperation('len', [c], clen),
##                SpaceOperation('growlist', [b, clen], dummy),
##                ]
##            block.exitswitch = None
##            allvars = block.getvariables()

##            condition_block = Block(allvars+[i])
##            condition_block.operations += [
##                SpaceOperation('lt', [i, clen], z),
##                ]
##            condition_block.exitswitch = z

##            loopbody_block = Block(allvars+[i])
##            loopbody_block.operations += [
##                SpaceOperation('getitem', [c, i], x),
##                SpaceOperation('fastappend', [b, x], dummy),
##                SpaceOperation('add', [i, Constant(1)], i1),
##                ]

##            sequel_block = Block(allvars+[a])
##            sequel_block.operations = sequel_operations
##            sequel_block.exitswitch = sequel_exitswitch

##            # link the blocks together
##            block.recloseblock(
##                Link(allvars+[Constant(0)], condition_block),
##                )
##            condition_block.closeblock(
##                Link(allvars+[i],           loopbody_block,  exitcase=True),
##                Link(allvars+[b],           sequel_block,    exitcase=False),
##                )
##            loopbody_block.closeblock(
##                Link(allvars+[i1],          condition_block),
##                )
##            sequel_block.closeblock(*sequel_exits)

##            # now rename the variables -- so far all blocks use the
##            # same variables, which is forbidden
##            renamevariables(self, condition_block)
##            renamevariables(self, loopbody_block)
##            renamevariables(self, sequel_block)

##            allblocks.append(sequel_block)
##            break

##def renamevariables(self, block):
##    """Utility to rename the variables in a block to fresh variables.
##    The annotations are carried over from the old to the new vars."""
##    varmap = {}
##    block.inputargs = [varmap.setdefault(a, Variable())
##                       for a in block.inputargs]
##    operations = []
##    for op in block.operations:
##        result = varmap.setdefault(op.result, Variable())
##        args = [varmap.get(a, a) for a in op.args]
##        op = SpaceOperation(op.opname, args, result)
##        operations.append(op)
##    block.operations = operations
##    block.exitswitch = varmap.get(block.exitswitch, block.exitswitch)
##    exits = []
##    for exit in block.exits:
##        args = [varmap.get(a, a) for a in exit.args]
##        exits.append(Link(args, exit.target, exit.exitcase))
##    block.recloseblock(*exits)
##    # carry over the annotations
##    for a1, a2 in varmap.items():
##        if a1 in self.bindings:
##            self.setbinding(a2, self.bindings[a1])
##    self.annotated[block] = True

def transform_dead_code(self):
    """Remove dead code: these are the blocks that are not annotated at all
    because the annotation considered that no conditional jump could reach
    them."""
    for block in fully_annotated_blocks(self):
        for link in block.exits:
            if link not in self.links_followed:
                lst = list(block.exits)
                lst.remove(link)
                block.exits = tuple(lst)
                if len(block.exits) == 1:
                    block.exitswitch = None
                    block.exits[0].exitcase = None


def transform_graph(ann):
    """Apply set of transformations available."""
    # WARNING: this produces incorrect results if the graph has been
    #          modified by t.simplify() after is had been annotated.
    if ann.translator:
        ann.translator.checkgraphs()
    transform_dead_code(ann)
    transform_allocate(ann)
    transform_slice(ann)
    ##transform_listextend(ann)
    # do this last, after the previous transformations had a
    # chance to remove dependency on certain variables
    transform_dead_op_vars(ann)
    if ann.translator:
        ann.translator.checkgraphs()
