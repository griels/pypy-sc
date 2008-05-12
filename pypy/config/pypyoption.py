import autopath
import py, os
import sys
from pypy.config.config import OptionDescription, BoolOption, IntOption, ArbitraryOption
from pypy.config.config import ChoiceOption, StrOption, to_optparse, Config
from pypy.config.config import ConfigError

modulepath = py.magic.autopath().dirpath().dirpath().join("module")
all_modules = [p.basename for p in modulepath.listdir()
               if p.check(dir=True, dotfile=False)
               and p.join('__init__.py').check()]

essential_modules = dict.fromkeys(
    ["exceptions", "_file", "sys", "__builtin__", "posix"]
)

default_modules = essential_modules.copy()
default_modules.update(dict.fromkeys(
    ["_codecs", "gc", "_weakref", "marshal", "errno",
     "math", "_sre", "_pickle_support", "operator",
     "recparser", "symbol", "_random", "__pypy__"]))


working_modules = default_modules.copy()
working_modules.update(dict.fromkeys(
    ["_socket", "unicodedata", "mmap", "fcntl",
      "rctime" , "select",
     "crypt", "signal", "dyngram", "_rawffi", "termios", "zlib",
     "struct", "md5", "sha", "bz2", "_minimal_curses", "cStringIO"]
))

if sys.platform == "win32":
    # unix only modules
    del working_modules["crypt"]
    del working_modules["fcntl"]
    del working_modules["termios"]
    del working_modules["_minimal_curses"]
    # modules currently missing explicit windows support
    del working_modules["signal"]
    del working_modules["_rawffi"]
    # modules with broken windows support
    del working_modules["mmap"]    # MLS - Added 5/11/08 - broken
    del working_modules["_socket"] # MLS - Added 5/11/08 - broken
    del working_modules["select"] # MLS - Added 5/11/08 - broken
    # modules with unknown windows support
    # XXX what exactly is broken here? are the libs installed on the buildbots?
    del working_modules["zlib"] # MLS - Added 5/11/08 - broken
    del working_modules["bz2"]  # UNKNOWN State - needs validating



module_dependencies = {}
module_suggests = {    # the reason you want _rawffi is for ctypes, which
                       # itself needs the interp-level struct module
                       # because 'P' is missing from the app-level one
                       '_rawffi': [("objspace.usemodules.struct", True)],
                       }
if os.name == "posix":
    module_dependencies['rctime'] = [("objspace.usemodules.select", True),]

module_import_dependencies = {
    # no _rawffi if importing pypy.rlib.libffi raises ImportError
    "_rawffi": ["pypy.rlib.libffi"],
    }

def get_module_validator(modname):
    if modname in module_import_dependencies:
        modlist = module_import_dependencies[modname]
        def validator(config):
            try:
                for name in modlist:
                    __import__(name)
            except ImportError, e:
                err = "%s: %s" % (e.__class__.__name__, e)
                config.add_warning(
                    "The module %r is disabled\n" % (modname,) +
                    "because importing %s raised\n" % (name,) +
                    err)
                raise ConfigError("--withmod-%s: %s" % (modname, err))
        return validator
    else:
        return None


pypy_optiondescription = OptionDescription("objspace", "Object Space Options", [
    ChoiceOption("name", "Object Space name",
                 ["std", "flow", "thunk", "dump", "taint", "reflective"],
                 "std",
                 requires={"reflective":
                               [("objspace.disable_call_speedhacks", True)]
                          },
                 cmdline='--objspace -o'),

    ChoiceOption("parser", "which parser to use for app-level code",
                 ["pypy", "cpython"], "pypy",
                 cmdline='--parser'),

    ChoiceOption("compiler", "which compiler to use for app-level code",
                 ["cpython", "ast"], "ast",
                 cmdline='--compiler'),

    ChoiceOption("pyversion", "which grammar to use for app-level code",
                 ["2.3", "2.4", "2.5a"], "2.4",
                 cmdline='--pyversion'),

    OptionDescription("opcodes", "opcodes to enable in the interpreter", [
        BoolOption("CALL_LIKELY_BUILTIN", "emit a special bytecode for likely calls to builtin functions",
                   default=False,
                   requires=[("objspace.std.withmultidict", True),
                             ("translation.stackless", False)]),
        BoolOption("CALL_METHOD", "emit a special bytecode for expr.name()",
                   default=False),
        ]),

    BoolOption("nofaking", "disallow faking in the object space",
               default=False,
               requires=[
                   ("objspace.usemodules.posix", True),
                   ("objspace.usemodules.time", True),
                   ("objspace.usemodules.errno", True)],
               cmdline='--nofaking'),

    OptionDescription("usemodules", "Which Modules should be used", [
        BoolOption(modname, "use module %s" % (modname, ),
                   default=modname in default_modules,
                   cmdline="--withmod-%s" % (modname, ),
                   requires=module_dependencies.get(modname, []),
                   suggests=module_suggests.get(modname, []),
                   negation=modname not in essential_modules,
                   validator=get_module_validator(modname))
        for modname in all_modules]),

    BoolOption("allworkingmodules", "use as many working modules as possible",
               default=False,
               cmdline="--allworkingmodules",
               suggests=[("objspace.usemodules.%s" % (modname, ), True)
                             for modname in working_modules
                             if modname in all_modules],
               negation=False),

    BoolOption("geninterp", "specify whether geninterp should be used",
               cmdline=None,
               default=True),

    BoolOption("logbytecodes",
               "keep track of bytecode usage",
               default=False),

    BoolOption("usepycfiles", "Write and read pyc files when importing",
               default=True),
   
    BoolOption("honor__builtins__",
               "Honor the __builtins__ key of a module dictionary",
               default=False),

    BoolOption("disable_call_speedhacks",
               "make sure that all calls go through space.call_args",
               default=False),

    OptionDescription("std", "Standard Object Space Options", [
        BoolOption("withtproxy", "support transparent proxies",
                   default=True),

        BoolOption("withsmallint", "use tagged integers",
                   default=False,
                   requires=[("translation.gc", "boehm")]),

        BoolOption("withprebuiltint", "prebuild commonly used int objects",
                   default=False,
                   requires=[("objspace.std.withsmallint", False)]),

        IntOption("prebuiltintfrom", "lowest integer which is prebuilt",
                  default=-5, cmdline="--prebuiltintfrom"),

        IntOption("prebuiltintto", "highest integer which is prebuilt",
                  default=100, cmdline="--prebuiltintto"),

        BoolOption("withstrjoin", "use strings optimized for addition",
                   default=False),

        BoolOption("withstrslice", "use strings optimized for slicing",
                   default=False),

        BoolOption("withprebuiltchar",
                   "use prebuilt single-character string objects",
                   default=False),

        BoolOption("sharesmallstr",
                   "always reuse the prebuilt string objects "
                   "(the empty string and potentially single-char strings)",
                   default=False),

        BoolOption("withrope", "use ropes as the string implementation",
                   default=False,
                   requires=[("objspace.std.withstrslice", False),
                             ("objspace.std.withstrjoin", False)],
                   suggests=[("objspace.std.withprebuiltchar", True),
                             ("objspace.std.sharesmallstr", True)]),

        BoolOption("withropeunicode", "use ropes for the unicode implementation",
                   default=False,
                   requires=[("objspace.std.withrope", True)]),

        BoolOption("withmultidict",
                   "use dictionaries optimized for flexibility",
                   default=False),

        BoolOption("withsharingdict",
                   "use dictionaries that share the keys part",
                   default=False,
                   requires=[("objspace.std.withmultidict", True)]),

        BoolOption("withdictmeasurement",
                   "create huge files with masses of information "
                   "about dictionaries",
                   default=False,
                   requires=[("objspace.std.withmultidict", True)]),

        BoolOption("withbucketdict",
                   "use dictionaries with chained hash tables "
                   "(default is open addressing)",
                   default=False,
                   requires=[("objspace.std.withmultidict", True)]),

        BoolOption("withsmalldicts",
                   "handle small dictionaries differently",
                   default=False,
                   requires=[("objspace.std.withmultidict", True)]),

        BoolOption("withrangelist",
                   "enable special range list implementation that does not "
                   "actually create the full list until the resulting "
                   "list is mutated",
                   default=False),

        BoolOption("withtypeversion",
                   "version type objects when changing them",
                   cmdline=None,
                   default=False,
                   # weakrefs needed, because of get_subclasses()
                   requires=[("translation.rweakref", True)]),

        BoolOption("withshadowtracking",
                   "track whether an instance attribute shadows a type"
                   " attribute",
                   default=False,
                   requires=[("objspace.std.withmultidict", True),
                             ("objspace.std.withtypeversion", True),
                             ("translation.rweakref", True)]),
        BoolOption("withmethodcache",
                   "try to cache method lookups",
                   default=False,
                   requires=[("objspace.std.withtypeversion", True),
                             ("translation.rweakref", True)]),
        BoolOption("withmethodcachecounter",
                   "try to cache methods and provide a counter in __pypy__. "
                   "for testing purposes only.",
                   default=False,
                   requires=[("objspace.std.withmethodcache", True)]),
        IntOption("methodcachesizeexp",
                  " 2 ** methodcachesizeexp is the size of the of the method cache ",
                  default=11),
        BoolOption("withmultilist",
                   "use lists optimized for flexibility",
                   default=False,
                   requires=[("objspace.std.withrangelist", False),
                             ("objspace.name", "std"),
                             ("objspace.std.withtproxy", False)]),
        BoolOption("withfastslice",
                   "make list slicing lazy",
                   default=False,
                   requires=[("objspace.std.withmultilist", True)]),
        BoolOption("withchunklist",
                   "introducing a new nesting level to slow down list operations",
                   default=False,
                   requires=[("objspace.std.withmultilist", True)]),
        BoolOption("withsmartresizablelist",
                   "only overallocate O(sqrt(n)) elements for lists",
                   default=False,
                   requires=[("objspace.std.withmultilist", True)]),
        BoolOption("withblist",
                   "good asymptotic performance for very large lists",
                   default=False,
                   requires=[("objspace.std.withmultilist", True)]),
        BoolOption("optimized_int_add",
                   "special case the addition of two integers in BINARY_ADD",
                   default=False),
        BoolOption("optimized_comparison_op",
                   "special case the comparison of integers",
                   default=False),
        BoolOption("optimized_list_getitem",
                   "special case the 'list[integer]' expressions",
                   default=False),
        BoolOption("builtinshortcut",
                   "a shortcut for operations between built-in types",
                   default=False),
        BoolOption("getattributeshortcut",
                   "track types that override __getattribute__",
                   default=False),

        BoolOption("oldstyle",
                   "specify whether the default metaclass should be classobj",
                   default=False, cmdline="-k --oldstyle"),

        BoolOption("logspaceoptypes",
                   "a instrumentation option: before exit, print the types seen by "
                   "certain simpler bytecodes",
                   default=False),

        BoolOption("allopts",
                   "enable all thought-to-be-working optimizations",
                   default=False,
                   suggests=[("objspace.opcodes.CALL_LIKELY_BUILTIN", True),
                             ("objspace.opcodes.CALL_METHOD", True),
                             ("translation.withsmallfuncsets", 5),
                             ("translation.profopt",
                              "-c 'from richards import main;main(); from test import pystone; pystone.main()'"),
                             ("objspace.std.withmultidict", True),
#                             ("objspace.std.withstrjoin", True),
                             ("objspace.std.withshadowtracking", True),
#                             ("objspace.std.withstrslice", True),
#                             ("objspace.std.withsmallint", True),
                             ("objspace.std.withrangelist", True),
                             ("objspace.std.withmethodcache", True),
#                             ("objspace.std.withfastslice", True),
                             ("objspace.std.withprebuiltchar", True),
                             ("objspace.std.builtinshortcut", True),
                             ("objspace.std.optimized_list_getitem", True),
                             ("objspace.std.getattributeshortcut", True),
                             ("translation.list_comprehension_operations",True),
                             ],
                   cmdline="--allopts --faassen", negation=False),

##         BoolOption("llvmallopts",
##                    "enable all optimizations, and use llvm compiled via C",
##                    default=False,
##                    requires=[("objspace.std.allopts", True),
##                              ("translation.llvm_via_c", True),
##                              ("translation.backend", "llvm")],
##                    cmdline="--llvm-faassen", negation=False),
     ]),
    #BoolOption("lowmem", "Try to use less memory during translation",
    #           default=False, cmdline="--lowmem",
    #           requires=[("objspace.geninterp", False)]),


])

def get_pypy_config(overrides=None, translating=False):
    from pypy.config.translationoption import get_combined_translation_config
    return get_combined_translation_config(
            pypy_optiondescription, overrides=overrides,
            translating=translating)

if __name__ == '__main__':
    config = get_pypy_config()
    print config.getpaths()
    parser = to_optparse(config) #, useoptions=["translation.*"])
    option, args = parser.parse_args()
    print config
