#!/usr/bin/python 

"""PyPy compiler to be used as a wrapper around the various backend translators. As a sideeffect the entry function of the compiled code will be run.

options:
    -h(elp)
    -v(iew flow graph)
    -b<org/c/cl/llvm> (set backend) [default=llvm]
    -s(show source)
    -C(ompilation disable)
    -t(est compiled)
    [python script] <entry function (default=main())>
"""

import autopath, os, sys
from pypy.translator.translator import Translator
from pypy.rpython.rtyper import *
from pypy.rpython.rarithmetic import *


class Options(object):
    available_backends = {'org':'Original source', 'c':'C translation', 'cl':'common lisp translation', 'llvm':'LLVM translation(default)', 'pyrex':'pyrex translation'}
    backend         = 'llvm'
    python_script   = ''
    entry_function  = 'main()'
    view_flow_graph = False
    show_source     = False
    compile         = True
    test_compiled   = False

    def __init__(self,argv=[]):
        if not argv:
            print __doc__
            sys.exit(0)
    
        for arg in argv:
            if arg[0] == '-':
                option = arg[:2]

                if option == '-b':
                    new_backend = arg[2:]
                    if new_backend in self.available_backends:
                        self.backend = new_backend
                    else:
                        print 'error: unknown backend', new_backend, '. Avaialable backends are:', self.available_backends
                        sys.exit(0)
            
                elif option == '-v':
                    self.view_flow_graph = True
            
                elif option == '-s':
                    self.show_source = True
            
                elif option == '-C':
                    self.compile = False
            
                elif option == '-t':
                    self.test_compiled = True
            
                else:
                    print __doc__
                    sys.exit(0)
                
            else:
                if not self.python_script:
                    self.python_script  = arg
                else:
                    self.entry_function = arg


def main(argv=[]):
    options = Options(argv)

    modname = options.python_script.replace('/', '.')
    if modname[-3:] == '.py':
        modname = modname[:-3]

    if modname[0] == '.':   #absolute path
        #print imp.find_module(options.python_script)
        sys.path.append('/')  #XXX may not work on all platforms
        #print sys.path
        absmodname = modname[1:]
        exec "import %(absmodname)s as testmodule" % locals()
        ##print 'pop',sys.path.pop()
    else:   #relative path
        exec "import %(modname)s as testmodule" % locals()

    if '(' in options.entry_function:
        entry_function, arguments = options.entry_function.split('(',1)
    else:
        entry_function, arguments = options.entry_function, ')'

    #print 'entry_functionText=',entry_function
    entry_function = getattr(testmodule, entry_function)
    #print 'entry_function=',entry_function

    if arguments != ')' and arguments.find(',') == -1:
        arguments = arguments[:-1] + ',)'
    arguments = [argument for argument in eval('('+arguments)]
    #print 'arguments=',arguments

    argumentTypes = [type(arg) for arg in arguments]
    #print 'argumentTypes=',argumentTypes
    
    t = Translator(entry_function)
    t.simplify()
    a = t.annotate(argumentTypes)
    a.simplify()

    if options.view_flow_graph:
        rtyper = RPythonTyper(t.annotator)
        rtyper.specialize()
        t.view()
        t = Translator(entry_function)
        t.simplify()
        a = t.annotate(argumentTypes)
        a.simplify()

    if options.show_source:
        if options.backend == 'org':
            print t.source()
        
        elif options.backend == 'c':
            print t.c()
            #note: this is a workaround until GenC can generate identical code multiple times
            t = Translator(entry_function)
            t.simplify()
            a = t.annotate([type(arg), type(arg) == type(int)])           # pass the list of args types
            a.simplify()

        elif options.backend == 'cl':
            print t.cl()

        elif options.backend == 'llvm':
            print t.llvm()

        elif options.backend == 'pyrex':
            print t.pyrex()

    if options.compile:
        if options.backend == 'c':
            a.specialize()                     # use low level operations (for C only)
            f = t.ccompile()

        elif options.backend == 'llvm':
            f = t.llvmcompile()

        elif options.backend == 'pyrex':
            f = t.pyrexcompile()

        else:
            print 'warning: backend', options.backend, 'has no compile phase'
            sys.exit(0)

        assert f
        print 'Backend', options.backend, 'compilation successful!'
        backendReturn = t.call(*arguments)

        if options.test_compiled:
            pythonReturn = f(*arguments)
            assert backendReturn == pythonReturn
            print 'Backend', options.backend, 'compiled code returns same as python script (%s)' % backendReturn
        else:
            print 'Backend', options.backend, 'compiled code returns (%s)' % backendReturn, '[use -t to perform a sanity check]'


if __name__ == '__main__':
    if (os.getcwd() not in sys.path and
        os.path.curdir not in sys.path):
        sys.path.insert(0, os.getcwd())

    sys.exit(main(sys.argv[1:]))

