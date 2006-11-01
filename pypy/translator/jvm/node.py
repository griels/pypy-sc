"""
Rendering nodes for the JVM.  I suspect that a lot of this could be
made to be common between CLR and JVM.
"""


from pypy.rpython.lltypesystem import lltype
from pypy.rpython.ootypesystem import ootype
from pypy.translator.jvm.typesystem import \
     jString, jStringArray, jVoid, jThrowable
from pypy.translator.jvm.typesystem import jvm_for_class, jvm_method_desc, jInt
from pypy.translator.jvm.opcodes import opcodes
from pypy.translator.jvm.option import getoption
from pypy.translator.oosupport.function import Function as OOFunction
import pypy.translator.jvm.generator as jvmgen

class Node(object):
    def set_db(self, db):
        self.db = db

class EntryPoint(Node):

    """
    A special node that generates the pypy.Main class which has a static
    main method.  Can be configured with a number of options for internal
    testing (see __init__)
    """

    def __init__(self, graph, expandargs, printresult):
        """
        'graph' --- The initial graph to invoke from main()
        'expandargs' --- controls whether the arguments passed to main()
        are passed as a list, or expanded to match each argument to the graph

        The 'expandargs' option deserves explanation:
        
          it will be false for a standalone build, because in that
          case we want to convert the String[] array that main() receives
          into a corresponding python List of string objects.

          it will (generally) be true when compiling individual
          functions, in which case we might be compiling an entry
          point with a signature like (a:int,b:float) in which case
          argv[1] should be converted to an integer, and argv[2]
          should be converted to a float.
        """
        self.graph = graph
        self.expand_arguments = expandargs
        self.print_result = printresult
        pass

    # XXX --- perhaps this table would be better placed in typesystem.py
    # so as to constrain the knowledge of lltype and ootype
    _type_conversion_methods = {
        ootype.Signed:jvmgen.PYPYSTRTOINT,
        ootype.Unsigned:jvmgen.PYPYSTRTOUINT,
        lltype.SignedLongLong:jvmgen.PYPYSTRTOLONG,
        lltype.UnsignedLongLong:jvmgen.PYPYSTRTOULONG,
        ootype.Bool:jvmgen.PYPYSTRTOBOOL,
        ootype.Float:jvmgen.PYPYSTRTODOUBLE,
        ootype.Char:jvmgen.PYPYSTRTOCHAR
        }

    def render(self, gen):
        gen.begin_class('pypy.Main', 'java.lang.Object')
        gen.begin_function(
            'main', (), [jStringArray], jVoid, static=True)

        # Handle arguments:
        if self.expand_arguments:
            # Convert each entry into the array to the desired type by
            # invoking an appropriate helper function on each one
            for i, arg in enumerate(self.graph.getargs()):
                jty = self.db.lltype_to_cts(arg.concretetype)
                gen.load_jvm_var(jStringArray, 0)
                gen.emit(jvmgen.ICONST, i)
                gen.load_from_array(jString)
                gen.emit(self._type_conversion_methods[arg.concretetype])
        else:
            # Convert the array of strings to a List<String> as the
            # python method expects
            arg0 = self.graph.getargs()[0]
            assert isinstance(arg0.concretetype, ootype.List), str(arg0.concretetype)
            assert arg0._ITEMTYPE is ootype.String
            gen.load_jvm_var(0)
            gen.emit(jvmgen.PYPYARRAYTOLIST)

        # Generate a call to this method
        gen.emit(self.db.pending_function(self.graph))

        # Print result?
        if self.print_result:
            gen.emit(jvmgen.ICONST, 0)
            RESOOTYPE = self.graph.getreturnvar().concretetype
            dumpmethod = self.db.generate_dump_method_for_ootype(RESOOTYPE)
            dumpmethod.invoke(gen)

        # And finish up
        gen.return_val(jVoid)
        
        gen.end_function()
        gen.end_class()

class Function(OOFunction):
    
    """ Represents a function to be emitted. """
    
    def __init__(self, db, classobj, name, jargtypes,
                 jrettype, graph, is_static):
        """
        classobj: the Class object this is a part of (even static
        functions have a class)
        name: the name of the function
        jargtypes: JvmType of each argument
        jrettype: JvmType this function returns
        graph: the graph representing the body of the function
        is_static: boolean flag indicate whether func is static (!)
        """
        OOFunction.__init__(self, db, graph, name, not is_static)
        self.classnm = classobj.name
        self.jargtypes = jargtypes
        self.jrettype = jrettype
        self._block_labels = {}

    def method(self):
        """ Returns a jvmgen.Method that can invoke this function """
        if not self.is_method:
            opcode = jvmgen.INVOKESTATIC
            startidx = 0
        else:
            opcode = jvmgen.INVOKEVIRTUAL
            startidx = 1
        mdesc = jvm_method_desc(self.jargtypes[startidx:], self.jrettype)
        return jvmgen.Method(self.classnm, self.name, mdesc, opcode=opcode)

    def begin_render(self):
        # Prepare argument lists for begin_function call
        lltype_to_cts = self.db.lltype_to_cts
        jargvars = []
        jargtypes = []
        for arg in self.graph.getargs():
            if arg.concretetype is ootype.Void: continue
            jargvars.append(arg)
            jargtypes.append(lltype_to_cts(arg.concretetype))

        # Determine return type
        jrettype = lltype_to_cts(self.graph.getreturnvar().concretetype)
        self.ilasm.begin_function(
            self.name, jargvars, jargtypes, jrettype, static=not self.is_method)

    def end_render(self):
        self.ilasm.end_function()

    def _create_generator(self, ilasm):
        # JVM doesn't distinguish
        return ilasm

    def _get_block_name(self, block):
        if block in self._block_labels:
            return self._block_labels[block]
        blocklbl = self.ilasm.unique_label('BasicBlock')
        self._block_labels[block] = blocklbl
        return blocklbl

    def set_label(self, blocklbl):
        self.ilasm.mark(blocklbl)

    def begin_try(self):
        self.ilasm.begin_try()

    def end_try(self, exit_label):
        self.ilasm.branch_unconditionally(exit_label)
        self.ilasm.end_try()

    def begin_catch(self, llexitcase):
        unimplemented

    def end_catch(self, llexitcase):
        unimplemented

    def store_exception_and_link(self, link):
        unimplemented

    def render_return_block(self, block):
        return_var = block.inputargs[0]
        return_ty = self.db.lltype_to_cts(return_var.concretetype)
        if return_var.concretetype is not ootype.Void:
            self.ilasm.load(return_var)
        self.ilasm.return_val(return_ty)

    def render_raise_block(self, block):
        exc = block.inputargs[1]
        self.ilasm.load(exc)
        self.ilasm.throw()

    def _render_op(self, op):
        self.generator.add_comment(str(op))
        
        if getoption('trace'):
            jvmgen.SYSTEMERR.load(self.generator)
            self.generator.load_string(str(op) + "\n")
            jvmgen.PRINTSTREAMPRINTSTR.invoke(self.generator)
            
        OOFunction._render_op(self, op)

class Class(Node):

    """ Represents a class to be emitted.  Note that currently, classes
    are emitted all in one shot, not piecemeal. """

    def __init__(self, name, supername):
        """
        'name' and 'super_name' should be fully qualified Java class names like
        "java.lang.String"
        """
        self.name = name             # public attribute
        self.super_name = supername  # public attribute
        self.fields = {}
        self.rendered = False
        self.methods = {}

    def jvm_type(self):
        return jvm_for_class(self.name)

    def add_field(self, fieldobj):
        """ Creates a new field accessed via the jvmgen.Field
        descriptor 'fieldobj'.  Must be called before render()."""
        assert not self.rendered and isinstance(fieldobj, jvmgen.Field)
        self.fields[fieldobj.field_name] = fieldobj

    def lookup_field(self, fieldnm):
        """ Given a field name, returns a jvmgen.Field object """
        return self.fields[fieldnm]

    def lookup_method(self, methodnm):
        """ Given the method name, returns a jvmgen.Method object """
        return self.methods[methodnm].method()

    def add_method(self, func):
        """ Creates a new method in this class, represented by the
        Function object 'func'.  Must be called before render();
        intended to be invoked by the database.  Note that some of these
        'methods' may actually represent static functions. """
        self.methods[func.name] = func

    def add_dump_method(self, dm):
        self.dump_method = dm # public attribute for reading
        self.add_method(dm)
        
    def render(self, gen):
        self.rendered = True
        gen.begin_class(self.name, self.super_name)

        for field in self.fields.values():
            gen.add_field(field)

        gen.emit_constructor()

        for method in self.methods.values():
            method.render(gen)
        
        gen.end_class()

class TestDumpMethod(object):

    def __init__(self, db, OOCLASS, clsobj):
        self.db = db
        self.OOCLASS = OOCLASS
        self.clsobj = clsobj
        self.name = "_pypy_dump"
        self.jargtypes = [clsobj.jvm_type(), jInt]
        self.jrettype = jVoid

    def method(self):
        """ Returns a jvmgen.Method that can invoke this function """
        mdesc = jvm_method_desc(self.jargtypes[1:], self.jrettype)
        return jvmgen.Method(self.clsobj.name, self.name, mdesc,
                             opcode=jvmgen.INVOKEVIRTUAL)

    def render(self, gen):
        clsobj = self.clsobj

        gen.begin_function(
            self.name, (), self.jargtypes, self.jrettype, static=False)

        def genprint(str, unoffset=0):
            gen.load_jvm_var(jInt, 1)
            if unoffset:
                gen.emit(jvmgen.ICONST, unoffset)
                gen.emit(jvmgen.ISUB)
            gen.load_string(str)
            jvmgen.PYPYDUMPINDENTED.invoke(gen)

        # Start the dump
        genprint("InstanceWrapper([")

        # Increment the indent
        gen.load_jvm_var(jInt, 1)
        gen.emit(jvmgen.ICONST, 2)
        gen.emit(jvmgen.IADD)
        gen.store_jvm_var(jInt, 1)

        for fieldnm, (FIELDOOTY, fielddef) in self.OOCLASS._fields.iteritems():

            if FIELDOOTY is ootype.Void: continue

            genprint("(")
            genprint(fieldnm+",")

            print "fieldnm=%r fieldty=%r" % (fieldnm, FIELDOOTY)

            # Print the value of the field:
            gen.load_this_ptr()
            fieldobj = clsobj.lookup_field(fieldnm)
            fieldobj.load(gen)
            gen.load_jvm_var(jInt, 1)
            dumpmethod = self.db.generate_dump_method_for_ootype(FIELDOOTY)
            gen.emit(dumpmethod)

            genprint(")")

        # Decrement indent and dump close
        genprint("])", 2)

        gen.emit(jvmgen.RETURN.for_type(jVoid))

        gen.end_function()
        
        
