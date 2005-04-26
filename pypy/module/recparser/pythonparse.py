#!/usr/bin/env python
from grammar import BaseGrammarBuilder
from pythonlexer import PythonSource
from ebnfparse import parse_grammar
import sys
import pythonutil


def parse_python_source( textsrc, gram, goal ):
    """Parse a python source according to goal"""
    target = gram.rules[goal]
    src = PythonSource(textsrc)
    builder = BaseGrammarBuilder(debug=False, rules=gram.rules)
    result = target.match(src, builder)
    # <HACK> XXX find a clean way to process encoding declarations
    if src.encoding:
        builder._source_encoding = src.encoding
    # </HACK>
    if not result:
        print src.debug()
        raise SyntaxError("at %s" % src.debug() )
    return builder

def parse_file_input(pyf, gram):
    """Parse a python file"""
    return parse_python_source( pyf.read(), gram, "file_input" )
    
def parse_single_input(textsrc, gram):
    """Parse a python file"""
    return parse_python_source( textsrc, gram, "single_input" )

def parse_eval_input(textsrc, gram):
    """Parse a python file"""
    return parse_python_source( textsrc, gram, "eval_input" )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "python parse.py [-d N] test_file.py"
        sys.exit(1)
    if sys.argv[1] == "-d":
        debug_level = int(sys.argv[2])
        test_file = sys.argv[3]
    else:
        test_file = sys.argv[1]
    print "-"*20
    print
    print "pyparse \n", pythonutil.pypy_parse(test_file)
    print "parser  \n", pythonutil.python_parse(test_file)

