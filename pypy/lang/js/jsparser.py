
""" Using narcisus to generate code
"""

# TODO Should be replaced by a real parser

import os
import os.path as path
import re
from pypy.rlib.parsing.ebnfparse import parse_ebnf, make_parse_function
from pypy.rlib.parsing.ebnfparse import Symbol
from pypy.rlib.streamio import open_file_as_stream

DEBUG = False

class JsSyntaxError(Exception):
    pass

SLASH = "\\"
def read_js_output(code_string):
    tmp = []
    last = ""
    for c in code_string:
        if c == "'" and last != SLASH:
            tmp.append("\\'")
        else:
            if c == SLASH:
                tmp.append(SLASH*2)
            elif c == "\n":
                tmp.append("\\n")
            else:
                tmp.append(c)
    stripped_code = "".join(tmp)
    if DEBUG:
        print "------ got:"
        print code_string
        print "------ put:"
        print stripped_code
    jsdir = path.join(path.dirname(__file__),"js")
    f_jsdefs = open_file_as_stream(path.join(jsdir, "jsdefs.js")) 
    jsdefs = f_jsdefs.readall()
    f_jsdefs.close()
    f_jsparse = open_file_as_stream(path.join(jsdir, "jsparse.js"))
    jsparse = f_jsparse.readall()
    f_jsparse.close()
    fname = path.join(path.dirname(__file__) ,"tobeparsed.js")
    f = open_file_as_stream(fname, 'w')
    f.write(jsdefs+jsparse+"print(parse('%s'));\n" % stripped_code)
    f.close()
    c2pread, c2pwrite = os.pipe()
    if os.fork() == 0:
        #child
        os.dup2(c2pwrite, 1)
        for i in range(3, 256):
            try:
                os.close(i)
            except OSError:
                pass
        cmd = ['/bin/sh', '-c', 'js -f '+fname]
        os.execvp(cmd[0], cmd)
    os.close(c2pwrite)
    retval = os.read(c2pread, -1)
    os.close(c2pread)
    if not retval.startswith("{"):
        raise JsSyntaxError(retval)
    if DEBUG:
        print "received back:"
        print retval
    return retval

def unquote(t):
    if isinstance(t, Symbol):
        if t.symbol == "QUOTED_STRING":
            t.additional_info = t.additional_info[1:-1].replace("\\'", "'").replace("\\\\", "\\")
    else:
        for i in t.children:
            unquote(i)

def parse(code_string):
    read_code = read_js_output(code_string)
    output = read_code.split(os.linesep)
    t = parse_bytecode("\n".join(output))
    return t

def parse_bytecode(bytecode):
    # print bytecode
    t = parse_tree(bytecode)
    tree = ToAST().transform(t)
    unquote(tree)
    return tree

regexs, rules, ToAST = parse_ebnf(r"""
    QUOTED_STRING: "'([^\\\']|\\[\\\'])*'";"""+"""
    IGNORE: " |\n";
    data: <dict> | <QUOTED_STRING> | <list>;
    dict: ["{"] (dictentry [","])* dictentry ["}"];
    dictentry: QUOTED_STRING [":"] data;
    list: ["["] (data [","])* data ["]"];
""")
parse_tree = make_parse_function(regexs, rules, eof=True)
