import py
import math
from pypy.lang.smalltalk.primitives import prim_table, PrimitiveFailedError
from pypy.lang.smalltalk import model, shadow
from pypy.lang.smalltalk import interpreter
from pypy.lang.smalltalk import classtable
from pypy.lang.smalltalk import objtable
from pypy.lang.smalltalk import constants
from pypy.rlib.rarithmetic import INFINITY, NAN, isinf, isnan
from pypy.lang.smalltalk import primitives

mockclass = classtable.bootstrap_class

class MockFrame(model.W_MethodContext):
    def __init__(self, stack):
        self.stack = stack

def wrap(x):
    if isinstance(x, int): return objtable.wrap_int(x)
    if isinstance(x, float): return objtable.wrap_float(x)
    if isinstance(x, model.W_Object): return x
    if isinstance(x, str) and len(x) == 1: return objtable.wrap_char(x)
    if isinstance(x, str): return objtable.wrap_string(x)
    raise NotImplementedError
    
def mock(stack):
    mapped_stack = [wrap(x) for x in stack]
    frame = MockFrame(mapped_stack)
    interp = interpreter.Interpreter()
    interp.w_active_context = frame
    return (interp, len(stack))

def prim(code, stack):
    interp, argument_count = mock(stack)
    res = prim_table[code](interp, argument_count-1)
    assert not len(interp.w_active_context.stack) # check args are consumed
    return res

def prim_fails(code, stack):
    interp, argument_count = mock(stack)
    orig_stack = list(interp.w_active_context.stack)
    try:
        prim_table[code](interp, argument_count-1)
        py.test.fail("Expected PrimitiveFailedError")
    except PrimitiveFailedError:
        assert interp.w_active_context.stack == orig_stack
        
# smallinteger tests
def test_small_int_add():
    assert prim(primitives.ADD, [1,2]).value == 3
    assert prim(primitives.ADD, [3,4]).value == 7

def test_small_int_add_fail():
    prim_fails(primitives.ADD, [1073741823,2])

def test_small_int_minus():
    assert prim(primitives.SUBTRACT, [5,9]).value == -4

def test_small_int_minus_fail():
    prim_fails(primitives.SUBTRACT, [-1073741823,2])
    
def test_small_int_multiply():
    assert prim(primitives.MULTIPLY, [6,3]).value == 18

def test_small_int_multiply_overflow():
    prim_fails(primitives.MULTIPLY, [1073741823, 2])
    prim_fails(primitives.MULTIPLY, [1073741823, 1073741823])
    prim_fails(primitives.MULTIPLY, [1073741823, -4])
    prim_fails(primitives.MULTIPLY, [-1073741823, 2])
    
def test_small_int_divide():
    assert prim(primitives.DIVIDE, [6,3]).value == 2
    
def test_small_int_divide_fail():
    prim_fails(primitives.DIVIDE, [12, 0])
    prim_fails(primitives.DIVIDE, [12, 7])
    
def test_small_int_mod():
    assert prim(primitives.MOD, [12,7]).value == 5

def test_small_int_mod_fail():
    prim_fails(primitives.MOD, [12, 0])
    
def test_small_int_div():
    assert prim(primitives.DIV, [12,3]).value == 4
    assert prim(primitives.DIV, [12,7]).value == 1

def test_small_int_div_fail():
    prim_fails(primitives.DIV, [12, 0])
    
def test_small_int_quo():
    assert prim(primitives.QUO, [12,3]).value == 4
    assert prim(primitives.QUO, [12,7]).value == 1

def test_small_int_quo_fail():
    prim_fails(primitives.QUO, [12, 0])
    
def test_small_int_bit_and():
    assert prim(primitives.BIT_AND, [2, 4]).value == 0
    assert prim(primitives.BIT_AND, [2, 3]).value == 2
    assert prim(primitives.BIT_AND, [3, 4]).value == 0
    assert prim(primitives.BIT_AND, [4, 4]).value == 4
    
def test_small_int_bit_or():
    assert prim(primitives.BIT_OR, [2, 4]).value == 6
    assert prim(primitives.BIT_OR, [2, 3]).value == 3
    assert prim(primitives.BIT_OR, [3, 4]).value == 7
    assert prim(primitives.BIT_OR, [4, 4]).value == 4

def test_small_int_bit_xor():
    assert prim(primitives.BIT_XOR, [2, 4]).value == 6
    assert prim(primitives.BIT_XOR, [2, 3]).value == 1
    assert prim(primitives.BIT_XOR, [3, 4]).value == 7
    assert prim(primitives.BIT_XOR, [4, 4]).value == 0

def test_small_int_bit_shift():
    assert prim(primitives.BIT_SHIFT, [0, -3]).value == 0
    assert prim(primitives.BIT_SHIFT, [0, -2]).value == 0
    assert prim(primitives.BIT_SHIFT, [0, -1]).value == 0
    assert prim(primitives.BIT_SHIFT, [0, 0]).value == 0
    assert prim(primitives.BIT_SHIFT, [0, 1]).value == 0
    assert prim(primitives.BIT_SHIFT, [0, 2]).value == 0
    assert prim(primitives.BIT_SHIFT, [0, 3]).value == 0
    
def test_small_int_bit_shift_positive():
    assert prim(primitives.BIT_SHIFT, [4, -3]).value == 0
    assert prim(primitives.BIT_SHIFT, [4, -2]).value == 1
    assert prim(primitives.BIT_SHIFT, [4, -1]).value == 2
    assert prim(primitives.BIT_SHIFT, [4, 0]).value == 4
    assert prim(primitives.BIT_SHIFT, [4, 1]).value == 8
    assert prim(primitives.BIT_SHIFT, [4, 2]).value == 16
    assert prim(primitives.BIT_SHIFT, [4, 3]).value == 32
    assert prim(primitives.BIT_SHIFT, [4, 27]).value == 536870912
    
def test_small_int_bit_shift_negative():
    assert prim(primitives.BIT_SHIFT, [-4, -3]).value == -1
    assert prim(primitives.BIT_SHIFT, [-4, -2]).value == -1
    assert prim(primitives.BIT_SHIFT, [-4, -1]).value == -2
    assert prim(primitives.BIT_SHIFT, [-4, 0]).value == -4
    assert prim(primitives.BIT_SHIFT, [-4, 1]).value == -8
    assert prim(primitives.BIT_SHIFT, [-4, 2]).value == -16
    assert prim(primitives.BIT_SHIFT, [-4, 3]).value == -32
    assert prim(primitives.BIT_SHIFT, [-4, 27]).value == -536870912
    
def test_small_int_bit_shift_fail():
    prim_fails(primitives.BIT_SHIFT, [4, 32])
    prim_fails(primitives.BIT_SHIFT, [4, 31])
    prim_fails(primitives.BIT_SHIFT, [4, 30])
    prim_fails(primitives.BIT_SHIFT, [4, 29])
    prim_fails(primitives.BIT_SHIFT, [4, 28])

def test_float_add():
    assert prim(primitives.FLOAT_ADD, [1.0,2.0]).value == 3.0
    assert prim(primitives.FLOAT_ADD, [3.0,4.5]).value == 7.5

def test_float_subtract():
    assert prim(primitives.FLOAT_SUBTRACT, [1.0,2.0]).value == -1.0
    assert prim(primitives.FLOAT_SUBTRACT, [15.0,4.5]).value == 10.5

def test_float_multiply():
    assert prim(primitives.FLOAT_MULTIPLY, [10.0,2.0]).value == 20.0
    assert prim(primitives.FLOAT_MULTIPLY, [3.0,4.5]).value == 13.5

def test_float_divide():
    assert prim(primitives.FLOAT_DIVIDE, [1.0,2.0]).value == 0.5
    assert prim(primitives.FLOAT_DIVIDE, [3.5,4.0]).value == 0.875

def test_float_truncate():
    assert prim(primitives.FLOAT_TRUNCATED, [-4.6]).value == -4
    assert prim(primitives.FLOAT_TRUNCATED, [-4.5]).value == -4
    assert prim(primitives.FLOAT_TRUNCATED, [-4.4]).value == -4
    assert prim(primitives.FLOAT_TRUNCATED, [4.4]).value == 4
    assert prim(primitives.FLOAT_TRUNCATED, [4.5]).value == 4
    assert prim(primitives.FLOAT_TRUNCATED, [4.6]).value == 4

def test_at():
    w_obj = mockclass(0, varsized=True).as_class_get_shadow().new(1)
    w_obj.store(0, "foo")
    assert prim(primitives.AT, [w_obj, 1]) == "foo"

def test_invalid_at():
    w_obj = mockclass(0).as_class_get_shadow().new()
    prim_fails(primitives.AT, [w_obj, 1])

def test_at_put():
    w_obj = mockclass(0, varsized=1).as_class_get_shadow().new(1)
    assert prim(primitives.AT_PUT, [w_obj, 1, 22]).value == 22
    assert prim(primitives.AT, [w_obj, 1]).value == 22
    
def test_invalid_at_put():
    w_obj = mockclass(0).as_class_get_shadow().new()
    prim_fails(primitives.AT_PUT, [w_obj, 1, 22])

def test_string_at():
    assert prim(primitives.STRING_AT, ["foobar", 4]) == wrap("b")

def test_string_at_put():
    test_str = wrap("foobar")
    assert prim(primitives.STRING_AT_PUT, [test_str, 4, "c"]) == wrap("c")
    exp = "foocar"
    for i in range(len(exp)):
        assert prim(primitives.STRING_AT, [test_str, i]) == wrap(exp[i])

def test_object_at():
    w_v = prim(primitives.OBJECT_AT, ["q", constants.CHARACTER_VALUE_INDEX+1])
    assert w_v.value == ord("q")

def test_invalid_object_at():
    prim_fails(primitives.OBJECT_AT, ["q", constants.CHARACTER_VALUE_INDEX+2])
    
def test_object_at_put():
    w_obj = mockclass(1).as_class_get_shadow().new()
    assert prim(primitives.OBJECT_AT_PUT, [w_obj, 1, "q"]) is wrap("q")
    assert prim(primitives.OBJECT_AT, [w_obj, 1]) is wrap("q")

def test_invalid_object_at_put():
    w_obj = mockclass(1).as_class_get_shadow().new()
    prim_fails(primitives.OBJECT_AT_PUT, [w_obj, 2, 42])
    
def test_string_at_put():
    test_str = wrap("foobar")
    assert prim(primitives.STRING_AT_PUT, [test_str, 4, "c"]) == wrap("c")
    exp = "foocar"
    for i in range(1,len(exp)+1):
        assert prim(primitives.STRING_AT, [test_str, i]) == wrap(exp[i-1])

def test_new():
    w_Object = classtable.classtable['w_Object']
    w_res = prim(primitives.NEW, [w_Object])
    assert w_res.getclass() is w_Object
    
def test_invalid_new():
    prim_fails(primitives.NEW, [classtable.w_String])

def test_new_with_arg():
    w_res = prim(primitives.NEW_WITH_ARG, [classtable.w_String, 20])
    assert w_res.getclass() == classtable.w_String
    assert w_res.size() == 20    

def test_invalid_new_with_arg():
    w_Object = classtable.classtable['w_Object']
    prim_fails(primitives.NEW_WITH_ARG, [w_Object, 20])
    
def test_inst_var_at():
    w_v = prim(primitives.INST_VAR_AT, ["q", constants.CHARACTER_VALUE_INDEX])
    assert w_v.value == ord("q")

def test_inst_var_at_put():
    w_q = classtable.w_Character.as_class_get_shadow().new()
    vidx = constants.CHARACTER_VALUE_INDEX
    ordq = ord("q")
    assert prim(primitives.INST_VAR_AT, [w_q, vidx]) == objtable.w_nil
    assert prim(primitives.INST_VAR_AT_PUT, [w_q, vidx, ordq]).value == ordq
    assert prim(primitives.INST_VAR_AT, [w_q, vidx]).value == ordq

def test_class():
    assert prim(primitives.CLASS, ["string"]) == classtable.w_String
    assert prim(primitives.CLASS, [1]) == classtable.w_SmallInteger

def test_as_oop():
    py.test.skip("not yet clear what AS_OOP returns: hash or header?")
    w_obj = mockclass(0).as_class_get_shadow().new()
    w_obj.w_hash = wrap(22)
    assert prim(primitives.AS_OOP, [w_obj]).value == 22

def test_as_oop_not_applicable_to_int():
    prim_fails(primitives.AS_OOP, [22])

def test_const_primitives():
    for (code, const) in [
        (primitives.PUSH_TRUE, objtable.w_true),
        (primitives.PUSH_FALSE, objtable.w_false),
        (primitives.PUSH_NIL, objtable.w_nil),
        (primitives.PUSH_MINUS_ONE, objtable.w_mone),
        (primitives.PUSH_ZERO, objtable.w_zero),
        (primitives.PUSH_ONE, objtable.w_one),
        (primitives.PUSH_TWO, objtable.w_two),
        ]:
        assert prim(code, [objtable.w_nil]) is const
    assert prim(primitives.PUSH_SELF, [objtable.w_nil]) is objtable.w_nil
    assert prim(primitives.PUSH_SELF, ["a"]) is wrap("a")

def test_boolean():
    assert prim(primitives.LESSTHAN, [1,2]) == objtable.w_true
    assert prim(primitives.GREATERTHAN, [3,4]) == objtable.w_false
    assert prim(primitives.LESSOREQUAL, [1,2]) == objtable.w_true
    assert prim(primitives.GREATEROREQUAL, [3,4]) == objtable.w_false
    assert prim(primitives.EQUAL, [2,2]) == objtable.w_true
    assert prim(primitives.NOTEQUAL, [2,2]) == objtable.w_false

def test_float_boolean():
    assert prim(primitives.FLOAT_LESSTHAN, [1.0,2.0]) == objtable.w_true
    assert prim(primitives.FLOAT_GREATERTHAN, [3.0,4.0]) == objtable.w_false
    assert prim(primitives.FLOAT_LESSOREQUAL, [1.3,2.6]) == objtable.w_true
    assert prim(primitives.FLOAT_GREATEROREQUAL, [3.5,4.9]) == objtable.w_false
    assert prim(primitives.FLOAT_EQUAL, [2.2,2.2]) == objtable.w_true
    assert prim(primitives.FLOAT_NOTEQUAL, [2.2,2.2]) == objtable.w_false
    
def test_block_copy_and_value():
    # see test_interpreter for tests of these opcodes
    return

ROUNDING_DIGITS = 8

def float_equals(w_f,f):
    return round(w_f.value,ROUNDING_DIGITS) == round(f,ROUNDING_DIGITS)

def test_primitive_square_root():
    assert prim(primitives.FLOAT_SQUARE_ROOT, [4.0]).value == 2.0
    assert float_equals(prim(primitives.FLOAT_SQUARE_ROOT, [2.0]), math.sqrt(2))
    prim_fails(primitives.FLOAT_SQUARE_ROOT, [-2.0])

def test_primitive_sin():
    assert prim(primitives.FLOAT_SIN, [0.0]).value == 0.0
    assert float_equals(prim(primitives.FLOAT_SIN, [math.pi]), 0.0)
    assert float_equals(prim(primitives.FLOAT_SIN, [math.pi/2]), 1.0)

def test_primitive_arctan():
    assert prim(primitives.FLOAT_ARCTAN, [0.0]).value == 0.0
    assert float_equals(prim(primitives.FLOAT_ARCTAN, [1]), math.pi/4)
    assert float_equals(prim(primitives.FLOAT_ARCTAN, [1e99]), math.pi/2)

def test_primitive_log_n():
    assert prim(primitives.FLOAT_LOG_N, [1.0]).value == 0.0
    assert prim(primitives.FLOAT_LOG_N, [math.e]).value == 1.0
    assert float_equals(prim(primitives.FLOAT_LOG_N, [10.0]), math.log(10))
    assert isinf(prim(primitives.FLOAT_LOG_N, [0.0]).value) # works also for negative infinity
    assert isnan(prim(primitives.FLOAT_LOG_N, [-1.0]).value)

def test_primitive_exp():
    assert float_equals(prim(primitives.FLOAT_EXP, [-1.0]), 1/math.e)
    assert prim(primitives.FLOAT_EXP, [0]).value == 1
    assert float_equals(prim(primitives.FLOAT_EXP, [1]), math.e)
    assert float_equals(prim(primitives.FLOAT_EXP, [math.log(10)]), 10)

def equals_ttp(rcvr,arg,res):
    return float_equals(prim(primitives.FLOAT_TIMES_TWO_POWER, [rcvr,arg]), res)

def test_times_two_power():
    assert equals_ttp(1,1,2)
    assert equals_ttp(1.5,1,3)
    assert equals_ttp(2,4,32)
    assert equals_ttp(0,2,0)
    assert equals_ttp(-1,2,-4)
    assert equals_ttp(1.5,0,1.5)
    assert equals_ttp(1.5,-1,0.75)

def test_inc_gc():
    # Should not fail :-)
    prim(primitives.INC_GC, [42]) # Dummy arg

def test_full_gc():
    # Should not fail :-)
    prim(primitives.FULL_GC, [42]) # Dummy arg

def test_become():
    py.test.skip("implement me!")
    """
    testBecome
    	| p1 p2 a |
    	p1 := 1@2.
    	p2 := #(3 4 5).
    	a := p1 -> p2.
    	self assert: 1@2 = a key.
    	self assert: #(3 4 5) = a value.
    	self assert: p1 -> p2 = a.
    	self assert: p1 == a key.
    	self assert: p2 == a value.
    	p1 become: p2.
    	self assert: 1@2 = a value.
    	self assert: #(3 4 5) = a key.
    	self assert: p1 -> p2 = a.
    	self assert: p1 == a key.
    	self assert: p2 == a value.
	
    	self should: [1 become: 2] raise: Error.
    """

# Note:
#   primitives.PRIMITIVE_BLOCK_COPY is tested in test_interpreter
#   primitives.PRIMITIVE_VALUE is tested in test_interpreter
#   primitives.PRIMITIVE_VALUE_WITH_ARGS is tested in test_interpreter
