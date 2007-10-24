import py
from pypy.lang.smalltalk import model, interpreter, primitives, mirror
from pypy.lang.smalltalk.fakeimage import wrap_int
import pypy.lang.smalltalk.classtable as ct

mockclassmirror = ct.bootstrap_classmirror

# expose the bytecode's values as global constants.
# Bytecodes that have a whole range are exposed as global functions:
# call them with an argument 'n' to get the bytecode number 'base + n'.
# XXX hackish
def setup():
    def make_getter(entry):
        def get_opcode_chr(n):
            opcode = entry[0] + n
            assert entry[0] <= opcode <= entry[1]
            return chr(opcode)
        return get_opcode_chr
    for entry in interpreter.BYTECODE_RANGES:
        name = entry[-1].__name__
        if len(entry) == 2:     # no range
            globals()[name] = chr(entry[0])
        else:
            globals()[name] = make_getter(entry)
setup()


def new_interpreter(bytes, receiver="receiver"):
    assert isinstance(bytes, str)
    w_method = model.W_CompiledMethod(0, bytes=bytes,
                                      argsize=2, tempsize=1)
    w_frame = w_method.createFrame(receiver, ["foo", "bar"])
    interp = interpreter.Interpreter()
    interp.activeContext = w_frame
    return interp

def test_create_frame():
    w_method = model.W_CompiledMethod(0, bytes="hello",
                                      argsize=2, tempsize=1)
    w_frame = w_method.createFrame("receiver", ["foo", "bar"])
    assert w_frame.receiver == "receiver"
    assert w_frame.gettemp(0) == "foo"
    assert w_frame.gettemp(1) == "bar"
    assert w_frame.gettemp(2) == None
    w_frame.settemp(2, "spam")
    assert w_frame.gettemp(2) == "spam"
    assert w_frame.getNextBytecode() == ord("h")
    assert w_frame.getNextBytecode() == ord("e")
    assert w_frame.getNextBytecode() == ord("l")

def test_push_pop():
    interp = new_interpreter("")
    frame = interp.activeContext
    frame.push(12)
    frame.push(34)
    frame.push(56)
    assert frame.peek(2) == 12
    assert frame.pop() == 56
    assert frame.top() == 34
    frame.pop_n(0)
    assert frame.top() == 34
    frame.push(56)
    frame.pop_n(2)
    assert frame.top() == 12

def test_unknownBytecode():
    interp = new_interpreter(unknownBytecode)
    py.test.raises(interpreter.MissingBytecode, interp.interpret)

# push bytecodes
def test_pushReceiverBytecode():
    interp = new_interpreter(pushReceiverBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.activeContext.receiver

def test_pushReceiverVariableBytecode(bytecode = (pushReceiverVariableBytecode(0) +
                                                  pushReceiverVariableBytecode(1) +
                                                  pushReceiverVariableBytecode(2))):
    w_demo = mockclassmirror(3).new()
    w_demo.store(0, "egg")
    w_demo.store(1, "bar")
    w_demo.store(2, "baz")
    interp = new_interpreter(bytecode, receiver = w_demo)
    interp.step()
    interp.step()
    interp.step()
    assert interp.activeContext.stack == ["egg", "bar", "baz"]

def test_pushTemporaryVariableBytecode(bytecode=(pushTemporaryVariableBytecode(0) +
                                                 pushTemporaryVariableBytecode(1) +
                                                 pushTemporaryVariableBytecode(2))):
    interp = new_interpreter(bytecode)
    interp.activeContext.settemp(2, "temp")
    interp.step()
    interp.step()
    interp.step()
    assert interp.activeContext.stack == ["foo", "bar", "temp"]

def test_pushLiteralConstantBytecode(bytecode=pushLiteralConstantBytecode(0) +
                                              pushLiteralConstantBytecode(1) +
                                              pushLiteralConstantBytecode(2)):
    interp = new_interpreter(bytecode)
    interp.activeContext.method.literals = ["a", "b", "c"]
    interp.step()
    interp.step()
    interp.step()
    assert interp.activeContext.stack == ["a", "b", "c"]

def test_pushLiteralVariableBytecode(bytecode=pushLiteralVariableBytecode(0)):
    w_association = mockclassmirror(2).new()
    w_association.store(0, "mykey")
    w_association.store(1, "myvalue")
    interp = new_interpreter(bytecode)
    interp.activeContext.method.literals = [w_association]
    interp.step()
    assert interp.activeContext.stack == ["myvalue"]

def test_storeAndPopReceiverVariableBytecode(bytecode=storeAndPopReceiverVariableBytecode,
                                             popped=True):
    m_class = mockclassmirror(8)
    for index in range(8):
        w_object = m_class.new()
        interp = new_interpreter(pushConstantTrueBytecode + bytecode(index))
        interp.activeContext.receiver = w_object
        interp.step()
        interp.step()
        if popped:
            assert interp.activeContext.stack == []
        else:
            assert interp.activeContext.stack == [interp.TRUE]

        for test_index in range(8):
            if test_index == index:
                assert w_object.fetch(test_index) == interp.TRUE
            else:
                assert w_object.fetch(test_index) == None

def test_storeAndPopTemporaryVariableBytecode(bytecode=storeAndPopTemporaryVariableBytecode):
    for index in range(8):
        interp = new_interpreter(pushConstantTrueBytecode + bytecode(index))
        interp.activeContext.temps = [None] * 8
        interp.step()
        interp.step()
        assert interp.activeContext.stack == []
        for test_index in range(8):
            if test_index == index:
                assert interp.activeContext.temps[test_index] == interp.TRUE
            else:
                assert interp.activeContext.temps[test_index] == None
    

def test_pushConstantTrueBytecode():
    interp = new_interpreter(pushConstantTrueBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.TRUE

def test_pushConstantFalseBytecode():
    interp = new_interpreter(pushConstantFalseBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.FALSE

def test_pushConstantNilBytecode():
    interp = new_interpreter(pushConstantNilBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.NIL

def test_pushConstantMinusOneBytecode():
    interp = new_interpreter(pushConstantMinusOneBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.MONE

def test_pushConstantZeroBytecode():
    interp = new_interpreter(pushConstantZeroBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.ZERO
    
def test_pushConstantOneBytecode():
    interp = new_interpreter(pushConstantOneBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.ONE

def test_pushConstantTwoBytecode():
    interp = new_interpreter(pushConstantTwoBytecode)
    interp.step()
    assert interp.activeContext.top()

def test_pushActiveContextBytecode():
    interp = new_interpreter(pushActiveContextBytecode)
    interp.step()
    assert interp.activeContext.top() == interp.activeContext
    
def test_duplicateTopBytecode():
    interp = new_interpreter(pushConstantZeroBytecode + duplicateTopBytecode)
    interp.step()
    interp.step()
    assert interp.activeContext.stack == [interp.ZERO, interp.ZERO]

# m_class - the class from which the method is going to be called
# (and on which it is going to be installed)
# w_object - the actual object we will be sending the method to
# bytecodes - the bytecode to be executed
def sendBytecodesTest(m_class, w_object, bytecodes):
    for bytecode, result in [ (returnReceiver, w_object), 
          (returnTrue, interpreter.Interpreter.TRUE), 
          (returnFalse, interpreter.Interpreter.FALSE),
          (returnNil, interpreter.Interpreter.NIL),
          (returnTopFromMethod, interpreter.Interpreter.ONE) ]:
        m_class.installmethod("foo",
                              model.W_CompiledMethod(0, pushConstantOneBytecode + bytecode))
        interp = new_interpreter(bytecodes)
        interp.activeContext.method.literals = ["foo"]
        interp.activeContext.push(w_object)
        callerContext = interp.activeContext
        interp.step()
        assert interp.activeContext.sender == callerContext
        assert interp.activeContext.stack == []
        assert interp.activeContext.receiver == w_object
        assert interp.activeContext.method == m_class.methoddict["foo"]
        assert callerContext.stack == []
        interp.step()
        interp.step()
        assert interp.activeContext == callerContext
        assert interp.activeContext.stack == [result]

def test_sendLiteralSelectorBytecode():
    m_class = mockclassmirror(0)
    w_object = m_class.new()
    sendBytecodesTest(m_class, w_object, sendLiteralSelectorBytecode(0))
        
def test_fibWithArgument():
    bytecode = ''.join(map(chr, [ 16, 119, 178, 154, 118, 164, 11, 112, 16, 118, 177, 224, 112, 16, 119, 177, 224, 176, 124 ]))
    m_class = mockclassmirror(0)
    method = model.W_CompiledMethod(1, bytecode, 1)
    method.literals[0] = "fib:"
    m_class.installmethod("fib:", method)
    w_object = m_class.new()
    interp = new_interpreter(sendLiteralSelectorBytecode(16) + returnTopFromMethod)
    interp.activeContext.method.literals = ["fib:"]
    interp.activeContext.push(w_object)
    interp.activeContext.push(wrap_int(8))
    result = interp.interpret()
    assert primitives.unwrap_int(result) == 34

def test_send_to_primitive():
    m_smallintclass = ct.m_SmallInteger
    prim_meth = model.W_CompiledMethod(0, "", argsize=1,
                                       primitive=primitives.SUBTRACT)
    m_smallintclass.installmethod("sub", prim_meth)
    try:
        interp = new_interpreter(sendLiteralSelectorBytecode(1 + 16))
        interp.activeContext.method.literals = ["foo", "sub"]
        interp.activeContext.push(wrap_int(50))
        interp.activeContext.push(wrap_int(8))
        callerContext = interp.activeContext
        interp.step()
        assert interp.activeContext is callerContext
        assert len(interp.activeContext.stack) == 1
        w_result = interp.activeContext.pop()
        assert primitives.unwrap_int(w_result) == 42
    finally:
        del m_smallintclass.methoddict['sub']    # clean up after you

def test_longJumpIfTrue():
    interp = new_interpreter(longJumpIfTrue(0) + chr(15) + longJumpIfTrue(0) + chr(15))
    interp.activeContext.push(interp.FALSE)
    pc = interp.activeContext.pc + 2
    interp.step()
    assert interp.activeContext.pc == pc
    interp.activeContext.push(interp.TRUE)
    pc = interp.activeContext.pc + 2
    interp.step()
    assert interp.activeContext.pc == pc + 15

def test_longJumpIfFalse():
    interp = new_interpreter(pushConstantTrueBytecode + longJumpIfFalse(0) + chr(15) +
                             pushConstantFalseBytecode + longJumpIfFalse(0) + chr(15))
    interp.step()
    pc = interp.activeContext.pc + 2
    interp.step()
    assert interp.activeContext.pc == pc
    interp.step()
    pc = interp.activeContext.pc + 2
    interp.step()
    assert interp.activeContext.pc == pc + 15

def test_longUnconditionalJump():
    interp = new_interpreter(longUnconditionalJump(0) + chr(15))
    pc = interp.activeContext.pc + 2
    interp.step()
    assert interp.activeContext.pc == pc + 15

def test_shortUnconditionalJump():
    interp = new_interpreter(chr(145))
    pc = interp.activeContext.pc + 1
    interp.step()
    assert interp.activeContext.pc == pc + 2

def test_shortConditionalJump():
    interp = new_interpreter(pushConstantTrueBytecode + shortConditionalJump(3) +
                             pushConstantFalseBytecode + shortConditionalJump(3))
    interp.step()
    pc = interp.activeContext.pc + 1
    interp.step()
    assert interp.activeContext.pc == pc
    interp.step()
    pc = interp.activeContext.pc + 1
    interp.step()
    assert interp.activeContext.pc == pc + 4

def test_popStackBytecode():
    interp = new_interpreter(pushConstantTrueBytecode +
                             popStackBytecode)
    interp.step()
    assert interp.activeContext.stack == [interp.TRUE]
    interp.step()
    assert interp.activeContext.stack == []

def test_extendedPushBytecode():
    test_pushReceiverVariableBytecode(extendedPushBytecode + chr((0<<6) + 0) +
                                      extendedPushBytecode + chr((0<<6) + 1) +
                                      extendedPushBytecode + chr((0<<6) + 2))

    test_pushTemporaryVariableBytecode(extendedPushBytecode + chr((1<<6) + 0) +
                                       extendedPushBytecode + chr((1<<6) + 1) +
                                       extendedPushBytecode + chr((1<<6) + 2))

    test_pushLiteralConstantBytecode(extendedPushBytecode + chr((2<<6) + 0) +
                                     extendedPushBytecode + chr((2<<6) + 1) +
                                     extendedPushBytecode + chr((2<<6) + 2))

    test_pushLiteralVariableBytecode(extendedPushBytecode + chr((3<<6) + 0))

def storeAssociation(bytecode):
    w_association = mockclassmirror(2).new()
    w_association.store(0, "mykey")
    w_association.store(1, "myvalue")
    interp = new_interpreter(pushConstantOneBytecode + bytecode)
    interp.activeContext.method.literals = [w_association]
    interp.step()
    interp.step()
    assert w_association.fetch(1) == interp.ONE

def test_extendedStoreAndPopBytecode():
    test_storeAndPopReceiverVariableBytecode(lambda index: extendedStoreAndPopBytecode + chr((0<<6) + index))
                
    test_storeAndPopTemporaryVariableBytecode(lambda index: extendedStoreAndPopBytecode + chr((1<<6) + index))

    py.test.raises(interpreter.IllegalStoreError,
                   test_storeAndPopTemporaryVariableBytecode,
                   lambda index: extendedStoreAndPopBytecode + chr((2<<6) + index))

    storeAssociation(extendedStoreAndPopBytecode + chr((3<<6) + 0))

def test_callPrimitiveAndPush_fallback():
    interp = new_interpreter(bytecodePrimAdd)
    m_class = mockclassmirror(0)
    m_class.installmethod("+", model.W_CompiledMethod(1, "", 1))
    w_object = m_class.new()
    interp.activeContext.push(w_object)
    interp.activeContext.push(interp.ONE)
    interp.step()
    assert interp.activeContext.method == m_class.methoddict["+"]
    assert interp.activeContext.receiver is w_object
    assert interp.activeContext.gettemp(0) == interp.ONE
    assert interp.activeContext.stack == []

def test_bytecodePrimBool():
    interp = new_interpreter(bytecodePrimLessThan +
                             bytecodePrimGreaterThan +
                             bytecodePrimLessOrEqual +
                             bytecodePrimGreaterOrEqual +
                             bytecodePrimEqual +
                             bytecodePrimNotEqual)
    for i in range(6):
        interp.activeContext.push(interp.ONE)
        interp.activeContext.push(interp.TWO)
        interp.step()
    assert interp.activeContext.stack == [interp.TRUE, interp.FALSE,
                                          interp.TRUE, interp.FALSE,
                                          interp.FALSE, interp.TRUE]

def test_singleExtendedSendBytecode():
    m_class = mockclassmirror(0)
    w_object = m_class.new()
    sendBytecodesTest(m_class, w_object, singleExtendedSendBytecode + chr((0<<5)+0))

def test_singleExtendedSuperBytecode(bytecode=singleExtendedSuperBytecode + chr((0<<5) + 0)):
    m_supersuper = mockclassmirror(0)
    m_super = mockclassmirror(0, m_superclass=m_supersuper)
    m_class = mockclassmirror(0, m_superclass=m_super)
    w_object = m_class.new()
    # first call method installed in m_class
    bytecodes = singleExtendedSendBytecode + chr(0)
    # which does a call to its super
    m_class.installmethod("foo",
                          model.W_CompiledMethod(0, bytecode))
    # and that one again to its super
    m_super.installmethod("foo",
                          model.W_CompiledMethod(0, bytecode))
    m_supersuper.installmethod("foo",
                               model.W_CompiledMethod(0, ""))
    m_class.methoddict["foo"].literals = ["foo"]
    m_super.methoddict["foo"].literals = ["foo"]
    interp = new_interpreter(bytecodes)
    interp.activeContext.method.literals = ["foo"]
    interp.activeContext.push(w_object)
    for m_specificclass in [m_class, m_super, m_supersuper]:
        callerContext = interp.activeContext
        interp.step()
        assert interp.activeContext.sender == callerContext
        assert interp.activeContext.stack == []
        assert interp.activeContext.receiver == w_object
        assert interp.activeContext.method == m_specificclass.methoddict["foo"]
        assert callerContext.stack == []

def test_secondExtendedSendBytecode():
    m_class = mockclassmirror(0)
    w_object = m_class.new()
    sendBytecodesTest(m_class, w_object, secondExtendedSendBytecode + chr(0)) 

def test_doubleExtendedDoAnythinBytecode():
    m_class = mockclassmirror(0)
    w_object = m_class.new()

    sendBytecodesTest(m_class, w_object, doubleExtendedDoAnythingBytecode + chr((0<<5) + 0) + chr(0))

    test_singleExtendedSuperBytecode(doubleExtendedDoAnythingBytecode + (chr((1<<5) + 0) + chr(0)))

    test_pushReceiverVariableBytecode(doubleExtendedDoAnythingBytecode + chr(2<<5) + chr(0) +
                                      doubleExtendedDoAnythingBytecode + chr(2<<5) + chr(1) +
                                      doubleExtendedDoAnythingBytecode + chr(2<<5) + chr(2))

    test_pushLiteralConstantBytecode(doubleExtendedDoAnythingBytecode + chr(3<<5) + chr(0) +
                                     doubleExtendedDoAnythingBytecode + chr(3<<5) + chr(1) +
                                     doubleExtendedDoAnythingBytecode + chr(3<<5) + chr(2))

    test_pushLiteralVariableBytecode(doubleExtendedDoAnythingBytecode + chr(4<<5) + chr(0))

    test_storeAndPopReceiverVariableBytecode(lambda index: doubleExtendedDoAnythingBytecode + chr(5<<5) + chr(index), False)

    test_storeAndPopReceiverVariableBytecode(lambda index: doubleExtendedDoAnythingBytecode + chr(6<<5) + chr(index))

    storeAssociation(doubleExtendedDoAnythingBytecode + chr(7<<5) + chr(0))
