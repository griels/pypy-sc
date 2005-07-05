__all__ = ["python_parse", "pypy_parse", "ast_single_input", "ast_file_input",
           "ast_eval_input"]

import parser
import symbol

import pythonparse
from tuplebuilder import TupleBuilder

PYTHON_PARSER = pythonparse.PYTHON_PARSER
TARGET_DICT = {
    'exec'   : "file_input",
    'eval'   : "eval_input",
    'single' : "file_input",
    }

## convenience functions around CPython's parser functions
def python_parsefile(filename, lineno=False):
    """parse <filename> using CPython's parser module and return nested tuples
    """
    pyf = file(filename)
    source = pyf.read()
    pyf.close()
    return python_parse(source, 'exec', lineno)

def python_parse(source, mode='exec', lineno=False):
    """parse python source using CPython's parser module and return
    nested tuples
    """
    if mode == 'eval':
        tp = parser.expr(source)
    else:
        tp = parser.suite(source)
    return parser.ast2tuple(tp, line_info=lineno)

## convenience functions around recparser functions
def pypy_parsefile(filename, lineno=False):
    """parse <filename> using PyPy's parser module and return
    a tuple of three elements :
     - The encoding declaration symbol or None if there were no encoding
       statement
     - The TupleBuilder's stack top element (instance of
       tuplebuilder.StackElement which is a wrapper of some nested tuples
       like those returned by the CPython's parser)
     - The encoding string or None if there were no encoding statement
    nested tuples
    """
    pyf = file(filename)
    source = pyf.read()
    pyf.close()
    return pypy_parse(source, 'exec', lineno)

def pypy_parse(source, mode='exec', lineno=False):
    """parse <source> using PyPy's parser module and return
    a tuple of three elements :
     - The encoding declaration symbol or None if there were no encoding
       statement
     - The TupleBuilder's stack top element (instance of
       tuplebuilder.StackElement which is a wrapper of some nested tuples
       like those returned by the CPython's parser)
     - The encoding string or None if there were no encoding statement
    nested tuples
    """
    builder = TupleBuilder(PYTHON_PARSER.rules, lineno=False)
    target_rule = TARGET_DICT[mode]
    PYTHON_PARSER.parse_source(source, target_rule, builder)
    stack_element = builder.stack[-1]
    # convert the stack element into nested tuples (caution, the annotator
    # can't follow this call)
    nested_tuples = stack_element.as_tuple(lineno)
    if builder.source_encoding is not None:
        return (symbol.encoding_decl, nested_tuples, builder.source_encoding)
    else:
        return nested_tuples

## convenience functions for computing AST objects using recparser
def ast_from_input(input, mode, transformer):
    """converts a source input into an AST

     - input : the source to be converted
     - mode : 'exec', 'eval' or 'single'
     - transformer : the transfomer instance to use to convert
                     the nested tuples into the AST
     XXX: transformer could be instantiated here but we don't want
          here to explicitly import compiler or stablecompiler or
          etc. This is to be fixed in a clean way
    """
    tuples = pypy_parse(input, mode, True)
    ast = transformer.compile_node(tuples)
    return ast

## TARGET FOR ANNOTATORS #############################################
def annotateme(source):
    """This function has no other role than testing the parser's annotation

    annotateme() is basically the same code that pypy_parse(), but with the
    following differences :
     - directly take a list of strings rather than a filename in input
       in order to avoid using file() (which is faked for now)
       
     - returns a tuplebuilder.StackElement instead of the *real* nested
       tuples (StackElement is only a wrapper class around these tuples)

    """
    builder = TupleBuilder(PYTHON_PARSER.rules, lineno=False)
    PYTHON_PARSER.parse_source(source, 'file_input', builder)
    nested_tuples = builder.stack[-1]
    if builder.source_encoding is not None:
        return (symbol.encoding_decl, nested_tuples, builder.source_encoding)
    else:
        return (None, nested_tuples, None)


if __name__ == "__main__":
    import sys
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
    print "pyparse \n", pypy_parsefile(test_file)
    print "parser  \n", python_parsefile(test_file)
