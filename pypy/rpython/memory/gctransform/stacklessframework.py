from pypy.rpython.memory.gctransform.transform import var_ispyobj
from pypy.rpython.memory.gctransform.framework import FrameworkGCTransformer
from pypy.rpython.lltypesystem import lltype, llmemory


class StacklessFrameworkGCTransformer(FrameworkGCTransformer):
    use_stackless = True

    def __init__(self, translator):
        FrameworkGCTransformer.__init__(self, translator)
        # and now, fun fun fun, we need to inline malloc_fixedsize
        # manually into all 'malloc' operation users, because inlining
        # it after it has been stackless transformed is both a Very
        # Bad Idea and forbidden by the fact that stackless transform
        # makes it self-recursive!  Argh.
##        self.replace_and_inline_malloc_already_now()
        # nothing left to inline during code generation
        self.inline = False

##     def replace_and_inline_malloc_already_now(self):
##         for graph in self.translator.graphs:
##             any_malloc = False
##             for block in graph.iterblocks():
##                 if block.operations:
##                     newops = []
##                     for op in block.operations:
##                         if op.opname.startswith('malloc'):
##                             any_malloc = True
##                             ops = self.replace_malloc(op, [], block)
##                             if isinstance(ops, tuple):
##                                 ops = ops[0]
##                             newops.extend(ops)
##                         else:
##                             newops.append(op)
##                     block.operations = newops
##             if any_malloc:
##                 self.inline_helpers(graph)

    def build_stack_root_iterator(self):
        from pypy.rlib.rstack import stack_capture
        sizeofaddr = llmemory.sizeof(llmemory.Address)
        gcdata = self.gcdata
        captured_frame_holder = llmemory.raw_malloc(sizeofaddr)
        captured_frame_holder.address[0] = llmemory.NULL

        class StackRootIterator:
            _alloc_flavor_ = 'raw'

            def setup_root_stack():
                pass
            setup_root_stack = staticmethod(setup_root_stack)

            need_root_stack = False

            def __init__(self):
                # XXX what should be done with the stack_capture()d frames
                # when we are finished?  what about moving GCs?
                frame = llmemory.cast_ptr_to_adr(stack_capture())
                self.static_current = gcdata.static_root_start
                captured_frame_holder.address[0] = frame
                self.finished = False

            def pop(self):
                while self.static_current != gcdata.static_root_end:
                    result = self.static_current
                    self.static_current += sizeofaddr
                    if result.address[0].address[0] != llmemory.NULL:
                        return result.address[0]
                if not self.finished:
                    self.finished = True
                    return captured_frame_holder
                return llmemory.NULL

        return StackRootIterator
