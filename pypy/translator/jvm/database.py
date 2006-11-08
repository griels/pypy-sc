"""
The database centralizes information about the state of our translation,
and the mapping between the OOTypeSystem and the Java type system.
"""

from cStringIO import StringIO
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.ootypesystem import ootype
from pypy.translator.jvm import typesystem as jvmtype
from pypy.translator.jvm import node
from pypy.translator.jvm.option import getoption
import pypy.translator.jvm.generator as jvmgen
import pypy.translator.jvm.constant as jvmconst
from pypy.translator.jvm.typesystem import \
     jStringBuilder, jInt, jVoid, jString, jChar, jPyPyConst, jObject
from pypy.translator.jvm.builtin import JvmBuiltInType

from pypy.translator.oosupport.database import Database as OODatabase


# ______________________________________________________________________
# Database object

class Database(OODatabase):
    def __init__(self, genoo):
        OODatabase.__init__(self, genoo)
        
        # Private attributes:
        self._jasmin_files = [] # list of strings --- .j files we made
        self._classes = {} # Maps ootype class objects to node.Class objects,
                           # and JvmType objects as well
        self._functions = {}      # graph -> jvmgen.Method

        self._function_names = {} # graph --> function_name

        self._constants = {}      # flowmodel.Variable --> jvmgen.Const

    # _________________________________________________________________
    # Java String vs Byte Array
    #
    # We allow the user to configure whether Python strings are stored
    # as Java strings, or as byte arrays.  The latter saves space; the
    # former may be faster.  

    using_byte_array = False

    # XXX have to fill this in
    
    # _________________________________________________________________
    # Miscellaneous
    
    def _uniq(self, nm):
        return nm + "_" + str(self.unique())

    def _pkg(self, nm):
        return "%s.%s" % (getoption('package'), nm)

    def class_name(self, TYPE):
        jtype = self.lltype_to_cts(TYPE)
        assert isinstance(jtype, jvmtype.JvmClassType)
        return jtype.name

    def add_jasmin_file(self, jfile):
        """ Adds to the list of files we need to run jasmin on """
        self._jasmin_files.append(jfile)

    def jasmin_files(self):
        """ Returns list of files we need to run jasmin on """
        return self._jasmin_files

    # _________________________________________________________________
    # Node Creation
    #
    # Creates nodes that represents classes, functions, simple constants.
    
    def _function_for_graph(self, classobj, funcnm, is_static, graph):
        
        """
        Creates a node.Function object for a particular graph.  Adds
        the method to 'classobj', which should be a node.Class object.
        """
        argtypes = [arg.concretetype for arg in graph.getargs()
                    if arg.concretetype is not ootype.Void]
        jargtypes = [self.lltype_to_cts(argty) for argty in argtypes]
        rettype = graph.getreturnvar().concretetype
        jrettype = self.lltype_to_cts(rettype)
        funcobj = node.Function(
            self, classobj, funcnm, jargtypes, jrettype, graph, is_static)
        return funcobj
    
    def _translate_instance(self, OOTYPE):
        assert isinstance(OOTYPE, ootype.Instance)
        assert OOTYPE is not ootype.ROOT

        # Create class object if it does not already exist:
        if OOTYPE in self._classes:
            return self._classes[OOTYPE]
        
        # Resolve super class first
        assert OOTYPE._superclass
        supercls = self.pending_class(OOTYPE._superclass)

        # TODO --- make package of java class reflect the package of the
        # OO class?
        clsnm = self._pkg(
            self._uniq(OOTYPE._name.replace('.','_')))
        clsobj = node.Class(clsnm, supercls)

        print "Class %s has super %s" % (
            clsnm, supercls.name)

        # Store the class object for future calls
        self._classes[OOTYPE] = clsobj

        # TODO --- mangle field and method names?  Must be
        # deterministic, or use hashtable to avoid conflicts between
        # classes?
        
        # Add fields:
        for fieldnm, (FIELDOOTY, fielddef) in OOTYPE._fields.iteritems():
            print "Class %s has field %s of type %s" % (
                clsobj.name, fieldnm, FIELDOOTY)
            if FIELDOOTY is ootype.Void: continue
            fieldty = self.lltype_to_cts(FIELDOOTY)
            clsobj.add_field(jvmgen.Field(clsnm, fieldnm, fieldty, False))
            
        # Add methods:
        for mname, mimpl in OOTYPE._methods.iteritems():
            if not hasattr(mimpl, 'graph'):
                # Abstract method
                TODO
            else:
                # if the first argument's type is not a supertype of
                # this class it means that this method this method is
                # not really used by the class: don't render it, else
                # there would be a type mismatch.
                args =  mimpl.graph.getargs()
                SELF = args[0].concretetype
                if not ootype.isSubclass(OOTYPE, SELF): continue
                mobj = self._function_for_graph(
                    clsobj, mname, False, mimpl.graph)
                clsobj.add_method(mobj)

        # currently, we always include a special "dump" method for debugging
        # purposes
        dump_method = node.TestDumpMethod(self, OOTYPE, clsobj)
        clsobj.add_dump_method(dump_method)

        self.pending_node(clsobj)
        return clsobj

    def pending_class(self, OOTYPE):
        return self.lltype_to_cts(OOTYPE)

    def pending_function(self, graph):
        """
        This is invoked when a standalone function is to be compiled.
        It creates a class named after the function with a single
        method, invoke().  This class is added to the worklist.
        Returns a jvmgen.Method object that allows this function to be
        invoked.
        """
        if graph in self._functions:
            return self._functions[graph]
        classnm = self._pkg(self._uniq(graph.name))
        classobj = node.Class(classnm, self.pending_class(ootype.ROOT))
        funcobj = self._function_for_graph(classobj, "invoke", True, graph)
        classobj.add_method(funcobj)
        self.pending_node(classobj)
        res = self._functions[graph] = funcobj.method()
        return res

    # _________________________________________________________________
    # Type printing functions
    #
    # Returns a method that prints details about the value out to
    # stdout.  Should generalize to make it allow for stderr as well.
    
    _type_printing_methods = {
        ootype.Signed:jvmgen.PYPYDUMPINT,
        ootype.Unsigned:jvmgen.PYPYDUMPUINT,
        ootype.SignedLongLong:jvmgen.PYPYDUMPLONG,
        ootype.Float:jvmgen.PYPYDUMPDOUBLE,
        ootype.Bool:jvmgen.PYPYDUMPBOOLEAN,
        ootype.Class:jvmgen.PYPYDUMPOBJECT,
        ootype.String:jvmgen.PYPYDUMPSTRING,
        ootype.StringBuilder:jvmgen.PYPYDUMPOBJECT,
        ootype.Void:jvmgen.PYPYDUMPVOID,
        }

    def generate_dump_method_for_ootype(self, OOTYPE):
        """
        Assuming than an instance of type OOTYPE is pushed on the
        stack, returns a Method object that you can invoke.  This
        method will require that you also push an integer (usually 0)
        that represents the indentation, and then invoke it.  i.e., you
        can do something like:

        > gen.load(var)
        > mthd = db.generate_dump_method_for_ootype(var.concretetype)
        > gen.emit(jvmgen.ICONST, 0)
        > mthd.invoke(gen)

        to print the value of 'var'.
        """
        if OOTYPE in self._type_printing_methods:
            return self._type_printing_methods[OOTYPE]
        pclass = self.pending_class(OOTYPE)
        assert hasattr(pclass, 'dump_method'), "No dump_method for %r" % (OOTYPE, )
        return pclass.dump_method.method()

    # _________________________________________________________________
    # Type translation functions
    #
    # Functions which translate from OOTypes to JvmType instances.
    # FIX --- JvmType and their Class nodes should not be different.

    def escape_name(self, nm):
        # invoked by oosupport/function.py; our names don't need escaping?
        return nm

    def llvar_to_cts(self, llv):
        """ Returns a tuple (JvmType, str) with the translated type
        and name of the given variable"""
        return self.lltype_to_cts(llv.concretetype), llv.name

    # Dictionary for scalar types; in this case, if we see the key, we
    # will return the value
    ootype_to_scalar = {
        ootype.Void:             jvmtype.jVoid,
        ootype.Signed:           jvmtype.jInt,
        ootype.Unsigned:         jvmtype.jInt,
        ootype.SignedLongLong:   jvmtype.jLong,
        ootype.UnsignedLongLong: jvmtype.jLong,
        ootype.Bool:             jvmtype.jBool,
        ootype.Float:            jvmtype.jDouble,
        ootype.Char:             jvmtype.jByte,
        ootype.UniChar:          jvmtype.jChar,
        ootype.Class:            jvmtype.jClass,
        ootype.ROOT:             jvmtype.jObject,  # count this as a scalar...
        }

    # Dictionary for non-scalar types; in this case, if we see the key, we
    # will return a JvmBuiltInType based on the value
    ootype_to_builtin = {
        ootype.String:           jvmtype.jString,
        ootype.StringBuilder:    jvmtype.jStringBuilder
        }

    def lltype_to_cts(self, OOT):
        """ Returns an instance of JvmType corresponding to
        the given OOType """

        # Handle built-in types:
        if OOT in self.ootype_to_scalar:
            return self.ootype_to_scalar[OOT]
        if isinstance(OOT, lltype.Ptr) and isinstance(t.TO, lltype.OpaqueType):
            return jObject
        if OOT in self.ootype_to_builtin:
            return JvmBuiltInType(self, self.ootype_to_builtin[OOT], OOT)

        # Handle non-built-in-types:
        if isinstance(OOT, ootype.Instance):
            return self._translate_instance(OOT)
        if isinstance(OOT, ootype.Record):
            return self._translate_record(OOT)
        if isinstance(OOT, ootype.StaticMethod):
            return XXX
        
        assert False, "Untranslatable type %s!" % OOT

    # _________________________________________________________________
    # Uh....
    #
    # These functions are invoked by the code in oosupport, but I
    # don't think we need them or use them otherwise.
    
    def record_function(self, graph, name):
        self._function_names[graph] = name

    def graph_name(self, graph):
        # XXX: graph name are not guaranteed to be unique
        return self._function_names.get(graph, None)
