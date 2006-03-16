import datetime, sys
from pypy.objspace.flow.model import Constant, Variable, Block
from pypy.objspace.flow.model import last_exception, checkgraph
from pypy.translator.gensupp import NameManager
from pypy.translator.squeak.message import Message, camel_case
from pypy.translator.squeak.opformatter import OpFormatter
from pypy.rpython.ootypesystem.ootype import Instance, ROOT
from pypy import conftest
try:
    set
except NameError:
    from sets import Set as set


class GenSqueak:

    sqnames = {
        Constant(None).key:  'nil',
        Constant(False).key: 'false',
        Constant(True).key:  'true',
    }
    
    def __init__(self, sqdir, translator, modname=None):
        self.sqdir = sqdir
        self.translator = translator
        self.modname = (modname or
                        translator.graphs[0].name)

        self.name_manager = NameManager(number_sep="")
        self.unique_name_mapping = {}
        self.pending_nodes = []
        self.generated_nodes = set()
        self.constant_insts = {}

        if conftest.option.view:
            self.translator.view()

        graph = self.translator.graphs[0]
        self.pending_nodes.append(FunctionNode(self, graph))
        self.filename = '%s.st' % graph.name
        file = self.sqdir.join(self.filename).open('w')
        self.gen_source(file)
        self.pending_nodes.append(SetupNode(self, self.constant_insts)) 
        self.gen_source(file)
        file.close()

    def gen_source(self, file):
        while self.pending_nodes:
            node = self.pending_nodes.pop()
            self.gen_node(node, file)

    def gen_node(self, node, f):
        for dep in node.dependencies():
            if dep not in self.generated_nodes:
                self.pending_nodes.append(node)
                self.schedule_node(dep)
                return
        self.generated_nodes.add(node)
        for line in node.render():
            print >> f, line
        print >> f, ""

    def schedule_node(self, node):
        if node not in self.generated_nodes:
            if node in self.pending_nodes:
                # We move the node to the front so we can enforce
                # the generation of dependencies.
                self.pending_nodes.remove(node)
            self.pending_nodes.append(node)

    def nameof(self, obj):
        key = Constant(obj).key
        try:
            return self.sqnames[key]
        except KeyError:
            for cls in type(obj).__mro__:
                meth = getattr(self,
                               'nameof_' + cls.__name__.replace(' ', ''),
                               None)
                if meth:
                    break
            else:
                types = ['nameof_'+t.__name__ for t in type(obj).__mro__]
                raise Exception, "nameof(%r): no method %s" % (obj, types)
            name = meth(obj)
            self.sqnames[key] = name
            return name

    def nameof_int(self, i):
        return str(i)

    def nameof_str(self, s):
        return "'s'"

    def nameof_Instance(self, INSTANCE):
        if INSTANCE is None:
            return "Object"
        self.schedule_node(ClassNode(self, INSTANCE))
        class_name = INSTANCE._name.split(".")[-1]
        squeak_class_name = self.unique_name(INSTANCE, class_name)
        return "Py%s" % squeak_class_name

    def nameof__class(self, class_):
        return self.nameof_Instance(class_._INSTANCE)

    def nameof__callable(self, callable):
        return self.nameof_function(callable.graph.func)

    def nameof_function(self, function):
        squeak_func_name = self.unique_name(function, function.__name__)
        return squeak_func_name
        
    def unique_name(self, key, basename):
        if self.unique_name_mapping.has_key(key):
            unique = self.unique_name_mapping[key]
        else:
            camel_basename = camel_case(basename)
            unique = self.name_manager.uniquename(camel_basename)
            self.unique_name_mapping[key] = unique
        return unique


class CodeNode:

    def __hash__(self):
        return hash(self.hash_key)
    
    def __eq__(self, other):
        return isinstance(other, CodeNode) \
                and self.hash_key == other.hash_key
    
    # XXX need other comparison methods?

    def render_fileout_header(self, class_name, category):
        return "!%s methodsFor: '%s' stamp: 'pypy %s'!" % (
                class_name, category,
                datetime.datetime.now().strftime("%m/%d/%Y %H:%M"))

    def unique_field(self, INSTANCE, field_name):
        # XXX for now we ignore the issue of nameclashes between
        # field names. It's not so simple because superclasses must
        # be considered, too.
        return camel_case(field_name)

class ClassNode(CodeNode):

    def __init__(self, gen, INSTANCE, class_vars=None):
        self.gen = gen
        self.INSTANCE = INSTANCE
        self.class_vars = [] # XXX should probably go away
        if class_vars is not None:
            self.class_vars = class_vars
        self.hash_key = INSTANCE

    def dependencies(self):
        if self.INSTANCE._superclass is not None: # not root
            return [ClassNode(self.gen, self.INSTANCE._superclass)]
        else:
            return []

    def render(self):
        yield "%s subclass: #%s" % (
            self.gen.nameof_Instance(self.INSTANCE._superclass), 
            self.gen.nameof_Instance(self.INSTANCE))
        fields = [self.unique_field(self.INSTANCE, f) for f in
            self.INSTANCE._fields.iterkeys()]
        yield "    instanceVariableNames: '%s'" % ' '.join(fields)
        yield "    classVariableNames: '%s'" % ' '.join(self.class_vars)
        yield "    poolDictionaries: ''"
        yield "    category: 'PyPy-Test'!"

class LoopFinder:

    def __init__(self, startblock):
        self.loops = {}
        self.parents = {startblock: startblock}
        self.temps = {}
        self.seen = []
        self.visit_Block(startblock)
   
    def visit_Block(self, block, switches=[]):
        #self.temps.has_key()
        self.seen.append(block)
        if block.exitswitch:
            switches.append(block)
            self.parents[block] = block
        for link in block.exits:
            self.visit_Link(link, switches) 

    def visit_Link(self, link, switches):
        if link.target in switches:
            self.loops[link.target] = True
        if not link.target in self.seen:
            self.parents[link.target] = self.parents[link.prevblock]
            self.visit_Block(link.target, switches)

class CallableNode(CodeNode):

    def render_body(self, startblock):
        self.loops = LoopFinder(startblock).loops
        args = self.arguments(startblock)
        sel = Message(self.name)
        yield sel.signature([self.expr(v) for v in args])
 
        # XXX should declare local variables here
        for line in self.render_block(startblock):
            yield "    %s" % line
        yield '! !'

    def expr(self, v):
        if isinstance(v, Variable):
            return camel_case(v.name)
        elif isinstance(v, Constant):
            if isinstance(v.concretetype, Instance):
                const_id = self.gen.unique_name(
                        v, "const_%s" % self.gen.nameof(v.value._TYPE))
                self.gen.constant_insts[v] = const_id
                return "(PyConstants getConstant: '%s')" % const_id
            return self.gen.nameof(v.value)
        else:
            raise TypeError, "expr(%r)" % (v,)

    def render_return(self, args):
        if len(args) == 2:
            # exception
            exc_cls = self.expr(args[0])
            exc_val = self.expr(args[1])
            yield "(PyOperationError class: %s value: %s) signal." % (exc_cls, exc_val)
        else:
            # regular return block
            retval = self.expr(args[0])
            yield "^%s" % retval

    def render_link(self, link):
        block = link.target
        if link.args:
            for i in range(len(link.args)):
                yield '%s := %s.' % \
                        (self.expr(block.inputargs[i]), self.expr(link.args[i]))
        for line in self.render_block(block):
            yield line

    def render_block(self, block):
        if self.loops.has_key(block):
            if not self.loops[block]:
                yield '"skip1"'
                return
            yield "["
        formatter = OpFormatter(self.gen, self)
        for op in block.operations:
            yield "%s." % formatter.format(op)
        if len(block.exits) == 0:
            for line in self.render_return(block.inputargs):
                yield line
            return
        elif block.exitswitch is None:
            # single-exit block
            assert len(block.exits) == 1
            for line in self.render_link(block.exits[0]):
                yield line
        else:
            #exitswitch
            if self.loops.has_key(block):
                if self.loops[block]:
                    self.loops[block] = False
                    yield "%s] whileTrue: [" % self.expr(block.exitswitch)
                    for line in self.render_link(block.exits[True]):
                        yield "    %s" % line
                    yield "]."
                    for line in self.render_link(block.exits[False]):
                        yield "%s" % line
            else:
                yield "%s ifTrue: [" % self.expr(block.exitswitch)
                for line in self.render_link(block.exits[True]):
                    yield "    %s" % line
                yield "] ifFalse: [" 
                for line in self.render_link(block.exits[False]):
                    yield "    %s" % line
                yield "]"

class MethodNode(CallableNode):

    def __init__(self, gen, INSTANCE, method_name):
        self.gen = gen
        self.INSTANCE = INSTANCE
        self.name = method_name
        self.self = None # Will be set upon rendering
        self.hash_key = (INSTANCE, method_name)

    def dependencies(self):
        return [ClassNode(self.gen, self.INSTANCE)]

    def arguments(self, startblock):
        # Omit the explicit self
        return startblock.inputargs[1:]
    
    def render(self):
        yield self.render_fileout_header(
                self.gen.nameof(self.INSTANCE), "methods")
        graph = self.INSTANCE._methods[self.name].graph
        self.self = graph.startblock.inputargs[0]
        for line in self.render_body(graph.startblock):
            yield line

class FunctionNode(CallableNode):
    
    FUNCTIONS = Instance("Functions", ROOT)

    def __init__(self, gen, graph):
        self.gen = gen
        self.graph = graph
        self.name = gen.nameof(graph.func)
        self.self = None
        self.hash_key = graph

    def dependencies(self):
        return [ClassNode(self.gen, self.FUNCTIONS)]

    def arguments(self, startblock):
        return startblock.inputargs
    
    def render(self):
        yield self.render_fileout_header("PyFunctions class", "functions")
        for line in self.render_body(self.graph.startblock):
            yield line

class AccessorNode(CodeNode):

    def __init__(self, gen, INSTANCE, field_name):
        self.gen = gen
        self.INSTANCE = INSTANCE
        self.field_name = field_name
        self.hash_key = (INSTANCE, field_name, self.__class__)

    def dependencies(self):
        return [ClassNode(self.gen, self.INSTANCE)]

class SetterNode(AccessorNode):

    def render(self):
        yield self.render_fileout_header(
                self.gen.nameof_Instance(self.INSTANCE), "accessors")
        yield "%s: value" % self.field_name
        yield "    %s := value" % self.field_name
        yield "! !"

class GetterNode(AccessorNode):

    def render(self):
        yield self.render_fileout_header(
                self.gen.nameof_Instance(self.INSTANCE), "accessors")
        yield self.field_name
        yield "    ^%s" % self.field_name
        yield "! !"

class HelperNode(CodeNode):
    
    HELPERS = Instance("Helpers", ROOT)

    def __init__(self, gen, message, code):
        self.gen = gen
        self.message = message
        self.code = code
        self.hash_key = ("helper", code)

    def apply(self, args):
        return self.message.send_to(self.HELPERS, args)
    
    def dependencies(self):
        return [ClassNode(self.gen, self.HELPERS)]

    def render(self):
        # XXX should not use explicit name "PyHelpers" here
        yield self.render_fileout_header("PyHelpers class", "helpers")
        for line in self.code.strip().split("\n"):
            yield line
        yield "! !"

class FieldInitializerNode(CodeNode):

    def __init__(self, gen, INSTANCE):
        self.gen = gen
        self.INSTANCE = INSTANCE
        self.hash_key = ("fieldinit", INSTANCE)

    def dependencies(self):
        return [ClassNode(self.gen, self.INSTANCE)]

    def render(self):
        yield self.render_fileout_header(
                self.gen.nameof_Instance(self.INSTANCE), "initializers")
        fields = self.INSTANCE._allfields()
        sel = Message("field_init")
        arg_names = ["a%s" % i for i in range(len(fields))]
        yield sel.signature(arg_names)
        for field_name, arg_name in zip(fields.keys(), arg_names):
            yield "    %s := %s." % (
                    self.unique_field(self.INSTANCE, field_name),
                    arg_name)
        yield "! !"

class SetupNode(CodeNode):

    CONSTANTS = Instance("Constants", ROOT)
    
    def __init__(self, gen, constants):
        self.gen = gen
        self.constants = constants
        self.hash_key = "setup"

    def dependencies(self):
        # Important: Field initializers for the *runtime* type
        return [FieldInitializerNode(self.gen, c.value._TYPE)
            for c in self.constants.iterkeys()] + \
            [ClassNode(self.gen, self.CONSTANTS, class_vars=["Constants"])]

    def render(self):
        yield self.render_fileout_header("PyConstants class", "internals")
        sel = Message("setupConstants")
        yield sel.signature([])
        yield "    Constants := Dictionary new."
        for const, const_id in self.constants.iteritems():
            INST = const.value._TYPE
            class_name = self.gen.nameof(INST)
            field_names = INST._allfields().keys()
            field_values = [self.gen.nameof(getattr(const.value, f))
                    for f in field_names]
            init_sel = Message("field_init")
            yield "    Constants at: '%s' put: (%s new %s)." \
                    % (const_id, class_name,
                        init_sel.signature(field_values))
        yield "! !"
        yield ""

        yield self.render_fileout_header("PyConstants class", "internals")
        sel = Message("getConstant")
        yield sel.signature(["constId"])
        yield "    ^ Constants at: constId"
        yield "! !"

