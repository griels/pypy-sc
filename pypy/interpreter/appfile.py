import os


class AppFile:
    """Dynamic loader of a set of Python functions and objects that
    should work at the application level (conventionally in .app.py files)"""

    # absolute name of the parent directory
    ROOTDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def __init__(self, filename):
        "Load and compile the file."
        # XXX looking for a pre-compiled file here will be quite essential
        #     when we want to bootstrap the compiler
        fullfn = os.path.join(AppFile.ROOTDIR, filename)
        f = open(fullfn, 'r')
        src = f.read()
        f.close()
        self.bytecode = compile(src, filename, 'exec')


class Namespace:

    def __init__(self, space):
        self.space = space
        ec = space.getexecutioncontext()
        self.w_namespace = ec.make_standard_w_globals()

    def get(self, objname):
        "Returns a wrapped copy of an object by name."
        w_name = self.space.wrap(objname)
        w_obj = self.space.getitem(self.w_namespace, w_name)
        return w_obj

    def call(self, functionname, argumentslist):
        "Call a module function."
        w_function = self.get(functionname)
        w_arguments = self.space.newtuple(argumentslist)
        w_keywords = self.space.newdict([])
        return self.space.call(w_function, w_arguments, w_keywords)

    def runbytecode(self, bytecode):
        # initialize the module by running the bytecode in a new
        # dictionary, in a new execution context
        ec = self.space.getexecutioncontext()
        frame = pyframe.PyFrame(self.space, bytecode,
                                self.w_namespace, self.w_namespace)
        ec.eval_frame(frame)


class AppHelper(Namespace):

    def __init__(self, space, bytecode):
        Namespace.__init__(self, space)
        self.runbytecode(bytecode)
