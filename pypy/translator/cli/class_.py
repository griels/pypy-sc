from pypy.translator.cli.node import Node
from pypy.translator.cli.cts import CTS

class Class(Node):
    def __init__(self, db, classdef):
        self.db = db
        self.cts = CTS(db)
        self.classdef = classdef
        self.namespace, self.name = self.cts.split_class_name(classdef._name)

        if not self.is_root(classdef):
            self.db.pending_class(classdef._superclass)

    def __hash__(self):
        return hash(self.classdef)

    def __eq__(self, other):
        return self.classdef == other.classdef

    def is_root(classdef):
        return classdef._superclass is None
    is_root = staticmethod(is_root)

    def get_name(self):
        return self.name

    def get_base_class(self):
        base_class = self.classdef._superclass
        if self.is_root(base_class):
            return '[mscorlib]System.Object'
        else:
            return base_class._name

    def render(self, ilasm):
        if self.is_root(self.classdef):
            return

        if self.db.class_name(self.classdef) is not None:
            return # already rendered

        self.ilasm = ilasm
        if self.namespace:
            ilasm.begin_namespace(self.namespace)

        ilasm.begin_class(self.name, self.get_base_class())
        for f_name, (f_type, f_default) in self.classdef._fields.iteritems():
            cts_type = self.cts.lltype_to_cts(f_type)
            if cts_type != 'void':
                ilasm.field(f_name, cts_type)

        # TODO: should the .ctor set the default values?
        self._ctor()

        # lazy import to avoid circular dependencies
        import pypy.translator.cli.function as function
        for m_name, m_meth in self.classdef._methods.iteritems():
            f = function.Function(self.db, m_meth.graph, m_name, is_method = True)
            f.render(ilasm)

        ilasm.end_class()

        if self.namespace:
            ilasm.end_namespace()

        self.db.record_class(self.classdef, self.name)


    def _ctor(self):
        self.ilasm.begin_function('.ctor', [], 'void', False, 'specialname', 'rtspecialname', 'instance')
        self.ilasm.opcode('ldarg.0')
        self.ilasm.call('instance void %s::.ctor()' % self.get_base_class())
        self.ilasm.opcode('ret')
        self.ilasm.end_function()
