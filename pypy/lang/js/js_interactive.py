#!/usr/bin/env python
# encoding: utf-8
"""
js_interactive.py
"""

import autopath
import sys
import getopt
from pypy.lang.js.interpreter import *
from pypy.lang.js.jsobj import W_Builtin

help_message = '''
The help message goes here.
'''


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "ho:v", ["help", "output="])
        except getopt.error, msg:
            raise Usage(msg)
    
        # option processing
        for option, value in opts:
            if option == "-v":
                verbose = True
            if option in ("-h", "--help"):
                raise Usage(help_message)
            if option in ("-o", "--output"):
                output = value
    
    except Usage, err:
        print >> sys.stderr, sys.argv[0].split("/")[-1] + ": " + str(err.msg)
        print >> sys.stderr, "\t for help use --help"
        return 2
    
    interp = Interpreter()
    def quiter():
        sys.exit(0)
        return "this should not be printed"
    
    interp.w_Global.Put('quit', W_Builtin(quiter))
    
    while 1:
        res = interp.run(load_source(raw_input("pypy-js>")))
        if res is not None:
            print res


if __name__ == "__main__":
    sys.exit(main())
