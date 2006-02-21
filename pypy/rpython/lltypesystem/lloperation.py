"""
The table of all LL operations.
"""

class LLOp(object):

    def __init__(self, sideeffects=True, canfold=False, canraise=(), pyobj=False):
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

        # The operation manipulates PyObjects
        self.pyobj = pyobj

    # __________ make the LLOp instances callable from LL helpers __________

    __name__ = property(lambda self: 'llop_'+self.opname)

    def __call__(self, RESULTTYPE, *args):
        raise TypeError, "llop is meant to be rtyped and not called direclty"

    def compute_result_annotation(self, RESULTTYPE, *args):
        from pypy.annotation.model import lltype_to_annotation
        assert RESULTTYPE.is_constant()
        return lltype_to_annotation(RESULTTYPE.const)

    def specialize(self, hop):
        args_v = [hop.inputarg(r, i+1) for i, r in enumerate(hop.args_r[1:])]
        hop.exception_is_here()
        return hop.genop(self.opname, args_v, resulttype=hop.r_result.lowleveltype)


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

# ____________________________________________________________
#
# This list corresponds to the operations implemented by the LLInterpreter.
# XXX Some clean-ups are needed:
#      * many exception-raising operations are being replaced by calls to helpers
#      * there are still many _ovf operations that cannot really raise OverflowError
#      * the div/truediv/floordiv mess needs to be sorted out and reduced
#      * float_mod vs float_fmod ?
# Run test_lloperation after changes.  Feel free to clean up LLInterpreter too :-)

LL_OPERATIONS = {

    'direct_call':          LLOp(canraise=(Exception,)),
    'indirect_call':        LLOp(canraise=(Exception,)),

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
    'int_div':              LLOp(canfold=True),
    'int_truediv':          LLOp(canfold=True),
    'int_floordiv':         LLOp(canfold=True),
    'int_mod':              LLOp(canfold=True),
    'int_lt':               LLOp(canfold=True),
    'int_le':               LLOp(canfold=True),
    'int_eq':               LLOp(canfold=True),
    'int_ne':               LLOp(canfold=True),
    'int_gt':               LLOp(canfold=True),
    'int_ge':               LLOp(canfold=True),
    'int_and':              LLOp(canfold=True),
    'int_or':               LLOp(canfold=True),
    'int_lshift':           LLOp(canfold=True),
    'int_rshift':           LLOp(canfold=True),
    'int_xor':              LLOp(canfold=True),
    'int_add_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_sub_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_mul_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_div_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_truediv_ovf':      LLOp(canfold=True, canraise=(OverflowError,)),
    'int_floordiv_ovf':     LLOp(canfold=True, canraise=(OverflowError,)),
    'int_mod_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_lt_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_le_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_eq_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_ne_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_gt_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_ge_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_and_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_or_ovf':           LLOp(canfold=True, canraise=(OverflowError,)),
    'int_lshift_ovf':       LLOp(canfold=True, canraise=(OverflowError,)),
    'int_rshift_ovf':       LLOp(canfold=True, canraise=(OverflowError,)),
    'int_xor_ovf':          LLOp(canfold=True, canraise=(OverflowError,)),
    'int_floordiv_ovf_zer': LLOp(canfold=True, canraise=(OverflowError, ZeroDivisionError)),
    'int_mod_ovf_zer':      LLOp(canfold=True, canraise=(OverflowError, ZeroDivisionError)),

    'uint_is_true':         LLOp(canfold=True),
    'uint_neg':             LLOp(canfold=True),
    'uint_abs':             LLOp(canfold=True),
    'uint_invert':          LLOp(canfold=True),

    'uint_add':             LLOp(canfold=True),
    'uint_sub':             LLOp(canfold=True),
    'uint_mul':             LLOp(canfold=True),
    'uint_div':             LLOp(canfold=True),
    'uint_truediv':         LLOp(canfold=True),
    'uint_floordiv':        LLOp(canfold=True),
    'uint_mod':             LLOp(canfold=True),
    'uint_lt':              LLOp(canfold=True),
    'uint_le':              LLOp(canfold=True),
    'uint_eq':              LLOp(canfold=True),
    'uint_ne':              LLOp(canfold=True),
    'uint_gt':              LLOp(canfold=True),
    'uint_ge':              LLOp(canfold=True),
    'uint_and':             LLOp(canfold=True),
    'uint_or':              LLOp(canfold=True),
    'uint_lshift':          LLOp(canfold=True),
    'uint_rshift':          LLOp(canfold=True),
    'uint_xor':             LLOp(canfold=True),

    'float_is_true':        LLOp(canfold=True),
    'float_neg':            LLOp(canfold=True),
    'float_abs':            LLOp(canfold=True),

    'float_add':            LLOp(canfold=True),
    'float_sub':            LLOp(canfold=True),
    'float_mul':            LLOp(canfold=True),
    'float_div':            LLOp(canfold=True),
    'float_truediv':        LLOp(canfold=True),
    'float_floordiv':       LLOp(canfold=True),
    'float_mod':            LLOp(canfold=True),
    'float_lt':             LLOp(canfold=True),
    'float_le':             LLOp(canfold=True),
    'float_eq':             LLOp(canfold=True),
    'float_ne':             LLOp(canfold=True),
    'float_gt':             LLOp(canfold=True),
    'float_ge':             LLOp(canfold=True),
    'float_floor':          LLOp(canfold=True),
    'float_fmod':           LLOp(canfold=True),

    'llong_is_true':        LLOp(canfold=True),
    'llong_neg':            LLOp(canfold=True),
    'llong_abs':            LLOp(canfold=True),
    'llong_invert':         LLOp(canfold=True),

    'llong_add':            LLOp(canfold=True),
    'llong_sub':            LLOp(canfold=True),
    'llong_mul':            LLOp(canfold=True),
    'llong_div':            LLOp(canfold=True),
    'llong_truediv':        LLOp(canfold=True),
    'llong_floordiv':       LLOp(canfold=True),
    'llong_mod':            LLOp(canfold=True),
    'llong_lt':             LLOp(canfold=True),
    'llong_le':             LLOp(canfold=True),
    'llong_eq':             LLOp(canfold=True),
    'llong_ne':             LLOp(canfold=True),
    'llong_gt':             LLOp(canfold=True),
    'llong_ge':             LLOp(canfold=True),

    'ullong_is_true':       LLOp(canfold=True),
    'ullong_neg':           LLOp(canfold=True),
    'ullong_abs':           LLOp(canfold=True),
    'ullong_invert':        LLOp(canfold=True),

    'ullong_add':           LLOp(canfold=True),
    'ullong_sub':           LLOp(canfold=True),
    'ullong_mul':           LLOp(canfold=True),
    'ullong_div':           LLOp(canfold=True),
    'ullong_truediv':       LLOp(canfold=True),
    'ullong_floordiv':      LLOp(canfold=True),
    'ullong_mod':           LLOp(canfold=True),
    'ullong_lt':            LLOp(canfold=True),
    'ullong_le':            LLOp(canfold=True),
    'ullong_eq':            LLOp(canfold=True),
    'ullong_ne':            LLOp(canfold=True),
    'ullong_gt':            LLOp(canfold=True),
    'ullong_ge':            LLOp(canfold=True),

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

    'malloc':               LLOp(canraise=(MemoryError,)),
    'malloc_varsize':       LLOp(canraise=(MemoryError,)),
    'flavored_malloc':      LLOp(canraise=(MemoryError,)),
    'flavored_free':        LLOp(),
    'getfield':             LLOp(sideeffects=False),
    'getarrayitem':         LLOp(sideeffects=False),
    'getarraysize':         LLOp(canfold=True),
    'getsubstruct':         LLOp(canfold=True),
    'getarraysubstruct':    LLOp(canfold=True),
    'setfield':             LLOp(),
    'setarrayitem':         LLOp(),
    'cast_pointer':         LLOp(canfold=True),
    'ptr_eq':               LLOp(canfold=True),
    'ptr_ne':               LLOp(canfold=True),
    'ptr_nonzero':          LLOp(canfold=True),
    'ptr_iszero':           LLOp(canfold=True),
    'cast_ptr_to_int':      LLOp(sideeffects=False),

    # __________ address operations __________

    'raw_malloc':           LLOp(canraise=(MemoryError,)),
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

    # __________ GC operations __________

    'gc__collect':          LLOp(),
    'gc_free':              LLOp(),
    'gc_fetch_exception':   LLOp(),
    'gc_restore_exception': LLOp(),
    'gc_call_rtti_destructor': LLOp(),

    # __________ misc operations __________

    'keepalive':            LLOp(),
    'same_as':              LLOp(canfold=True),
    'hint':                 LLOp(),
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
