"""
Implementation of the interpreter-level default import logic.
"""

import sys, os

from pypy.interpreter.module import Module
from pypy.interpreter.error import OperationError
from pypy.interpreter.baseobjspace import W_Root, ObjSpace
from pypy.tool.osfilewrapper import OsFileWrapper

# XXX this uses the os.path module at interp-level, which means
# XXX that translate_pypy will produce a translated version of
# XXX PyPy that will only run on the same platform, as it contains
# XXX a frozen version of some routines of only one of the
# XXX posixpath/ntpath/macpath modules.

try:
    BIN_READMASK = os.O_BINARY | os.O_RDONLY
    BIN_WRITEMASK = os.O_BINARY | os.O_RDWR
except AttributeError:
    BIN_READMASK = os.O_RDONLY
    BIN_WRITEMASK = os.O_RDWR

NOFILE = 0
PYFILE = 1
PYCFILE = 2

import stat

def info_modtype(filepart):
    """
    calculate whether the .py file exists, the .pyc file exists
    and whether the .pyc file has the correct mtime entry.
    The latter is only true if the .py file exists.
    The .pyc file is only considered existing if it has a valid
    magic number.
    """
    pyfile = filepart + ".py"
    pyfile_exist = False
    if os.path.exists(pyfile):
        pyfile_ts = os.stat(pyfile)[stat.ST_MTIME]
        pyfile_exist = True
    else:
        pyfile_ts = 0
        pyfile_exist = False
    
    pycfile = filepart + ".pyc"    
    if os.path.exists(pycfile):
        pyc_state = check_compiled_module(pyfile, pyfile_ts, pycfile)
        pycfile_exists = pyc_state >= 0
        pycfile_ts_valid = pyc_state > 0 and pyfile_exists
    else:
        pycfile_exists = False
        pycfile_ts_valid = False
        
    return pyfile_exist, pycfile_exists, pycfile_ts_valid

def find_modtype(filepart):
    """ This is the way pypy does it.  A pyc is only used if the py file exists AND
    the pyc file contains the timestamp of the py. """
    pyfile_exist, pycfile_exists, pycfile_ts_valid = info_modtype(filepart)
    if pycfile_ts_valid:
        return PYCFILE
    elif pyfile_exist:
        return PYFILE
    else:
        return NOFILE
    
def find_modtype_cpython(filepart):
    """ This is the way cpython does it (where the py file doesnt exist but there
    is a valid pyc file. """  
    pyfile_exist, pycfile_exists, pycfile_ts_valid = info_modtype(filepart)
    if pycfile_ts_valid:
        return PYCFILE
    elif pyfile_exist:
        return PYFILE
    elif pycfile_exists:
        return PYCFILE
    else:
        return NOFILE

def try_import_mod(space, w_modulename, filepart, w_parent, w_name, pkgdir=None):

    # decide what type we want (pyc/py)
    modtype = find_modtype(filepart)

    if modtype == NOFILE:
        return None

    w = space.wrap
    w_mod = w(Module(space, w_modulename))

    e = None
    if modtype == PYFILE:
        filename = filepart + ".py"
        fd = os.open(filename, os.O_RDONLY, 0777)
    else:
        assert modtype == PYCFILE
        filename = filepart + ".pyc"
        fd = os.open(filename, os.O_RDONLY, 0777)

    space.sys.setmodule(w_mod)
    space.setattr(w_mod, w('__file__'), space.wrap(filename))
    space.setattr(w_mod, w('__doc__'), space.w_None)
    if pkgdir is not None:
        space.setattr(w_mod, w('__path__'), space.newlist([w(pkgdir)]))

    try:
        if modtype == PYFILE:
            load_source_module(space, w_modulename, w_mod, filename, fd)
        else:
            load_compiled_module(space, w_modulename, w_mod, filename, fd)

    except OperationError, e:
        if e.match(space, space.w_SyntaxError):
            w_mods = space.sys.get('modules')
            try:
                space.delitem(w_mods, w_modulename)
            except OperationError, kerr:
                if not kerr.match(space, space.w_KeyError):
                    raise
             
    w_mod = check_sys_modules(space, w_modulename)
    if w_mod is not None and w_parent is not None:
        space.setattr(w_parent, w_name, w_mod)
    if e:
        raise e        
    return w_mod

def try_getattr(space, w_obj, w_name):
    try:
        return space.getattr(w_obj, w_name)
    except OperationError, e:
        # ugh, but blame CPython :-/ this is supposed to emulate
        # hasattr, which eats all exceptions.
        return None

def try_getitem(space, w_obj, w_key):
    try:
        return space.getitem(w_obj, w_key)
    except OperationError, e:
        if not e.match(space, space.w_KeyError):
            raise
        return None


def check_sys_modules(space, w_modulename):
    w_modules = space.sys.get('modules')
    try:
        w_mod = space.getitem(w_modules, w_modulename) 
    except OperationError, e:
        pass
    else:
        return w_mod
    if not e.match(space, space.w_KeyError):
        raise
    return None

def importhook(space, modulename, w_globals=None,
               w_locals=None, w_fromlist=None):
    if not isinstance(modulename, str):
        try:
            helper = ', not ' + modulename.__class__.__name__
        except AttributeError:
            helper = ''
        raise OperationError(space.w_TypeError,
              space.wrap("__import__() argument 1 must be string" + helper))
    w = space.wrap

    if w_globals is not None and not space.is_true(space.is_(w_globals, space.w_None)):
        ctxt_w_name = try_getitem(space, w_globals, w('__name__'))
        ctxt_w_path = try_getitem(space, w_globals, w('__path__'))
    else:
        ctxt_w_name = None
        ctxt_w_path = None

    rel_modulename = None
    if ctxt_w_name is not None:

        ctxt_name_prefix_parts = space.str_w(ctxt_w_name).split('.')
        if ctxt_w_path is None: # context is a plain module
            ctxt_name_prefix_parts = ctxt_name_prefix_parts[:-1]
            if ctxt_name_prefix_parts:
                rel_modulename = '.'.join(ctxt_name_prefix_parts+[modulename])
        else: # context is a package module
            rel_modulename = space.str_w(ctxt_w_name)+'.'+modulename
        if rel_modulename is not None:
            w_mod = check_sys_modules(space, w(rel_modulename))
            if (w_mod is None or
                not space.is_true(space.is_(w_mod,space.w_None))):
                
                w_mod = absolute_import(space, rel_modulename,
                                        len(ctxt_name_prefix_parts),
                                        w_fromlist, tentative=1)
                if w_mod is not None:
                    return w_mod
            else:
                rel_modulename = None

    w_mod = absolute_import(space, modulename, 0, w_fromlist, tentative=0)
    if rel_modulename is not None:
        space.setitem(space.sys.get('modules'), w(rel_modulename),space.w_None)
    return w_mod
#
importhook.unwrap_spec = [ObjSpace,str,W_Root,W_Root,W_Root]

def absolute_import(space, modulename, baselevel, w_fromlist, tentative):
    w = space.wrap
    
    w_mod = None
    parts = modulename.split('.')
    prefix = []
    # it would be nice if we could do here: w_path = space.sys.w_path
    # instead:
    w_path = space.sys.get('path') 

    first = None
    level = 0

    for part in parts:
        w_mod = load_part(space, w_path, prefix, part, w_mod,
                          tentative=tentative)
        if w_mod is None:
            return None

        if baselevel == level:
            first = w_mod
            tentative = 0
        prefix.append(part)
        w_path = try_getattr(space, w_mod, w('__path__'))
        level += 1

    if w_fromlist is not None and space.is_true(w_fromlist):
        if w_path is not None:
            fromlist_w = space.unpackiterable(w_fromlist)
            if len(fromlist_w) == 1 and space.eq_w(fromlist_w[0],w('*')):
                w_all = try_getattr(space, w_mod, w('__all__'))
                if w_all is not None:
                    fromlist_w = space.unpackiterable(w_all)
            for w_name in fromlist_w:
                if try_getattr(space, w_mod, w_name) is None:
                    load_part(space, w_path, prefix, space.str_w(w_name), w_mod,
                              tentative=1)
        return w_mod
    else:
        return first

def load_part(space, w_path, prefix, partname, w_parent, tentative):
    w = space.wrap
    modulename = '.'.join(prefix + [partname])
    w_modulename = w(modulename)
    w_mod = check_sys_modules(space, w_modulename)
    if w_mod is not None:
        if not space.is_true(space.is_(w_mod, space.w_None)):
            return w_mod
    else:
        w_mod = space.sys.getmodule(modulename) 
        if w_mod is not None:
            return w_mod
        
        if w_path is not None:
            for path in space.unpackiterable(w_path):
                dir = os.path.join(space.str_w(path), partname)
                if os.path.isdir(dir):
                    fn = os.path.join(dir, '__init__')
                    w_mod = try_import_mod(space, w_modulename, fn, w_parent,
                                           w(partname), pkgdir=dir)
                    if w_mod is not None:
                        return w_mod
                fn = os.path.join(space.str_w(path), partname)
                w_mod = try_import_mod(space, w_modulename, fn, w_parent,
                                       w(partname))
                if w_mod is not None:
                    return w_mod

    if tentative:
        return None
    else:
        # ImportError
        w_failing = w_modulename
        w_exc = space.call_function(space.w_ImportError, w_failing)
        raise OperationError(space.w_ImportError, w_exc)

# __________________________________________________________________
#
# .pyc file support

"""
   Magic word to reject .pyc files generated by other Python versions.
   It should change for each incompatible change to the bytecode.

   The value of CR and LF is incorporated so if you ever read or write
   a .pyc file in text mode the magic number will be wrong; also, the
   Apple MPW compiler swaps their values, botching string constants.

   The magic numbers must be spaced apart atleast 2 values, as the
   -U interpeter flag will cause MAGIC+1 being used. They have been
   odd numbers for some time now.

   There were a variety of old schemes for setting the magic number.
   The current working scheme is to increment the previous value by
   10.

   Known values:
       Python 1.5:   20121
       Python 1.5.1: 20121
       Python 1.5.2: 20121
       Python 2.0:   50823
       Python 2.0.1: 50823
       Python 2.1:   60202
       Python 2.1.1: 60202
       Python 2.1.2: 60202
       Python 2.2:   60717
       Python 2.3a0: 62011
       Python 2.3a0: 62021
       Python 2.3a0: 62011 (!)
       Python 2.4a0: 62041
       Python 2.4a3: 62051
       Python 2.4b1: 62061
"""

# XXX how do we configure this ???
MAGIC = 62061 | (ord('\r')<<16) | (ord('\n')<<24)

"""Magic word as global; note that _PyImport_Init() can change the
   value of this global to accommodate for alterations of how the
   compiler works which are enabled by command line switches.
"""

pyc_magic = MAGIC


def parse_source_module(space, pathname, fd):
    """ Parse a source file and return the corresponding code object """
    w = space.wrap
    try:
        size = os.fstat(fd)[stat.ST_SIZE]
        source = os.read(fd, size)
    finally:
        os.close(fd)
        
    w_source = w(source)
    w_mode = w("exec")
    w_pathname = w(pathname)
    w_code = space.builtin.call('compile', w_source, w_pathname, w_mode) 
    pycode = space.interpclass_w(w_code)
    return pycode

def load_source_module(space, w_modulename, w_mod, pathname, fd):
    """
    Load a source module from a given file and return its module
    object.
    """
    w = space.wrap
    pycode = parse_source_module(space, pathname, fd)

    w_dict = space.getattr(w_mod, w('__dict__'))                                      
    space.call_method(w_dict, 'setdefault', 
                      w('__builtins__'), 
                      w(space.builtin))
    pycode.exec_code(space, w_dict, w_dict) 

    mtime = os.stat(fd)[stat.ST_MTIME]
    cpathname = pathname + 'c'
    write_compiled_module(space, pycode, cpathname, mtime)

    return w_mod

# helper, to avoid exposing internals of marshal
def _r_long(osfile):
    a = ord(osfile.read(1))
    b = ord(osfile.read(1))
    c = ord(osfile.read(1))
    d = ord(osfile.read(1))
    x = a | (b<<8) | (c<<16) | (d<<24)
    if d & 0x80 and x > 0:
        x = -((1L<<32) - x)
    return int(x)

def _w_long(osfile, x):
    a = x & 0xff
    x >> = 8
    b = x & 0xff
    x >> = 8
    c = x & 0xff
    x >> = 8
    d = x & 0xff
    osfile.write(chr(a) + chr(b) + chr(c) + chr(d))

def check_compiled_module(pathname, mtime, cpathname):
    """
    Given a pathname for a Python source file, its time of last
    modification, and a pathname for a compiled file, check whether the
    compiled file represents the same version of the source.  If so,
    return a FILE pointer for the compiled file, positioned just after
    the header; if not, return NULL.
    Doesn't set an exception.
    """
    fd = os.open(cpathname, BIN_READMASK, 0777) # using no defaults
    osfile = OsFileWrapper(fd)
    magic = _r_long(osfile)
    try:
        if magic != pyc_magic:
            # XXX what to do about Py_VerboseFlag ?
            # PySys_WriteStderr("# %s has bad magic\n", cpathname);
            return -1
        pyc_mtime = _r_long(osfile)
        if pyc_mtime != mtime:
            # PySys_WriteStderr("# %s has bad mtime\n", cpathname);
            return 0
        # if (Py_VerboseFlag)
           # PySys_WriteStderr("# %s matches %s\n", cpathname, pathname);
    finally:
        os.close(fd)
    return 1

def read_compiled_module(space, cpathname, fd):
    """ Read a code object from a file and check it for validity """

    w_marshal = space.getbuiltinmodule('marshal')
    w_U = space.getattr(w_marshal, space.wrap('_Unmarshaller'))
    w_unmarshaller = space.call_function(w_U, space.wrap(fd))
    w_code = space.call_method(w_unmarshaller, 'load')
    pycode = space.interpclass_w(w_code)
    if pycode is None:
        raise OperationError(space.w_ImportError, space.wrap(
            "Non-code object in %.200s" % cpathname))
    return pycode

def load_compiled_module(space, w_modulename, w_mod, cpathname, fd):
    """
    Load a module from a compiled file, execute it, and return its
    module object.
    """
    osfile = OsFileWrapper(fd)
    magic = _r_long(osfile)
    if magic != pyc_magic:
        raise OperationError(space.w_ImportError, space.wrap(
            "Bad magic number in %.200s" % cpathname))
        return NULL;
    _r_long(osfile) # skip time stamp
    code_w = read_compiled_module(space, cpathname, fd)
    #if (Py_VerboseFlag)
    #    PySys_WriteStderr("import %s # precompiled from %s\n",
    #        name, cpathname);
    w_dic = space.getattr(w_mod, space.wrap('__dict__'))
    code_w.exec_code(space, w_dic, w_dic)
    return w_mod


def write_compiled_module(space, co, cpathname, mtime):
    """
    Write a compiled module to a file, placing the time of last
    modification of its source into the header.
    Errors are ignored, if a write error occurs an attempt is made to
    remove the file.
    """
    fd = os.open(cpathname, BIN_WRITEMASK, 0777)
    osfile = OsFileWrapper(fd)
    _w_long(osfile, pyc_magic)
    _w_long(osfile, mtime)
    w_marshal = space.getbuiltinmodule('marshal')
    w_M = space.getattr(w_marshal, space.wrap('_Marshaller'))
    w_marshaller = space.call_function(w_U, space.wrap(fd))
    space.call_method(w_unmarshaller, 'dump', space.wrap(co))
    os.close(fd)
