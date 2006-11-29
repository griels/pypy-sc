import py

import os, sys

# as of revision 27081, multimethod.py uses the InstallerVersion1 by default
# because it is much faster both to initialize and run on top of CPython.
# The InstallerVersion2 is optimized for making a translator-friendly
# structure.  So we patch here...
from pypy.objspace.std import multimethod
multimethod.Installer = multimethod.InstallerVersion2

from pypy.objspace.std.objspace import StdObjSpace
from pypy.interpreter import gateway
from pypy.interpreter.error import OperationError
from pypy.translator.goal.ann_override import PyPyAnnotatorPolicy
from pypy.config.pypyoption import pypy_optiondescription
from pypy.config.config import Config, to_optparse, make_dict
from pypy.tool.option import make_objspace

thisdir = py.magic.autopath().dirpath()
app_basic_example_path = str(thisdir.join("app_basic_example.py"))

try:
    this_dir = os.path.dirname(__file__)
except NameError:
    this_dir = os.path.dirname(sys.argv[0])

def debug(msg): 
    os.write(2, "debug: " + msg + '\n')

# __________  Entry point  __________

def create_entry_point(space, w_dict):
    w_entry_point = space.getitem(w_dict, space.wrap('entry_point'))
    w_run_toplevel = space.getitem(w_dict, space.wrap('run_toplevel'))
    w_call_finish_gateway = space.wrap(gateway.interp2app(call_finish))
    w_call_startup_gateway = space.wrap(gateway.interp2app(call_startup))

    def entry_point(argv):
        debug("entry point starting") 
        for arg in argv: 
            debug(" argv -> " + arg)
        try:
            try:
                space.call_function(w_run_toplevel, w_call_startup_gateway)
                w_executable = space.wrap(argv[0])
                w_argv = space.newlist([space.wrap(s) for s in argv[1:]])
                w_exitcode = space.call_function(w_entry_point, w_executable, w_argv)
                exitcode = space.int_w(w_exitcode)
                # try to pull it all in
            ##    from pypy.interpreter import main, interactive, error
            ##    con = interactive.PyPyConsole(space)
            ##    con.interact()
            except OperationError, e:
                debug("OperationError:")
                debug(" operror-type: " + e.w_type.getname(space, '?'))
                debug(" operror-value: " + space.str_w(space.str(e.w_value)))
                return 1
        finally:
            try:
                space.call_function(w_run_toplevel, w_call_finish_gateway)
            except OperationError, e:
                debug("OperationError:")
                debug(" operror-type: " + e.w_type.getname(space, '?'))
                debug(" operror-value: " + space.str_w(space.str(e.w_value)))
                return 1
        return exitcode
    return entry_point

def call_finish(space):
    space.finish()

def call_startup(space):
    space.startup()

# _____ Define and setup target ___

# for now this will do for option handling

class PyPyTarget(object):

    usage = "target PyPy standalone"

    take_options = True

    def opt_parser(self, config):
        parser = to_optparse(config, useoptions=["objspace.*"],
                             parserkwargs={'usage': self.usage})
        return parser

    def handle_config(self, config):
        pass

    def handle_translate_config(self, translateconfig):
        pass

    def print_help(self, config):
        self.opt_parser(config).print_help()

    def target(self, driver, args):
        driver.exe_name = 'pypy-%(backend)s'

        config = driver.config
        parser = self.opt_parser(config)

        parser.parse_args(args)

        # expose the following variables to ease debugging
        global space, entry_point

        # obscure hack to stuff the translation options into the translated PyPy
        import pypy.module.sys
        options = make_dict(config)
        wrapstr = 'space.wrap(%r)' % (options)
        pypy.module.sys.Module.interpleveldefs['pypy_translation_info'] = wrapstr

        if config.translation.thread:
            config.objspace.usemodules.thread = True
        elif config.objspace.usemodules.thread:
            config.translation.thread = True

        if config.translation.stackless:
            config.objspace.usemodules._stackless = True
        elif config.objspace.usemodules._stackless:
            config.translation.stackless = True

        config.objspace.nofaking = True
        config.objspace.compiler = "ast"
        config.translating = True

        import translate
        translate.log_config(config.objspace, "PyPy config object")
 
        return self.get_entry_point(config)

    def get_entry_point(self, config):
        space = make_objspace(config)

        # disable translation of the whole of classobjinterp.py
        StdObjSpace.setup_old_style_classes = lambda self: None


        # manually imports app_main.py
        filename = os.path.join(this_dir, 'app_main.py')
        w_dict = space.newdict()
        space.exec_(open(filename).read(), w_dict, w_dict)
        entry_point = create_entry_point(space, w_dict)

        # sanity-check: call the entry point
        res = entry_point(["pypy", app_basic_example_path])
        assert res == 0

        return entry_point, None, PyPyAnnotatorPolicy(single_space = space)

    def interface(self, ns):
        for name in ['take_options', 'handle_config', 'print_help', 'target',
                     'handle_translate_config']:
            ns[name] = getattr(self, name)


PyPyTarget().interface(globals())

