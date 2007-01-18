import py
from py.__.doc.conftest import Directory, DoctestText, ReSTChecker

Option = py.test.config.Option
option = py.test.config.addoptions("pypy-doc options", 
        Option('--generate-redirections', action="store_true",
               dest="generateredirections",
               default=False, help="Generate the redirecting HTML files"),
        Option('--enable-doctests', action="store_true",
               dest="doctests", 
               default=False, help="enable doctests in .txt files"), 
    )

class PyPyDoctestText(DoctestText): 

    def run(self): 
        if not option.doctests: 
            py.test.skip("specify --enable-doctests to run doctests") 
        # XXX refine doctest support with respect to scoping 
        return super(PyPyDoctestText, self).run()
        
    def execute(self, module, docstring): 
        # XXX execute PyPy prompts as well 
        l = []
        for line in docstring.split('\n'): 
            if line.find('>>>>') != -1: 
                line = "" 
            l.append(line) 
        text = "\n".join(l) 
        super(PyPyDoctestText, self).execute(module, text) 

        #mod = py.std.types.ModuleType(self.fspath.basename, text) 
        #self.mergescopes(mod, scopes) 
        #failed, tot = py.std.doctest.testmod(mod, verbose=1)
        #if failed:
        #    py.test.fail("doctest %s: %s failed out of %s" %(
        #                 self.fspath, failed, tot))

class PyPyReSTChecker(ReSTChecker): 
    DoctestText = PyPyDoctestText 
    
class Directory(Directory): 
    ReSTChecker = PyPyReSTChecker 
