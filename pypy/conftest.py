import py
from pypy.interpreter.gateway import app2interp_temp 
from pypy.interpreter.error import OperationError
from pypy.objspace.std import StdObjSpace
from pypy.tool import pytestsupport

#
# PyPy's command line extra options (these are added 
# to py.test's standard options) 
#
Option = py.test.Option
options = ('pypy options', [
        Option('-o', '--objspace', action="store", default=None, 
               type="string", dest="objspacename", 
               help="object space to run tests on."), 
])


def getobjspace(name=None, _spacecache={}): 
    """ helper for instantiating and caching space's for testing. 
    """ 
    if name is None: 
        name = py.test.config.option.objspacename  
        if name is None:
            name = py.std.os.environ.get('OBJSPACE', 'std')
    else:
        optionname = py.test.config.option.objspacename
        if optionname is not None and optionname != name:
            return None
    try:
        return _spacecache[name]
    except KeyError:
        module = __import__("pypy.objspace.%s" % name, None, None, ["Space"])
        space = module.Space()
        _spacecache[name] = space
        space.setitem(space.w_builtins, space.wrap('AssertionError'), 
                      pytestsupport.build_pytest_assertion(space))
        return space

# 
# Interfacing/Integrating with py.test's collection process 
#

class Module(py.test.collect.Module): 
    """ we take care of collecting classes both at app level 
        and at interp-level (because we need to stick a space 
        at the class) ourselves. 
    """
    def collect_function(self, extpy): 
        if extpy.check(func=1, basestarts='test_'):
            if extpy.check(genfunc=1): 
                yield IntTestGenerator(extpy) 
            else: 
                yield IntTestFunction(extpy)

    def collect_app_function(self, extpy): 
        if extpy.check(func=1, basestarts='app_test_'):
            assert not extpy.check(genfunc=1), "you must be joking" 
            yield AppTestFunction(extpy)
            
    def collect_class(self, extpy): 
        if extpy.check(class_=1, basestarts="Test"): 
            yield IntClassCollector(extpy) 

    def collect_appclass(self, extpy): 
        if extpy.check(class_=1, basestarts="AppTest"): 
            yield AppClassCollector(extpy) 

def gettestobjspace(name=None):
    space = getobjspace(name)
    if space is None:
        py.test.skip('test requires object space %r' % (name,))
    return space


class PyPyItem(py.test.Item):
    # All PyPy test items catch and display OperationErrors specially.
    def execute_in_space(self, space, target, *args):
        try:
            target(*args)
        except OperationError, e:
            raise self.Failed(excinfo=pytestsupport.AppExceptionInfo(space, e))

class IntTestFunction(PyPyItem):
    def execute(self, target, *args):
        co = target.func_code
        if 'space' in co.co_varnames[:co.co_argcount]: 
            name = target.func_globals.get('objspacename', None) 
            space = gettestobjspace(name) 
            self.execute_in_space(space, target, space, *args)
        else:
            target(*args)

class AppTestFunction(PyPyItem): 
    def execute(self, target, *args):
        assert not args 
        name = target.func_globals.get('objspacename', None) 
        space = gettestobjspace(name) 
        func = app2interp_temp(target, target.__name__)
        self.execute_in_space(space, target)

class IntTestMethod(PyPyItem): 
    def execute(self, target, *args):
        name = target.func_globals.get('objspacename', None) 
        if name is None: 
            name = getattr(target.im_class, 'objspacename', None)
        instance = target.im_self
        instance.space = space = gettestobjspace(name)
        self.execute_in_space(space, target, *args)

class AppTestMethod(PyPyItem): 
    def execute(self, target, *args): 
        assert not args 
        name = target.func_globals.get('objspacename', None) 
        if name is None: 
            name = getattr(target.im_class, 'objspacename', None)
        space = gettestobjspace(name)
        func = app2interp_temp(target.im_func, target.__name__) 
        self.execute_in_space(space, func, space, space.w_None)

class AppClassCollector(py.test.collect.Class): 
    Item = AppTestMethod 

class IntClassCollector(py.test.collect.Class): 
    Item = IntTestMethod 
    
