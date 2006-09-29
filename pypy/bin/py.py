#!/usr/bin/env python

"""Main entry point into the PyPy interpreter.  For a list of options, type

      py.py --help

"""

try:
    import autopath
except ImportError:
    pass

from pypy.tool import option
from py.compat.optparse import make_option
from pypy.interpreter import main, interactive, error
import os, sys
import time

class Options(option.Options):
    verbose = os.getenv('PYPY_TB')
    interactive = 0
    command = []
    completer = False
    module = None
    module_args = []

def get_main_options():
    config, parser = option.get_standard_options()

    options = []
    options.append(make_option(
        '-v', action='store_true', dest='verbose',
        help='show verbose interpreter-level traceback'))

    options.append(make_option(
        '-C', action='store_true', dest='completer',
        help='use readline commandline completer'))

    options.append(make_option(
        '-i', action="store_true", dest="interactive",
        help="inspect interactively after running script"))

    options.append(make_option(
        '-O', action="store_true", dest="optimize",
        help="dummy optimization flag for compatibility with C Python"))

    def command_callback(option, opt, value, parser):
        parser.values.command = parser.rargs[:]
        parser.rargs[:] = []
        
    options.append(make_option(
        '-c', action="callback",
        callback=command_callback,
        help="program passed in as CMD (terminates option list)"))

    def runmodule_callback(option, opt, value, parser):
        parser.values.module_args = parser.rargs[:]
        parser.values.module = value
        parser.rargs[:] = []

    options.append(make_option(
        '-m', action="callback", metavar='NAME',
        callback=runmodule_callback, type="string",
        help="library module to be run as a script (terminates option list)"))

    parser.add_options(options)
        
    return config, parser

def main_(argv=None):
    starttime = time.time()
    config, parser = get_main_options()
    args = option.process_options(parser, Options, argv[1:])
    if Options.verbose:
        error.RECORD_INTERPLEVEL_TRACEBACK = True

    # create the object space

    space = option.make_objspace(config)

    space._starttime = starttime
    #assert 'pypy.tool.udir' not in sys.modules, (
    #    "running py.py should not import pypy.tool.udir, which is\n"
    #    "only for testing or translating purposes.")
    # ^^^ _socket and other rctypes-based modules need udir
    space.setitem(space.sys.w_dict,space.wrap('executable'),space.wrap(argv[0]))

    # store the command-line arguments into sys.argv
    go_interactive = Options.interactive
    banner = ''
    exit_status = 0
    if Options.command:
        args = ['-c'] + Options.command[1:]
    for arg in args:
        space.call_method(space.sys.get('argv'), 'append', space.wrap(arg))

    # load the source of the program given as command-line argument
    if Options.command:
        def doit():
            main.run_string(Options.command[0], space=space)
    elif Options.module:
        def doit():
            main.run_module(Options.module, Options.module_args, space=space)
    elif args:
        scriptdir = os.path.dirname(os.path.abspath(args[0]))
        space.call_method(space.sys.get('path'), 'insert',
                          space.wrap(0), space.wrap(scriptdir))
        def doit():
            main.run_file(args[0], space=space)
    else:
        def doit():
            pass
        space.call_method(space.sys.get('argv'), 'append', space.wrap(''))
        go_interactive = 1
        banner = None

    try:
        def do_start():
            space.startup()
        if main.run_toplevel(space, do_start, verbose=Options.verbose):
            # compile and run it
            if not main.run_toplevel(space, doit, verbose=Options.verbose):
                exit_status = 1

            # start the interactive console
            if go_interactive:
                con = interactive.PyPyConsole(
                    space, verbose=Options.verbose,
                    completer=Options.completer)
                if banner == '':
                    banner = '%s / %s'%(con.__class__.__name__,
                                        repr(space))
                con.interact(banner)
                exit_status = 0
    finally:
        def doit():
            space.finish()
        main.run_toplevel(space, doit, verbose=Options.verbose)

    return exit_status


if __name__ == '__main__':
    try:
        import readline
    except:
        pass
    if hasattr(sys, 'setrecursionlimit'):
        # for running "python -i py.py -Si -- py.py -Si" 
        sys.setrecursionlimit(3000)
    sys.exit(main_(sys.argv))
