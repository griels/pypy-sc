try:
    set
except NameError:
    from sets import Set as set

import sys
from types import MethodType

from pypy.translator.cli import conftest
from pypy.translator.cli.ilgenerator import IlasmGenerator
from pypy.translator.cli.function import Function
from pypy.translator.cli.class_ import Class
from pypy.translator.cli.option import getoption


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
    def __init__(self, tmpdir, translator, entrypoint = None):
        self.tmpdir = tmpdir
        self.translator = translator
        self.entrypoint = entrypoint
        self.classdefs = set()

        if entrypoint is None:
            self.assembly_name = self.translator.graphs[0].name
        else:
            self.assembly_name = entrypoint.get_name()

        self.tmpfile = tmpdir.join(self.assembly_name + '.il')

    def generate_source(self):
        out = self.tmpfile.open('w')
        if getoption('stdout'):
            out = Tee(sys.stdout, out)

        self.ilasm = IlasmGenerator(out, self.assembly_name)
        self.gen_all_functions()
        self.gen_classes()
        out.close()
        return self.tmpfile.strpath

    def gen_all_functions(self):
        if self.entrypoint:
            self.entrypoint.render(self.ilasm)

        # generate code for all 'global' functions, i.e., those who are not methods.            
        for graph in self.translator.graphs:

            # TODO: remove this test
            if graph.name.startswith('ll_'):
                continue
            
            if '.' not in graph.name: # it's not a method
                f = Function(graph)
                f.render(self.ilasm)
                self.classdefs.update(f.classdefs)

    def gen_classes(self):
        for classdef in self.classdefs:
            c = Class(classdef)
            c.render(self.ilasm)
