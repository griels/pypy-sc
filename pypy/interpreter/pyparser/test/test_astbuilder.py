import os

from pypy.interpreter.pyparser.pythonparse import PYTHON_PARSER
from pypy.interpreter.pyparser.astbuilder import AstBuilder
from pypy.interpreter.pyparser.pythonutil import ast_from_input
from pypy.interpreter.stablecompiler.transformer import Transformer
import py.test

from pypy.interpreter.astcompiler import ast

expressions = [
    "x = a + 1",
    "x = 1 - a",
    "x = a * b",
    "x = a ** 2",
    "x = a / b",
    "x = a & b",
    "x = a | b",
    "x = a ^ b",
    "x = a // b",
    "x = a * b + 1",
    "x = a + 1 * b",
    "x = a * b / c",
    "x = a * (1 + c)",
    "x, y, z = 1, 2, 3",
    "x = 'a' 'b' 'c'",
    "del foo",
    "del foo[bar]",
    "del foo.bar",
    "l[0]",
    "m[a,b]",
]

funccalls = [
    "l = func()",
    "l = func(10)",
    "l = func(10, 12, a, b=c, *args)",
    "l = func(10, 12, a, b=c, **kwargs)",
    "l = func(10, 12, a, b=c, *args, **kwargs)",
    "l = func(10, 12, a, b=c)",
    "e = l.pop(3)",
    "e = k.l.pop(3)",
    ]

listmakers = [
    "l = []",
    "l = [1, 2, 3]",
    "l = [i for i in range(10)]",
    "l = [i for i in range(10) if i%2 == 0]",
    "l = [i for i in range(10) if i%2 == 0 or i%2 == 1]",
    "l = [i for i in range(10) if i%2 == 0 and i%2 == 1]",
    "l = [i for j in range(10) for i in range(j)]",
    "l = [i for j in range(10) for i in range(j) if j%2 == 0]",
    "l = [i for j in range(10) for i in range(j) if j%2 == 0 and i%2 == 0]",
    "l = [(a, b) for (a,b,c) in l2]",
    "l = [{a:b} for (a,b,c) in l2]",
    "l = [i for j in k if j%2 == 0 if j*2 < 20 for i in j if i%2==0]",
    ]

genexps = [
    "l = (i for i in j)",
    "l = (i for i in j if i%2 == 0)",
    "l = (i for j in k for i in j)",
    "l = (i for j in k for i in j if j%2==0)",
    "l = (i for j in k if j%2 == 0 if j*2 < 20 for i in j if i%2==0)",
    ]


dictmakers = [
    "l = {a : b, 'c' : 0}",
    "l = {}",
    ]

backtrackings = [
    "f = lambda x: x+1",
    "f = lambda x,y: x+y",
    "f = lambda x,y=1,z=t: x+y",
    "f = lambda x,y=1,z=t,*args,**kwargs: x+y",
    "f = lambda x,y=1,z=t,*args: x+y",
    "f = lambda x,y=1,z=t,**kwargs: x+y",
    "f = lambda: 1",
    "f = lambda *args: 1",
    "f = lambda **kwargs: 1",
    ]

comparisons = [
    "a < b",
    "a > b",
    "a not in b",
    "a is not b",
    "a in b",
    "a is b",
    "3 < x < 5",
    "(3 < x) < 5",
    "a < b < c < d",
    "(a < b) < (c < d)",
    "a < (b < c) < d",
    ]

multiexpr = [
    'a = b; c = d;',
    'a = b = c = d',
    ]

attraccess = [
    'a.b = 2',
    'x = a.b',
    ]

slices = [
    "l[:]",
    "l[1:2]",
    "l[1:]",
    "l[:2]",
    "l[0:1:2]",
    ]

imports = [
    'import os',
    'import sys, os',
    'import os.path',
    'import os.path, sys',
    'import sys, os.path as osp',
    'import os.path as osp',
    'import os.path as osp, sys as _sys',
    'import a.b.c.d',
    'import a.b.c.d as abcd',
    'from os import path',
    'from os import path, system',
    'from os import path, system,',
    'from os import path as P, system as S,',
    'from os import (path as P, system as S,)',
    'from os import *',
    ]

if_stmts = [
    "if a == 1: a+= 2",
    """if a == 1:
    a += 2
elif a == 2:
    a += 3
else:
    a += 4
"""
    ]

asserts = [
    'assert False',
    'assert a == 1',
    'assert a == 1 and b == 2',
    'assert a == 1 and b == 2, "assertion failed"',
    ]

execs = [
    'exec a',
    'exec "a=b+3"',
    'exec a in f()',
    'exec a in f(), g()',
    ]

prints = [
    'print',
    'print a',
    'print a,',
    'print a, b',
    'print a, "b", c',
    'print >> err',
    'print >> err, "error"',
    'print >> err, "error",',
    'print >> err, "error", a',
    ]

globs = [
    'global a',
    'global a,b,c',
    ]

raises = [
    'raise',
    'raise ValueError',
    'raise ValueError("error")',
    'raise ValueError, "error"',
    'raise ValueError, "error", foo',
    ]

tryexcepts = [
    """try:
    a
    b
except:
    pass
""",
    """try:
    a
    b
except NameError:
    pass
""",
    """try:
    a
    b
except NameError, err:
    pass
""",
    """try:
    a
    b
except (NameError, ValueError):
    pass
""",
    """try:
    a
    b
except (NameError, ValueError), err:
    pass
""",
    """try:
    a
except NameError, err:
    pass
except ValueError, err:
    pass
""",
    """try:
    a
except NameError, err:
    a = 1
    b = 2
except ValueError, err:
    a = 2
    return a
"""
    """try:
    a
except NameError, err:
    a = 1
except ValueError, err:
    a = 2
else:
    a += 3
""",
    """try:
    a
finally:
    b
""",
    """try:
    return a
finally:
    a = 3
    return 1
""",

    ]
    
one_stmt_funcdefs = [
    "def f(): return 1",
    "def f(x): return x+1",
    "def f(x,y): return x+y",
    "def f(x,y=1,z=t): return x+y",
    "def f(x,y=1,z=t,*args,**kwargs): return x+y",
    "def f(x,y=1,z=t,*args): return x+y",
    "def f(x,y=1,z=t,**kwargs): return x+y",
    "def f(*args): return 1",
    "def f(**kwargs): return 1",
    ]

docstrings = [
    '''def foo():
    """foo docstring"""
    return 1
    ''',
    '''def foo():
    """foo docstring"""
    a = 1
    """bar"""
    return a
    '''
    ]

TESTS = [
    expressions,
    comparisons,
    funccalls,
    backtrackings,
    listmakers,
    genexps,
    dictmakers,
    multiexpr,
    attraccess,
    slices,
    imports,
    asserts,
    execs,
    prints,
    globs,
    raises,
    ]

EXEC_INPUTS = [
    one_stmt_funcdefs,
    if_stmts,
    tryexcepts,
    docstrings,
    ]

TARGET_DICT = {
    'single' : 'single_input',
    'exec'   : 'file_input',
    'eval'   : 'eval_input',
    }

def ast_parse_expr(expr, target='single'):
    target = TARGET_DICT[target]
    builder = AstBuilder()
    PYTHON_PARSER.parse_source(expr, target, builder)
    return builder

def tuple_parse_expr(expr, target='single'):
    t = Transformer()
    return ast_from_input(expr, target, t)

def check_expression(expr, target='single'):
    r1 = ast_parse_expr(expr, target)
    ast = tuple_parse_expr(expr, target)
    print "-" * 30
    print "ORIG :", ast
    print 
    print "BUILT:", r1.rule_stack[-1]
    print "-" * 30
    assert ast == r1.rule_stack[-1], 'failed on %r' % (expr)


def test_basic_astgen():
    for family in TESTS:
        for expr in family:
            yield check_expression, expr

def test_exec_inputs():
    for family in EXEC_INPUTS:
        for expr in family:
            yield check_expression, expr, 'exec'


SNIPPETS = [    
    'snippet_1.py',
    'snippet_several_statements.py',
    'snippet_simple_function.py',
    'snippet_simple_for_loop.py',
    'snippet_while.py',
    'snippet_import_statements.py',
    'snippet_generator.py',
    'snippet_exceptions.py',
    'snippet_classes.py',
    'snippet_simple_class.py',
    'snippet_docstring.py',
    'snippet_2.py',
    'snippet_3.py',
    'snippet_4.py',
    'snippet_comment.py',
    'snippet_encoding_declaration2.py',
    'snippet_encoding_declaration3.py',
    'snippet_encoding_declaration.py',
    'snippet_function_calls.py',
    'snippet_import_statements.py',
    'snippet_list_comps.py',
    'snippet_multiline.py',
    'snippet_numbers.py',
    'snippet_only_one_comment.py',
    'snippet_redirected_prints.py',
    'snippet_simple_assignment.py',
    'snippet_simple_in_expr.py',
    'snippet_slice.py',
    'snippet_whitespaces.py',
#    'snippet_samples.py',
    ]

def test_snippets():
    for snippet_name in SNIPPETS:
        filepath = os.path.join(os.path.dirname(__file__), 'samples', snippet_name)
        source = file(filepath).read()
        yield check_expression, source, 'exec'

