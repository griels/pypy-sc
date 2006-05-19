import sys
from types import MethodType

from pypy.translator.cli import conftest
from pypy.translator.cli.ilgenerator import IlasmGenerator
from pypy.translator.cli.function import Function
from pypy.translator.cli.class_ import Class
from pypy.translator.cli.option import getoption
from pypy.translator.cli.database import LowLevelDatabase
from pypy.translator.cli.cts import CTS
from pypy.translator.cli.opcodes import opcodes
from pypy.translator.squeak.node import LoopFinder

class Tee(object):
    def __init__(self, *args):
        self.outfiles = args

    def write(self, s):
        for outfile in self.outfiles:
            outfile.write(s)

    def close(self):
        for outfile in self.outfiles:
            if outfile is not sys.stdout:
                outfile.close()

class GenCli(object):
    def __init__(self, tmpdir, translator, entrypoint = None , type_system_class = CTS , opcode_dict = opcodes ):
        self.tmpdir = tmpdir
        self.translator = translator
        self.entrypoint = entrypoint
        self.db = LowLevelDatabase( type_system_class = type_system_class , opcode_dict = opcode_dict )

        if entrypoint is None:
            self.assembly_name = self.translator.graphs[0].name
        else:
            self.assembly_name = entrypoint.get_name()

        self.tmpfile = tmpdir.join(self.assembly_name + '.il')

    def generate_source(self , asm_class = IlasmGenerator ):
        out = self.tmpfile.open('w')
        if getoption('stdout'):
            out = Tee(sys.stdout, out)

        self.ilasm = asm_class(out, self.assembly_name )
        
        # TODO: instance methods that are also called as unbound
        # methods are rendered twice, once within the class and once
        # as an external function. Fix this.
        self.fix_names()
        self.gen_entrypoint()
        self.gen_pendings()
        self.db.gen_constants(self.ilasm)
        self.gen_pendings()
        out.close()
        return self.tmpfile.strpath

    def gen_entrypoint(self):
        if self.entrypoint:
            self.entrypoint.db = self.db
            self.db.pending_node(self.entrypoint)
        else:
            self.db.pending_function(self.translator.graphs[0])

    def gen_pendings(self):
        while self.db._pending_nodes:
            node = self.db._pending_nodes.pop()
            node.render(self.ilasm)

    def fix_names(self):
        # it could happen that two distinct graph have the same name;
        # here we assign an unique name to each graph.
        names = set()
        for graph in self.translator.graphs:
            while graph.name in names:
                graph.name += '_'
            names.add(graph.name)
