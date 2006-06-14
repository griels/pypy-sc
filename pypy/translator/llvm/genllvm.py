import time

from pypy.tool import isolate

from pypy.translator.llvm import buildllvm
from pypy.translator.llvm.database import Database 
from pypy.translator.llvm.pyxwrapper import write_pyx_wrapper 
from pypy.rpython.rmodel import inputconst
from pypy.rpython.typesystem import getfunctionptr
from pypy.rpython.lltypesystem import lltype
from pypy.tool.udir import udir
from pypy.translator.llvm.codewriter import CodeWriter
from pypy.translator.llvm import extfuncnode
from pypy.translator.llvm.module.support import \
     extdeclarations, extfunctions, extfunctions_standalone, write_raise_exc
from pypy.translator.llvm.node import LLVMNode
from pypy.translator.llvm.externs2ll import setup_externs, generate_llfile
from pypy.translator.llvm.gc import GcPolicy
from pypy.translator.llvm.exception import ExceptionPolicy
from pypy.translator.llvm.log import log
from pypy import conftest
from pypy.translator.llvm.buildllvm import llvm_is_on_path

class GenLLVM(object):

    # see open_file() below
    function_count = {}

    def __init__(self, translator, gcpolicy, exceptionpolicy, standalone,
                 debug=False, logging=True):
    
        # reset counters
        LLVMNode.nodename_count = {}    

        # create and set internals
        self.db = Database(self, translator)
        self.db.gcpolicy = GcPolicy.new(self.db, gcpolicy)
        self.db.exceptionpolicy = ExceptionPolicy.new(self.db,
                                                      exceptionpolicy)

        self.standalone = standalone
        self.translator = translator

        # the debug flag is for creating comments of every operation
        # that may be executed
        self.debug = debug 

        # the logging flag is for logging information statistics in the build
        # process
        self.logging = logging

        self.source_generated = False

    def gen_llvm_source(self, func):
        self._checkpoint()

        codewriter = self.setup(func)

        # write top part of llvm file
        self.write_headers(codewriter)

        codewriter.startimpl()

        # write bottom part of llvm file
        self.write_implementations(codewriter)

        self.source_generated = True
        self._checkpoint('done')
        codewriter.close()
        return self.filename

    def setup(self, func):
        """ setup all nodes
            create c file for externs
            create ll file for c file
            create codewriter """
        
        # get entry point
        entry_point = self.get_entry_point(func)
        self._checkpoint('get_entry_point')
        
        # set up all nodes
        self.db.setup_all()
        self.entrynode = self.db.set_entrynode(entry_point)
        self._checkpoint('setup_all all nodes')

        # set up externs nodes
        self.extern_decls = setup_externs(self.db)
        self.translator.rtyper.specialize_more_blocks()
        self.db.setup_all()
        self._checkpoint('setup_all externs')

        for node in self.db.getnodes():
            node.post_setup_transform()
        
        self._print_node_stats()

        # create ll file from c code
        self.generate_ll_externs()
        self._checkpoint('setup_externs')

        # open file & create codewriter
        codewriter, self.filename = self.create_codewriter()
        self._checkpoint('open file and create codewriter')        
        return codewriter

    def _set_wordsize(self, s):
        s = s.replace('UWORD', self.db.get_machine_uword())
        s = s.replace( 'WORD', self.db.get_machine_word())
        return s

    def write_headers(self, codewriter):
        # write external function headers
        codewriter.header_comment('External Function Headers')
        codewriter.write_lines(self.llexterns_header)

        codewriter.header_comment("Type Declarations")

        # write extern type declarations
        self.write_extern_decls(codewriter)
        self._checkpoint('write externs type declarations')

        # write exception declarations
        ep = self.db.exceptionpolicy
        codewriter.write_lines(ep.llvm_declcode())

        # write node type declarations
        for typ_decl in self.db.getnodes():
            typ_decl.writedatatypedecl(codewriter)
        self._checkpoint('write data type declarations')

        codewriter.header_comment("Global Data")

        # write pbcs
        for typ_decl in self.db.getnodes():
            typ_decl.writeglobalconstants(codewriter)
        self._checkpoint('write global constants')

        codewriter.header_comment("Function Prototypes")

        # write external protos
        codewriter.write_lines(self._set_wordsize(extdeclarations))

        # write node protos
        for typ_decl in self.db.getnodes():
            typ_decl.writedecl(codewriter)

        self._checkpoint('write function prototypes')

    def write_implementations(self, codewriter):
        codewriter.header_comment("Function Implementation")

        # write external function implementations
        codewriter.header_comment('External Function Implementation')
        codewriter.write_lines(self.llexterns_functions)
        codewriter.write_lines(self._set_wordsize(extfunctions))
        if self.standalone:
            codewriter.write_lines(self._set_wordsize(extfunctions_standalone))
        self.write_extern_impls(codewriter)
        self.write_setup_impl(codewriter)
        
        self._checkpoint('write support implentations')

        # write exception implementaions
        ep = self.db.exceptionpolicy
        codewriter.write_lines(ep.llvm_implcode(self.entrynode))

        # write all node implementations
        for typ_decl in self.db.getnodes():
            typ_decl.writeimpl(codewriter)
        self._checkpoint('write node implementations')

        # write entry point if there is one
        codewriter.comment("End of file")
    
    def get_entry_point(self, func):
        assert func is not None
        self.entrypoint = func

        bk = self.translator.annotator.bookkeeper
        ptr = getfunctionptr(bk.getdesc(func).getuniquegraph())
        c = inputconst(lltype.typeOf(ptr), ptr)
        self.db.prepare_arg_value(c)
        self.entry_func_name = func.func_name
        return c.value._obj 

    def generate_ll_externs(self):
        self.llexterns_header, self.llexterns_functions = \
                               generate_llfile(self.db,
                                               self.extern_decls,
                                               self.entrynode,
                                               self.standalone)

    def create_codewriter(self):
        # prevent running the same function twice in a test
        if self.entry_func_name in self.function_count:
            postfix = '_%d' % self.function_count[self.entry_func_name]
            self.function_count[self.entry_func_name] += 1
        else:
            postfix = ''
            self.function_count[self.entry_func_name] = 1
        filename = udir.join(self.entry_func_name + postfix).new(ext='.ll')
        f = open(str(filename), 'w')
        return CodeWriter(f, self.db), filename

    def write_extern_decls(self, codewriter):        
        for c_name, obj in self.extern_decls:
            if isinstance(obj, lltype.LowLevelType):
                if isinstance(obj, lltype.Ptr):
                    obj = obj.TO

                l = "%%%s = type %s" % (c_name, self.db.repr_type(obj))
                codewriter.write_lines(l)
                
    def write_extern_impls(self, codewriter):
        for c_name, obj in self.extern_decls:
            if c_name.startswith("RPyExc_"):
                c_name = c_name[1:]
                exc_repr = self.db.repr_constant(obj)[1]
                write_raise_exc(c_name, exc_repr, codewriter)

    def write_setup_impl(self, codewriter):
        open_decl =  "sbyte* %LLVM_RPython_StartupCode()"
        codewriter.openfunc(open_decl)
        for node in self.db.getnodes():
            node.writesetupcode(codewriter)

        codewriter.ret("sbyte*", "null")
        codewriter.closefunc()

    def compile_llvm_source(self, optimize=True,
                            exe_name=None, return_fn=False):
        assert self.source_generated

        assert hasattr(self, "filename")
        if exe_name is not None:
            assert self.standalone
            assert not return_fn
            return buildllvm.make_module_from_llvm(self, self.filename,
                                                   optimize=optimize,
                                                   exe_name=exe_name)
        else:
            assert not self.standalone

            # use pyrex to create module for CPython
            postfix = ''
            basename = self.filename.purebasename + '_wrapper' + postfix + '.pyx'
            pyxfile = self.filename.new(basename = basename)
            write_pyx_wrapper(self, pyxfile)    
            info = buildllvm.make_module_from_llvm(self, self.filename,
                                                   pyxfile=pyxfile,
                                                   optimize=optimize)

            mod, wrap_fun = self.isolate_module(*info)
            if return_fn:
                return wrap_fun
            return mod, wrap_fun

    def isolate_module(self, modname, dirpath):
        ext_module = isolate.Isolate((dirpath, modname))
        wrap_fun = getattr(ext_module, 'pypy_' + self.entry_func_name + "_wrapper")
        return ext_module, wrap_fun
    
    def _checkpoint(self, msg=None):
        if not self.logging:
            return
        if msg:
            t = (time.time() - self.starttime)
            log('\t%s took %02dm%02ds' % (msg, t/60, t%60))
        else:
            log('GenLLVM:')
        self.starttime = time.time()

    def _print_node_stats(self):
        # disable node stats output
        if not self.logging: 
            return 

        nodecount = {}
        for node in self.db.getnodes():
            typ = type(node)
            try:
                nodecount[typ] += 1
            except:
                nodecount[typ] = 1
        stats = [(count, str(typ)) for typ, count in nodecount.iteritems()]
        stats.sort()
        for s in stats:
            log('STATS %s' % str(s))

def genllvm(translator, entry_point, gcpolicy=None,
            exceptionpolicy=None, standalone=False,
            log_source=False, logging=False, **kwds):

    gen = GenLLVM(translator, gcpolicy, exceptionpolicy,
                  standalone, logging=logging)
    filename = gen.gen_llvm_source(entry_point)

    if log_source:
        log(open(filename).read())

    return gen.compile_llvm_source(**kwds)

def genllvm_compile(function, annotation, view=False, optimize=True, **kwds):
    assert llvm_is_on_path()
    
    from pypy.translator.translator import TranslationContext
    from pypy.translator.backendopt.all import backend_optimizations
    t = TranslationContext()
    t.buildannotator().build_types(function, annotation)
    t.buildrtyper().specialize()
    if optimize:
        backend_optimizations(t, raisingop2direct_call_all=True)
    else:
        backend_optimizations(t,
                              raisingop2direct_call_all=True,
                              inline_threshold=0,
                              mallocs=False,
                              merge_if_blocks_to_switch=False,
                              propagate=False)

    # note: this is without policy transforms
    if view or conftest.option.view:
        t.view()
    return genllvm(t, function, optimize=optimize, **kwds)
