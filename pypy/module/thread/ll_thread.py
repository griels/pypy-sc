
from pypy.rpython.lltypesystem import rffi
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.tool import rffi_platform as platform
from pypy.rpython.extfunc import genericcallable
from pypy.rpython.annlowlevel import cast_instance_to_base_ptr
from pypy.translator.tool.cbuild import ExternalCompilationInfo
from pypy.rpython.lltypesystem import llmemory
import thread, py
from pypy.rpython.extregistry import ExtRegistryEntry
from pypy.annotation import model as annmodel
from pypy.rpython.lltypesystem.lltype import typeOf
from pypy.rlib.objectmodel import debug_assert
from pypy.tool import autopath

error = thread.error

eci = ExternalCompilationInfo(
    includes = ['unistd.h', 'src/thread.h'],
    separate_module_sources=['''
    #include <Python.h>
    #include <src/exception.h>
    #include <src/thread.h>
    '''],
    include_dirs = [str(py.path.local(autopath.pypydir).join('translator', 'c'))]
)

def llexternal(name, args, result, **kwds):
    return rffi.llexternal(name, args, result, compilation_info=eci,
                           **kwds)

CALLBACK = lltype.Ptr(lltype.FuncType([rffi.VOIDP], rffi.VOIDP))
c_thread_start = llexternal('RPyThreadStart', [CALLBACK, rffi.VOIDP], rffi.INT)
c_thread_get_ident = llexternal('RPyThreadGetIdent', [], rffi.INT)

TLOCKP = rffi.COpaquePtr('struct RPyOpaque_ThreadLock',
                          compilation_info=eci)

c_thread_lock_init = llexternal('RPyThreadLockInit', [TLOCKP], lltype.Void)
c_thread_acquirelock = llexternal('RPyThreadAcquireLock', [TLOCKP, rffi.INT],
                                  rffi.INT)
c_thread_releaselock = llexternal('RPyThreadReleaseLock', [TLOCKP], lltype.Void)

# another set of functions, this time in versions that don't cause the
# GIL to be released.  To use to handle the GIL lock itself.
c_thread_acquirelock_NOAUTO = llexternal('RPyThreadAcquireLock',
                                         [TLOCKP, rffi.INT], rffi.INT,
                                         threadsafe=False)
c_thread_releaselock_NOAUTO = llexternal('RPyThreadReleaseLock',
                                         [TLOCKP], lltype.Void,
                                         threadsafe=False)
c_thread_fused_releaseacquirelock_NOAUTO = llexternal(
     'RPyThreadFusedReleaseAcquireLock', [TLOCKP], lltype.Void,
                                         threadsafe=False)

def allocate_lock():
    ll_lock = lltype.malloc(TLOCKP.TO, flavor='raw')
    res = c_thread_lock_init(ll_lock)
    if res == -1:
        lltype.free(ll_lock, flavor='raw')
        raise error("out of resources")
    return Lock(ll_lock)

def allocate_lock_NOAUTO():
    ll_lock = lltype.malloc(TLOCKP.TO, flavor='raw')
    res = c_thread_lock_init(ll_lock)
    if res == -1:
        lltype.free(ll_lock, flavor='raw')
        raise error("out of resources")
    return Lock_NOAUTO(ll_lock)

def _start_new_thread(x, y):
    return thread.start_new_thread(x, (y,))

def ll_start_new_thread(l_func, arg):
    l_arg = cast_instance_to_base_ptr(arg)
    l_arg = rffi.cast(rffi.VOIDP, l_arg)
    ident = c_thread_start(l_func, l_arg)
    if ident == -1:
        raise error("can't start new thread")
    return ident

class LLStartNewThread(ExtRegistryEntry):
    _about_ = _start_new_thread
    
    def compute_result_annotation(self, s_func, s_arg):
        bookkeeper = self.bookkeeper
        s_result = bookkeeper.emulate_pbc_call(bookkeeper.position_key,
                                               s_func, [s_arg])
        assert annmodel.s_None.contains(s_result)
        return annmodel.SomeInteger()
    
    def specialize_call(self, hop):
        rtyper = hop.rtyper
        bk = rtyper.annotator.bookkeeper
        r_result = rtyper.getrepr(hop.s_result)
        hop.exception_is_here()
        args_r = [rtyper.getrepr(s_arg) for s_arg in hop.args_s]
        _callable = hop.args_s[0].const
        funcptr = lltype.functionptr(CALLBACK.TO, _callable.func_name,
                                     _callable=_callable)
        func_s = bk.immutablevalue(funcptr)
        s_args = [func_s, hop.args_s[1]]
        obj = rtyper.getannmixlevel().delayedfunction(
            ll_start_new_thread, s_args, annmodel.SomeInteger())
        bootstrap = rtyper.getannmixlevel().delayedfunction(
            _callable, [hop.args_s[1]], annmodel.s_None)
        vlist = [hop.inputconst(typeOf(obj), obj),
                 hop.inputconst(typeOf(bootstrap), bootstrap),
                 #hop.inputarg(args_r[0], 0),
                 hop.inputarg(args_r[1], 1)]
        return hop.genop('direct_call', vlist, r_result)

# wrappers...

def get_ident():
    return c_thread_get_ident()

def start_new_thread(x, y):
    return _start_new_thread(x, y[0])

class Lock(object):
    """ Container for low-level implementation
    of a lock object
    """
    def __init__(self, ll_lock):
        self._lock = ll_lock

    def acquire(self, flag):
        return bool(c_thread_acquirelock(self._lock, int(flag)))

    def release(self):
        # Sanity check: the lock must be locked
        if self.acquire(False):
            c_thread_releaselock(self._lock)
            raise error("bad lock")
        else:
            c_thread_releaselock(self._lock)

    def __del__(self):
        lltype.free(self._lock, flavor='raw')

class Lock_NOAUTO(object):
    """A special lock that doesn't cause the GIL to be released when
    we try to acquire it.  Used for the GIL itself."""

    def __init__(self, ll_lock):
        self._lock = ll_lock

    def acquire(self, flag):
        return bool(c_thread_acquirelock_NOAUTO(self._lock, int(flag)))

    def release(self):
        debug_assert(not self.acquire(False), "Lock_NOAUTO was not held!")
        c_thread_releaselock_NOAUTO(self._lock)

    def fused_release_acquire(self):
        debug_assert(not self.acquire(False), "Lock_NOAUTO was not held!")
        c_thread_fused_releaseacquirelock_NOAUTO(self._lock)

    def __del__(self):
        lltype.free(self._lock, flavor='raw')
