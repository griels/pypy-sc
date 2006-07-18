from pypy.rpython.ootypesystem import ootype
from pypy.translator.cli.node import Node
from pypy.translator.cli.cts import CTS

class Class(Node):
    def __init__(self, db, INSTANCE, namespace, name):
        self.db = db
        self.cts = db.type_system_class(db)
        self.INSTANCE = INSTANCE
        self.namespace = namespace
        self.name = name

    def dependencies(self):
        if not self.is_root(self.INSTANCE):
            self.db.pending_class(self.INSTANCE._superclass)

    def __hash__(self):
        return hash(self.INSTANCE)

    def __eq__(self, other):
        return self.INSTANCE == other.INSTANCE

    def __ne__(self, other):
        return not self == other

    def is_root(INSTANCE):
        return INSTANCE._superclass is None
    is_root = staticmethod(is_root)

    def get_name(self):
        return self.name

    def __repr__(self):
        return '<Class %s>' % self.name

    def get_base_class(self):
        base_class = self.INSTANCE._superclass
        if self.is_root(base_class):
            return '[mscorlib]System.Object'
        else:
            return self.db.class_name(base_class)

    def render(self, ilasm):        
        if self.is_root(self.INSTANCE):
            return

        self.ilasm = ilasm
        if self.namespace:
            ilasm.begin_namespace(self.namespace)

        ilasm.begin_class(self.name, self.get_base_class())
        for f_name, (f_type, f_default) in self.INSTANCE._fields.iteritems():
            cts_type = self.cts.lltype_to_cts(f_type)
            f_name = self.cts.escape_name(f_name)
            if cts_type != 'void':
                ilasm.field(f_name, cts_type)

        self._ctor()
        self._toString()

        for m_name, m_meth in self.INSTANCE._methods.iteritems():
            if hasattr(m_meth, 'graph'):
                # if the first argument of the method is a strict subclass
                # of this class, then this method is not really used by
                # the class: don't render it, else there would be a type
                # mismatch.
                args =  m_meth.graph.getargs()
                SELF = args[0].concretetype
                if SELF is not self.INSTANCE and ootype.isSubclass(SELF, self.INSTANCE):
                    continue
                f = self.db.function_class(self.db, m_meth.graph, m_name, is_method = True)
                f.render(ilasm)
            else:
                # abstract method
                METH = m_meth._TYPE
                arglist = [(self.cts.lltype_to_cts(ARG), 'v%d' % i)
                           for i, ARG in enumerate(METH.ARGS)
                           if ARG is not ootype.Void]
                returntype = self.cts.lltype_to_cts(METH.RESULT)
                ilasm.begin_function(m_name, arglist, returntype, False, 'virtual', 'abstract')
                ilasm.end_function()

        ilasm.end_class()

        if self.namespace:
            ilasm.end_namespace()

    def _ctor(self):
        from pypy.translator.cli.database import AbstractConst
        self.ilasm.begin_function('.ctor', [], 'void', False, 'specialname', 'rtspecialname', 'instance')
        self.ilasm.opcode('ldarg.0')
        self.ilasm.call('instance void %s::.ctor()' % self.get_base_class())
        # set default values for fields
        for f_name, (F_TYPE, f_default) in self.INSTANCE._fields.iteritems():
            cts_type = self.cts.lltype_to_cts(F_TYPE)
            f_name = self.cts.escape_name(f_name)
            if cts_type != 'void':
                self.ilasm.opcode('ldarg.0')
                AbstractConst.load(self.db, F_TYPE, f_default, self.ilasm)
                class_name = self.db.class_name(self.INSTANCE)
                self.ilasm.set_field((cts_type, class_name, f_name))

        self.ilasm.opcode('ret')
        self.ilasm.end_function()

    def _toString(self):
        self.ilasm.begin_function('ToString', [], 'string', False, 'virtual', 'instance', 'default')
        self.ilasm.opcode('ldarg.0')
        self.ilasm.call('string class [pypylib]pypy.test.Result::InstanceToPython(object)')
        self.ilasm.ret()
        self.ilasm.end_function()

