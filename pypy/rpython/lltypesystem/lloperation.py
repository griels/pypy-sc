"""
The table of all LL operations.
"""

from pypy.rpython.extregistry import ExtRegistryEntry


class LLOp(object):

    def __init__(self, sideeffects=True, canfold=False, canraise=(),
                 pyobj=False, canunwindgc=False):
        # self.opname = ... (set afterwards)

        if canfold:
            sideeffects = False

        # The operation has no side-effects: it can be removed
        # if its result is not used
        self.sideeffects = sideeffects

        # Can be safely constant-folded: no side-effects
        #  and always gives the same result for given args
        self.canfold = canfold

        # Exceptions that can be raised
        self.canraise = canraise
        assert isinstance(canraise, tuple)

        # The operation manipulates PyObjects
        self.pyobj = pyobj

        # The operation can unwind the stack in a stackless gc build
        self.canunwindgc = canunwindgc
        if canunwindgc:
            if (StackException not in self.canraise and
                Exception not in self.canraise):
                self.canraise += (StackException,)

    # __________ make the LLOp instances callable from LL helpers __________

    __name__ = property(lambda self: 'llop_'+self.opname)

    def __call__(self, RESULTTYPE, *args):
        raise TypeError, "llop is meant to be rtyped and not called direclty"


def enum_ops_without_sideeffects(raising_is_ok=False):
    """Enumerate operations that have no side-effects
    (see also enum_foldable_ops)."""
    for opname, opdesc in LL_OPERATIONS.iteritems():
        if not opdesc.sideeffects:
            if not opdesc.canraise or raising_is_ok:
                yield opname

def enum_foldable_ops(raising_is_ok=False):
    """Enumerate operations that can be constant-folded."""
    for opname, opdesc in LL_OPERATIONS.iteritems():
        if opdesc.canfold:
            if not opdesc.canraise or raising_is_ok:
                yield opname


class Entry(ExtRegistryEntry):
    "Annotation and rtyping of LLOp instances, which are callable."
    _type_ = LLOp

    def compute_result_annotation(self, RESULTTYPE, *args):
        from pypy.annotation.model import lltype_to_annotation
        assert RESULTTYPE.is_constant()
        return lltype_to_annotation(RESULTTYPE.const)

    def specialize_call(self, hop):
        op = self.instance    # the LLOp object that was called
        args_v = [hop.inputarg(r, i+1) for i, r in enumerate(hop.args_r[1:])]
        hop.exception_is_here()
        return hop.genop(op.opname, args_v, resulttype=hop.r_result.lowleveltype)


class StackException(Exception):
    """Base for internal exceptions possibly used by the stackless
    implementation."""

# ____________________________________________________________
#
# This list corresponds to the operations implemented by the LLInterpreter.
# XXX Some clean-ups are needed:
#      * many exception-raising operations are being replaced by calls to helpers
#      * float_mod vs float_fmod ?
# Run test_lloperation after changes.  Feel free to clean up LLInterpreter too :-)

LL_OPERATIONS = {

    'direct_call':          LLOp(canraise=(Exception,)),
    'indirect_call':        LLOp(canraise=(Exception,)),
    'safe_call':            LLOp(),
    'unsafe_call':          LLOp(canraise=(Exception,)),

    # __________ numeric operations __________

    'bool_not':             LLOp(canfold=True),

    'char_lt':              LLOp(canfold=True),
    'char_le':              LLOp(canfold=True),
    'char_eq':              LLOp(canfold=True),
    'char_ne':              LLOp(canfold=True),
    'char_gt':              LLOp(canfold=True),
    'char_ge':              LLOp(canfold=True),

    'unichar_eq':           LLOp(canfold=True),
    'unichar_ne':           LLOp(canfold=True),

    'int_is_true':          LLOp(canfold=True),
    'int_neg':              LLOp(canfold=True),
    'int_neg_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_abs':              LLOp(canfold=True),
    'int_abs_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_invert':           LLOp(canfold=True),

    'int_add':              LLOp(canfold=True),
    'int_sub':              LLOp(canfold=True),
    'int_mul':              LLOp(canfold=True),
    'int_floordiv':         LLOp(canfold=True),
    'int_floordiv_zer':     LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'int_mod':              LLOp(canfold=True),
    'int_mod_zer':          LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'int_lt':               LLOp(canfold=True),
    'int_le':               LLOp(canfold=True),
    'int_eq':               LLOp(canfold=True),
    'int_ne':               LLOp(canfold=True),
    'int_gt':               LLOp(canfold=True),
    'int_ge':               LLOp(canfold=True),
    'int_and':              LLOp(canfold=True),
    'int_or':               LLOp(canfold=True),
    'int_lshift':           LLOp(canfold=True),
    'int_lshift_val':       LLOp(canfold=True, canraise=(ValueError,)),
    'int_rshift':           LLOp(canfold=True),
    'int_rshift_val':       LLOp(canfold=True, canraise=(ValueError,)),
    'int_xor':              LLOp(canfold=True),

    'int_add_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_sub_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_mul_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_floordiv_ovf':     LLOp(canfold=True, canraise=(OverflowError,)),
    'int_floordiv_ovf_zer': LLOp(canfold=True, canraise=(OverflowError, ZeroDivisionError)),
    'int_mod_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_mod_ovf_zer':      LLOp(canfold=True, canraise=(OverflowError, ZeroDivisionError)),
    'int_lshift_ovf':       LLOp(canfold=True, canraise=(OverflowError,)),
    'int_lshift_ovf_val':   LLOp(canfold=True, canraise=(OverflowError, ValueError,)),

    'uint_is_true':         LLOp(canfold=True),
    'uint_neg':             LLOp(canfold=True),
    'uint_abs':             LLOp(canfold=True),
    'uint_invert':          LLOp(canfold=True),

    'uint_add':             LLOp(canfold=True),
    'uint_sub':             LLOp(canfold=True),
    'uint_mul':             LLOp(canfold=True),
    'uint_floordiv':        LLOp(canfold=True),
    'uint_floordiv_zer':    LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'uint_mod':             LLOp(canfold=True),
    'uint_mod_zer':         LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'uint_lt':              LLOp(canfold=True),
    'uint_le':              LLOp(canfold=True),
    'uint_eq':              LLOp(canfold=True),
    'uint_ne':              LLOp(canfold=True),
    'uint_gt':              LLOp(canfold=True),
    'uint_ge':              LLOp(canfold=True),
    'uint_and':             LLOp(canfold=True),
    'uint_or':              LLOp(canfold=True),
    'uint_lshift':          LLOp(canfold=True),
    'uint_lshift_val':      LLOp(canfold=True, canraise=(ValueError,)),
    'uint_rshift':          LLOp(canfold=True),
    'uint_rshift_val':      LLOp(canfold=True, canraise=(ValueError,)),
    'uint_xor':             LLOp(canfold=True),

    'float_is_true':        LLOp(canfold=True),
    'float_neg':            LLOp(canfold=True),
    'float_abs':            LLOp(canfold=True),

    'float_add':            LLOp(canfold=True),
    'float_sub':            LLOp(canfold=True),
    'float_mul':            LLOp(canfold=True),
    'float_truediv':        LLOp(canfold=True),
    'float_mod':            LLOp(canfold=True),
    'float_lt':             LLOp(canfold=True),
    'float_le':             LLOp(canfold=True),
    'float_eq':             LLOp(canfold=True),
    'float_ne':             LLOp(canfold=True),
    'float_gt':             LLOp(canfold=True),
    'float_ge':             LLOp(canfold=True),
    'float_floor':          LLOp(canfold=True),
    'float_fmod':           LLOp(canfold=True),
    'float_pow':            LLOp(canfold=True),

    'llong_is_true':        LLOp(canfold=True),
    'llong_neg':            LLOp(canfold=True),
    'llong_abs':            LLOp(canfold=True),
    'llong_invert':         LLOp(canfold=True),

    'llong_add':            LLOp(canfold=True),
    'llong_sub':            LLOp(canfold=True),
    'llong_mul':            LLOp(canfold=True),
    'llong_floordiv':       LLOp(canfold=True),
    'llong_floordiv_zer':   LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'llong_mod':            LLOp(canfold=True),
    'llong_mod_zer':        LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'llong_lt':             LLOp(canfold=True),
    'llong_le':             LLOp(canfold=True),
    'llong_eq':             LLOp(canfold=True),
    'llong_ne':             LLOp(canfold=True),
    'llong_gt':             LLOp(canfold=True),
    'llong_ge':             LLOp(canfold=True),
    'llong_and':            LLOp(canfold=True),
    'llong_or':             LLOp(canfold=True),
    'llong_lshift':         LLOp(canfold=True),
    'llong_lshift_val':     LLOp(canfold=True, canraise=(ValueError,)),
    'llong_rshift':         LLOp(canfold=True),
    'llong_rshift_val':     LLOp(canfold=True, canraise=(ValueError,)),
    'llong_xor':            LLOp(canfold=True),

    'ullong_is_true':       LLOp(canfold=True),
    'ullong_neg':           LLOp(canfold=True),
    'ullong_abs':           LLOp(canfold=True),
    'ullong_invert':        LLOp(canfold=True),

    'ullong_add':           LLOp(canfold=True),
    'ullong_sub':           LLOp(canfold=True),
    'ullong_mul':           LLOp(canfold=True),
    'ullong_floordiv':      LLOp(canfold=True),
    'ullong_floordiv_zer':  LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'ullong_mod':           LLOp(canfold=True),
    'ullong_mod_zer':       LLOp(canfold=True, canraise=(ZeroDivisionError,)),
    'ullong_lt':            LLOp(canfold=True),
    'ullong_le':            LLOp(canfold=True),
    'ullong_eq':            LLOp(canfold=True),
    'ullong_ne':            LLOp(canfold=True),
    'ullong_gt':            LLOp(canfold=True),
    'ullong_ge':            LLOp(canfold=True),
    'ullong_and':           LLOp(canfold=True),
    'ullong_or':            LLOp(canfold=True),
    'ullong_lshift':        LLOp(canfold=True),
    'ullong_lshift_val':    LLOp(canfold=True, canraise=(ValueError,)),
    'ullong_rshift':        LLOp(canfold=True),
    'ullong_rshift_val':    LLOp(canfold=True, canraise=(ValueError,)),
    'ullong_xor':           LLOp(canfold=True),

    'cast_primitive':       LLOp(canfold=True),
    'cast_bool_to_int':     LLOp(canfold=True),
    'cast_bool_to_uint':    LLOp(canfold=True),
    'cast_bool_to_float':   LLOp(canfold=True),
    'cast_char_to_int':     LLOp(canfold=True),
    'cast_unichar_to_int':  LLOp(canfold=True),
    'cast_int_to_char':     LLOp(canfold=True),
    'cast_int_to_unichar':  LLOp(canfold=True),
    'cast_int_to_uint':     LLOp(canfold=True),
    'cast_int_to_float':    LLOp(canfold=True),
    'cast_int_to_longlong': LLOp(canfold=True),
    'cast_uint_to_int':     LLOp(canfold=True),
    'cast_float_to_int':    LLOp(canfold=True),
    'cast_float_to_uint':   LLOp(canfold=True),
    'truncate_longlong_to_int':LLOp(canfold=True),

    # __________ pointer operations __________

    'malloc':               LLOp(canraise=(MemoryError,), canunwindgc=True),
    'malloc_varsize':       LLOp(canraise=(MemoryError,), canunwindgc=True),
    'flavored_malloc':      LLOp(canraise=(MemoryError,)),
    'flavored_free':        LLOp(),
    'getfield':             LLOp(sideeffects=False),
    'getarrayitem':         LLOp(sideeffects=False),
    'getarraysize':         LLOp(canfold=True),
    'getsubstruct':         LLOp(canfold=True),
    'getarraysubstruct':    LLOp(canfold=True),
    'setfield':             LLOp(),
    'bare_setfield':        LLOp(),
    'setarrayitem':         LLOp(),
    'cast_pointer':         LLOp(canfold=True),
    'ptr_eq':               LLOp(canfold=True),
    'ptr_ne':               LLOp(canfold=True),
    'ptr_nonzero':          LLOp(canfold=True),
    'ptr_iszero':           LLOp(canfold=True),
    'cast_ptr_to_int':      LLOp(sideeffects=False),
    'cast_int_to_ptr':      LLOp(sideeffects=False),
    'direct_fieldptr':      LLOp(canfold=True),
    'direct_arrayitems':    LLOp(canfold=True),
    'direct_ptradd':        LLOp(canfold=True),
    'cast_opaque_ptr':      LLOp(canfold=True),

    # _________ XXX l3interp hacks ___________

    'call_boehm_gc_alloc':  LLOp(canraise=(MemoryError,)),

    # __________ address operations __________

    'raw_malloc':           LLOp(canraise=(MemoryError,)),
    'raw_malloc_usage':     LLOp(sideeffects=False),
    'raw_free':             LLOp(),
    'raw_memcopy':          LLOp(),
    'raw_load':             LLOp(sideeffects=False),
    'raw_store':            LLOp(),
    'adr_add':              LLOp(canfold=True),
    'adr_sub':              LLOp(canfold=True),
    'adr_delta':            LLOp(canfold=True),
    'adr_lt':               LLOp(canfold=True),
    'adr_le':               LLOp(canfold=True),
    'adr_eq':               LLOp(canfold=True),
    'adr_ne':               LLOp(canfold=True),
    'adr_gt':               LLOp(canfold=True),
    'adr_ge':               LLOp(canfold=True),
    'cast_ptr_to_adr':      LLOp(canfold=True),
    'cast_adr_to_ptr':      LLOp(canfold=True),
    'cast_ptr_to_weakadr':  LLOp(canfold=True),
    'cast_weakadr_to_ptr':  LLOp(canfold=True),
    'cast_weakadr_to_int':  LLOp(canfold=True),
    'cast_adr_to_int':      LLOp(canfold=True),

    # __________ GC operations __________

    'gc__collect':          LLOp(canunwindgc=True),
    'gc_free':              LLOp(),
    'gc_fetch_exception':   LLOp(),
    'gc_restore_exception': LLOp(),
    'gc_call_rtti_destructor': LLOp(),
    'gc_deallocate':        LLOp(),
    'gc_push_alive_pyobj':  LLOp(),
    'gc_pop_alive_pyobj':   LLOp(),
    'gc_protect':           LLOp(),
    'gc_unprotect':         LLOp(),    
    'gc_reload_possibly_moved': LLOp(),
    # experimental operations in support of thread cloning, only
    # implemented by the Mark&Sweep GC
    'gc_x_swap_pool':       LLOp(canraise=(MemoryError,), canunwindgc=True),
    'gc_x_clone':           LLOp(canraise=(MemoryError, RuntimeError),
                                 canunwindgc=True),
    'gc_x_size_header':     LLOp(),
    # this one is even more experimental; only implemented with the
    # Mark&Sweep GC, and likely only useful when combined with
    # stackless:
    'gc_x_become':          LLOp(canraise=(RuntimeError,), canunwindgc=True),

    # NOTE NOTE NOTE! don't forget *** canunwindgc=True *** for anything that
    # can go through a stack unwind, in particular anything that mallocs!

    # __________ stackless operation(s) __________

    'yield_current_frame_to_caller': LLOp(canraise=(StackException,)),
    #                               can always unwind, not just if stackless gc

    'resume_point':         LLOp(canraise=(Exception,)),
    'resume_state_create':  LLOp(canraise=(MemoryError,), canunwindgc=True),
    'resume_state_invoke':  LLOp(canraise=(Exception, StackException)),

    # __________ misc operations __________

    'keepalive':            LLOp(),
    'same_as':              LLOp(canfold=True),
    'hint':                 LLOp(),
    'check_no_more_arg':    LLOp(canraise=(Exception,)),
    'check_self_nonzero':   LLOp(canraise=(Exception,)),
    'decode_arg':           LLOp(canraise=(Exception,)),
    'decode_arg_def':       LLOp(canraise=(Exception,)),
    'getslice':             LLOp(canraise=(Exception,)),

    # __________ debugging __________
    'debug_view':           LLOp(),
    'debug_print':          LLOp(),
    'debug_pdb':            LLOp(),
    'debug_log_exc':        LLOp()
}

    # __________ operations on PyObjects __________

from pypy.objspace.flow.operation import FunctionByName
opimpls = FunctionByName.copy()
opimpls['is_true'] = True
opimpls['simple_call'] = True
for opname in opimpls:
    LL_OPERATIONS[opname] = LLOp(canraise=(Exception,), pyobj=True)
del opname, opimpls, FunctionByName

# ____________________________________________________________
# Post-processing

# Stick the opnames into the LLOp instances
for opname, opdesc in LL_OPERATIONS.iteritems():
    opdesc.opname = opname
del opname, opdesc

# Also export all operations in an attribute-based namespace.
# Example usage from LL helpers:  z = llop.int_add(Signed, x, y)

class LLOP(object):
    def _freeze_(self):
        return True
llop = LLOP()
for opname, opdesc in LL_OPERATIONS.iteritems():
    setattr(llop, opname, opdesc)
del opname, opdesc
