from pypy.interpreter.executioncontext import ExecutionContext
from pypy.interpreter.error import OperationError
from pypy.objspace.flow.model import *
from pypy.objspace.flow.framestate import FrameState


class OperationThatShouldNotBePropagatedError(OperationError):
    pass

class StopFlowing(Exception):
    pass

class MergeBlock(Exception):
    pass


class SpamBlock(Block):
    dead = False
      
    def __init__(self, framestate):
        Block.__init__(self, framestate.getvariables())
        self.framestate = framestate

    def patchframe(self, frame):
        if self.dead:
            raise StopFlowing
        self.framestate.restoreframe(frame)
        return BlockRecorder(self)


class EggBlock(Block):

    def __init__(self, inputargs, prevblock, booloutcome):
        Block.__init__(self, inputargs)
        self.prevblock = prevblock
        self.booloutcome = booloutcome

    def patchframe(self, frame):
        parentblocks = []
        block = self
        while isinstance(block, EggBlock):
            block = block.prevblock
            parentblocks.append(block)
        # parentblocks = [Egg, Egg, ..., Egg, Spam] not including self
        block.patchframe(frame)
        recorder = BlockRecorder(self)
        prevblock = self
        for block in parentblocks:
            recorder = Replayer(block, prevblock.booloutcome, recorder)
            prevblock = block
        return recorder

# ____________________________________________________________

class Recorder:

    def append(self, operation):
        raise NotImplementedError

    def bytecode_trace(self, ec, frame):
        pass

    def guessbool(self, ec, w_condition, **kwds):
        raise AssertionError, "cannot guessbool(%s)" % (w_condition,)


class BlockRecorder(Recorder):
    # Records all generated operations into a block.

    def __init__(self, block):
        self.crnt_block = block
        # saved state at the join point most recently seen
        self.last_join_point = None
        self.progress = False

    def append(self, operation):
        if self.last_join_point is not None:
            # don't add more operations if we already crossed a join point
            raise MergeBlock(self.crnt_block, self.last_join_point)
        self.crnt_block.operations.append(operation)

    def bytecode_trace(self, ec, frame):
        assert frame is ec.crnt_frame, "seeing an unexpected frame!"
        next_instr = frame.next_instr
        if self.crnt_block.operations or isinstance(self.crnt_block, EggBlock):
            # if we have already produced at least one operation or a branch,
            # make a join point as early as possible (but not before we
            # actually try to generate more operations)
            self.last_join_point = FrameState(frame)
        else:
            ec.crnt_offset = next_instr # save offset for opcode
            varnames = frame.code.getvarnames()
            for name, w_value in zip(varnames, frame.getfastscope()):
                if isinstance(w_value, Variable):
                    w_value.rename(name)
            # record passage over already-existing join points
            if self.progress and next_instr in ec.joinpoints:
                self.last_join_point = FrameState(frame)
        self.progress = True

    def guessbool(self, ec, w_condition, cases=[False,True],
                  replace_last_variable_except_in_first_case = None):
        block = self.crnt_block
        vars = vars2 = block.getvariables()
        links = []
        for case in cases:
            egg = EggBlock(vars2, block, case)
            ec.pendingblocks.append(egg)
            link = Link(vars, egg, case)
            links.append(link)
            if replace_last_variable_except_in_first_case is not None:
                assert block.operations[-1].result is vars[-1]
                vars = vars[:-1]
                vars.extend(replace_last_variable_except_in_first_case)
                vars2 = vars2[:-1]
                while len(vars2) < len(vars):
                    vars2.append(Variable())
                replace_last_variable_except_in_first_case = None
        block.exitswitch = w_condition
        block.closeblock(*links)
        # forked the graph. Note that False comes before True by default
        # in the exits tuple so that (just in case we need it) we
        # actually have block.exits[False] = elseLink and
        # block.exits[True] = ifLink.
        raise StopFlowing


class Replayer(Recorder):
    
    def __init__(self, block, booloutcome, nextreplayer):
        self.crnt_block = block
        self.listtoreplay = block.operations
        self.booloutcome = booloutcome
        self.nextreplayer = nextreplayer
        self.index = 0
        
    def append(self, operation):
        operation.result = self.listtoreplay[self.index].result
        assert operation == self.listtoreplay[self.index], (
            '\n'.join(["Not generating the same operation sequence:"] +
                      [str(s) for s in self.listtoreplay[:self.index]] +
                      ["  ---> | while repeating we see here"] +
                      ["       | %s" % operation] +
                      [str(s) for s in self.listtoreplay[self.index:]]))
        self.index += 1

    def guessbool(self, ec, w_condition, **kwds):
        assert self.index == len(self.listtoreplay)
        ec.recorder = self.nextreplayer
        return self.booloutcome


class ConcreteNoOp(Recorder):
    # In "concrete mode", no SpaceOperations between Variables are allowed.
    # Concrete mode is used to precompute lazily-initialized caches,
    # when we don't want this precomputation to show up on the flow graph.
    def append(self, operation):
        raise AssertionError, "concrete mode: cannot perform %s" % operation

# ____________________________________________________________


class FlowExecutionContext(ExecutionContext):

    def __init__(self, space, code, globals, constargs={}, closure=None,
                 name=None):
        ExecutionContext.__init__(self, space)
        self.code = code
        
        self.w_globals = w_globals = space.wrap(globals)
        
        self.crnt_offset = -1
        self.crnt_frame = None
        if closure is None:
            self.closure = None
        else:
            from pypy.interpreter.nestedscope import Cell
            self.closure = [Cell(Constant(value)) for value in closure]
        frame = self.create_frame()
        formalargcount = code.getformalargcount()
        arg_list = [Variable() for i in range(formalargcount)]
        for position, value in constargs.items():
            arg_list[position] = Constant(value)
        frame.setfastscope(arg_list)
        self.joinpoints = {}
        #for joinpoint in code.getjoinpoints():
        #    self.joinpoints[joinpoint] = []  # list of blocks
        initialblock = SpamBlock(FrameState(frame).copy())
        self.pendingblocks = [initialblock]
        self.graph = FunctionGraph(name or code.co_name, initialblock)

    def create_frame(self):
        # create an empty frame suitable for the code object
        # while ignoring any operation like the creation of the locals dict
        self.recorder = []
        return self.code.create_frame(self.space, self.w_globals,
                                      self.closure)

    def bytecode_trace(self, frame):
        self.recorder.bytecode_trace(self, frame)

    def guessbool(self, w_condition, **kwds):
        return self.recorder.guessbool(self, w_condition, **kwds)

    def guessexception(self, *classes):
        outcome = self.guessbool(Constant(last_exception, last_exception=True),
                                 cases = [None] + list(classes),
                                 replace_last_variable_except_in_first_case = [
                                     Constant(last_exception, last_exception=True),   # exc. class
                                     Constant(last_exc_value, last_exc_value=True)])  # exc. value
        if outcome is None:
            w_exc_cls, w_exc_value = None, None
        else:
            w_exc_cls, w_exc_value = self.recorder.crnt_block.inputargs[-2:]
        return outcome, w_exc_cls, w_exc_value

    def build_flow(self):
        from pypy.objspace.flow.objspace import UnwrapException
        while self.pendingblocks:
            block = self.pendingblocks.pop(0)
            frame = self.create_frame()
            try:
                self.recorder = block.patchframe(frame)
            except StopFlowing:
                continue   # restarting a dead SpamBlock
            try:
                self.crnt_frame = frame
                try:
                    w_result = frame.resume()
                finally:
                    self.crnt_frame = None

            except OperationThatShouldNotBePropagatedError, e:
                raise Exception(
                    'found an operation that always raises %s: %s' % (
                        self.space.unwrap(e.w_type).__name__,
                        self.space.unwrap(e.w_value)))

            except OperationError, e:
                link = Link([e.w_type, e.w_value], self.graph.exceptblock)
                self.recorder.crnt_block.closeblock(link)

            except StopFlowing:
                pass

            except MergeBlock, e:
                block, currentstate = e.args
                self.mergeblock(block, currentstate)

            else:
                assert w_result is not None
                link = Link([w_result], self.graph.returnblock)
                self.recorder.crnt_block.closeblock(link)

            del self.recorder
        self.fixeggblocks()

    def fixeggblocks(self):
        # EggBlocks reuse the variables of their previous block,
        # which is deemed not acceptable for simplicity of the operations
        # that will be performed later on the flow graph.
        def fixegg(node):
            if isinstance(node, EggBlock):
                mapping = {}
                for a in node.inputargs:
                    mapping[a] = Variable(a)
                node.renamevariables(mapping)
            elif isinstance(node, SpamBlock):
                del node.framestate     # memory saver
        traverse(fixegg, self.graph)

    def mergeblock(self, currentblock, currentstate):
        next_instr = currentstate.next_instr
        # can 'currentstate' be merged with one of the blocks that
        # already exist for this bytecode position?
        candidates = self.joinpoints.setdefault(next_instr, [])
        for block in candidates:
            newstate = block.framestate.union(currentstate)
            if newstate is not None:
                # yes
                finished = newstate == block.framestate
                break
        else:
            # no
            newstate = currentstate.copy()
            finished = False
            block = None

        if finished:
            newblock = block
        else:
            newblock = SpamBlock(newstate)
        # unconditionally link the current block to the newblock
        outputargs = currentstate.getoutputargs(newstate)
        currentblock.closeblock(Link(outputargs, newblock))
        # phew
        if not finished:
            if block is not None and block.exits:
                # to simplify the graph, we patch the old block to point
                # directly at the new block which is its generalization
                block.dead = True
                block.operations = ()
                block.exitswitch = None
                outputargs = block.framestate.getoutputargs(newstate)
                block.recloseblock(Link(outputargs, newblock))
            candidates.insert(0, newblock)
            self.pendingblocks.append(newblock)
