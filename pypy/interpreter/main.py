from pypy.objspace.std import StdObjSpace
from pypy.module.builtin import Builtin
from pypy.interpreter import executioncontext, baseobjspace, pyframe
import sys

def run_string(source, fname):
    space = None   # in case StdObjSpace.__init__() crashes
    try:
        space = StdObjSpace()

        compile = space.builtin.compile
        w=space.wrap
        w_code = compile(w(source), w(fname), w('exec'),
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
        ec.eval_frame(frame)

def run_file(fname):
    istring = open(fname).read()
    run_string(istring, fname)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    try:
        run_file(argv[1])
    except baseobjspace.PyPyError, pypyerr:
        pypyerr.operationerr.print_detailed_traceback(pypyerr.space)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
    
