import autopath
from pypy.tool import test, option
from pypy.objspace.std import StdObjSpace
from pypy.module.builtin import Builtin
from pypy.interpreter import executioncontext, baseobjspace, pyframe
import sys, os

def _run_eval_string(source, filename, space, eval):
    if eval:
        cmd = 'eval'
    else:
        cmd = 'exec'
        
    try:
        if space is None:
            space = StdObjSpace()

        compile = space.builtin.compile
        w = space.wrap
        w_code = compile(w(source), w(filename), w(cmd),
                         w(0), w(0))

        ec = executioncontext.ExecutionContext(space)

        w_mainmodule = space.newmodule(space.wrap("__main__"))
        w_globals = space.getattr(w_mainmodule, space.wrap("__dict__"))
        space.setitem(w_globals, space.wrap("__builtins__"), space.w_builtins)
        
        frame = pyframe.PyFrame(space, space.unwrap(w_code),
                                w_globals, w_globals)
    except baseobjspace.OperationError, operationerr:
        operationerr.record_interpreter_traceback()
        raise baseobjspace.PyPyError(space, operationerr)
    else:
        if eval:
            return ec.eval_frame(frame)
        else:
            ec.eval_frame(frame)
    
def run_string(source, filename='<string>', space=None):
    _run_eval_string(source, filename, space, False)

def eval_string(source, filename='<string>', space=None):
    return _run_eval_string(source, filename, space, True)

def run_file(filename, space=None):
    if __name__=='__main__':
        print "Running %r with %r" % (filename, space)
    istring = open(filename).read()
    run_string(istring, filename, space)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    argv = option.process_options(option.get_standard_options(),
                                  option.Options)
    space = option.objspace()
    try:
        run_file(argv[0], space)
    except baseobjspace.PyPyError, pypyerr:
        pypyerr.operationerr.print_detailed_traceback(pypyerr.space)

if __name__ == '__main__':
    main(sys.argv)
    
