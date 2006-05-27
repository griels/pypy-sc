from pypy.translator.cli.cts import CTS
from pypy.translator.cli.function import Function
from pypy.translator.cli.class_ import Class
from pypy.translator.cli.record import Record
from pypy.rpython.ootypesystem import ootype
from pypy.rpython.lltypesystem import lltype
from pypy.translator.cli.opcodes import opcodes

try:
    set
except NameError:
    from sets import Set as set

CONST_NAMESPACE = 'pypy.runtime'
CONST_CLASS = 'Constants'

class LowLevelDatabase(object):
    def __init__(self, type_system_class = CTS, opcode_dict = opcodes, function_class = Function):
        self._pending_nodes = set()
        self.opcode_dict = opcode_dict
        self._rendered_nodes = set()
        self.function_class = function_class
        self.type_system_class = type_system_class
        self.classes = {} # classdef --> class_name
        self.functions = {} # graph --> function_name
        self.methods = {} # graph --> method_name
        self.consts = {}  # value --> const_name
        self.const_names = set()

    def pending_function(self, graph):
        self.pending_node(self.function_class(self, graph))

    def pending_class(self, classdef):
        self.pending_node(Class(self, classdef))

    def pending_record(self, record):
        r = Record(self, record)
        self.pending_node(r)
        return r.get_name()

    def pending_node(self, node):
        if node in self._pending_nodes or node in self._rendered_nodes:
            return
        self._pending_nodes.add(node)

    def record_function(self, graph, name):
        self.functions[graph] = name

    def record_class(self, classdef, name):
        self.classes[classdef] = name

    def graph_name(self, graph):
        return self.functions.get(graph, None)

    def class_name(self, classdef):
        return self.classes.get(classdef, None)

    def record_const(self, value):
        const = AbstractConst.make(self, value)
        try:
            name = self.consts[const]
        except KeyError:
            name = const.get_name()
            if name in self.const_names:
                name += '__%d' % len(self.consts)
            self.consts[const] = name
            self.const_names.add(name)

        return '%s.%s::%s' % (CONST_NAMESPACE, CONST_CLASS, name)

    def gen_constants(self, ilasm):
        if not ilasm.show_const():
            return
        ilasm.begin_namespace(CONST_NAMESPACE)
        ilasm.begin_class(CONST_CLASS)

        # initialize fields

        # This strange machinery it's necessary because it could be
        # happen that new constants are registered during rendering of
        # constants. So we split initialization of constants in a
        # number of 'steps' that are executed in reverse order as they
        # are rendered. The first step to be executed will be stepN,
        # the last step0.

        step = 0
        while self.consts: 
            consts = self.consts
            self.consts = {}

            # render field definitions
            for const, name in consts.iteritems():
                ilasm.field(name, const.get_type(), static=True)

            ilasm.begin_function('step%d' % step, [], 'void', False, 'static')
            for const, name in consts.iteritems():
                const.init(ilasm)
                type_ = const.get_type()
                ilasm.set_static_field (type_, CONST_NAMESPACE, CONST_CLASS, name)

            ilasm.ret()
            ilasm.end_function()
            step += 1

        # the constructor calls the steps in reverse order
        ilasm.begin_function('.cctor', [], 'void', False, 'static',
                             'specialname', 'rtspecialname', 'default')

        last_step = step-1
        for step in xrange(last_step, -1, -1):
            func = '%s.%s::%s' % (CONST_NAMESPACE, CONST_CLASS, 'step%d' % step)
            ilasm.call('void %s()' % func)

        ilasm.ret()
        ilasm.end_function()

        ilasm.end_class()
        ilasm.end_namespace()


class AbstractConst(object):
    def make(db, const):
        if isinstance(const, ootype._view):
            static_type = const._TYPE
            const = const._inst
        else:
            static_type = None

        if isinstance(const, ootype._instance):
            return InstanceConst(db, const, static_type)
        elif isinstance(const, ootype._record):
            return RecordConst(db, const)
        elif isinstance(const, ootype._list):
            return ListConst(db, const)
        else:
            assert False, 'Unknown constant: %s' % const
    make = staticmethod(make)

    def load(db, TYPE, value, ilasm):
        if TYPE is ootype.Void:
            pass
        elif TYPE is ootype.Bool:
            ilasm.opcode('ldc.i4', str(int(value)))
        elif TYPE is ootype.Char or TYPE is ootype.UniChar:
            ilasm.opcode('ldc.i4', ord(value))
        elif TYPE is ootype.Float:
            ilasm.opcode('ldc.r8', repr(value))
        elif TYPE in (ootype.Signed, ootype.Unsigned):
            ilasm.opcode('ldc.i4', str(value))
        elif TYPE in (lltype.SignedLongLong, lltype.UnsignedLongLong):
            ilasm.opcode('ldc.i8', str(value))
        else:
            cts = CTS(db)
            name = db.record_const(value)
            cts_type = cts.lltype_to_cts(TYPE)
            ilasm.opcode('ldsfld %s %s' % (cts_type, name))
    load = staticmethod(load)

    def get_name(self):
        pass

    def get_type(self):
        pass

    def init(self, ilasm):
        pass

class RecordConst(AbstractConst):
    def __init__(self, db, record):
        self.db = db
        self.cts = CTS(db)        
        self.record = record

    def __hash__(self):
        return hash(self.record)

    def __eq__(self, other):
        return self.record == other.record

    def get_name(self):
        return 'Record'

    def get_type(self, include_class=True):
        return self.cts.lltype_to_cts(self.record._TYPE, include_class)

    def init(self, ilasm):
        class_name = self.get_type(False)
        ilasm.new('instance void class %s::.ctor()' % class_name)
        for f_name, (FIELD_TYPE, f_default) in self.record._TYPE._fields.iteritems():
            f_type = self.cts.lltype_to_cts(FIELD_TYPE)
            value = self.record._items[f_name]
            ilasm.opcode('dup')
            AbstractConst.load(self.db, FIELD_TYPE, value, ilasm)            
            ilasm.set_field((f_type, class_name, f_name))

class ListConst(AbstractConst):
    def __init__(self, db, list_):
        self.db = db
        self.cts = CTS(db)
        self.list = list_

    def __hash__(self):
        return hash(self.list)

    def __eq__(self, other):
        return self.list == other.list

    def get_name(self):
        return 'List'

    def get_type(self, include_class=True):
        return self.cts.lltype_to_cts(self.list._TYPE, include_class)

    def init(self, ilasm):
        if not self.list: # it is a null list
            ilasm.opcode('ldnull')
            return

        class_name = self.get_type(False)
        ITEMTYPE = self.list._TYPE._ITEMTYPE
        itemtype = self.cts.lltype_to_cts(ITEMTYPE)
        itemtype_T = self.cts.lltype_to_cts(self.list._TYPE.ITEMTYPE_T)
        ilasm.new('instance void class %s::.ctor()' % class_name)

        # special case: List(Void); only resize it, don't care of the contents
        if ITEMTYPE is ootype.Void:
            ilasm.opcode('dup')
            AbstractConst.load(self.db, ootype.Signed, len(self.list._list), ilasm)            
            meth = 'void class [pypylib]pypy.runtime.List`1<int32>::_ll_resize(int32)'
            ilasm.call_method(meth, False)
            return
        
        for item in self.list._list:
            ilasm.opcode('dup')
            AbstractConst.load(self.db, ITEMTYPE, item, ilasm)
            meth = 'void class [pypylib]pypy.runtime.List`1<%s>::Add(%s)' % (itemtype, itemtype_T)
            ilasm.call_method(meth, False)

class InstanceConst(AbstractConst):
    def __init__(self, db, obj, static_type):
        self.cts = CTS(db)
        self.obj = obj
        if static_type is None:
            self.static_type = obj._TYPE
        else:
            self.static_type = static_type
            self.cts.lltype_to_cts(obj._TYPE) # force scheduling of obj's class

    def __hash__(self):
        return hash(self.obj)

    def __eq__(self, other):
        return self.obj == other.obj

    def get_name(self):
        return self.obj._TYPE._name.replace('.', '_')

    def get_type(self):
        return self.cts.lltype_to_cts(self.static_type)

    def init(self, ilasm):
        classdef = self.obj._TYPE        
        ilasm.new('instance void class %s::.ctor()' % classdef._name)
        while classdef is not None:
            for name, (type_, default) in classdef._fields.iteritems():
                if isinstance(type_, ootype.StaticMethod):
                    continue
                elif type_ is ootype.Class:
                    value = getattr(self.obj, name)
                    self.cts.lltype_to_cts(value._INSTANCE) # force scheduling class generation
                    classname = value._INSTANCE._name
                    ilasm.opcode('dup')
                    ilasm.opcode('ldtoken', classname)
                    ilasm.call('class [mscorlib]System.Type class [mscorlib]System.Type::GetTypeFromHandle(valuetype [mscorlib]System.RuntimeTypeHandle)')
                    ilasm.opcode('stfld class [mscorlib]System.Type %s::%s' % (classdef._name, name))
            classdef = classdef._superclass

