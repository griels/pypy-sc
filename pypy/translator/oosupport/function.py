from pypy.objspace.flow import model as flowmodel
from pypy.rpython.ootypesystem.ootype import Void
from pypy.translator.oosupport.metavm import InstructionList

class Function(object):
    def __init__(self, db, graph, name = None, is_method = False, is_entrypoint = False):
        self.db = db
        self.cts = db.genoo.TypeSystem(db)
        self.graph = graph
        self.name = self.cts.escape_name(name or graph.name)
        self.is_method = is_method
        self.is_entrypoint = is_entrypoint
        self.blocknum = {}
        self._set_args()
        self._set_locals()
        self.generator = self._create_generator()

    def get_name(self):
        return self.name

    def __repr__(self):
        return '<Function %s>' % self.name

    def __hash__(self):
        return hash(self.graph)

    def __eq__(self, other):
        return self.graph == other.graph

    def __ne__(self, other):
        return not self == other

    def _is_return_block(self, block):
        return (not block.exits) and len(block.inputargs) == 1

    def _is_raise_block(self, block):
        return (not block.exits) and len(block.inputargs) == 2        

    def _is_exc_handling_block(self, block):
        return block.exitswitch == flowmodel.c_last_exception
        
    def begin_render(self):
        raise NotImplementedError

    def render_return_block(self, block):
        raise NotImplementedError

    def render_raise_block(self, block):
        raise NotImplementedError

    def begin_try(self):
        raise NotImplementedError

    def end_try(self):
        raise NotImplementedError

    def begin_catch(self, llexitcase):
        raise NotImplementedError
    
    def end_catch(self, target_label):
        raise NotImplementedError
    
    def render(self, ilasm):
        if self.db.graph_name(self.graph) is not None and not self.is_method:
            return # already rendered

        if getattr(self.graph.func, 'suggested_primitive', False):
            assert False, 'Cannot render a suggested_primitive'

        self.ilasm = ilasm
        graph = self.graph
        self.begin_render()

        return_blocks = []
        for block in graph.iterblocks():
            if self._is_return_block(block):
                return_blocks.append(block)
            elif self._is_raise_block(block):
                self.render_raise_block(block)
            elif self._is_exc_handling_block(block):
                self.render_exc_handling_block(block)
            else:
                self.render_normal_block(block)

        # render return blocks at the end just to please the .NET
        # runtime that seems to need a return statement at the end of
        # the function
        for block in return_blocks:
            self.render_return_block(block)

        self.end_render()
        if not self.is_method:
            self.db.record_function(self.graph, self.name)

    def render_exc_handling_block(self, block):
        self.set_label(self._get_block_name(block))

        # renders all ops but the last one
        for op in block.operations[:-1]:
            self._render_op(op)

        # render the last one (if any!) and prepend a .try
        if block.operations:
            self.begin_try()
            self._render_op(block.operations[-1])

        # search for the "default" block to be executed when no exception is raised
        for link in block.exits:
            if link.exitcase is None:
                self._setup_link(link)
                target_label = self._get_block_name(link.target)
                self.ilasm.leave(target_label)

        if block.operations:
            self.end_try()

        # catch the exception and dispatch to the appropriate block
        for link in block.exits:
            if link.exitcase is None:
                continue # see above
            assert issubclass(link.exitcase, Exception)
            ll_meta_exc = link.llexitcase
            self.db.record_const(ll_meta_exc)
            self.begin_catch(link.llexitcase)
            self.store_exception_and_link(link)
            target_label = self._get_block_name(link.target)
            self.end_catch(target_label)

    def store_exception_and_link(self, link):
        raise NotImplementedError
            
    def render_normal_block(self, block):
        self.set_label(self._get_block_name(block))

        # renders all ops but the last one
        for op in block.operations:
            self._render_op(op)

        for link in block.exits:
            self._setup_link(link)
            target_label = self._get_block_name(link.target)
            if link.exitcase is None or link is block.exits[-1]:
                self.ilasm.branch(target_label)
            else:
                assert type(link.exitcase is bool)
                assert block.exitswitch is not None
                self.load(block.exitswitch)
                self.ilasm.branch_if(link.exitcase, target_label)

    def _setup_link(self, link):
        target = link.target
        for to_load, to_store in zip(link.args, target.inputargs):
            if to_load.concretetype is not Void:
                self.generator.load(to_load)
                self.generator.store(to_store)

    def _set_locals(self):
        # this code is partly borrowed from pypy.translator.c.funcgen.FunctionCodeGenerator
        # TODO: refactoring to avoid code duplication

        graph = self.graph
        mix = [graph.getreturnvar()]
        for block in graph.iterblocks():
            self.blocknum[block] = len(self.blocknum)
            mix.extend(block.inputargs)

            for op in block.operations:
                mix.extend(op.args)
                mix.append(op.result)
                if getattr(op, "cleanup", None) is not None:
                    cleanup_finally, cleanup_except = op.cleanup
                    for cleanupop in cleanup_finally + cleanup_except:
                        mix.extend(cleanupop.args)
                        mix.append(cleanupop.result)
            for link in block.exits:
                mix.extend(link.getextravars())
                mix.extend(link.args)

        # filter only locals variables, i.e.:
        #  - must be variables
        #  - must appear only once
        #  - must not be function parameters
        #  - must not have 'void' type

        args = {}
        for ctstype, name in self.args:
            args[name] = True
        
        locals = []
        seen = {}
        for v in mix:
            is_var = isinstance(v, flowmodel.Variable)
            if id(v) not in seen and is_var and v.name not in args and v.concretetype is not Void:
                locals.append(self.cts.llvar_to_cts(v))
                seen[id(v)] = True

        self.locals = locals

    def _set_args(self):
        args = [arg for arg in self.graph.getargs() if arg.concretetype is not Void]
        self.args = map(self.cts.llvar_to_cts, args)
        self.argset = set([argname for argtype, argname in self.args])

    def _get_block_name(self, block):
        return 'block%s' % self.blocknum[block]

    def _render_op(self, op):
        instr_list = self.db.genoo.opcodes.get(op.opname, None)
        assert instr_list is not None, 'Unknown opcode: %s ' % op
        assert isinstance(instr_list, InstructionList)
        instr_list.render(self, op)

    def field_name(self, obj, field):
        raise NotImplementedError
