import sys
from pypy.rpython.memory.gc.semispace import SemiSpaceGC
from pypy.rpython.memory.gc.semispace import DEBUG_PRINT
from pypy.rpython.memory.gc.generation import GenerationGC, GCFLAG_FORWARDED
from pypy.rpython.memory.gc.generation import GCFLAG_NO_YOUNG_PTRS
from pypy.rpython.lltypesystem import lltype, llmemory, llarena
from pypy.rpython.lltypesystem.llmemory import raw_malloc_usage
from pypy.rpython.lltypesystem.lloperation import llop
from pypy.rlib.debug import ll_assert
from pypy.rlib.rarithmetic import ovfcheck

GCFLAG_UNVISITED = GenerationGC.first_unused_gcflag << 0
GCFLAG_AGING = GenerationGC.first_unused_gcflag << 1


class HybridGC(GenerationGC):
    """A two-generations semi-space GC like the GenerationGC,
    except that objects above a certain size are handled separately:
    they are allocated via raw_malloc/raw_free in a mark-n-sweep fashion.
    """
    first_unused_gcflag = GenerationGC.first_unused_gcflag << 2

    # the following values override the default arguments of __init__ when
    # translating to a real backend.
    TRANSLATION_PARAMS = GenerationGC.TRANSLATION_PARAMS.copy()
    TRANSLATION_PARAMS['large_object'] = 6*1024    # XXX adjust
    TRANSLATION_PARAMS['large_object_gcptrs'] = 31*1024    # XXX adjust
    TRANSLATION_PARAMS['min_nursery_size'] = 128*1024
    # condition: large_object <= large_object_gcptrs < min_nursery_size/4

    def __init__(self, *args, **kwds):
        large_object = kwds.pop('large_object', 24)
        large_object_gcptrs = kwds.pop('large_object_gcptrs', 32)
        GenerationGC.__init__(self, *args, **kwds)

        # Objects whose total size is at least 'large_object' bytes are
        # allocated separately in a mark-n-sweep fashion.  If the object
        # has GC pointers in its varsized part, we use instead the
        # higher limit 'large_object_gcptrs'.  The idea is that
        # separately allocated objects are allocated immediately "old"
        # and it's not good to have too many pointers from old to young
        # objects.

        # In this class, we assume that the 'large_object' limit is not
        # very high, so that all objects that wouldn't easily fit in the
        # nursery are considered large by this limit.  This is the
        # meaning of the 'assert' below.
        self.nonlarge_max = large_object - 1
        self.nonlarge_gcptrs_max = large_object_gcptrs - 1
        assert self.nonlarge_gcptrs_max <= self.lb_young_var_basesize
        assert self.nonlarge_max <= self.nonlarge_gcptrs_max
        self.large_objects_collect_trigger = self.space_size
        if DEBUG_PRINT:
            self._initial_trigger = self.large_objects_collect_trigger
        self.pending_external_object_list = self.AddressDeque()

    def setup(self):
        self.large_objects_list = self.AddressDeque()
        GenerationGC.setup(self)

    def set_max_heap_size(self, size):
        raise NotImplementedError

    # NB. to simplify the code, only varsized objects can be considered
    # 'large'.

    def malloc_varsize_clear(self, typeid, length, size, itemsize,
                             offset_to_length, can_collect,
                             has_finalizer=False):
        if has_finalizer or not can_collect:
            return SemiSpaceGC.malloc_varsize_clear(self, typeid, length, size,
                                                    itemsize, offset_to_length,
                                                    can_collect, has_finalizer)
        size_gc_header = self.gcheaderbuilder.size_gc_header
        nonvarsize = size_gc_header + size

        # Compute the maximal length that makes the object still
        # below 'nonlarge_max'.  All the following logic is usually
        # constant-folded because self.nonlarge_max, size and itemsize
        # are all constants (the arguments are constant due to
        # inlining) and self.has_gcptr_in_varsize() is constant-folded.
        if self.has_gcptr_in_varsize(typeid):
            nonlarge_max = self.nonlarge_gcptrs_max
        else:
            nonlarge_max = self.nonlarge_max

        if not raw_malloc_usage(itemsize):
            too_many_items = raw_malloc_usage(nonvarsize) > nonlarge_max
        else:
            maxlength = nonlarge_max - raw_malloc_usage(nonvarsize)
            maxlength = maxlength // raw_malloc_usage(itemsize)
            too_many_items = length > maxlength

        if not too_many_items:
            # With the above checks we know now that totalsize cannot be more
            # than 'nonlarge_max'; in particular, the + and * cannot overflow.
            # Let's try to fit the object in the nursery.
            totalsize = nonvarsize + itemsize * length
            result = self.nursery_free
            if raw_malloc_usage(totalsize) <= self.nursery_top - result:
                llarena.arena_reserve(result, totalsize)
                # GCFLAG_NO_YOUNG_PTRS is never set on young objs
                self.init_gc_object(result, typeid, flags=0)
                (result + size_gc_header + offset_to_length).signed[0] = length
                self.nursery_free = result + llarena.round_up_for_allocation(
                    totalsize)
                return llmemory.cast_adr_to_ptr(result+size_gc_header,
                                                llmemory.GCREF)
        return self.malloc_varsize_slowpath(typeid, length)

    def malloc_varsize_slowpath(self, typeid, length):
        # For objects that are too large, or when the nursery is exhausted.
        # In order to keep malloc_varsize_clear() as compact as possible,
        # we recompute what we need in this slow path instead of passing
        # it all as function arguments.
        size_gc_header = self.gcheaderbuilder.size_gc_header
        nonvarsize = size_gc_header + self.fixed_size(typeid)
        itemsize = self.varsize_item_sizes(typeid)
        offset_to_length = self.varsize_offset_to_length(typeid)
        try:
            varsize = ovfcheck(itemsize * length)
            totalsize = ovfcheck(nonvarsize + varsize)
        except OverflowError:
            raise MemoryError()
        if self.has_gcptr_in_varsize(typeid):
            nonlarge_max = self.nonlarge_gcptrs_max
        else:
            nonlarge_max = self.nonlarge_max
        if raw_malloc_usage(totalsize) > nonlarge_max:
            result = self.malloc_varsize_marknsweep(totalsize)
            flags = self.GCFLAGS_FOR_NEW_EXTERNAL_OBJECTS | GCFLAG_UNVISITED
        else:
            result = self.malloc_varsize_collecting_nursery(totalsize)
            flags = self.GCFLAGS_FOR_NEW_YOUNG_OBJECTS
        self.init_gc_object(result, typeid, flags)
        (result + size_gc_header + offset_to_length).signed[0] = length
        return llmemory.cast_adr_to_ptr(result+size_gc_header, llmemory.GCREF)

    malloc_varsize_slowpath._dont_inline_ = True

    def malloc_varsize_collecting_nursery(self, totalsize):
        result = self.collect_nursery()
        ll_assert(raw_malloc_usage(totalsize) <= self.nursery_top - result,
                  "not enough room in malloc_varsize_collecting_nursery()")
        llarena.arena_reserve(result, totalsize)
        self.nursery_free = result + llarena.round_up_for_allocation(
            totalsize)
        return result

    def malloc_varsize_marknsweep(self, totalsize):
        # In order to free the large objects from time to time, we
        # arbitrarily force a full collect() if none occurs when we have
        # allocated 'self.space_size' bytes of large objects.
        # XXX we should probably track the total raw_malloc'ed size
        # XXX and adjust sizes based on it; otherwise we risk doing
        # XXX many many collections if the program allocates a lot
        # XXX more than the current self.space_size.
        self.large_objects_collect_trigger -= raw_malloc_usage(totalsize)
        if self.large_objects_collect_trigger < 0:
            if DEBUG_PRINT:
                llop.debug_print(lltype.Void, "allocated",
                                 self._initial_trigger -
                                     self.large_objects_collect_trigger,
                                 "bytes, triggering full collection")
            self.semispace_collect()
        result = self.allocate_external_object(totalsize)
        if not result:
            raise MemoryError()
        # The parent classes guarantee zero-filled allocations, so we
        # need to follow suit.
        llmemory.raw_memclear(result, totalsize)
        size_gc_header = self.gcheaderbuilder.size_gc_header
        self.large_objects_list.append(result + size_gc_header)
        return result

    def allocate_external_object(self, totalsize):
        # XXX maybe we should use arena_malloc() above a certain size?
        # If so, we'd also use arena_reset() in malloc_varsize_marknsweep().
        return llmemory.raw_malloc(totalsize)

    # ___________________________________________________________________
    # the following methods are hook into SemiSpaceGC.semispace_collect()

    def starting_full_collect(self):
        # At the start of a collection, all raw_malloc'ed objects should
        # have the GCFLAG_UNVISITED bit set.  No other object ever has
        # this bit set.
        ll_assert(not self.pending_external_object_list.non_empty(),
                  "pending_external_object_list should be empty at start")
        if DEBUG_PRINT:
            self._nonmoving_copy_count = 0
            self._nonmoving_copy_size = 0

    def surviving(self, obj):
        # To use during a collection.  The objects that survive are the
        # ones with GCFLAG_FORWARDED set and GCFLAG_UNVISITED not set.
        # This is equivalent to self.is_forwarded() for all objects except
        # the ones obtained by raw_malloc.
        flags = self.header(obj).tid & (GCFLAG_FORWARDED|GCFLAG_UNVISITED)
        return flags == GCFLAG_FORWARDED

    def visit_external_object(self, obj):
        hdr = self.header(obj)
        if hdr.tid & GCFLAG_UNVISITED:
            # This is a not-visited-yet raw_malloced object.
            hdr.tid -= GCFLAG_UNVISITED
            self.pending_external_object_list.append(obj)

    def make_a_copy(self, obj, objsize):
        # During a full collect, all copied objects might implicitly come
        # from the nursery.  If they do, we must add the GCFLAG_NO_YOUNG_PTRS.
        # If they don't, we count how many times they are copied and when
        # some threshold is reached we make the copy a non-movable "external"
        # object.  For now we use a single flag GCFLAG_AGING, so threshold==2.
        tid = self.header(obj).tid
        if not (tid & GCFLAG_NO_YOUNG_PTRS):
            tid |= GCFLAG_NO_YOUNG_PTRS    # object comes from the nursery
        elif not (tid & GCFLAG_AGING):
            tid |= GCFLAG_AGING
        else:
            newobj = self.make_a_nonmoving_copy(obj, objsize)
            if newobj:
                return newobj
            tid &= ~GCFLAG_AGING
        # skip GenerationGC.make_a_copy() as we already did the right
        # thing about GCFLAG_NO_YOUNG_PTRS
        newobj = SemiSpaceGC.make_a_copy(self, obj, objsize)
        self.header(newobj).tid = tid
        return newobj

    def make_a_nonmoving_copy(self, obj, objsize):
        # NB. the object can have a finalizer or be a weakref, but
        # it's not an issue.
        totalsize = self.size_gc_header() + objsize
        if DEBUG_PRINT:
            self._nonmoving_copy_count += 1
            self._nonmoving_copy_size += raw_malloc_usage(totalsize)
        newaddr = self.allocate_external_object(totalsize)
        if not newaddr:
            return llmemory.NULL   # can't raise MemoryError during a collect()

        llmemory.raw_memcopy(obj - self.size_gc_header(), newaddr, totalsize)
        newobj = newaddr + self.size_gc_header()
        hdr = self.header(newobj)
        hdr.tid |= self.GCFLAGS_FOR_NEW_EXTERNAL_OBJECTS
        # GCFLAG_UNVISITED is not set
        self.large_objects_list.append(newobj)
        self.pending_external_object_list.append(newobj)
        return newobj

    def scan_copied(self, scan):
        # Alternate between scanning the regular objects we just moved
        # and scanning the raw_malloc'ed object we just visited.
        progress = True
        while progress:
            newscan = GenerationGC.scan_copied(self, scan)
            progress = newscan != scan
            scan = newscan
            while self.pending_external_object_list.non_empty():
                obj = self.pending_external_object_list.popleft()
                self.trace_and_copy(obj)
                progress = True
        return scan

    def finished_full_collect(self):
        ll_assert(not self.pending_external_object_list.non_empty(),
                  "pending_external_object_list should be empty at end")
        # free all mark-n-sweep-managed objects that have not been marked
        large_objects = self.large_objects_list
        remaining_large_objects = self.AddressDeque()
        if DEBUG_PRINT: alive_count = alive_size = 0
        if DEBUG_PRINT: dead_count = dead_size = 0
        while large_objects.non_empty():
            obj = large_objects.popleft()
            if self.header(obj).tid & GCFLAG_UNVISITED:
                if DEBUG_PRINT:dead_count+=1
                if DEBUG_PRINT:dead_size+=raw_malloc_usage(self.get_size(obj))
                addr = obj - self.gcheaderbuilder.size_gc_header
                llmemory.raw_free(addr)
            else:
                if DEBUG_PRINT:alive_count+=1
                if DEBUG_PRINT:alive_size+=raw_malloc_usage(self.get_size(obj))
                self.header(obj).tid |= GCFLAG_UNVISITED
                remaining_large_objects.append(obj)
        large_objects.delete()
        self.large_objects_list = remaining_large_objects
        # As we just collected, it's fine to raw_malloc'ate up to space_size
        # bytes again before we should force another collect.
        self.large_objects_collect_trigger = self.space_size

        if DEBUG_PRINT:
            self._initial_trigger = self.large_objects_collect_trigger
            llop.debug_print(lltype.Void,
                             "| [hybrid] made nonmoving:         ",
                             self._nonmoving_copy_size, "bytes in",
                             self._nonmoving_copy_count, "objs")
            llop.debug_print(lltype.Void,
                             "| [hybrid] nonmoving now alive:    ",
                             alive_size, "bytes in",
                             alive_count, "objs")
            llop.debug_print(lltype.Void,
                             "| [hybrid] nonmoving freed:        ",
                             dead_size, "bytes in",
                             dead_count, "objs")
