import py
from pypy.lang.js.interpreter import *
from pypy.lang.js.jsobj import W_Array
from pypy.lang.js.conftest import option

rootdir = py.magic.autopath().dirpath()
exclusionlist = ['shell.js', 'browser.js']

class JSDirectory(py.test.collect.Directory):

    def filefilter(self, path): 
        if path.check(file=1):
            return (path.basename not in exclusionlist)  and (path.ext == '.js')

    def join(self, name):
        if not name.endswith('.js'):
            return super(Directory, self).join(name)
        p = self.fspath.join(name)
        if p.check(file=1):
            return JSTestFile(p, parent=self)



class JSTestFile(py.test.collect.Collector):
    def __init__(self, filepath, parent=None):
        super(JSTestFile, self).__init__(filepath, parent)
        self.name = filepath.purebasename + " JSFILE"
        self.filepath = filepath
    
    def run(self):
        #actually run the file :)
        t = load_source(self.filepath.read())
        try:
            t.execute(interp.global_context)
        except:
            py.test.fail("Could not load js file")
        testcases = interp.global_context.resolve_identifier('testcases')
        values = testcases.GetValue().array
        testcases.PutValue(W_Array(), interp.global_context)
        return values

    def join(self, name):
        return JSTestItem(name, parent = self)

class JSTestItem(py.__.test.item.Item):        
    def __init__(self, name, parent=None):
        #super(JSTestItem, self).__init__(filepath, parent)
        self.name = name
         
    def run():
        ctx = interp.global_context
        r3 = ctx.resolve_identifier('run_test').GetValue()
        result = r3.Call(ctx=ctx, args=[name,]).ToNumber()
        if result == 0:
            py.test.fail()
        elif result == -1:
            py.test.skip()

if option.ecma:
    global interp
    interp = Interpreter()
    ctx = interp.global_context
    shellpath = rootdir/'shell.js'
    t = load_source(shellpath.read())
    t.execute(ctx)
    Directory = JSDirectory