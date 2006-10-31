"""

Mapping from OOType opcodes to JVM MicroInstructions.  Most of these
come from the oosupport directory.

"""

from pypy.translator.oosupport.metavm import \
     PushArg, PushAllArgs, StoreResult, InstructionList, New, DoNothing, Call
import pypy.translator.jvm.generator as jvmgen

def _check_zer(op):
    # TODO
    return op

def _check_ovf(op):
    # TODO
    return op

# This table maps the opcodes to micro-ops for processing them.
# It is post-processed by a function to be found below.
opcodes = {
    # __________ object oriented operations __________
    #'new':                      [New],
    #'runtimenew':               [RuntimeNew],
    #'oosetfield':               [SetField],
    #'oogetfield':               [GetField],
    #'oosend':                   [CallMethod],
    #'ooupcast':                 DoNothing,
    #'oodowncast':               [DownCast],
    #'oois':                     'ceq',
    #'oononnull':                [PushAllArgs, 'ldnull', 'ceq']+Not,
    #'instanceof':               [CastTo, 'ldnull', 'cgt.un'],
    #'subclassof':               [PushAllArgs, 'call bool [pypylib]pypy.runtime.Utils::SubclassOf(class [mscorlib]System.Type, class[mscorlib]System.Type)'],
    #'ooidentityhash':           [PushAllArgs, 'callvirt instance int32 object::GetHashCode()'],
    #'oohash':                   [PushAllArgs, 'callvirt instance int32 object::GetHashCode()'],    
    #'oostring':                 [OOString],
    #'ooparse_int':              [PushAllArgs, 'call int32 [pypylib]pypy.runtime.Utils::OOParseInt(string, int32)'],
    #'oonewcustomdict':          [NewCustomDict],
    #
    'same_as':                  DoNothing,
    #'hint':                     [PushArg(0), StoreResult],
    'direct_call':              [Call],
    #'indirect_call':            [IndirectCall],
    #
    #'cast_ptr_to_weakadr':      [PushAllArgs, 'newobj instance void class %s::.ctor(object)' % WEAKREF],
    #'cast_weakadr_to_ptr':      [CastWeakAdrToPtr],
    #'gc__collect':              'call void class [mscorlib]System.GC::Collect()',
    #'resume_point':             Ignore,

    # __________ numeric operations __________

    'bool_not':                 'logical_not',

    'char_lt':                  'less_than',
    'char_le':                  'less_equals',
    'char_eq':                  'equals',
    'char_ne':                  'not_equals',
    'char_gt':                  'greater_than',
    'char_ge':                  'greater_equals',

    'unichar_eq':               'equals',
    'unichar_ne':               'not_equals',

    'int_is_true':              'not_equals_zero',
    'int_neg':                  jvmgen.INEG,
    'int_neg_ovf':              None, # How to handle overflow?
    'int_abs':                  'iabs',
    'int_abs_ovf':              _check_ovf('iabs'),
    'int_invert':               'bitwise_negate',

    'int_add':                  jvmgen.IADD,
    'int_sub':                  jvmgen.ISUB,
    'int_mul':                  jvmgen.IMUL,
    'int_floordiv':             jvmgen.IDIV,
    'int_floordiv_zer':         _check_zer(jvmgen.IDIV),
    'int_mod':                  jvmgen.IREM,
    'int_lt':                   'less_than',
    'int_le':                   'less_equals',
    'int_eq':                   'equals',
    'int_ne':                   'not_equals',
    'int_gt':                   'greater_than',
    'int_ge':                   'greater_equals',
    'int_and':                  jvmgen.IAND,
    'int_or':                   jvmgen.IOR,
    'int_lshift':               jvmgen.ISHL,
    'int_rshift':               jvmgen.ISHR,
    'int_xor':                  jvmgen.IXOR,
    'int_add_ovf':              _check_ovf(jvmgen.IADD),
    'int_sub_ovf':              _check_ovf(jvmgen.ISUB),
    'int_mul_ovf':              _check_ovf(jvmgen.IMUL),
    'int_floordiv_ovf':         jvmgen.IDIV, # these can't overflow!
    'int_mod_ovf':              jvmgen.IREM,
    'int_lt_ovf':               'less_than',
    'int_le_ovf':               'less_equals',
    'int_eq_ovf':               'equals',
    'int_ne_ovf':               'not_equals',
    'int_gt_ovf':               'greater_than',
    'int_ge_ovf':               'greater_equals',
    'int_and_ovf':              jvmgen.IAND,
    'int_or_ovf':               jvmgen.IOR,

    'int_lshift_ovf':           _check_ovf(jvmgen.ISHL),
    'int_lshift_ovf_val':       _check_ovf(jvmgen.ISHL), # VAL??

    'int_rshift_ovf':           jvmgen.ISHR, # these can't overflow!
    'int_xor_ovf':              jvmgen.IXOR,
    'int_floordiv_ovf_zer':     _check_zer(jvmgen.IDIV),
    'int_mod_ovf_zer':          _check_zer(jvmgen.IREM),

    'uint_is_true':             'not_equals_zero',
    'uint_invert':              'bitwise_negate',

    'uint_add':                 jvmgen.IADD,
    'uint_sub':                 jvmgen.ISUB,
    'uint_mul':                 jvmgen.IMUL,
    'uint_div':                 jvmgen.IDIV,  # valid?
    'uint_truediv':             None,    # TODO
    'uint_floordiv':            jvmgen.IDIV,  # valid?
    'uint_mod':                 jvmgen.IREM,  # valid?
    'uint_lt':                  'u_less_than',
    'uint_le':                  'u_less_equals',
    'uint_eq':                  'u_equals',
    'uint_ne':                  'u_not_equals',
    'uint_gt':                  'u_greater_than',
    'uint_ge':                  'u_greater_equals',
    'uint_and':                 jvmgen.IAND,
    'uint_or':                  jvmgen.IOR,
    'uint_lshift':              jvmgen.ISHL,
    'uint_rshift':              jvmgen.IUSHR,
    'uint_xor':                 jvmgen.IXOR,

    'float_is_true':            [PushAllArgs,
                                 jvmgen.DCONST_0,
                                 'dbl_not_equals'],
    'float_neg':                jvmgen.DNEG,
    'float_abs':                'dbl_abs',

    'float_add':                jvmgen.DADD,
    'float_sub':                jvmgen.DSUB,
    'float_mul':                jvmgen.DMUL,
    'float_truediv':            jvmgen.DDIV, 
    'float_mod':                jvmgen.DREM, # use Math.IEEEremainder?
    'float_lt':                 'dbl_less_than',     
    'float_le':                 'dbl_less_equals',   
    'float_eq':                 'dbl_equals',        
    'float_ne':                 'dbl_not_equals',    
    'float_gt':                 'dbl_greater_than',  
    'float_ge':                 'dbl_greater_equals',
    'float_floor':              jvmgen.MATHFLOOR,
    'float_fmod':               jvmgen.DREM, # DREM is akin to fmod() in C

    'llong_is_true':            [PushAllArgs,
                                 jvmgen.LCONST_0,
                                 'long_not_equals'],
    'llong_neg':                jvmgen.LNEG,
    'llong_neg_ovf':            _check_ovf(jvmgen.LNEG),
    'llong_abs':                jvmgen.MATHLABS,
    'llong_invert':             jvmgen.PYPYLONGBITWISENEGATE,

    'llong_add':                jvmgen.LADD,
    'llong_sub':                jvmgen.LSUB,
    'llong_mul':                jvmgen.LMUL,
    'llong_div':                jvmgen.LDIV,
    'llong_truediv':            None, # TODO
    'llong_floordiv':           jvmgen.LDIV,
    'llong_mod':                jvmgen.LREM,
    'llong_lt':                 'long_less_than',     
    'llong_le':                 'long_less_equals',   
    'llong_eq':                 'long_equals',        
    'llong_ne':                 'long_not_equals',    
    'llong_gt':                 'long_greater_than',  
    'llong_ge':                 'long_greater_equals',
    'llong_and':                jvmgen.LAND,
    'llong_or':                 jvmgen.LOR,
    'llong_lshift':             jvmgen.LSHL,
    'llong_rshift':             jvmgen.LSHR,
    'llong_xor':                jvmgen.LXOR,

    'ullong_is_true':           [PushAllArgs,
                                 jvmgen.LCONST_0,
                                 'long_not_equals'],
    'ullong_invert':            jvmgen.PYPYLONGBITWISENEGATE,

    'ullong_add':               jvmgen.LADD,
    'ullong_sub':               jvmgen.LSUB,
    'ullong_mul':               jvmgen.LMUL,
    'ullong_div':               jvmgen.LDIV, # valid?
    'ullong_truediv':           None, # TODO
    'ullong_floordiv':          jvmgen.LDIV, # valid?
    'ullong_mod':               jvmgen.LREM, # valid?
    'ullong_lt':                'ulong_less_than',     
    'ullong_le':                'ulong_less_equals',   
    'ullong_eq':                'ulong_equals',        
    'ullong_ne':                'ulong_not_equals',    
    'ullong_gt':                'ulong_greater_than',  
    'ullong_ge':                'ulong_greater_equals',

    # when casting from bool we want that every truth value is casted
    # to 1: we can't simply DoNothing, because the CLI stack could
    # contains a truth value not equal to 1, so we should use the !=0
    # trick.
    'cast_bool_to_int':         DoNothing,
    'cast_bool_to_uint':        DoNothing,
    'cast_bool_to_float':       [PushAllArgs, 'not_equals_zero', jvmgen.I2D],
    
    'cast_char_to_int':         DoNothing,
    'cast_unichar_to_int':      DoNothing,
    'cast_int_to_char':         DoNothing,
    'cast_int_to_unichar':      DoNothing,
    'cast_int_to_uint':         DoNothing,
    'cast_int_to_float':        jvmgen.I2D,
    'cast_int_to_longlong':     jvmgen.I2L,
    'cast_uint_to_int':         DoNothing,
    'cast_uint_to_float':       jvmgen.PYPYUINTTODOUBLE, 
    'cast_float_to_int':        jvmgen.D2I,
    'cast_float_to_uint':       jvmgen.PYPYDOUBLETOUINT,
    'truncate_longlong_to_int': jvmgen.L2I,
    
}

for opc in opcodes:
    val = opcodes[opc]
    if not isinstance(val, list):
        val = InstructionList((PushAllArgs, val))
    else:
        val = InstructionList(val)
    opcodes[opc] = val
