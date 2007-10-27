import os
import sys

import py

from pypy.translator.llvm.log import log
from pypy.translator.tool import stdoutcapture

def write_ctypes_module(genllvm, dllname):
    """ use ctypes to create a temporary module """

    template = """
import ctypes
from os.path import join, dirname, realpath
_c = ctypes.CDLL(join(dirname(realpath(__file__)), "%(dllname)s"))

_setup = False

class LLVMException(Exception):
    pass

%(name)s = _c.__entrypoint__%(name)s
%(name)s.argtypes = %(args)s
%(name)s.restype = %(returntype)s

%(name)s_raised = _c.__entrypoint__raised_LLVMException
%(name)s_raised.argtypes = []
%(name)s_raised.restype = ctypes.c_int

GC_get_heap_size_wrapper = _c.GC_get_heap_size
GC_get_heap_size_wrapper.argtypes = []
GC_get_heap_size_wrapper.restype = ctypes.c_int

startup_code = _c.ctypes_RPython_StartupCode
startup_code.argtypes = []
startup_code.restype = ctypes.c_int

def %(name)s_wrapper(*args):
    global _setup
    if not _setup:
        if not startup_code():
            raise LLVMException("Failed to startup")
        _setup = True
    result = %(name)s(*args)
    if %(name)s_raised():
        raise LLVMException("Exception raised")
    return result
"""

    import ctypes
    from pypy.rpython.lltypesystem import lltype 

    basename = genllvm.filename.purebasename + '_wrapper.py'
    modfilename = genllvm.filename.new(basename = basename)

    TO_CTYPES = {lltype.Bool: "ctypes.c_int",
                 lltype.Float: "ctypes.c_double",
                 lltype.Char: "ctypes.c_char",
                 lltype.Signed: "ctypes.c_int",
                 lltype.Unsigned: "ctypes.c_uint"
                 }

    name = genllvm.entrynode.ref.strip("%")
    
    g = genllvm.entrynode.graph  
    returntype = TO_CTYPES[g.returnblock.inputargs[0].concretetype]
    inputargtypes = [TO_CTYPES[a.concretetype] for a in g.startblock.inputargs]
    args = '[%s]' % ", ".join(inputargtypes)
    modfilename.write(template % locals())
    return modfilename.purebasename

def llvm_is_on_path():
    if py.path.local.sysfind("llvm-as") is None or \
       py.path.local.sysfind("llvm-gcc") is None:
        return False 
    return True

def exe_version(exe, cache={}):
    try:
        v =  cache[exe]
    except KeyError:
        v = os.popen(exe + ' -version 2>&1').read()
        v = ''.join([c for c in v if c.isdigit()])
        v = int(v) / 10.0
        cache[exe] = v
    return v

def exe_version2(exe):
    v = os.popen(exe + ' --version 2>&1').read()
    i = v.index(')')
    v = v[i+2:].split()[0].split('.')
    major, minor = v[0], ''.join([c for c in v[1] if c.isdigit()])
    v = float(major) + float(minor) / 10.0
    return v

llvm_version = lambda: exe_version('llvm-as')
gcc_version = lambda: exe_version2('gcc')
llvm_gcc_version = lambda: exe_version2('llvm-gcc')

def have_boehm():
    import distutils.sysconfig
    from os.path import exists
    libdir = distutils.sysconfig.EXEC_PREFIX + "/lib"  
    return exists(libdir + '/libgc.so') or exists(libdir + '/libgc.a')

def postfix():
    if llvm_version() >= 2.0:
        return '.i32'
    else:
        return ''

class Builder(object):
    def __init__(self, genllvm):
        self.genllvm = genllvm
        self.cmds = []

    def optimizations(self):
        if llvm_version() < 2.0:
            cmd = "gccas /dev/null -o /dev/null -debug-pass=Arguments 2>&1"
            gccas_output = os.popen(cmd)
            opts = gccas_output.read()[17:-1] + " "
            
            # these were added by Chris Lattner for some old version of llvm
            #    opts += "-globalopt -constmerge -ipsccp -deadargelim -inline " \
            #            "-instcombine -scalarrepl -globalsmodref-aa -licm -load-vn " \
            #            "-gcse -instcombine -simplifycfg -globaldce "

            # added try to reduce the amount of excessive inlining by us, llvm and gcc
            #    opts += "-inline-threshold=175 "   #default: 200

        else:
            opts = '-std-compile-opts'
        return opts

    def execute_cmds(self):
        c = stdoutcapture.Capture(mixed_out_err=True)
        log.build("working in", py.path.local())
        try:
            try:
                for cmd in self.cmds:
                    log.build(cmd)
                    py.process.cmdexec(cmd)
            finally:
                foutput, ferror = c.done()
        except:
            data = 'OUTPUT:\n' + foutput.read() + '\n\nERROR:\n' + ferror.read()
            fdump = open("%s.errors" % self.genllvm.filename, "w")
            fdump.write(data)
            fdump.close()
            log.build(data)
            raise

    def cmds_bytecode(self, base):
        # run llvm assembler and optimizer
        opts = self.optimizations()

        if llvm_version() < 2.0:
            self.cmds.append("llvm-as < %s.ll | opt %s -f -o %s.bc" % (base, opts, base))
        else:
            # we generate 1.x .ll files, so upgrade these first
            self.cmds.append("llvm-upgrade < %s.ll | llvm-as | opt %s -f -o %s.bc" % (base, opts, base))

    def cmds_objects(self, base):
        # XXX why this hack???
        use_gcc = True #self.genllvm.config.translation.llvm_via_c
        if use_gcc:
            self.cmds.append("llc %s.bc -march=c -f -o %s.c" % (base, base))
            self.cmds.append("gcc %s.c -c -O3 -fomit-frame-pointer" % base)
        else:
            self.cmds.append("llc -relocation-model=pic %s.bc -f -o %s.s" % (base, base))
            self.cmds.append("as %s.s -o %s.o" % (base, base))

#             if (self.genllvm.config.translation.profopt is not None and
#                 not self.genllvm.config.translation.noprofopt):
#                 cmd = "gcc -fprofile-generate %s.c -c -O3 -pipe -o %s.o" % (base, base)
#                 self.cmds.append(cmd)
#                 cmd = "gcc -fprofile-generate %s.o %s %s -lm -pipe -o %s_gen" % \
#                       (base, gc_libs_path, gc_libs, exename)
#                 self.cmds.append(cmd)
#                 self.cmds.append("./%s_gen %s" % (exename, self.genllvm.config.translation.profopt))
#                 cmd = "gcc -fprofile-use %s.c -c -O3 -pipe -o %s.o" % (b, b)
#                 self.cmds.append(cmd)
#                 cmd = "gcc -fprofile-use %s.o %s %s -lm -pipe -o %s" % \
#                       (b, gc_libs_path, gc_libs, exename)
#             else:

    def setup(self):
        # set up directories
        llvmfile = self.genllvm.filename

        # change into dirpath and store current path to change back
        self.dirpath = llvmfile.dirpath()
        self.lastdir = py.path.local()
        self.dirpath.chdir()

        return llvmfile.purebasename
        
    def make_module(self):
        base = self.setup()
        self.cmds_bytecode(base)
        self.cmds_objects(base)

        # link (ok this is a mess!)
        library_files = self.genllvm.db.gcpolicy.gc_libraries()
        gc_libs = ' '.join(['-l' + lib for lib in library_files])

        if sys.platform == 'darwin':
            libdir = '/sw/lib'
            gc_libs_path = '-L%s -ldl' % libdir
            self.cmds.append("gcc -O3 %s.o %s %s -lm -bundle -o %s.so" % (base, gc_libs_path, gc_libs, base))
        else:

            gc_libs_path = '-static'
            XXX

        try:
            self.execute_cmds()
            modname = write_ctypes_module(self.genllvm, "%s.so" % base)

        finally:
            self.lastdir.chdir()

        return modname, str(self.dirpath)

    def make_standalone(self, exename):
        base = self.setup()
        self.cmds_bytecode(base)
        self.cmds_objects(base)

        object_files = ["-L/sw/lib"]
        library_files = self.genllvm.db.gcpolicy.gc_libraries()
        gc_libs = ' '.join(['-l' + lib for lib in library_files])

        if sys.platform == 'darwin':
            libdir = '/sw/' + "/lib"
            gc_libs_path = '-L%s -ldl' % libdir
        else:
            gc_libs_path = '-static'

        self.cmds.append("gcc -O3 %s.o %s %s -lm -pipe -o %s" % (base, gc_libs_path, gc_libs, exename))

        try:
            self.execute_cmds()
        finally:
            self.lastdir.chdir()

        return str(self.dirpath.join(exename))
