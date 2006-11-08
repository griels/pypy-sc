import os # 
from pypy.objspace.flow import model as flowmodel
from pypy.translator.oosupport.metavm import Generator
from pypy.rpython.ootypesystem import ootype
from pypy.translator.oosupport.constant import push_constant
from pypy.translator.jvm.typesystem import \
     JvmType, jString, jInt, jLong, jDouble, jBool, jString, \
     jPyPy, jVoid, jMath, desc_for_method, jPrintStream, jClass, jChar, \
     jObject, jByteArray

# ___________________________________________________________________________
# Helper class string constants

PYPYJAVA = jPyPy.name

# ___________________________________________________________________________
# Miscellaneous helper functions

def _isnan(v):
    return v != v*1.0 or (v == 1.0 and v == 2.0)

def _isinf(v):
    return v!=0 and (v == v*2)

def _unsigned_to_signed_32(val):
    """ In the JVM, we store unsigned integers in a signed integer slot
    (since JVM has no signed integers).  This function converts an
    unsigned value Python integer (possibly a long) into its corresponding
    Python signed integer. """
    if val <= 0x7FFFFFFF:
        return int(val)
    return int(_two_comp_32(val))

def _unsigned_to_signed_64(val):
    """ Same as _unsigned_to_signed_32, but for longs. """
    if val <= 0x7FFFFFFFFFFFFFFF:
        return val
    return _two_comp_64(val)

def _two_comp_32(val):
    """ Returns the 32 bit two's complement. """
    return -((val ^ 0xFFFFFFFF)+1)

def _two_comp_64(val):
    """ Returns the 64 bit two's complement. """
    return -((val ^ 0xFFFFFFFFFFFFFFFF)+1)

# ___________________________________________________________________________
# JVM Opcodes:
#
#   Map from symbolic name to an instance of the Opcode class

class Opcode(object):
    def __init__(self, jvmstr):
        """
        flags is a set of flags (see above) that describe opcode
        jvmstr is the name for jasmin printouts
        """
        self.jvmstr = jvmstr

    def __repr__(self):
        return "<Opcode %s:%x>" % (self.jvmstr, self.flags)

    def specialize(self, args):
        """ Process the argument list according to the various flags.
        Returns a tuple (OPCODE, ARGS) where OPCODE is a string representing
        the new opcode, and ARGS is a list of arguments or empty tuple.
        Most of these do not do anything. """
        return (self.jvmstr, args)

class IntConstOpcode(Opcode):
    """ The ICONST opcode specializes itself for small integer opcodes. """
    def specialize(self, args):
        assert len(args) == 1
        if args[0] == -1:
            return self.jvmstr + "_m1", ()
        elif args[0] >= 0 and args[0] <= 5:
            return self.jvmstr + "_" + str(args[0]), ()
        # Non obvious: convert ICONST to LDC if the constant is out of
        # range
        return "ldc", args

class VarOpcode(Opcode):
    """ An Opcode which takes a variable index as an argument; specialized
    to small integer indices. """
    def specialize(self, args):
        assert len(args) == 1
        if args[0] >= 0 and args[0] <= 3:
            return self.jvmstr + "_" + str(args[0]), ()
        return Opcode.specialize(self, args)

class IntClassNameOpcode(Opcode):
    """ An opcode which takes an internal class name as its argument;
    the actual argument will be a JvmType instance. """
    def specialize(self, args):
        args = [args[0].descriptor.int_class_name()]
        return self.jvmstr, args
        
class OpcodeFamily(object):
    """
    Many opcodes in JVM have variants that depend on the type of the
    operands; for example, one must choose the correct ALOAD, ILOAD,
    or DLOAD depending on whether one is loading a reference, integer,
    or double variable respectively.  Each instance of this class
    defines one 'family' of opcodes, such as the LOAD family shown
    above, and produces Opcode objects specific to a particular type.
    """
    def __init__(self, opcclass, suffix):
        """
        opcclass is the opcode subclass to use (see above) when
        instantiating a particular opcode
        
        jvmstr is the name for jasmin printouts
        """
        self.opcode_class = opcclass
        self.suffix = suffix
        self.cache = {}

    def _o(self, prefix):
        try:
            return self.cache[prefix]
        except KeyError:
            self.cache[prefix] = obj = self.opcode_class(
                prefix+self.suffix)
            return obj
        
    def for_type(self, argtype):
        """ Returns a customized opcode of this family appropriate to
        'argtype', a JvmType object. """

        desc = argtype.descriptor

        # These are always true:
        if desc[0] == 'L': return self._o("a")   # Objects
        if desc[0] == '[': return self._o("a")   # Arrays
        if desc == 'I':    return self._o("i")   # Integers
        if desc == 'J':    return self._o("l")   # Integers
        if desc == 'D':    return self._o("d")   # Doubles
        if desc == 'V':    return self._o("")    # Void [used by RETURN]

        # Chars/Bytes/Booleans are normally represented as ints
        # in the JVM, but some opcodes are different.  They use a
        # different OpcodeFamily (see ArrayOpcodeFamily for ex)
        if desc == 'C':    return self._o("i")   # Characters
        if desc == 'B':    return self._o("i")   # Bytes
        if desc == 'Z':    return self._o("i")   # Boolean

        assert False, "Unknown argtype=%s" % repr(argtype)
        raise NotImplementedError

class ArrayOpcodeFamily(OpcodeFamily):
    """ Opcode family specialized for array access instr """
    def for_type(self, argtype):
        if argtype == 'J':    return self._o("l")   # Integers
        if argtype == 'D':    return self._o("d")   # Doubles
        if argtype == 'C':    return self._o("c")   # Characters
        if argtype == 'B':    return self._o("b")   # Bytes
        if argtype == 'Z':    return self._o("b")   # Boolean (access as bytes)
        return OpcodeFamily.for_type(self, argtype)

# Define the opcodes for IFNE, IFEQ, IFLT, IF_ICMPLT, etc.  The IFxx
# variants compare a single integer arg against 0, and the IF_ICMPxx
# variants compare 2 integer arguments against each other.
for cmpop in ('ne', 'eq', 'lt', 'gt', 'le', 'ge'):
    ifop = "if%s" % cmpop
    if_icmpop = "if_icmp%s" % cmpop
    globals()[ifop.upper()] = Opcode(ifop)
    globals()[if_icmpop.upper()] = Opcode(if_icmpop)

# Compare references, either against NULL or against each other
IFNULL =    Opcode('ifnull')
IFNONNULL = Opcode('ifnonnull')
IF_ACMPEQ = Opcode('if_acmpeq')
IF_ACMPNE = Opcode('if_acmpne')

# Method invocation
INVOKESTATIC = Opcode('invokestatic')
INVOKEVIRTUAL = Opcode('invokevirtual')
INVOKESPECIAL = Opcode('invokespecial')

# Other opcodes
LDC =       Opcode('ldc')       # single-word types
LDC2 =      Opcode('ldc2_w')    # double-word types: doubles and longs
GOTO =      Opcode('goto')
ICONST =    IntConstOpcode('iconst')
ACONST_NULL=Opcode('aconst_null')
DCONST_0 =  Opcode('dconst_0')
DCONST_1 =  Opcode('dconst_0')
LCONST_0 =  Opcode('lconst_1')
LCONST_1 =  Opcode('lconst_1')
GETFIELD =  Opcode('getfield')
PUTFIELD =  Opcode('putfield')
GETSTATIC = Opcode('getstatic')
PUTSTATIC = Opcode('putstatic')
CHECKCAST = IntClassNameOpcode('checkcast')
INEG =      Opcode('ineg')
IXOR =      Opcode('ixor')
IADD =      Opcode('iadd')
ISUB =      Opcode('isub')
IMUL =      Opcode('imul')
IDIV =      Opcode('idiv')
IREM =      Opcode('irem')
IAND =      Opcode('iand')
IOR =       Opcode('ior')
ISHL =      Opcode('ishl')
ISHR =      Opcode('ishr')
IUSHR =     Opcode('iushr')
DCMPG =     Opcode('dcmpg')
DCMPL =     Opcode('dcmpl')
NOP =       Opcode('nop')
I2D =       Opcode('i2d')
I2L =       Opcode('i2l')
D2I=        Opcode('d2i')
L2I =       Opcode('l2i')
ATHROW =    Opcode('athrow')
DNEG =      Opcode('dneg')
DADD =      Opcode('dadd')
DSUB =      Opcode('dsub')
DMUL =      Opcode('dmul')
DDIV =      Opcode('ddiv')
DREM =      Opcode('drem')
LNEG =      Opcode('lneg')
LADD =      Opcode('ladd')
LSUB =      Opcode('lsub')
LMUL =      Opcode('lmul')
LDIV =      Opcode('ldiv')
LREM =      Opcode('lrem')
LAND =      Opcode('land')
LOR =       Opcode('lor')
LXOR =      Opcode('lxor')
LSHL =      Opcode('lshl')
LSHR =      Opcode('lshr')
LUSHR =     Opcode('lushr')
NEW =       IntClassNameOpcode('new')
DUP =       Opcode('dup')
DUP2 =      Opcode('dup2')
POP =       Opcode('pop')
POP2 =      Opcode('pop2')
INSTANCEOF= IntClassNameOpcode('instanceof')
# Loading/storing local variables
LOAD =      OpcodeFamily(VarOpcode, "load")
STORE =     OpcodeFamily(VarOpcode, "store")
RETURN =    OpcodeFamily(Opcode, "return")

# Loading/storing from arrays
#   *NOTE*: This family is characterized by the type of the ELEMENT,
#   not the type of the ARRAY.  
#   
#   Also: here I break from convention by naming the objects ARRLOAD
#   rather than ALOAD, even though the suffix is 'aload'.  This is to
#   avoid confusion with the ALOAD opcode.
ARRLOAD =      ArrayOpcodeFamily(Opcode, "aload")
ARRSTORE =     ArrayOpcodeFamily(Opcode, "astore")

# ___________________________________________________________________________
# Labels
#
# We use a class here just for sanity checks and debugging print-outs.

class Label(object):

    def __init__(self, number, desc):
        """ number is a unique integer
        desc is a short, descriptive string that is a valid java identifier """
        self.label = "%s_%s" % (desc, number)

    def __repr__(self):
        return "Label(%s)"%self.label

    def jasmin_syntax(self):
        return self.label
    
# ___________________________________________________________________________
# Methods
#
# "Method" objects describe all the information needed to invoke a
# method.  We create one for each node.Function object, as well as for
# various helper methods (defined below).  To invoke a method, you
# push its arguments and then use generator.emit(methobj) where
# methobj is its Method instance.

class Method(object):
    
    def v(classty, methnm, argtypes, rettype):
        """
        Shorthand to create a virtual method.
        'class' - JvmType object for the class
        'methnm' - name of the method (Python string)
        'argtypes' - list of JvmType objects, one for each argument but
        not the this ptr
        'rettype' - JvmType for return type
        """
        assert isinstance(classty, JvmType)
        classnm = classty.name
        argtypes = [a.descriptor for a in argtypes]
        rettype = rettype.descriptor
        return Method(classnm, methnm, desc_for_method(argtypes, rettype),
                      opcode=INVOKEVIRTUAL)
    v = staticmethod(v)
    
    def s(classty, methnm, argtypes, rettype):
        """
        Shorthand to create a static method.
        'class' - JvmType object for the class
        'methnm' - name of the method (Python string)
        'argtypes' - list of JvmType objects, one for each argument but
        not the this ptr
        'rettype' - JvmType for return type
        """
        assert isinstance(classty, JvmType)
        classnm = classty.name
        argtypes = [a.descriptor for a in argtypes]
        rettype = rettype.descriptor
        return Method(classnm, methnm, desc_for_method(argtypes, rettype))
    s = staticmethod(s)
    
    def __init__(self, classnm, methnm, desc, opcode=INVOKESTATIC):
        self.opcode = opcode
        self.class_name = classnm  # String, ie. "java.lang.Math"
        self.method_name = methnm  # String "abs"
        self.descriptor = desc     # String, (I)I
    def invoke(self, gen):
        gen._instr(self.opcode, self)
    def jasmin_syntax(self):
        return "%s/%s%s" % (self.class_name.replace('.','/'),
                            self.method_name,
                            self.descriptor)

MATHIABS =              Method.s(jMath, 'abs', (jInt,), jInt)
MATHLABS =              Method.s(jMath, 'abs', (jLong,), jLong)
MATHDABS =              Method.s(jMath, 'abs', (jDouble,), jDouble)
MATHFLOOR =             Method.s(jMath, 'floor', (jDouble,), jDouble)
PRINTSTREAMPRINTSTR =   Method.v(jPrintStream, 'print', (jString,), jVoid)
CLASSFORNAME =          Method.s(jClass, 'forName', (jString,), jClass)
PYPYUINTCMP =           Method.s(jPyPy, 'uint_cmp', (jInt,jInt,), jInt)
PYPYULONGCMP =          Method.s(jPyPy, 'ulong_cmp', (jLong,jLong), jInt)
PYPYUINTTODOUBLE =      Method.s(jPyPy, 'uint_to_double', (jInt,), jDouble)
PYPYDOUBLETOUINT =      Method.s(jPyPy, 'double_to_uint', (jDouble,), jInt)
PYPYLONGBITWISENEGATE = Method.s(jPyPy, 'long_bitwise_negate', (jLong,), jLong)
PYPYSTRTOINT =          Method.s(jPyPy, 'str_to_int', (jString,), jInt)
PYPYSTRTOUINT =         Method.s(jPyPy, 'str_to_uint', (jString,), jInt)
PYPYSTRTOLONG =         Method.s(jPyPy, 'str_to_long', (jString,), jLong)
PYPYSTRTOULONG =        Method.s(jPyPy, 'str_to_ulong', (jString,), jLong)
PYPYSTRTOBOOL =         Method.s(jPyPy, 'str_to_bool', (jString,), jBool)
PYPYSTRTODOUBLE =       Method.s(jPyPy, 'str_to_double', (jString,), jDouble)
PYPYSTRTOCHAR =         Method.s(jPyPy, 'str_to_char', (jString,), jChar)
PYPYDUMPINDENTED  =     Method.s(jPyPy, 'dump_indented', (jInt,jString,), jVoid)
PYPYDUMPINT  =          Method.s(jPyPy, 'dump_int', (jInt,jInt), jVoid)
PYPYDUMPUINT  =         Method.s(jPyPy, 'dump_uint', (jInt,jInt), jVoid)
PYPYDUMPLONG  =         Method.s(jPyPy, 'dump_long', (jLong,jInt), jVoid)
PYPYDUMPDOUBLE  =       Method.s(jPyPy, 'dump_double', (jDouble,jInt), jVoid)
PYPYDUMPSTRING  =       Method.s(jPyPy, 'dump_string', (jString,jInt), jVoid)
PYPYDUMPBOOLEAN =       Method.s(jPyPy, 'dump_boolean', (jBool,jInt), jVoid)
PYPYDUMPOBJECT =        Method.s(jPyPy, 'dump_object', (jObject,jInt,), jVoid)
PYPYDUMPVOID =          Method.s(jPyPy, 'dump_void', (jInt,), jVoid)
PYPYRUNTIMENEW =        Method.s(jPyPy, 'RuntimeNew', (jClass,), jObject)
PYPYSTRING2BYTES =      Method.s(jPyPy, 'string2bytes', (jString,), jByteArray)


# ___________________________________________________________________________
# Fields
#
# Field objects encode information about fields.

class Field(object):
    def __init__(self, classnm, fieldnm, jtype, static):
        # All fields are public
        self.class_name = classnm  # String, ie. "java.lang.Math"
        self.field_name = fieldnm  # String "someField"
        self.jtype = jtype         # JvmType
        self.is_static = static    # True or False
    def load(self, gen):
        if self.is_static:
            gen._instr(GETSTATIC, self)
        else:
            gen._instr(GETFIELD, self)
    def store(self, gen):
        if self.is_static:
            gen._instr(PUTSTATIC, self)
        else:
            gen._instr(PUTFIELD, self)
    def jasmin_syntax(self):
        return "%s/%s %s" % (
            self.class_name.replace('.','/'),
            self.field_name,
            self.jtype.descriptor)

SYSTEMOUT =    Field('java.lang.System', 'out', jPrintStream, True)
SYSTEMERR =    Field('java.lang.System', 'err', jPrintStream, True)
DOUBLENAN =    Field('java.lang.Double', 'NaN', jDouble, True)
DOUBLEPOSINF = Field('java.lang.Double', 'POSITIVE_INFINITY', jDouble, True)
DOUBLENEGINF = Field('java.lang.Double', 'NEGATIVE_INFINITY', jDouble, True)

# ___________________________________________________________________________
# Generator State

class ClassState(object):
    """ When you invoked begin_class(), one of these objects is allocated
    and tracks the state as we go through the definition process. """
    def __init__(self, classty, superclassty):
        self.class_type = classty
        self.superclass_type = superclassty
    def out(self, arg):
        self.file.write(arg)

class FunctionState(object):
    """ When you invoked begin_function(), one of these objects is allocated
    and tracks the state as we go through the definition process. """
    def __init__(self):
        self.next_offset = 0
        self.local_vars = {}
        self.instr_counter = 0
    def add_var(self, jvar, jtype):
        """ Adds new entry for variable 'jvar', of java type 'jtype' """
        idx = self.next_offset
        self.next_offset += jtype.descriptor.type_width()
        if jvar:
            assert jvar not in self.local_vars # never been added before
            self.local_vars[jvar] = idx
        return idx
    def var_offset(self, jvar, jtype):
        """ Returns offset for variable 'jvar', of java type 'jtype' """
        if jvar in self.local_vars:
            return self.local_vars[jvar]
        return self.add_var(jvar, jtype)


# ___________________________________________________________________________
# Generator

class JVMGenerator(Generator):

    """ Base class for all JVM generators.  Invokes a small set of '_'
    methods which indicate which opcodes to emit; these can be
    translated by a subclass into Jasmin assembly, binary output, etc.
    Must be inherited from to specify a particular output format;
    search for the string 'unimplemented' to find the methods that
    must be overloaded. """

    def __init__(self, db):
        self.db = db
        self.label_counter = 0
        self.curclass = None
        self.curfunc = None

    # __________________________________________________________________
    # JVM specific methods to be overloaded by a subclass
    #
    # If the name does not begin with '_', it will be called from
    # outside the generator.

    def begin_class(self, classty, superclsty):
        """
        Begins a class declaration.  Overall flow of class declaration
        looks like:

        begin_class()
        [add_field()]
        emit_constructor()
        [begin_function()...end_function()]
        end_class()

        Where items in brackets may appear anywhere from 0 to inf times.
        
        classty --- JvmType for the class
        superclassty --- JvmType for the superclass
        """
        assert not self.curclass
        self.curclass = ClassState(classty, superclsty)
        self._begin_class()

    def end_class(self):
        self._end_class()
        self.curclass = None
        self.curfunc = None

    def _begin_class(self):
        """ Main implementation of begin_class """
        raise NotImplementedError

    def _end_class(self):
        """ Main implementation of end_class """
        raise NotImplementedError    

    def add_field(self, fobj):
        """
        fobj: a Field object
        """
        unimplemented

    def emit_constructor(self):
        """
        Emits the constructor for this class, which merely invokes the
        parent constructor.
        
        superclsnm --- same Java name of super class as from begin_class
        """
        self.begin_function("<init>", [], [self.curclass.class_type], jVoid)
        self.load_jvm_var(self.curclass.class_type, 0)
        jmethod = Method(self.curclass.superclass_type.name, "<init>", "()V",
                         opcode=INVOKESPECIAL)
        jmethod.invoke(self)
        self.return_val(jVoid)
        self.end_function()

    def begin_function(self, funcname, argvars, argtypes, rettype,
                       static=False):
        """
        funcname --- name of the function
        argvars --- list of objects passed to load() that represent arguments;
                    should be in order, or () if load() will not be used
        argtypes --- JvmType for each argument [INCLUDING this]
        rettype --- JvmType for the return value
        static --- keyword, if true then a static func is generated

        This function also defines the scope for variables passed to
        load()/store().
        """
        # Compute the indicates of each argument in the local variables
        # for the function.  Note that some arguments take up two slots
        # depending on their type [this is compute by type_width()]
        assert not self.curfunc
        self.curfunc = FunctionState()
        for idx, ty in enumerate(argtypes):
            if idx < len(argvars): var = argvars[idx]
            else: var = None
            self.curfunc.add_var(var, ty)
        # Prepare a map for the local variable indices we will add
        # Let the subclass do the rest of the work; note that it does
        # not need to know the argvars parameter, so don't pass it
        self._begin_function(funcname, argtypes, rettype, static)

    def _begin_function(self, funcname, argtypes, rettype, static):
        """
        Main implementation of begin_function.  The begin_function()
        does some generic handling of args.
        """
        unimplemented        

    def end_function(self):
        self._end_function()
        self.curfunc = None

    def _end_function(self):
        unimplemented

    def mark(self, lbl):
        """ Marks the point that a label indicates. """
        unimplemented

    def _instr(self, opcode, *args):
        """ Emits an instruction with the given opcode and arguments.
        The correct opcode and their types depends on the opcode. """
        unimplemented

    def return_val(self, vartype):
        """ Returns a value from top of stack of the JvmType 'vartype' """
        self._instr(RETURN.for_type(vartype))

    def load_string(self, str):
        """ Pushes a Java version of a Python string onto the stack.
        'str' should be a Python string encoded in UTF-8 (I think) """
        # Create an escaped version of str:
        def escape(char):
            if char == '"': return r'\"'
            if char == '\n': return r'\n'
            return char
        res = ('"' + 
               "".join(escape(c) for c in str) +
               '"')
        # Use LDC to load the Java version:
        #     XXX --- support byte arrays here?  Would be trickier!
        self._instr(LDC, res)

    def load_jvm_var(self, vartype, varidx):
        """ Loads from jvm slot #varidx, which is expected to hold a value of
        type vartype """
        assert varidx < self.curfunc.next_offset
        opc = LOAD.for_type(vartype)
        self.add_comment("     load_jvm_jar: vartype=%s varidx=%s" % (
            repr(vartype), repr(varidx)))
        self._instr(opc, varidx)

    def store_jvm_var(self, vartype, varidx):
        """ Loads from jvm slot #varidx, which is expected to hold a value of
        type vartype """
        self.add_comment("     store_jvm_jar: vartype=%s varidx=%s" % (
            repr(vartype), repr(varidx)))
        self._instr(STORE.for_type(vartype), varidx)

    def load_from_array(self, elemtype):
        """ Loads something from an array; the result will be of type 'elemtype'
        (and hence the array is of type 'array_of(elemtype)'), where
        'elemtype' is a JvmType.  Assumes that the array ref and index are
        already pushed onto stack (in that order). """
        self._instr(ARRLOAD.for_type(elemtype))

    def store_to_array(self, elemtype):
        """ Stores something into an array; the result will be of type
        'elemtype' (and hence the array is of type
        'array_of(elemtype)'), where 'elemtype' is a JvmType.  Assumes
        that the array ref, index, and value are already pushed onto
        stack (in that order)."""
        self._instr(ARRLOAD.for_type(elemtype))

    def unique_label(self, desc, mark=False):
        """ Returns an opaque, unique label object that can be passed an
        argument for branching opcodes, or the mark instruction.

        'desc' should be a comment describing the use of the label.
        It is for decorative purposes only and should be a valid C
        identifier.

        'mark' --- if True, then also calls self.mark() with the new lbl """
        res = Label(self.label_counter, desc)
        self.label_counter += 1
        if mark:
            self.mark(res)
        return res

    def load_this_ptr(self):
        """ Convenience method.  Be sure you only call it from a
        virtual method, not static methods. """
        self.load_jvm_var(jObject, 0)

    # __________________________________________________________________
    # Exception Handling

    def begin_try(self):
        """
        Begins a try/catch region.  Must be followed by a call to end_try()
        after the code w/in the try region is complete.
        """
        self.begintrylbl = self.unique_label("begin_try", mark=True)

    def end_try(self):
        """
        Ends a try/catch region.  Must be followed immediately
        by a call to begin_catch().
        """
        self.endtrylbl = self.unique_label("end_try", mark=True)

    def begin_catch(self, excclsty):
        """
        Begins a catch region corresponding to the last try; there can
        be more than one call to begin_catch, in which case the last
        try region is reused.
        'excclsty' --- a JvmType for the class of exception to be caught
        """
        catchlbl = self.unique_label("catch")
        self.mark(catchlbl, mark=True)
        self.try_catch_region(
            excclsty, self.begintrylbl, send.endtrylbl, catchlbl)

    def end_catch(self):
        """
        Ends a catch region.
        (Included for CLI compatibility)
        """
        return
        
    def try_catch_region(self, excclsty, trystartlbl, tryendlbl, catchlbl):
        """
        Indicates a try/catch region:
        'excclsty' --- a JvmType for the class of exception to be caught
        'trystartlbl', 'tryendlbl' --- labels marking the beginning and end
        of the try region
        'catchlbl' --- label marking beginning of catch region
        """
        unimplemented
        
    # __________________________________________________________________
    # Generator methods and others that are invoked by MicroInstructions
    # 
    # These translate into calls to the above methods.

    def emit(self, instr, *args):
        """ 'instr' in our case must be either a string, in which case
        it is the name of a method to invoke, or an Opcode/Method
        object (defined above)."""

        if isinstance(instr, str):
            return getattr(self, instr)(*args)

        if isinstance(instr, Opcode):
            return self._instr(instr, *args)

        if isinstance(instr, Method):
            return instr.invoke(self)

        raise Exception("Unknown object in call to emit(): "+repr(instr))

    def _var_data(self, v):
        # Determine java type:
        jty = self.db.lltype_to_cts(v.concretetype)
        # Determine index in stack frame slots:
        #   note that arguments and locals can be treated the same here
        return jty, self.curfunc.var_offset(v, jty)
        
    def load(self, value):
        if isinstance(value, flowmodel.Variable):
            jty, idx = self._var_data(value)
            return self.load_jvm_var(jty, idx)

        if isinstance(value, flowmodel.Constant):
            return push_constant(self.db, value.concretetype, value.value, self)
            
        raise Exception('Unexpected type for v in load(): '+
                        repr(value.concretetype) + " v=" + repr(value))

    def store(self, v):
        # Ignore Void values
        if v.concretetype is ootype.Void:
            return

        if isinstance(v, flowmodel.Variable):
            jty, idx = self._var_data(v)
            return self.store_jvm_var(jty, idx)
        raise Exception('Unexpected type for v in store(): '+v)

    def set_field(self, CONCRETETYPE, fieldname):
        clsobj = self.db.pending_class(CONCRETETYPE)
        fieldobj = clsobj.lookup_field(fieldname)
        fieldobj.store(self)

    def get_field(self, CONCRETETYPE, fieldname):
        clsobj = self.db.pending_class(CONCRETETYPE)
        fieldobj = clsobj.lookup_field(fieldname)
        fieldobj.load(self)

    def downcast(self, TYPE):
        jtype = self.db.lltype_to_cts(TYPE)
        self._instr(CHECKCAST, jtype)
        
    def instanceof(self, TYPE):
        jtype = self.db.lltype_to_cts(TYPE)
        self._instr(INSTANCEOF, jtype)

    def branch_unconditionally(self, target_label):
        self._instr(GOTO, target_label)

    def branch_conditionally(self, cond, target_label):
        if cond:
            self._instr(IFNE, target_label)
        else:
            self._instr(IFEQ, target_label)

    def call_graph(self, graph):
        mthd = self.db.pending_function(graph)
        mthd.invoke(self)

    def call_method(self, OOCLASS, method_name):
        clsobj = self.db.pending_class(OOCLASS)
        mthd = clsobj.lookup_method(method_name)
        mthd.invoke(self)

    def call_primitive(self, graph):
        raise NotImplementedError

    def call_oostring(self, OOTYPE):
        cts_type = self.db.lltype_to_cts(OOTYPE)
        if cts_type != jByteArray:
            mthd = Method.s(jPyPy, 'oostring', [cts_type, jInt], jString)
            self.emit(mthd)
            if self.db.using_byte_array:
                self.emit(PYPYSTRING2BYTES)
        else:
            mthd = Method.s(jPyPy, 'oostring',
                            [jByteArray, jInt], jByteArray)
        
    def new(self, TYPE):
        jtype = self.db.lltype_to_cts(TYPE)
        ctor = Method(jtype.name, "<init>", "()V", opcode=INVOKESPECIAL)
        self.emit(NEW, jtype)
        self.emit(DUP)
        self.emit(ctor)
        
    def instantiate(self):
        self.emit(PYPYRUNTIMENEW)

    def getclassobject(self, OOINSTANCE):
        jvmtype = self.db.lltype_to_cts(OOINSTANCE)
        self.load_string(jvmtype.name)
        CLASSFORNAME.invoke(self)
        
    def dup(self, OOTYPE):
        jvmtype = self.db.lltype_to_cts(OOTYPE)
        if jvmtype.descriptor.type_width() == 1:
            self.emit(DUP)
        else:
            self.emit(DUP2)
            
    def pop(self, OOTYPE):
        jvmtype = self.db.lltype_to_cts(OOTYPE)
        if jvmtype.descriptor.type_width() == 1:
            self.emit(POP)
        else:
            self.emit(POP2)

    def push_null(self, OOTYPE):
        self.emit(ACONST_NULL)

    def push_primitive_constant(self, TYPE, value):
        if TYPE is ootype.Void:
            return
        elif TYPE in (ootype.Bool, ootype.Signed):
            self.emit(ICONST, int(value))
        elif TYPE is ootype.Unsigned:
            # Converts the unsigned int into its corresponding signed value
            # and emits it using ICONST.
            self.emit(ICONST, _unsigned_to_signed_32(value))
        elif TYPE is ootype.Char or TYPE is ootype.UniChar:
            self.emit(ICONST, ord(value))
        elif TYPE is ootype.SignedLongLong:
            self._push_long_constant(long(value))
        elif TYPE is ootype.UnsignedLongLong:
            self._push_long_constant(_unsigned_to_signed_64(value))
        elif TYPE is ootype.Float:
            self._push_double_constant(float(value))
        elif TYPE is ootype.String:
            self.load_string(str(value))

    def _push_long_constant(self, value):
        if value == 0:
            gen.emit(LCONST_0)
        elif value == 1:
            gen.emit(LCONST_1)
        else:
            gen.emit(LDC2, value)

    def _push_double_constant(self, value):
        if _isnan(value):
            DOUBLENAN.load(self)
        elif _isinf(value):
            if value > 0: DOUBLEPOSINF.load(self)
            else: DOUBLENEGINF.load(self)
        elif value == 0.0:
            gen.emit(DCONST_0)
        elif value == 1.0:
            gen.emit(DCONST_1)
        else:
            gen.emit(LDC2, self.value)        

    # __________________________________________________________________
    # Methods invoked directly by strings in jvm/opcode.py

    def throw(self):
        """ Throw the object from top of the stack as an exception """
        self._instr(ATHROW)

    def iabs(self):
        MATHIABS.invoke(self)

    def dbl_abs(self):
        MATHDABS.invoke(self)

    def bitwise_negate(self):
        """ Invert all the bits in the "int" on the top of the stack """
        self._instr(ICONST, -1)
        self._instr(IXOR)

    def goto_if_true(self, label):
        """ Jumps if the top of stack is true """
        self._instr(IFNE, label)

    ##### Comparison methods
    
    def _compare_op(self, cmpopcode):
        """
        Converts a comparison operation into a boolean value on the
        stack.  For example, compare_op(IFEQ) emits the instructions
        to perform a logical inversion [because it is true if the
        instruction equals zero].  Consumes as many operands from the
        stack as the cmpopcode consumes, typically 1 or 2.
        """
        midlbl = self.unique_label('cmpop')
        endlbl = self.unique_label('cmpop')
        self._instr(cmpopcode, midlbl)
        self._instr(ICONST, 0)
        self._instr(GOTO, endlbl)
        self.mark(midlbl)
        self._instr(ICONST, 1)
        self.mark(endlbl)

    is_null = lambda self: self._compare_op(IFNULL)
    is_not_null = lambda self: self._compare_op(IFNOTNULL)

    logical_not = lambda self: self._compare_op(IFEQ)
    equals_zero = logical_not
    not_equals_zero = lambda self: self._compare_op(IFNE)
    equals = lambda self: self._compare_op(IF_ICMPEQ)
    not_equals = lambda self: self._compare_op(IF_ICMPNE)
    less_than = lambda self: self._compare_op(IF_ICMPLT)
    greater_than = lambda self: self._compare_op(IF_ICMPGT)
    less_equals = lambda self: self._compare_op(IF_ICMPLT)
    greater_equals = lambda self: self._compare_op(IF_ICMPGE)

    def _uint_compare_op(self, cmpopcode):
        PYPYUINTCMP.invoke(self)
        self._compare_op(cmpopcode)

    u_equals = equals
    u_not_equals = not_equals
    u_less_than = lambda self: self._uint_compare_op(IFLT)
    u_greater_than = lambda self: self._uint_compare_op(IFGT)
    u_less_equals = lambda self: self._uint_compare_op(IFLE)
    u_greater_equals = lambda self: self._uint_compare_op(IFGE)

    def _dbl_compare_op(self, cmpopcode):
        # XXX --- NaN behavior?
        self._invoke(DCMPG)
        self._compare_op(cmpopcode)

    dbl_equals = lambda self: self._dbl_compare_op(IFEQ)
    dbl_not_equals = lambda self: self._dbl_compare_op(IFNE)
    dbl_less_than = lambda self: self._dbl_compare_op(IFLT)
    dbl_greater_than = lambda self: self._dbl_compare_op(IFGT)
    dbl_less_equals = lambda self: self._dbl_compare_op(IFLE)
    dbl_greater_equals = lambda self: self._dbl_compare_op(IFGE)

    def _long_compare_op(self, cmpopcode):
        self._invoke(LCMP)
        self._compare_op(cmpopcode)

    long_equals = lambda self: self._long_compare_op(IFEQ)
    long_not_equals = lambda self: self._long_compare_op(IFNE)
    long_less_than = lambda self: self._long_compare_op(IFLT)
    long_greater_than = lambda self: self._long_compare_op(IFGT)
    long_less_equals = lambda self: self._long_compare_op(IFLE)
    long_greater_equals = lambda self: self._long_compare_op(IFGE)

    def _ulong_compare_op(self, cmpopcode):
        PYPYULONGCMP.invoke(self)
        self._compare_op(cmpopcode)

    ulong_equals = long_equals
    ulong_not_equals = long_not_equals
    ulong_less_than = lambda self: self._ulong_compare_op(IFLT)
    ulong_greater_than = lambda self: self._ulong_compare_op(IFGT)
    ulong_less_equals = lambda self: self._ulong_compare_op(IFLE)
    ulong_greater_equals = lambda self: self._ulong_compare_op(IFGE)
        
class JasminGenerator(JVMGenerator):

    def __init__(self, db, outdir, package):
        JVMGenerator.__init__(self, db)
        self.outdir = outdir

    def _begin_class(self):
        """
        classnm --- full Java name of the class (i.e., "java.lang.String")
        """

        iclassnm = self.curclass.class_type.descriptor.int_class_name()
        isuper = self.curclass.superclass_type.descriptor.int_class_name()
        
        jfile = "%s/%s.j" % (self.outdir, iclassnm)

        try:
            jdir = jfile[:jfile.rindex('/')]
            os.makedirs(jdir)
        except OSError: pass
        self.curclass.file = open(jfile, 'w')
        self.db.add_jasmin_file(jfile)

        # Write the JasminXT header
        self.curclass.out(".class public %s\n" % iclassnm)
        self.curclass.out(".super %s\n" % isuper)
        
    def _end_class(self):
        self.curclass.file.close()

    def close(self):
        assert self.curclass is None

    def add_comment(self, comment):
        self.curclass.out("  ; %s\n" % comment)

    def add_field(self, fobj):
        kw = ['public']
        if fobj.is_static: kw.append('static')
        self.curclass.out('.field %s %s %s\n' % (
            " ".join(kw), fobj.field_name, fobj.jtype.descriptor))

    def _begin_function(self, funcname, argtypes, rettype, static):

        if not static: argtypes = argtypes[1:]

        # Throws clause?  Only use RuntimeExceptions?
        kw = ['public']
        if static: kw.append('static')
        self.curclass.out('.method %s %s(%s)%s\n' % (
            " ".join(kw),
            funcname,
            "".join([a.descriptor for a in argtypes]),
            rettype.descriptor))

    def _end_function(self):
        self.curclass.out('.limit stack 100\n') # HACK, track max offset
        self.curclass.out('.limit locals %d\n' % self.curfunc.next_offset)
        self.curclass.out('.end method\n')

    def mark(self, lbl):
        """ Marks the point that a label indicates. """
        assert isinstance(lbl, Label)
        self.curclass.out('  %s:\n' % lbl.jasmin_syntax())

    def _instr(self, opcode, *args):
        jvmstr, args = opcode.specialize(args)
        def jasmin_syntax(arg):
            if hasattr(arg, 'jasmin_syntax'): return arg.jasmin_syntax()
            return str(arg)
        strargs = [jasmin_syntax(arg) for arg in args]
        instr_text = '%s %s' % (jvmstr, " ".join(strargs))
        self.curclass.out('    %-60s ; %d\n' % (
            instr_text, self.curfunc.instr_counter))
        self.curfunc.instr_counter+=1

    def try_catch_region(self, excclsty, trystartlbl, tryendlbl, catchlbl):
        self.curclass.out('  .catch %s from %s to %s using %s\n' % (
            excclsty.int_class_name(), trystartlbl, tryendlbl, catchlbl))
                       
