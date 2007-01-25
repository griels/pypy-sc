from pypy.objspace.flow.model import Variable, Constant, Block, Link
from pypy.objspace.flow.model import SpaceOperation, mkentrymap
from pypy.annotation        import model as annmodel
from pypy.jit.hintannotator import model as hintmodel
from pypy.jit.hintannotator.model import originalconcretetype
from pypy.rpython.lltypesystem import lltype, llmemory, lloperation
from pypy.rpython.rmodel import inputconst
from pypy.translator.unsimplify import varoftype, copyvar
from pypy.translator.unsimplify import split_block, split_block_at_start
#from pypy.translator.simplify import rec_op_has_side_effects
from pypy.translator.backendopt import graphanalyze
from pypy.translator.backendopt.ssa import SSA_to_SSI
from pypy.translator.unsimplify import split_block


class HasSideeffects(graphanalyze.GraphAnalyzer):

    EXCEPTIONS = ('debug_assert',)

    def analyze_exceptblock(self, block, seen=None):
        # graphs explicitly raising have side-effects
        return True

    def operation_is_true(self, op):
        opname = op.opname
        return (lloperation.LL_OPERATIONS[opname].sideeffects and
                opname not in self.EXCEPTIONS)


class MergePointFamily(object):
    def __init__(self, tsgraph):
        self.tsgraph = tsgraph
        self.count = 0
        self.resumepoint_after_mergepoint = {}
        self.localmergepoints = []
        
    def add(self, kind):
        result = self.count
        self.count += 1
        attrname = 'mp%d' % result
        if kind == 'local':
            self.localmergepoints.append(attrname)
        return attrname

    def getlocalattrnames(self):
        return self.localmergepoints

    def has_global_mergepoints(self):
        return bool(self.resumepoint_after_mergepoint)


class HintGraphTransformer(object):
    c_dummy = inputconst(lltype.Void, None)

    def __init__(self, hannotator, graph, is_portal=False):
        self.hannotator = hannotator
        self.graph = graph
        self.is_portal = is_portal
        self.graphcolor = self.graph_calling_color(graph)
        self.resumepoints = {}
        self.mergepoint_set = {}    # set of blocks
        self.mergepointfamily = MergePointFamily(graph)
        self.c_mpfamily = inputconst(lltype.Void, self.mergepointfamily)
        self.tsgraphs_seen = []

        t = self.hannotator.base_translator
        self.sideeffects_analyzer = HasSideeffects(t)

    def has_sideeffects(self, op):
        return self.sideeffects_analyzer.analyze(op)

    def transform(self):
        self.compute_merge_points()
        self.insert_save_return()
        self.insert_splits()
        self.split_after_calls()
        self.handle_hints()
        self.insert_merge_points()
        self.insert_enter_frame()
        self.insert_dispatcher()
        self.insert_ensure_queue()
        self.insert_leave_graph()

    def compute_merge_points(self):
        entrymap = mkentrymap(self.graph)
        startblock = self.graph.startblock
        global_merge_blocks = {}
        for block in self.graph.iterblocks():
            if not block.operations:
                continue
            op = block.operations[0]
            hashint = False
            cand = 0
            if (op.opname == 'hint' and
                op.args[1].value == {'global_merge_point': True}):
                hashint = True
                if block is startblock or len(entrymap[block]) > 1:
                    global_merge_blocks[block] = True
                    cand += 1
                else:
                    prevblock = entrymap[block][0].prevblock
                    if len(entrymap[prevblock]) > 1:
                        global_merge_blocks[prevblock] = True
                        cand += 1
            #op = block.operations[-1]
            #if (op.opname == 'hint' and
            #    op.args[1].value == {'global_merge_point': True}):
            #    hashint = True
            #    for link in block.exits:
            #        if len(entrymap[link.target]) > 1:
            #            global_merge_blocks[link.target] = True
            #            cand += 1
            assert not hashint or cand==1, (
                "ambigous global merge point hint: %r" % block)
            for op in block.operations[1:]:
                assert not (op.opname == 'hint' and
                    op.args[1].value == {'global_merge_point': True}), (
                    "stranded global merge point hint: %r" % block)
                
        for block, links in entrymap.items():
            if len(links) > 1 and block is not self.graph.returnblock:
                if block in global_merge_blocks:
                    self.mergepoint_set[block] = 'global'
                else:
                    self.mergepoint_set[block] = 'local'
        if startblock in global_merge_blocks:
            self.mergepoint_set[startblock] = 'global'

    def graph_calling_color(self, tsgraph):
        args_hs, hs_res = self.hannotator.bookkeeper.tsgraphsigs[tsgraph]
        if originalconcretetype(hs_res) is lltype.Void:
            c = 'gray'
        elif hs_res.is_green():
            c = 'yellow'
        else:
            c = 'red'
        return c

    def timeshifted_graph_of(self, graph, args_v, v_result):
        bk = self.hannotator.bookkeeper
        args_hs = [self.hannotator.binding(v) for v in args_v]
        hs_result = self.hannotator.binding(v_result)
        if isinstance(hs_result, hintmodel.SomeLLAbstractConstant):
            fixed = hs_result.is_fixed()
        else:
            fixed = False
        specialization_key = bk.specialization_key(fixed, args_hs)
        tsgraph = bk.get_graph_by_key(graph, specialization_key)
        self.tsgraphs_seen.append(tsgraph)
        return tsgraph

    # __________ helpers __________

    def genop(self, block, opname, args, resulttype=None, result_like=None, red=False):
        # 'result_like' can be a template variable whose hintannotation is
        # copied
        if resulttype is not None:
            v_res = varoftype(resulttype)
            if red:
                hs = hintmodel.SomeLLAbstractVariable(resulttype)
            else:
                hs = hintmodel.SomeLLAbstractConstant(resulttype, {})
            self.hannotator.setbinding(v_res, hs)
        elif result_like is not None:
            v_res = copyvar(self.hannotator, result_like)
        else:
            v_res = self.new_void_var()

        spaceop = SpaceOperation(opname, args, v_res)
        if isinstance(block, list):
            block.append(spaceop)
        else:
            block.operations.append(spaceop)
        return v_res

    def genswitch(self, block, v_exitswitch, false, true):
        block.exitswitch = v_exitswitch
        link_f = Link([], false)
        link_f.exitcase = False
        link_t = Link([], true)
        link_t.exitcase = True
        block.recloseblock(link_f, link_t)

    def new_void_var(self, name=None):
        v_res = varoftype(lltype.Void, name)
        self.hannotator.setbinding(v_res, annmodel.s_ImpossibleValue)
        return v_res

    def new_block_before(self, block):
        newinputargs = [copyvar(self.hannotator, var)
                        for var in block.inputargs]
        newblock = Block(newinputargs)
        bridge = Link(newinputargs, block)
        newblock.closeblock(bridge)
        return newblock

    def naive_split_block(self, block, position):
        newblock = Block([])
        newblock.operations = block.operations[position:]
        del block.operations[position:]
        newblock.exitswitch = block.exitswitch
        block.exitswitch = None
        newblock.recloseblock(*block.exits)
        block.recloseblock(Link([], newblock))
        return newblock

    def variables_alive(self, block, before_position):
        created_before = dict.fromkeys(block.inputargs)
        for op in block.operations[:before_position]:
            created_before[op.result] = True
        used = {}
        for op in block.operations[before_position:]:
            for v in op.args:
                used[v] = True
        for link in block.exits:
            for v in link.args:
                used[v] = True
        return [v for v in used if v in created_before]

    def sort_by_color(self, vars, by_color_of_vars=None):
        reds = []
        greens = []
        if by_color_of_vars is None:
            by_color_of_vars = vars
        for v, bcv in zip(vars, by_color_of_vars):
            if v.concretetype is lltype.Void:
                continue
            if self.hannotator.binding(bcv).is_green():
                greens.append(v)
            else:
                reds.append(v)
        return reds, greens

    def before_start_block(self):
        entryblock = self.new_block_before(self.graph.startblock)
        entryblock.isstartblock = True
        self.graph.startblock.isstartblock = False
        self.graph.startblock = entryblock
        return entryblock

    def before_return_block(self):
        block = self.graph.returnblock
        block.operations = []
        split_block(self.hannotator, block, 0)
        [link] = block.exits
        assert len(link.args) == 0
        link.args = [self.c_dummy]
        link.target.inputargs = [self.new_void_var('dummy')]
        self.graph.returnblock = link.target
        self.graph.returnblock.operations = ()
        return block

    # __________ transformation steps __________

    def insert_splits(self):
        hannotator = self.hannotator
        for block in self.graph.iterblocks():
            if block.exitswitch is not None:
                assert isinstance(block.exitswitch, Variable)
                hs_switch = hannotator.binding(block.exitswitch)
                if not hs_switch.is_green():
                    self.insert_split_handling(block)

    def insert_split_handling(self, block):
        # lots of clever in-line logic commented out
        v_redswitch = block.exitswitch
        link_f, link_t = block.exits
        if link_f.exitcase:
            link_f, link_t = link_t, link_f
        assert link_f.exitcase is False
        assert link_t.exitcase is True

##        constant_block = Block([])
##        nonconstant_block = Block([])

##        v_flag = self.genop(block, 'is_constant', [v_redswitch],
##                            resulttype = lltype.Bool)
##        self.genswitch(block, v_flag, true  = constant_block,
##                                      false = nonconstant_block)

##        v_greenswitch = self.genop(constant_block, 'revealconst',
##                                   [v_redswitch],
##                                   resulttype = lltype.Bool)
##        constant_block.exitswitch = v_greenswitch
##        constant_block.closeblock(link_f, link_t)

        reds, greens = self.sort_by_color(link_f.args, link_f.target.inputargs)
        self.genop(block, 'save_locals', reds)
        resumepoint = self.get_resume_point(link_f.target)
        c_resumepoint = inputconst(lltype.Signed, resumepoint)
        v_flag = self.genop(block, 'split',
                            [v_redswitch, c_resumepoint] + greens,
                            resulttype = lltype.Bool)

        block.exitswitch = v_flag
##        true_block = Block([])
##        true_link  = Link([], true_block)
##        true_link.exitcase   = True
##        true_link.llexitcase = True
##        block.recloseblock(link_f, true_link)

##        reds, greens = self.sort_by_color(link_t.args)
##        self.genop(true_block, 'save_locals', reds)
##        self.genop(true_block, 'enter_block', [])
##        true_block.closeblock(Link(link_t.args, link_t.target))

##        SSA_to_SSI({block     : True,    # reachable from outside
##                    true_block: False}, self.hannotator)

    def get_resume_point_link(self, block):
        try:
            return self.resumepoints[block]
        except KeyError:
            resumeblock = Block([])
            redcount   = 0
            greencount = 0
            newvars = []
            for v in block.inputargs:
                if v.concretetype is lltype.Void:
                    v1 = self.c_dummy
                elif self.hannotator.binding(v).is_green():
                    c = inputconst(lltype.Signed, greencount)
                    v1 = self.genop(resumeblock, 'restore_green', [c],
                                    result_like = v)
                    greencount += 1
                else:
                    c = inputconst(lltype.Signed, redcount)
                    v1 = self.genop(resumeblock, 'restore_local', [c],
                                    result_like = v)
                    redcount += 1
                newvars.append(v1)

            resumeblock.closeblock(Link(newvars, block))
            reenter_link = Link([], resumeblock)
            N = len(self.resumepoints)
            reenter_link.exitcase = N
            self.resumepoints[block] = reenter_link
            return reenter_link

    def get_resume_point(self, block):
        return self.get_resume_point_link(block).exitcase

    def go_to_if(self, block, target, v_finished_flag):
        block.exitswitch = v_finished_flag
        [link_f] = block.exits
        link_t = Link([self.c_dummy], target)
        link_f.exitcase = False
        link_t.exitcase = True
        block.recloseblock(link_f, link_t)

    def go_to_dispatcher_if(self, block, v_finished_flag):
        self.go_to_if(block, self.graph.returnblock, v_finished_flag)

    def insert_merge_points(self):
        for block, kind in self.mergepoint_set.items():
            self.insert_merge(block, kind)

    def insert_merge(self, block, kind):
        allvars = block.inputargs[:]
        block.inputargs[:] = [copyvar(self.hannotator, v) for v in allvars]
        reds1, greens1 = self.sort_by_color(block.inputargs)
        reds3, greens3 = self.sort_by_color(allvars)
        nextblock = self.naive_split_block(block, 0)
        self.genop(block, 'save_locals', reds1)

        mp   = self.mergepointfamily.add(kind)
        c_mp = inputconst(lltype.Void, mp)
        if kind == 'global':
            prefix = 'global_'

            greens2 = [copyvar(self.hannotator, v) for v in greens1]
            mergeblock = self.naive_split_block(block, len(block.operations))
            mergeblock.inputargs[:] = greens2

            self.genop(block, 'save_greens', greens1)
            block.recloseblock(Link([self.c_dummy], self.graph.returnblock))

            N = self.get_resume_point(mergeblock)
            c_resumeindex = inputconst(lltype.Signed, N)
            self.genop(block, 'guard_global_merge', [c_resumeindex])

            # Note: the jitstate.greens list will contain the correct
            # green gv's for the following global_merge_point, because
            # the green values have just been restored by the resume
            # point logic here
        else:
            mergeblock = block
            greens2 = greens1
            prefix = ''
        mergeblock.exits[0].args[:] = greens2
        nextblock.inputargs[:] = greens3

        v_finished_flag = self.genop(mergeblock, '%smerge_point' % (prefix,),
                                     [self.c_mpfamily, c_mp] + greens2,
                                     resulttype = lltype.Bool)
        self.go_to_dispatcher_if(mergeblock, v_finished_flag)

        restoreops = []
        for i, v in enumerate(reds3):
            c = inputconst(lltype.Signed, i)
            restoreops.append(SpaceOperation('restore_local', [c], v))
        nextblock.operations[:0] = restoreops

        if kind == 'global':
            N = self.get_resume_point(nextblock)
            self.mergepointfamily.resumepoint_after_mergepoint[mp] = N

    def insert_dispatcher(self):
        if self.resumepoints:
            block = self.before_return_block()
            self.genop(block, 'dispatch_next', [])
            if self.mergepointfamily.has_global_mergepoints():
                block = self.before_return_block()
                entryblock = self.before_start_block()
                v_rp = self.genop(entryblock, 'getresumepoint', [],
                                  resulttype = lltype.Signed)
                c_zero = inputconst(lltype.Signed, 0)
                v_abnormal_entry = self.genop(entryblock, 'int_ge',
                                              [v_rp, c_zero],
                                              resulttype = lltype.Bool)
                self.go_to_if(entryblock, block, v_abnormal_entry)

            v_switchcase = self.genop(block, 'getresumepoint', [],
                                      resulttype = lltype.Signed)
            block.exitswitch = v_switchcase
            defaultlink = block.exits[0]
            defaultlink.exitcase = 'default'
            links = self.resumepoints.values()
            links.sort(lambda l, r: cmp(l.exitcase, r.exitcase))
            links.append(defaultlink)
            block.recloseblock(*links)

    def insert_save_return(self):
        block = self.before_return_block()
        [v_retbox] = block.inputargs
        if self.graphcolor == 'gray':
            self.genop(block, 'save_locals', [])
        elif self.graphcolor == 'yellow':
            self.genop(block, 'save_locals', [])
            self.genop(block, 'save_greens', [v_retbox])
        elif self.graphcolor == 'red':
            self.genop(block, 'save_locals', [v_retbox])
        else:
            raise AssertionError(self.graph, self.graphcolor)
        self.genop(block, 'save_return', [])

    def insert_ensure_queue(self):
        entryblock = self.before_start_block()
        if self.mergepointfamily.has_global_mergepoints():
            prefix = 'replayable_'
        else:
            prefix = ''
        self.genop(entryblock, prefix+'ensure_queue', [self.c_mpfamily])

    def insert_enter_frame(self):
        entryblock = self.before_start_block()
        self.genop(entryblock, 'enter_frame', [])

    def insert_leave_graph(self):
        block = self.before_return_block()
        if self.is_portal:
            assert self.graphcolor == 'red'
            self.genop(block, 'leave_graph_portal', [])
        else:
            self.genop(block, 'leave_graph_%s' % (self.graphcolor,), [])

    # __________ handling of the various kinds of calls __________

    def graphs_from(self, spaceop):
        if spaceop.opname == 'direct_call':
            c_func = spaceop.args[0]
            fnobj = c_func.value._obj
            graphs = [fnobj.graph]
            args_v = spaceop.args[1:]
        elif spaceop.opname == 'indirect_call':
            graphs = spaceop.args[-1].value
            args_v = spaceop.args[1:-1]
        else:
            raise AssertionError(spaceop.opname)
        if not self.hannotator.policy.look_inside_graphs(graphs):
            return    # cannot follow this call
        for graph in graphs:
            tsgraph = self.timeshifted_graph_of(graph, args_v, spaceop.result)
            yield graph, tsgraph

    def guess_call_kind(self, spaceop):
        if spaceop.opname == 'direct_call':
            c_func = spaceop.args[0]
            fnobj = c_func.value._obj
            if (hasattr(fnobj._callable, 'oopspec') and
                self.hannotator.policy.oopspec):
                if fnobj._callable.oopspec.startswith('vable.'):
                    return 'vable'
                return 'oopspec'

        for v in spaceop.args:
            hs_arg = self.hannotator.binding(v)
            if not hs_arg.is_green():
                break
        else:
            hs_res = self.hannotator.binding(spaceop.result)
            if hs_res.is_green():
                # all-green arguments and result.
                # Does the function have side-effects?
                if not self.has_sideeffects(spaceop):
                    return 'green'
        colors = {}
        for graph, tsgraph in self.graphs_from(spaceop):
            color = self.graph_calling_color(tsgraph)
            colors[color] = tsgraph
        if not colors:
            return 'residual'   # cannot follow this call
        assert len(colors) == 1, colors   # buggy normalization?
        return color

    def split_after_calls(self):
        for block in list(self.graph.iterblocks()):
            for i in range(len(block.operations)-1, -1, -1):
                op = block.operations[i]
                if op.opname in ('direct_call', 'indirect_call'):
                    call_kind = self.guess_call_kind(op)
                    handler = getattr(self, 'handle_%s_call' % (call_kind,))
                    handler(block, i)

    def make_call(self, block, op, save_locals_vars, color='red'):
        # the 'save_locals' pseudo-operation is used to save all
        # alive local variables into the current JITState
        self.genop(block, 'save_locals', save_locals_vars)
        targets = dict(self.graphs_from(op))
        #for tsgraph in targets.values():
        #    if self.graph_global_mps(tsgraph):
        #        # make sure jitstate.resumepoint is set to zero
        #        self.genop(block, 'resetresumepoint', [])
        #        break
        #  XXX do the right thing for call to portals
        #
        args_v = op.args[1:]
        if op.opname == 'indirect_call':
            del args_v[-1]
        if len(targets) == 1:
            [tsgraph] = targets.values()
            c_tsgraph = inputconst(lltype.Void, tsgraph)
            v_finished = self.genop(block, '%s_call' % (color,),
                                    [c_tsgraph] + args_v,
                                    resulttype = lltype.Bool)
            # Void result, because the call doesn't return its redbox result,
            # but only has the hidden side-effect of putting it in the jitstate
        else:
            c_targets = inputconst(lltype.Void, targets)
            args_v = op.args[:1] + args_v + [c_targets]
            hs_func = self.hannotator.binding(args_v[0])
            if not hs_func.is_green():
                # XXX for now, assume that it will be a constant red box
                v_greenfunc = self.genop(block, 'revealconst', [args_v[0]],
                                  resulttype = originalconcretetype(hs_func))
                args_v[0] = v_greenfunc
            v_finished = self.genop(block, 'indirect_%s_call' % (color,),
                                    args_v,
                                    resulttype = lltype.Bool)
        self.go_to_dispatcher_if(block, v_finished)

    def handle_red_call(self, block, pos, color='red'):
        link = split_block(self.hannotator, block, pos+1)
        op = block.operations.pop(pos)
        #if op.opname == 'direct_call':
        #    f = open('LOG', 'a')
        #    print >> f, color, op.args[0].value
        #    f.close()
        assert len(block.operations) == pos
        nextblock = link.target
        linkargs = link.args
        varsalive = list(linkargs)

        if color == 'red':
            assert not self.hannotator.binding(op.result).is_green()
            # the result will be either passed as an extra local 0
            # by the caller, or restored by a restore_local
            try:
                index = varsalive.index(op.result)
            except ValueError:
                linkargs.insert(0, op.result)
                v_result = copyvar(self.hannotator, op.result)
                nextblock.inputargs.insert(0, v_result)
            else:
                del varsalive[index]
                old_v_result = linkargs.pop(index)
                linkargs.insert(0, old_v_result)
                v_result = nextblock.inputargs.pop(index)
                nextblock.inputargs.insert(0, v_result)
        else:
            if op.result in varsalive:
                index = varsalive.index(op.result)
                del varsalive[index]
                linkargs.pop(index)
                c_void = Constant(None, lltype.Void)
                linkargs.insert(0, c_void)
                v_result = nextblock.inputargs.pop(index)
                nextblock.inputargs.insert(0, v_result)                                
        reds, greens = self.sort_by_color(varsalive)

        v_func = op.args[0]
        hs_func = self.hannotator.binding(v_func)
        if hs_func.is_green():
            constantblock = block
            nonconstantblock = None
            blockset = {}
        else:
            constantblock = Block([])
            nonconstantblock = Block([])
            blockset = {constantblock: False,
                        nonconstantblock: False}
            v_is_constant = self.genop(block, 'is_constant', [v_func],
                                       resulttype = lltype.Bool)
            self.genswitch(block, v_is_constant, true  = constantblock,
                                                 false = nonconstantblock)

        postconstantblock = self.naive_split_block(constantblock,
                                                 len(constantblock.operations))
        blockset[postconstantblock] = False
        self.make_call(constantblock, op, reds, color)

        resumepoint = self.get_resume_point(nextblock)
        c_resumepoint = inputconst(lltype.Signed, resumepoint)
        self.genop(postconstantblock, 'collect_split', [c_resumepoint] + greens)
        resumeblock = self.get_resume_point_link(nextblock).target
        postconstantblock.recloseblock(Link([], resumeblock))

        if nonconstantblock is not None:
            v_res, nonconstantblock2 = self.handle_residual_call_details(nonconstantblock, 0,
                                                                         op, color,
                                                                         preserve_res = False)

            if color == 'red':
                linkargs[0] = v_res

            blockset[nonconstantblock2] = False            
            nonconstantblock2.recloseblock(Link(linkargs, nextblock))

        blockset[block] = True     # reachable from outside
        blockset[nextblock] = True # reachable from outside
        SSA_to_SSI(blockset, self.hannotator)

    def handle_gray_call(self, block, pos):
        self.handle_red_call(block, pos, color='gray')

    def handle_oopspec_call(self, block, pos):
        op = block.operations[pos]
        assert op.opname == 'direct_call'
        op.opname = 'oopspec_call'

    def handle_vable_call(self, block, pos):
        op = block.operations[pos]
        assert op.opname == 'direct_call'
        oopspec = op.args[0].value._obj._callable.oopspec
        name, _ = oopspec.split('(')
        kind, name = name.split('_', 1)

        if kind == 'vable.get':
            opname = 'getfield'
        else:
            assert kind == 'vable.set'
            opname = 'setfield'
        args = op.args[1:]
        args.insert(1, Constant(name, lltype.Void))
        block.operations[pos] = SpaceOperation(opname, args, op.result)
        
    def handle_green_call(self, block, pos):
        # green-returning call, for now (XXX) we assume it's an
        # all-green function that we can just call
        op = block.operations[pos]
        assert op.opname == 'direct_call'
        op.opname = 'green_call'

    def handle_yellow_call(self, block, pos):
        op = block.operations[pos]
        #if op.opname == 'direct_call':
        #    f = open('LOG', 'a')
        #    print >> f, 'handle_yellow_call', op.args[0].value
        #    f.close()
        hs_result = self.hannotator.binding(op.result)
        if not hs_result.is_green():
            # yellow calls are supposed to return greens,
            # add an indirection if it's not the case
            # XXX a bit strange
            RESULT = originalconcretetype(hs_result)
            v_tmp = varoftype(RESULT)
            hs = hintmodel.SomeLLAbstractConstant(RESULT, {})
            self.hannotator.setbinding(v_tmp, hs)
            v_real_result = op.result
            op.result = v_tmp
            newop = SpaceOperation('same_as', [v_tmp], v_real_result)
            block.operations.insert(pos+1, newop)

        link = split_block(self.hannotator, block, pos+1)
        op1 = block.operations.pop(pos)
        assert op1 is op
        assert len(block.operations) == pos
        nextblock = link.target
        varsalive = link.args
        try:
            index = varsalive.index(op.result)
        except ValueError:
            XXX-later

        del varsalive[index]
        v_result = nextblock.inputargs.pop(index)
        nextblock.inputargs.insert(0, v_result)

        reds, greens = self.sort_by_color(varsalive)
        postblock = self.naive_split_block(block, len(block.operations))
        self.make_call(block, op, reds, 'yellow')

        resumepoint = self.get_resume_point(nextblock)
        c_resumepoint = inputconst(lltype.Signed, resumepoint)
        self.genop(postblock, 'collect_split', [c_resumepoint] + greens)
        link.args = []
        link.target = self.get_resume_point_link(nextblock).target

        # to merge some of the possibly many return jitstates
        self.mergepoint_set[nextblock] = 'local'  

        SSA_to_SSI({block: True,
                    postblock: False}, self.hannotator)

    def handle_residual_call(self, block, pos):
        op = block.operations[pos]        
        if op.result.concretetype is lltype.Void:
            color = 'gray'
        else:
            color = 'red'
        v_res, _ = self.handle_residual_call_details(block, pos, op, color)
        return v_res
                    
    def handle_residual_call_details(self, block, pos, op, color, preserve_res=True):
        if op.opname == 'direct_call':
            args_v = op.args[1:]
        elif op.opname == 'indirect_call':
            args_v = op.args[1:-1]
        else:
            raise AssertionError(op.opname)
        newops = []
        # pseudo-obscure: the arguments for the call go in save_locals
        args_v = [v for v in args_v if v.concretetype is not lltype.Void]
        self.genop(newops, 'save_locals', args_v)
        call_index = len(newops)
        v_res = self.genop(newops, 'residual_%s_call' % (color,),
                           [op.args[0]], result_like = op.result)
        v_shape = self.genop(newops, 'after_residual_call', [], resulttype=lltype.Signed, red=True)
        reshape_index = len(newops)
        self.genop(newops, 'reshape', [v_shape])
        reshape_pos = pos+reshape_index
        block.operations[pos:pos+1] = newops
        if preserve_res:
            v_res = newops[call_index].result = op.result

        link = split_block(self.hannotator, block, reshape_pos)
        nextblock = link.target

        reds, greens = self.sort_by_color(link.args)
        self.genop(block, 'save_locals', reds)
        v_finished_flag = self.genop(block, 'promote', [v_shape],
                                     resulttype = lltype.Bool)
        self.go_to_dispatcher_if(block, v_finished_flag)

            
        return v_res, nextblock


    # __________ hints __________

    def handle_hints(self):
        for block in list(self.graph.iterblocks()):
            for i in range(len(block.operations)-1, -1, -1):
                op = block.operations[i]
                if op.opname == 'hint':
                    hints = op.args[1].value
                    for key, value in hints.items():
                        if value == True:
                            methname = 'handle_%s_hint' % (key,)
                            if hasattr(self, methname):
                                handler = getattr(self, methname)
                                break
                    else:
                        handler = self.handle_default_hint
                    handler(block, i)

    def handle_default_hint(self, block, i):
        # just discard the hint by default
        op = block.operations[i]
        newop = SpaceOperation('same_as', [op.args[0]], op.result)
        block.operations[i] = newop

    def handle_reverse_split_queue_hint(self, block, i):
        op = block.operations[i]
        newop = SpaceOperation('reverse_split_queue', [], op.result)
        block.operations[i] = newop

    def handle_forget_hint(self, block, i):
        # a hint for testing only
        op = block.operations[i]
        assert self.hannotator.binding(op.result).is_green()
        assert not self.hannotator.binding(op.args[0]).is_green()
        newop = SpaceOperation('revealconst', [op.args[0]], op.result)
        block.operations[i] = newop

    def handle_promote_hint(self, block, i):
        op = block.operations[i]
        v_promote = op.args[0]
        newop = SpaceOperation('revealconst', [v_promote], op.result)
        block.operations[i] = newop

        link = split_block(self.hannotator, block, i)

        reds, greens = self.sort_by_color(link.args)
        self.genop(block, 'save_locals', reds)
        v_finished_flag = self.genop(block, 'promote', [v_promote],
                                     resulttype = lltype.Bool)
        self.go_to_dispatcher_if(block, v_finished_flag)
