import operator
from pypy.objspace.flow.model import Variable, Constant, SpaceOperation
from pypy.objspace.flow.model import Block, Link, FunctionGraph
from pypy.objspace.flow.model import checkgraph, last_exception
from pypy.rpython.lltypesystem import lltype
from pypy.translator.simplify import eliminate_empty_blocks, join_blocks


def const(value, T=None):
    c = Constant(value)
    c.concretetype = T or lltype.typeOf(value)
    return c

def newvar(T):
    v = Variable()
    v.concretetype = T
    return v


class LLAbstractValue(object):
    pass

class LLConcreteValue(LLAbstractValue):

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return '<concrete %r>' % (self.value,)

#    def __eq__(self, other):
#        return self.__class__ is other.__class__ and self.value == other.value
#
#    def __ne__(self, other):
#        return not (self == other)
#
#    def __hash__(self):
#        return hash(self.value)

    def getconcretetype(self):
        return lltype.typeOf(self.value)

    def forcevarorconst(self, builder):
        return const(self.value)

    def getruntimevars(self):
        return []

    def maybe_get_constant(self):
        return const(self.value)

    def with_fresh_variables(self, to_be_stored_into):
        return self

    def match(self, other):
        return isinstance(other, LLConcreteValue) and self.value == other.value


class LLRuntimeValue(LLAbstractValue):

    def __init__(self, orig_v):
        if isinstance(orig_v, Variable):
            self.copy_v = Variable(orig_v)
            self.copy_v.concretetype = orig_v.concretetype
        else:
            # we can share the Constant()
            self.copy_v = orig_v

    def __repr__(self):
        return '<runtime %r>' % (self.copy_v,)

    def getconcretetype(self):
        return self.copy_v.concretetype

    def forcevarorconst(self, builder):
        return self.copy_v

    def getruntimevars(self):
        return [self.copy_v]

    def maybe_get_constant(self):
        if isinstance(self.copy_v, Constant):
            return self.copy_v
        else:
            return None

    def with_fresh_variables(self, to_be_stored_into):
        return LLRuntimeValue(orig_v=to_be_stored_into)

    def match(self, other):
        if isinstance(other, LLRuntimeValue):
            if isinstance(self.copy_v, Variable):
                return isinstance(other.copy_v, Variable)
            else:
                return self.copy_v == other.copy_v
        else:
            return False

ll_no_return_value = LLRuntimeValue(const(None, lltype.Void))


class VirtualStruct(object):
    def __init__(self, STRUCT):
        self.T = STRUCT
        self.fields = {}

    def getfield(self, name):
        try:
            return self.fields[name]
        except KeyError:
            T = getattr(self.T, name)
            return LLRuntimeValue(const(T._defl()))

    def setfield(self, name, value):
        self.fields[name] = value

    def copy(self):
        result = VirtualStruct(self.T)
        for name, a_value in self.fields.items():
            v = newvar(a_value.getconcretetype())
            result.fields[name] = a_value.with_fresh_variables(v)
        return result

    def force(self, builder):
        v_result = newvar(lltype.Ptr(self.T))
        op = SpaceOperation('malloc', [const(self.T, lltype.Void)], v_result)
        print 'force:', op
        builder.residual_operations.append(op)
        # initialize all fields by relying on the assumption that the
        # structure is initialized to zeros
        for name in self.T._names:
            if name in self.fields:
                v_value = self.fields[name].forcevarorconst(builder)
                op = SpaceOperation('setfield', [v_result,
                                                 const(name, lltype.Void),
                                                 v_value],
                                    newvar(lltype.Void))
                print 'force:', op
                builder.residual_operations.append(op)
        return v_result

    def getruntimevars(self):
        result = []
        for name in self.T._names:
            result.extend(self.getfield(name).getruntimevars())
        return result

    def match(self, other):
        assert self.T == other.T
        for name in self.T._names:
            a1 = self.getfield(name)
            a2 = other.getfield(name)
            if not a1.match(a2):
                return False
        else:
            return True


class LLVirtualPtr(LLAbstractValue):

    def __init__(self, containerobj):
        self.containerobj = containerobj    # a VirtualStruct

    def getconcretetype(self):
        return lltype.Ptr(self.containerobj.T)

    def forcevarorconst(self, builder):
        v_result = self.containerobj.force(builder)
        self.__class__ = LLRuntimeValue
        self.__dict__ = {'copy_v': v_result}
        return v_result

    def getruntimevars(self):
        return self.containerobj.getruntimevars()

    def maybe_get_constant(self):
        return None

    def with_fresh_variables(self, to_be_stored_into):
        return LLVirtualPtr(self.containerobj.copy())

    def match(self, other):
        if isinstance(other, LLVirtualPtr):
            return self.containerobj.match(other.containerobj)
        else:
            return False

# ____________________________________________________________

class BlockState(object):
    """Entry state of a block, as a combination of LLAbstractValues
    for its input arguments."""

    def __init__(self, origblock, args_a):
        assert len(args_a) == len(origblock.inputargs)
        self.args_a = args_a
        self.origblock = origblock
        self.copyblock = None

    def match(self, args_a):
        # simple for now
        for a1, a2 in zip(self.args_a, args_a):
            if not a1.match(a2):
                return False
        else:
            return True

    def resolveblock(self, newblock):
        #print "RESOLVING BLOCK", newblock
        self.copyblock = newblock

# ____________________________________________________________

class LLAbstractInterp(object):

    def __init__(self):
        self.graphs = []
        self.graphstates = {}     # {origgraph: {BlockState: GraphState}}
        self.pendingstates = {}   # {Link-or-GraphState: next-BlockState}

    def itercopygraphs(self):
        return self.graphs

    def eval(self, origgraph, hints):
        # for now, 'hints' means "I'm absolutely sure that the
        # given variables will have the given ll value"
        self.hints = hints
        self.blocks = {}   # {origblock: list-of-LLStates}
        args_a = [LLRuntimeValue(orig_v=v) for v in origgraph.getargs()]
        graphstate, args_a = self.schedule_graph(args_a, origgraph)
        graphstate.complete()
        return graphstate.copygraph

    def applyhint(self, args_a, origblock):
        result_a = []
        # apply the hints to make more LLConcreteValues
        for a, origv in zip(args_a, origblock.inputargs):
            if origv in self.hints:
                # use the hint, ignore the source binding
                a = LLConcreteValue(self.hints[origv])
            result_a.append(a)
        return result_a

    def schedule_graph(self, args_a, origgraph):
        origblock = origgraph.startblock
        state, args_a = self.schedule_getstate(args_a, origblock)
        try:
            graphstate = self.graphstates[origgraph][state]
        except KeyError:
            d = self.graphstates.setdefault(origgraph, {})
            graphstate = GraphState(self, origgraph, args_a, n=len(d))
            d[state] = graphstate
            self.pendingstates[graphstate] = state
        #print "SCHEDULE_GRAPH", graphstate
        return graphstate, args_a

    def schedule(self, args_a, origblock):
        #print "SCHEDULE", args_a, origblock
        # args_a: [the-a-corresponding-to-v for v in origblock.inputargs]
        state, args_a = self.schedule_getstate(args_a, origblock)
        args_v = []
        for a in args_a:
            args_v.extend(a.getruntimevars())
        newlink = Link(args_v, None)
        self.pendingstates[newlink] = state
        return newlink

    def schedule_getstate(self, args_a, origblock):
        # NOTA BENE: copyblocks can get shared between different copygraphs!
        args_a = self.applyhint(args_a, origblock)
        pendingstates = self.blocks.setdefault(origblock, [])
        # try to match this new state with an existing one
        for state in pendingstates:
            if state.match(args_a):
                # already matched
                return state, args_a
        else:
            # schedule this new state
            state = BlockState(origblock, args_a)
            pendingstates.append(state)
            return state, args_a


class GraphState(object):
    """Entry state of a graph."""

    def __init__(self, interp, origgraph, args_a, n):
        self.interp = interp
        self.origgraph = origgraph
        name = '%s_%d' % (origgraph.name, n)
        self.copygraph = FunctionGraph(name, Block([]))   # grumble
        interp.graphs.append(self.copygraph)
        for orig_v, copy_v in [(origgraph.getreturnvar(),
                                self.copygraph.getreturnvar()),
                               (origgraph.exceptblock.inputargs[0],
                                self.copygraph.exceptblock.inputargs[0]),
                               (origgraph.exceptblock.inputargs[1],
                                self.copygraph.exceptblock.inputargs[1])]:
            if hasattr(orig_v, 'concretetype'):
                copy_v.concretetype = orig_v.concretetype
        self.a_return = None
        self.state = "before"

    def settarget(self, block):
        block.isstartblock = True
        self.copygraph.startblock = block

    def complete(self):
        assert self.state != "during"
        if self.state == "after":
            return
        self.state = "during"
        graph = self.copygraph
        interp = self.interp
        pending = [self]
        seen = {}
        # follow all possible links, forcing the blocks along the way to be
        # computed
        while pending:
            next = pending.pop()
            state = interp.pendingstates[next]
            if state.copyblock is None:
                self.flowin(state)
            next.settarget(state.copyblock)
            for link in state.copyblock.exits:
                if link not in seen:
                    seen[link] = True
                    if link.target is None or link.target.operations != ():
                        pending.append(link)
                    else:
                        # link.target is a return or except block; make sure
                        # that it is really the one from 'graph' -- by patching
                        # 'graph' if necessary.
                        if len(link.target.inputargs) == 1:
                            self.a_return = state.args_a[0]
                            graph.returnblock = link.target
                        elif len(link.target.inputargs) == 2:
                            graph.exceptblock = link.target
                        else:
                            raise Exception("uh?")
        # the graph should be complete now; sanity-check
        checkgraph(graph)
        eliminate_empty_blocks(graph)
        join_blocks(graph)
        self.state = "after"

    def flowin(self, state):
        # flow in the block
        origblock = state.origblock
        builder = BlockBuilder(self.interp)
        newinputargs = []
        for v, a in zip(origblock.inputargs, state.args_a):
            a = a.with_fresh_variables(to_be_stored_into=v)
            builder.bindings[v] = a
            newinputargs.extend(a.getruntimevars())
        print
        # flow the actual operations of the block
        for op in origblock.operations:
            builder.dispatch(op)
        # done

        newexitswitch = None
        if origblock.operations != ():
            # build exit links and schedule their target for later completion
            if origblock.exitswitch is None:
                links = origblock.exits
            elif origblock.exitswitch == Constant(last_exception):
                XXX
            else:
                a = builder.bindings[origblock.exitswitch]
                v = a.forcevarorconst(builder)
                if isinstance(v, Variable):
                    newexitswitch = v
                    links = origblock.exits
                else:
                    links = [link for link in origblock.exits
                                  if link.llexitcase == v.value]
            newlinks = []
            for origlink in links:
                args_a = [builder.binding(v) for v in origlink.args]
                newlink = self.interp.schedule(args_a, origlink.target)
                newlinks.append(newlink)
        else:
            # copies of return and except blocks are *normal* blocks currently;
            # they are linked to the official return or except block of the
            # copygraph.  If needed, LLConcreteValues are turned into Constants.
            if len(origblock.inputargs) == 1:
                target = self.copygraph.returnblock
            else:
                target = self.copygraph.exceptblock
            args_v = [builder.binding(v).forcevarorconst(builder)
                      for v in origblock.inputargs]
            newlinks = [Link(args_v, target)]
        #print "CLOSING"

        newblock = builder.buildblock(newinputargs, newexitswitch, newlinks)
        state.resolveblock(newblock)


class BlockBuilder(object):

    def __init__(self, interp):
        self.interp = interp
        self.bindings = {}   # {Variables-of-origblock: a_value}
        self.residual_operations = []

    def buildblock(self, newinputargs, newexitswitch, newlinks):
        b = Block(newinputargs)
        b.operations = self.residual_operations
        b.exitswitch = newexitswitch
        b.closeblock(*newlinks)
        return b

    def binding(self, v):
        if isinstance(v, Constant):
            return LLRuntimeValue(orig_v=v)
        else:
            return self.bindings[v]

    def dispatch(self, op):
        handler = getattr(self, 'op_' + op.opname)
        a_result = handler(op, *[self.binding(v) for v in op.args])
        self.bindings[op.result] = a_result


    def constantfold(self, constant_op, args_a):
        concretevalues = []
        any_concrete = False
        for a in args_a:
            v = a.maybe_get_constant()
            if v is None:
                return None    # cannot constant-fold
            concretevalues.append(v.value)
            any_concrete = any_concrete or isinstance(a, LLConcreteValue)
        # can constant-fold
        print 'fold:', constant_op, concretevalues
        concreteresult = constant_op(*concretevalues)
        if any_concrete:
            return LLConcreteValue(concreteresult)
        else:
            c = Constant(concreteresult)
            c.concretetype = typeOf(concreteresult)
            return LLRuntimeValue(c)

    def residual(self, opname, args_a, a_result):
        v_result = a_result.forcevarorconst(self)
        if isinstance(v_result, Constant):
            v_result = newvar(v_result.concretetype)
        op = SpaceOperation(opname,
                            [a.forcevarorconst(self) for a in args_a],
                            v_result)
        print 'keep:', op
        self.residual_operations.append(op)

    def residualize(self, op, args_a, constant_op=None):
        if constant_op:
            RESULT = op.result.concretetype
            if RESULT is lltype.Void:
                return ll_no_return_value
            a_result = self.constantfold(constant_op, args_a)
            if a_result is not None:
                return a_result
        a_result = LLRuntimeValue(op.result)
        self.residual(op.opname, args_a, a_result)
        return a_result

    # ____________________________________________________________

    def op_int_is_true(self, op, a):
        return self.residualize(op, [a], operator.truth)

    def op_int_add(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.add)

    def op_int_sub(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.sub)

    def op_int_mul(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.mul)

    def op_int_and(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.and_)

    def op_int_rshift(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.rshift)

    def op_int_neg(self, op, a1):
        return self.residualize(op, [a1], operator.neg)

    def op_int_gt(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.gt)

    def op_int_lt(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.lt)

    def op_int_ge(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.ge)

    def op_int_le(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.le)

    def op_int_eq(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.eq)

    def op_int_ne(self, op, a1, a2):
        return self.residualize(op, [a1, a2], operator.ne)

    def op_cast_char_to_int(self, op, a):
        return self.residualize(op, [a], ord)

    def op_same_as(self, op, a):
        return a

    def op_direct_call(self, op, a_func, *args_a):
        a_result = LLRuntimeValue(op.result)
        v_func = a_func.maybe_get_constant()
        if v_func is not None:
            fnobj = v_func.value._obj
            if (hasattr(fnobj, 'graph') and
                not getattr(fnobj._callable, 'suggested_primitive', False)):
                origgraph = fnobj.graph
                graphstate, args_a = self.interp.schedule_graph(
                    args_a, origgraph)
                #print 'SCHEDULE_GRAPH', args_a, '==>', graphstate.copygraph.name
                if graphstate.state != "during":
                    print 'ENTERING', graphstate.copygraph.name, args_a
                    graphstate.complete()
                    if (graphstate.a_return is not None and
                        graphstate.a_return.maybe_get_constant() is not None):
                        a_result = graphstate.a_return
                    print 'LEAVING', graphstate.copygraph.name, graphstate.a_return
                
                origfptr = v_func.value
                ARGS = []
                new_args_a = []
                for a in args_a:
                    if not isinstance(a, LLConcreteValue):
                        ARGS.append(a.getconcretetype())
                        new_args_a.append(a)
                args_a = new_args_a
                TYPE = lltype.FuncType(
                   ARGS, lltype.typeOf(origfptr).TO.RESULT)
                fptr = lltype.functionptr(
                   TYPE, graphstate.copygraph.name, graph=graphstate.copygraph)
                fconst = Constant(fptr)
                fconst.concretetype = lltype.typeOf(fptr)
                a_func = LLRuntimeValue(fconst)
        self.residual("direct_call", [a_func] + list(args_a), a_result) 
        return a_result

    def op_getfield(self, op, a_ptr, a_attrname):
        if isinstance(a_ptr, LLVirtualPtr):
            c_attrname = a_attrname.maybe_get_constant()
            assert c_attrname is not None
            return a_ptr.containerobj.getfield(c_attrname.value)
        constant_op = None
        T = a_ptr.getconcretetype().TO
        if T._hints.get('immutable', False):
            constant_op = getattr
        return self.residualize(op, [a_ptr, a_attrname], constant_op)

    def op_getsubstruct(self, op, a_ptr, a_attrname):
        return self.residualize(op, [a_ptr, a_attrname], getattr)

    def op_getarraysize(self, op, a_ptr):
        return self.residualize(op, [a_ptr], len)

    def op_getarrayitem(self, op, a_ptr, a_index):
        constant_op = None
        T = a_ptr.getconcretetype().TO
        if T._hints.get('immutable', False):
            constant_op = operator.getitem
        return self.residualize(op, [a_ptr, a_index], constant_op)

    def op_malloc(self, op, a_T):
        c_T = a_T.maybe_get_constant()
        assert c_T is not None
        S = VirtualStruct(c_T.value)
        return LLVirtualPtr(S)

    def op_malloc_varsize(self, op, a_T, a_size):
        return self.residualize(op, [a_T, a_size])

    def op_setfield(self, op, a_ptr, a_attrname, a_value):
        if isinstance(a_ptr, LLVirtualPtr):
            c_attrname = a_attrname.maybe_get_constant()
            assert c_attrname is not None
            a_ptr.containerobj.setfield(c_attrname.value, a_value)
            return ll_no_return_value
        return self.residualize(op, [a_ptr, a_attrname, a_value])

    def op_setarrayitem(self, op, a_ptr, a_index, a_value):
        return self.residualize(op, [a_ptr, a_index, a_value])

    def op_cast_pointer(self, op, a_ptr):
        def constant_op(ptr):
            return lltype.cast_pointer(op.result.concretetype, ptr)
        return self.residualize(op, [a_ptr], constant_op)
