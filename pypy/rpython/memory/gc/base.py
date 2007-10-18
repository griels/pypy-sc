from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rlib.objectmodel import debug_assert

class GCBase(object):
    _alloc_flavor_ = "raw"
    moving_gc = False

    def set_query_functions(self, is_varsize, getfinalizer,
                            offsets_to_gc_pointers,
                            fixed_size, varsize_item_sizes,
                            varsize_offset_to_variable_part,
                            varsize_offset_to_length,
                            varsize_offsets_to_gcpointers_in_var_part,
                            weakpointer_offset):
        self.getfinalizer = getfinalizer
        self.is_varsize = is_varsize
        self.offsets_to_gc_pointers = offsets_to_gc_pointers
        self.fixed_size = fixed_size
        self.varsize_item_sizes = varsize_item_sizes
        self.varsize_offset_to_variable_part = varsize_offset_to_variable_part
        self.varsize_offset_to_length = varsize_offset_to_length
        self.varsize_offsets_to_gcpointers_in_var_part = varsize_offsets_to_gcpointers_in_var_part
        self.weakpointer_offset = weakpointer_offset

    def write_barrier(self, addr, addr_to, addr_struct):
        addr_to.address[0] = addr

    def setup(self):
        pass

    def statistics(self, index):
        return -1

    def size_gc_header(self, typeid=0):
        return self.gcheaderbuilder.size_gc_header

    def malloc(self, typeid, length=0, zero=False):
        """For testing.  The interface used by the gctransformer is
        the four malloc_[fixed,var]size[_clear]() functions.
        """
        size = self.fixed_size(typeid)
        needs_finalizer = bool(self.getfinalizer(typeid))
        weakptr_offset = self.weakpointer_offset(typeid)
        #XXX cannot compare weakptr_offset with -1
        #contains_weakptr = weakpointer_offset. != -1
        if isinstance(weakptr_offset, int):
            assert weakptr_offset == -1
            contains_weakptr = False
        else:
            contains_weakptr = True
        assert not (needs_finalizer and contains_weakptr)
        if self.is_varsize(typeid):
            assert not contains_weakptr
            itemsize = self.varsize_item_sizes(typeid)
            offset_to_length = self.varsize_offset_to_length(typeid)
            if zero:
                malloc_varsize = self.malloc_varsize_clear
            else:
                malloc_varsize = self.malloc_varsize
            ref = malloc_varsize(typeid, length, size, itemsize,
                                 offset_to_length, True, needs_finalizer)
        else:
            if zero:
                malloc_fixedsize = self.malloc_fixedsize_clear
            else:
                malloc_fixedsize = self.malloc_fixedsize
            ref = malloc_fixedsize(typeid, size, True, needs_finalizer,
                                   contains_weakptr)
        # lots of cast and reverse-cast around...
        return llmemory.cast_ptr_to_adr(ref)

    def id(self, ptr):
        return lltype.cast_ptr_to_int(ptr)

    def x_swap_pool(self, newpool):
        return newpool

    def x_clone(self, clonedata):
        raise RuntimeError("no support for x_clone in the GC")

    def x_become(self, target_addr, source_addr):
        raise RuntimeError("no support for x_become in the GC")


class MovingGCBase(GCBase):
    moving_gc = True

    def __init__(self):
        self.wr_to_objects_with_id = []
        self.object_id_dict = {}
        self.object_id_dict_ends_at = 0

    def id(self, ptr):
        self.disable_finalizers()
        try:
            return self._compute_id(ptr)
        finally:
            self.enable_finalizers()

    def _compute_id(self, ptr):
        # XXX this may explode if --no-translation-rweakref is specified
        # ----------------------------------------------------------------
        # Basic logic: the list item wr_to_objects_with_id[i] contains a
        # weakref to the object whose id is i + 1.  The object_id_dict is
        # an optimization that tries to reduce the number of linear
        # searches in this list.
        # ----------------------------------------------------------------
        # Invariant: if object_id_dict_ends_at >= 0, then object_id_dict
        # contains all pairs {address: id}, for the addresses
        # of all objects that are the targets of the weakrefs of the
        # following slice: wr_to_objects_with_id[:object_id_dict_ends_at].
        # ----------------------------------------------------------------
        # Essential: as long as notify_objects_just_moved() is not called,
        # we assume that the objects' addresses did not change.  We also
        # assume that the address of a live object cannot be reused for
        # another object without an intervening notify_objects_just_moved()
        # call, but this could be fixed easily if needed.
        # ----------------------------------------------------------------
        # First check the dictionary
        i = self.object_id_dict_ends_at
        if i < 0:
            self.object_id_dict.clear()      # dictionary invalid
            self.object_id_dict_ends_at = 0
            i = 0
        else:
            adr = llmemory.cast_ptr_to_adr(ptr)
            try:
                i = self.object_id_dict[adr]
            except KeyError:
                pass
            else:
                # double-check that the answer we got is correct
                lst = self.wr_to_objects_with_id
                target = llmemory.weakref_deref(llmemory.GCREF, lst[i])
                debug_assert(target == ptr, "bogus object_id_dict")
                return i + 1     # found via the dict
        # Walk the tail of the list, where entries are not also in the dict
        lst = self.wr_to_objects_with_id
        end = len(lst)
        freeentry = -1
        while i < end:
            target = llmemory.weakref_deref(llmemory.GCREF, lst[i])
            if not target:
                freeentry = i
            else:
                # record this entry in the dict
                adr = llmemory.cast_ptr_to_adr(target)
                self.object_id_dict[adr] = i
                if target == ptr:
                    break               # found
            i += 1
        else:
            # not found
            wr = llmemory.weakref_create(ptr)
            if freeentry < 0:
                debug_assert(end == len(lst), "unexpected lst growth in gc_id")
                i = end
                lst.append(wr)
            else:
                i = freeentry       # reuse the id() of a dead object
                lst[i] = wr
            adr = llmemory.cast_ptr_to_adr(ptr)
            self.object_id_dict[adr] = i
        # all entries up to and including index 'i' are now valid in the dict
        # unless a collection occurred while we were working, in which case
        # the object_id_dict is bogus anyway
        if self.object_id_dict_ends_at >= 0:
            self.object_id_dict_ends_at = i + 1
        return i + 1       # this produces id() values 1, 2, 3, 4...

    def notify_objects_just_moved(self):
        self.object_id_dict_ends_at = -1


def choose_gc_from_config(config):
    """Return a (GCClass, GC_PARAMS) from the given config object.
    """
    assert config.translation.gctransformer == "framework"
    if config.translation.gc == "marksweep":
        GC_PARAMS = {'start_heap_size': 8*1024*1024} # XXX adjust
        from pypy.rpython.memory.gc.marksweep import MarkSweepGC
        return MarkSweepGC, GC_PARAMS
    if config.translation.gc == "statistics":
        GC_PARAMS = {'start_heap_size': 8*1024*1024} # XXX adjust
        from pypy.rpython.memory.gc.marksweep import PrintingMarkSweepGC
        return PrintingMarkSweepGC, GC_PARAMS
    elif config.translation.gc == "semispace":
        GC_PARAMS = {'space_size': 8*1024*1024} # XXX adjust
        from pypy.rpython.memory.gc.semispace import SemiSpaceGC
        return SemiSpaceGC, GC_PARAMS
    elif config.translation.gc == "generation":
        GC_PARAMS = {'space_size': 8*1024*1024, # XXX adjust
                     'nursery_size': 12*1024}
        from pypy.rpython.memory.gc.generation import GenerationGC
        return GenerationGC, GC_PARAMS
    else:
        raise ValueError("unknown value for frameworkgc: %r" % (
            config.translation.frameworkgc,))
