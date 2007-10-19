import array
from pypy.rpython.lltypesystem import lltype, llmemory

# An "arena" is a large area of memory which can hold a number of
# objects, not necessarily all of the same type or size.  It's used by
# some of our framework GCs.  Addresses that point inside arenas support
# direct arithmetic: adding and subtracting integers, and taking the
# difference of two addresses.  When not translated to C, the arena
# keeps track of which bytes are used by what object to detect GC bugs;
# it internally uses raw_malloc_usage() to estimate the number of bytes
# it needs to reserve.

class ArenaError(Exception):
    pass

class Arena(object):
    object_arena_location = {}     # {container: (arena, offset)}

    def __init__(self, nbytes, zero):
        self.nbytes = nbytes
        self.usagemap = array.array('c')
        self.objectptrs = {}        # {offset: ptr-to-container}
        self.objectsizes = {}       # {offset: size}
        self.freed = False
        self.reset(zero)

    def reset(self, zero, start=0, size=None):
        self.check()
        if size is None:
            stop = self.nbytes
        else:
            stop = start + size
        assert 0 <= start <= stop <= self.nbytes
        for offset, ptr in self.objectptrs.items():
            size = self.objectsizes[offset]
            if offset < start:   # object is before the cleared area
                assert offset + size <= start, "object overlaps cleared area"
            elif offset + size > stop:  # object is after the cleared area
                assert offset >= stop, "object overlaps cleared area"
            else:
                obj = ptr._obj
                del Arena.object_arena_location[obj]
                del self.objectptrs[offset]
                del self.objectsizes[offset]
                obj._free()
        if zero:
            initialbyte = "0"
        else:
            initialbyte = "#"
        self.usagemap[start:stop] = array.array('c', initialbyte*(stop-start))

    def check(self):
        if self.freed:
            raise ArenaError("arena was already freed")

    def _getid(self):
        address, length = self.usagemap.buffer_info()
        return address

    def getaddr(self, offset):
        if not (0 <= offset <= self.nbytes):
            raise ArenaError("Address offset is outside the arena")
        return fakearenaaddress(self, offset)

    def allocate_object(self, offset, size):
        self.check()
        bytes = llmemory.raw_malloc_usage(size)
        if offset + bytes > self.nbytes:
            raise ArenaError("object overflows beyond the end of the arena")
        zero = True
        for c in self.usagemap[offset:offset+bytes]:
            if c == '0':
                pass
            elif c == '#':
                zero = False
            else:
                raise ArenaError("new object overlaps a previous object")
        assert offset not in self.objectptrs
        addr2 = size._raw_malloc([], zero=zero)
        pattern = 'X' + 'x'*(bytes-1)
        self.usagemap[offset:offset+bytes] = array.array('c', pattern)
        self.objectptrs[offset] = addr2.ptr
        self.objectsizes[offset] = bytes
        Arena.object_arena_location[addr2.ptr._obj] = self, offset
        # common case: 'size' starts with a GCHeaderOffset.  In this case
        # we can also remember that the real object starts after the header.
        while isinstance(size, RoundedUpForAllocation):
            size = size.basesize
        if (isinstance(size, llmemory.CompositeOffset) and
            isinstance(size.offsets[0], llmemory.GCHeaderOffset)):
            objaddr = addr2 + size.offsets[0]
            hdrbytes = llmemory.raw_malloc_usage(size.offsets[0])
            objoffset = offset + hdrbytes
            assert objoffset not in self.objectptrs
            self.objectptrs[objoffset] = objaddr.ptr
            self.objectsizes[objoffset] = bytes - hdrbytes
            Arena.object_arena_location[objaddr.ptr._obj] = self, objoffset
        return addr2

class fakearenaaddress(llmemory.fakeaddress):

    def __init__(self, arena, offset):
        self.arena = arena
        self.offset = offset

    def _getptr(self):
        try:
            return self.arena.objectptrs[self.offset]
        except KeyError:
            self.arena.check()
            raise ArenaError("don't know yet what type of object "
                             "is at offset %d" % (self.offset,))
    ptr = property(_getptr)

    def __repr__(self):
        return '<arenaaddr %s + %d>' % (self.arena, self.offset)

    def __add__(self, other):
        if isinstance(other, (int, long)):
            position = self.offset + other
        elif isinstance(other, llmemory.AddressOffset):
            # this is really some Do What I Mean logic.  There are two
            # possible meanings: either we want to go past the current
            # object in the arena, or we want to take the address inside
            # the current object.  Try to guess...
            bytes = llmemory.raw_malloc_usage(other)
            if (self.offset in self.arena.objectsizes and
                bytes < self.arena.objectsizes[self.offset]):
                # looks like we mean "inside the object"
                return llmemory.fakeaddress.__add__(self, other)
            position = self.offset + bytes
        else:
            return NotImplemented
        return self.arena.getaddr(position)

    def __sub__(self, other):
        if isinstance(other, llmemory.AddressOffset):
            other = llmemory.raw_malloc_usage(other)
        if isinstance(other, (int, long)):
            return self.arena.getaddr(self.offset - other)
        if isinstance(other, fakearenaaddress):
            if self.arena is not other.arena:
                raise ArenaError("The two addresses are from different arenas")
            return self.offset - other.offset
        return NotImplemented

    def __nonzero__(self):
        return True

    def compare_with_fakeaddr(self, other):
        if not other:
            return None, None
        obj = other.ptr._obj
        innerobject = False
        while obj not in Arena.object_arena_location:
            obj = obj._parentstructure()
            if obj is None:
                return None, None     # not found in the arena
            innerobject = True
        arena, offset = Arena.object_arena_location[obj]
        if innerobject:
            # 'obj' is really inside the object allocated from the arena,
            # so it's likely that its address "should be" a bit larger than
            # what 'offset' says.
            # We could estimate the correct offset but it's a bit messy;
            # instead, let's check the answer doesn't depend on it
            if self.arena is arena:
                objectsize = arena.objectsizes[offset]
                if offset < self.offset < offset+objectsize:
                    raise AssertionError(
                        "comparing an inner address with a "
                        "fakearenaaddress that points in the "
                        "middle of the same object")
                offset += objectsize // 2      # arbitrary
        return arena, offset

    def __eq__(self, other):
        if isinstance(other, fakearenaaddress):
            arena = other.arena
            offset = other.offset
        elif isinstance(other, llmemory.fakeaddress):
            arena, offset = self.compare_with_fakeaddr(other)
        else:
            return llmemory.fakeaddress.__eq__(self, other)
        return self.arena is arena and self.offset == offset

    def __lt__(self, other):
        if isinstance(other, fakearenaaddress):
            arena = other.arena
            offset = other.offset
        elif isinstance(other, llmemory.fakeaddress):
            arena, offset = self.compare_with_fakeaddr(other)
            if arena is None:
                return False       # self < other-not-in-any-arena  => False
                                   # (arbitrarily)
        else:
            raise TypeError("comparing a %s and a %s" % (
                self.__class__.__name__, other.__class__.__name__))
        if self.arena is arena:
            return self.offset < offset
        else:
            return self.arena._getid() < arena._getid()

    def _cast_to_int(self):
        return self.arena._getid() + self.offset


class RoundedUpForAllocation(llmemory.AddressOffset):
    """A size that is rounded up in order to preserve alignment of objects
    following it.  For arenas containing heterogenous objects.
    """
    def __init__(self, basesize):
        assert isinstance(basesize, llmemory.AddressOffset)
        self.basesize = basesize

    def __repr__(self):
        return '< RoundedUpForAllocation %r >' % (self.basesize,)

    def ref(self, ptr):
        return self.basesize.ref(ptr)

    def _raw_malloc(self, rest, zero):
        return self.basesize._raw_malloc(rest, zero=zero)

    def raw_memcopy(self, srcadr, dstadr):
        self.basesize.raw_memcopy(srcadr, dstadr)

# ____________________________________________________________
#
# Public interface: arena_malloc(), arena_free(), arena_reset()
# are similar to raw_malloc(), raw_free() and raw_memclear(), but
# work with fakearenaaddresses on which arbitrary arithmetic is
# possible even on top of the llinterpreter.

def arena_malloc(nbytes, zero):
    """Allocate and return a new arena, optionally zero-initialized."""
    return Arena(nbytes, zero).getaddr(0)

def arena_free(arena_addr):
    """Release an arena."""
    assert isinstance(arena_addr, fakearenaaddress)
    assert arena_addr.offset == 0
    arena_addr.arena.reset(False)
    arena_addr.arena.freed = True

def arena_reset(arena_addr, size, zero):
    """Free all objects in the arena, which can then be reused.
    The arena is filled with zeroes if 'zero' is True.  This can also
    be used on a subrange of the arena."""
    assert isinstance(arena_addr, fakearenaaddress)
    arena_addr.arena.reset(zero, arena_addr.offset, size)

def arena_reserve(addr, size, check_alignment=True):
    """Mark some bytes in an arena as reserved, and returns addr.
    For debugging this can check that reserved ranges of bytes don't
    overlap.  The size must be symbolic; in non-translated version
    this is used to know what type of lltype object to allocate."""
    from pypy.rpython.memory.lltypelayout import memory_alignment
    assert isinstance(addr, fakearenaaddress)
    if check_alignment and (addr.offset & (memory_alignment-1)) != 0:
        raise ArenaError("object at offset %d would not be correctly aligned"
                         % (addr.offset,))
    addr.arena.allocate_object(addr.offset, size)

def round_up_for_allocation(size):
    """Round up the size in order to preserve alignment of objects
    following an object.  For arenas containing heterogenous objects."""
    return RoundedUpForAllocation(size)

# ____________________________________________________________
#
# Translation support: the functions above turn into the code below.
# We can tweak these implementations to be more suited to very large
# chunks of memory.

import os, sys
from pypy.rpython.lltypesystem import rffi, lltype
from pypy.rpython.extfunc import register_external
from pypy.rlib.objectmodel import debug_assert, CDefinedIntSymbolic

if os.name == 'posix':
    READ_MAX = (sys.maxint//4) + 1    # upper bound on reads to avoid surprises
    os_read = rffi.llexternal('read',
                              [rffi.INT, llmemory.Address, rffi.SIZE_T],
                              rffi.SIZE_T,
                              sandboxsafe=True)

    def clear_large_memory_chunk(baseaddr, size):
        # on Linux at least, reading from /dev/zero is the fastest way
        # to clear arenas, because the kernel knows that it doesn't
        # need to even allocate the pages before they are used
        try:
            fd = os.open('/dev/zero', os.O_RDONLY, 0644)
        except OSError:
            pass
        else:
            while size > 0:
                count = os_read(fd, baseaddr, min(READ_MAX, size))
                count = rffi.cast(lltype.Signed, count)
                if count < 0:
                    break
                size -= count
                baseaddr += count
            os.close(fd)

        if size > 0:     # reading from /dev/zero failed, fallback
            llmemory.raw_memclear(baseaddr, size)

else:
    # XXX any better implementation on Windows?
    clear_large_memory_chunk = llmemory.raw_memclear


def llimpl_arena_malloc(nbytes, zero):
    addr = llmemory.raw_malloc(nbytes)
    if zero and bool(addr):
        clear_large_memory_chunk(addr, nbytes)
    return addr
register_external(arena_malloc, [int, bool], llmemory.Address,
                  'll_arena.arena_malloc',
                  llimpl=llimpl_arena_malloc,
                  llfakeimpl=arena_malloc,
                  sandboxsafe=True)

def llimpl_arena_free(arena_addr):
    llmemory.raw_free(arena_addr)
register_external(arena_free, [llmemory.Address], None, 'll_arena.arena_free',
                  llimpl=llimpl_arena_free,
                  llfakeimpl=arena_free,
                  sandboxsafe=True)

def llimpl_arena_reset(arena_addr, size, zero):
    if zero:
        clear_large_memory_chunk(arena_addr, size)
register_external(arena_reset, [llmemory.Address, int, bool], None,
                  'll_arena.arena_reset',
                  llimpl=llimpl_arena_reset,
                  llfakeimpl=arena_reset,
                  sandboxsafe=True)

def llimpl_arena_reserve(addr, size):
    pass
register_external(arena_reserve, [llmemory.Address, int], None,
                  'll_arena.arena_reserve',
                  llimpl=llimpl_arena_reserve,
                  llfakeimpl=arena_reserve,
                  sandboxsafe=True)

llimpl_round_up_for_allocation = rffi.llexternal('ROUND_UP_FOR_ALLOCATION',
                                                 [rffi.INT], rffi.INT,
                                                 sandboxsafe=True)
register_external(round_up_for_allocation, [int], int,
                  'll_arena.round_up_for_allocation',
                  llimpl=llimpl_round_up_for_allocation,
                  llfakeimpl=round_up_for_allocation,
                  sandboxsafe=True)
