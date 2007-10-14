from pypy.rpython.lltypesystem.llmemory import raw_malloc, raw_free
from pypy.rpython.lltypesystem.llmemory import raw_memcopy, raw_memclear
from pypy.rpython.lltypesystem.llmemory import NULL, raw_malloc_usage
from pypy.rpython.memory.support import get_address_linked_list
from pypy.rpython.memory.gcheader import GCHeaderBuilder
from pypy.rpython.lltypesystem import lltype, llmemory, llarena
from pypy.rlib.objectmodel import free_non_gc_object, debug_assert
from pypy.rpython.lltypesystem.lloperation import llop
from pypy.rlib.rarithmetic import ovfcheck
from pypy.rpython.memory.gc.base import MovingGCBase


import sys, os

memoryError = MemoryError()

class SemiSpaceGC(MovingGCBase):
    _alloc_flavor_ = "raw"
    inline_simple_malloc = True

    HDR = lltype.Struct('header', ('forw', llmemory.Address),
                                  ('typeid', lltype.Signed))

    def __init__(self, AddressLinkedList, space_size=4096,
                 max_space_size=sys.maxint//2+1,
                 get_roots=None):
        MovingGCBase.__init__(self)
        self.space_size = space_size
        self.max_space_size = max_space_size
        self.get_roots = get_roots
        self.gcheaderbuilder = GCHeaderBuilder(self.HDR)
        self.AddressLinkedList = AddressLinkedList

    def setup(self):
        self.tospace = llarena.arena_malloc(self.space_size, True)
        debug_assert(bool(self.tospace), "couldn't allocate tospace")
        self.top_of_space = self.tospace + self.space_size
        self.fromspace = llarena.arena_malloc(self.space_size, True)
        debug_assert(bool(self.fromspace), "couldn't allocate fromspace")
        self.free = self.tospace
        self.objects_with_finalizers = self.AddressLinkedList()
        self.run_finalizers = self.AddressLinkedList()
        self.executing_finalizers = False
        self.objects_with_weakrefs = self.AddressLinkedList()

    def malloc_fixedsize(self, typeid, size, can_collect, has_finalizer=False,
                         contains_weakptr=False):
        size_gc_header = self.gcheaderbuilder.size_gc_header
        totalsize = size_gc_header + size
        result = self.free
        if raw_malloc_usage(totalsize) > self.top_of_space - result:
            if not can_collect:
                raise memoryError
            result = self.obtain_free_space(totalsize)
        llarena.arena_reserve(result, totalsize)
        self.init_gc_object(result, typeid)
        self.free = result + totalsize
        if has_finalizer:
            self.objects_with_finalizers.append(result + size_gc_header)
        if contains_weakptr:
            self.objects_with_weakrefs.append(result + size_gc_header)
        return llmemory.cast_adr_to_ptr(result+size_gc_header, llmemory.GCREF)

    def malloc_varsize(self, typeid, length, size, itemsize, offset_to_length,
                       can_collect, has_finalizer=False):
        size_gc_header = self.gcheaderbuilder.size_gc_header
        nonvarsize = size_gc_header + size
        try:
            varsize = ovfcheck(itemsize * length)
            totalsize = ovfcheck(nonvarsize + varsize)
        except OverflowError:
            raise memoryError
        result = self.free
        if raw_malloc_usage(totalsize) > self.top_of_space - result:
            if not can_collect:
                raise memoryError
            result = self.obtain_free_space(totalsize)
        llarena.arena_reserve(result, totalsize)
        self.init_gc_object(result, typeid)
        (result + size_gc_header + offset_to_length).signed[0] = length
        self.free = result + llarena.round_up_for_allocation(totalsize)
        if has_finalizer:
            self.objects_with_finalizers.append(result + size_gc_header)
        return llmemory.cast_adr_to_ptr(result+size_gc_header, llmemory.GCREF)

    # for now, the spaces are filled with zeroes in advance
    malloc_fixedsize_clear = malloc_fixedsize
    malloc_varsize_clear   = malloc_varsize

    def obtain_free_space(self, needed):
        # a bit of tweaking to maximize the performance and minimize the
        # amount of code in an inlined version of malloc_fixedsize()
        if not self.try_obtain_free_space(needed):
            raise memoryError
        return self.free
    obtain_free_space.dont_inline = True

    def try_obtain_free_space(self, needed):
        # XXX for bonus points do big objects differently
        needed = raw_malloc_usage(needed)
        self.semispace_collect()
        missing = needed - (self.top_of_space - self.free)
        if missing <= 0:
            return True      # success
        else:
            # first check if the object could possibly fit
            proposed_size = self.space_size
            while missing > 0:
                if proposed_size >= self.max_space_size:
                    return False    # no way
                missing -= proposed_size
                proposed_size *= 2
            # For address space fragmentation reasons, we double the space
            # size possibly several times, moving the objects at each step,
            # instead of going directly for the final size.  We assume that
            # it's a rare case anyway.
            while self.space_size < proposed_size:
                if not self.double_space_size():
                    return False
            debug_assert(needed <= self.top_of_space - self.free,
                         "double_space_size() failed to do its job")
            return True

    def double_space_size(self):
        old_fromspace = self.fromspace
        newsize = self.space_size * 2
        newspace = llarena.arena_malloc(newsize, True)
        if not newspace:
            return False    # out of memory
        llarena.arena_free(old_fromspace)
        self.fromspace = newspace
        # now self.tospace contains the existing objects and
        # self.fromspace is the freshly allocated bigger space

        self.semispace_collect(size_changing=True)
        self.top_of_space = self.tospace + newsize
        # now self.tospace is the freshly allocated bigger space,
        # and self.fromspace is the old smaller space, now empty
        llarena.arena_free(self.fromspace)

        newspace = llarena.arena_malloc(newsize, True)
        if not newspace:
            # Complex failure case: we have in self.tospace a big chunk
            # of memory, and the two smaller original spaces are already gone.
            # Unsure if it's worth these efforts, but we can artificially
            # split self.tospace in two again...
            self.max_space_size = self.space_size    # don't try to grow again,
            #              because doing arena_free(self.fromspace) would crash
            self.fromspace = self.tospace + self.space_size
            self.top_of_space = self.fromspace
            debug_assert(self.free <= self.top_of_space,
                         "unexpected growth of GC space usage during collect")
            return False     # out of memory

        self.fromspace = newspace
        self.space_size = newsize
        return True    # success

    def collect(self):
        self.semispace_collect()
        # the indirection is required by the fact that collect() is referred
        # to by the gc transformer, and the default argument would crash

    def semispace_collect(self, size_changing=False):
        #llop.debug_print(lltype.Void, 'semispace_collect', int(size_changing))
        tospace = self.fromspace
        fromspace = self.tospace
        self.fromspace = fromspace
        self.tospace = tospace
        self.top_of_space = tospace + self.space_size
        scan = self.free = tospace
        self.collect_roots()
        scan = self.scan_copied(scan)
        if self.objects_with_weakrefs.non_empty():
            self.invalidate_weakrefs()
        if self.run_finalizers.non_empty():
            self.update_run_finalizers()
        if self.objects_with_finalizers.non_empty():
            self.deal_with_objects_with_finalizers()
        scan = self.scan_copied(scan)
        if not size_changing:
            llarena.arena_reset(fromspace, self.space_size, True)
            self.execute_finalizers()

    def scan_copied(self, scan):
        while scan < self.free:
            curr = scan + self.size_gc_header()
            self.trace_and_copy(curr)
            scan += self.size_gc_header() + self.get_size(curr)
        return scan

    def collect_roots(self):
        roots = self.get_roots()
        while 1:
            root = roots.pop()
            if root == NULL:
                break
            root.address[0] = self.copy(root.address[0])
        free_non_gc_object(roots)

    def copy(self, obj):
        # Objects not living the GC heap have all been initialized by
        # setting their 'forw' address so that it points to themselves.
        # The logic below will thus simply return 'obj' if 'obj' is prebuilt.
##         print "copying regularly", obj,
        if self.is_forwarded(obj):
##             print "already copied to", self.get_forwarding_address(obj)
            return self.get_forwarding_address(obj)
        else:
            newaddr = self.free
            totalsize = self.size_gc_header() + self.get_size(obj)
            llarena.arena_reserve(newaddr, totalsize)
            raw_memcopy(obj - self.size_gc_header(), newaddr, totalsize)
            self.free += totalsize
            newobj = newaddr + self.size_gc_header()
##             print "to", newobj
            self.set_forwarding_address(obj, newobj)
            return newobj

    def trace_and_copy(self, obj):
        gc_info = self.header(obj)
        typeid = gc_info.typeid
        offsets = self.offsets_to_gc_pointers(typeid)
        i = 0
        while i < len(offsets):
            pointer = obj + offsets[i]
            if pointer.address[0] != NULL:
                pointer.address[0] = self.copy(pointer.address[0])
            i += 1
        if self.is_varsize(typeid):
            offset = self.varsize_offset_to_variable_part(
                typeid)
            length = (obj + self.varsize_offset_to_length(typeid)).signed[0]
            offsets = self.varsize_offsets_to_gcpointers_in_var_part(typeid)
            itemlength = self.varsize_item_sizes(typeid)
            i = 0
            while i < length:
                item = obj + offset + itemlength * i
                j = 0
                while j < len(offsets):
                    pointer = item + offsets[j]
                    if pointer.address[0] != NULL:
                        pointer.address[0] = self.copy(pointer.address[0])
                    j += 1
                i += 1

    def is_forwarded(self, obj):
        return self.header(obj).forw != NULL

    def get_forwarding_address(self, obj):
        return self.header(obj).forw

    def set_forwarding_address(self, obj, newobj):
        gc_info = self.header(obj)
        gc_info.forw = newobj

    def get_size(self, obj):
        typeid = self.header(obj).typeid
        size = self.fixed_size(typeid)
        if self.is_varsize(typeid):
            lenaddr = obj + self.varsize_offset_to_length(typeid)
            length = lenaddr.signed[0]
            size += length * self.varsize_item_sizes(typeid)
            size = llarena.round_up_for_allocation(size)
        return size

    def header(self, addr):
        addr -= self.gcheaderbuilder.size_gc_header
        return llmemory.cast_adr_to_ptr(addr, lltype.Ptr(self.HDR))

    def init_gc_object(self, addr, typeid):
        hdr = llmemory.cast_adr_to_ptr(addr, lltype.Ptr(self.HDR))
        #hdr.forw = NULL   -- unneeded, the space is initially filled with zero
        hdr.typeid = typeid

    def init_gc_object_immortal(self, addr, typeid):
        # immortal objects always have forward to themselves
        hdr = llmemory.cast_adr_to_ptr(addr, lltype.Ptr(self.HDR))
        hdr.forw = addr + self.gcheaderbuilder.size_gc_header
        hdr.typeid = typeid

    def deal_with_objects_with_finalizers(self):
        # walk over list of objects with finalizers
        # if it is not copied, add it to the list of to-be-called finalizers
        # and copy it, to me make the finalizer runnable
        new_with_finalizer = self.AddressLinkedList()
        while self.objects_with_finalizers.non_empty():
            obj = self.objects_with_finalizers.pop()
            if self.is_forwarded(obj):
                new_with_finalizer.append(self.get_forwarding_address(obj))
            else:
                self.run_finalizers.append(self.copy(obj))
        self.objects_with_finalizers.delete()
        self.objects_with_finalizers = new_with_finalizer

    def invalidate_weakrefs(self):
        # walk over list of objects that contain weakrefs
        # if the object it references survives then update the weakref
        # otherwise invalidate the weakref
        new_with_weakref = self.AddressLinkedList()
        while self.objects_with_weakrefs.non_empty():
            obj = self.objects_with_weakrefs.pop()
            if not self.is_forwarded(obj):
                continue # weakref itself dies
            obj = self.get_forwarding_address(obj)
            offset = self.weakpointer_offset(self.header(obj).typeid)
            pointing_to = (obj + offset).address[0]
            if pointing_to:
                if self.is_forwarded(pointing_to):
                    (obj + offset).address[0] = self.get_forwarding_address(
                        pointing_to)
                    new_with_weakref.append(obj)
                else:
                    (obj + offset).address[0] = NULL
        self.objects_with_weakrefs.delete()
        self.objects_with_weakrefs = new_with_weakref

    def update_run_finalizers(self):
        # we are in an inner collection, caused by a finalizer
        # the run_finalizers objects need to be copied
        new_run_finalizer = self.AddressLinkedList()
        while self.run_finalizers.non_empty():
            obj = self.run_finalizers.pop()
            new_run_finalizer.append(self.copy(obj))
        self.run_finalizers.delete()
        self.run_finalizers = new_run_finalizer

    def execute_finalizers(self):
        if self.executing_finalizers:
            return    # the outer invocation of execute_finalizers() will do it
        self.executing_finalizers = True
        try:
            while self.run_finalizers.non_empty():
                obj = self.run_finalizers.pop()
                hdr = self.header(obj)
                finalizer = self.getfinalizer(hdr.typeid)
                finalizer(obj)
        finally:
            self.executing_finalizers = False

    STATISTICS_NUMBERS = 0
