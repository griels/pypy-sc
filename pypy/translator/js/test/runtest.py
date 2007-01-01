'''
    Skipped tests should still be fixed. (or only run with py.test --browser)
    Sests with DONT in front of them will probably not be fixed for the time being.
'''

import py, os, re, subprocess
from pypy.translator.translator import TranslationContext
from pypy.translator.backendopt.all import backend_optimizations
from pypy.translator.js.js import JS
from pypy.translator.js.test.browsertest import jstest
from pypy.translator.js import conftest
from pypy.translator.js.log import log
from pypy.conftest import option
from pypy.rpython.test.tool import BaseRtypingTest, OORtypeMixin
from pypy.translator.transformer.debug import DebugTransformer
from pypy.rlib.nonconst import NonConstant

from pypy.rpython.llinterp import LLException

log = log.runtest
use_browsertest = conftest.option.browser
use_tg = conftest.option.tg

port = 8080

def _CLI_is_on_path():
    try:
        py.path.local.sysfind('js') #we recommend Spidermonkey
    except py.error.ENOENT:
        return False
    return True

class compile_function(object):
    def __init__(self, function, annotations, stackless=False, view=False, html=None, is_interactive=False, root = None, run_browser = True, debug_transform = False):
        if not use_browsertest and not _CLI_is_on_path():
            py.test.skip('Javascript CLI (js) not found')

        self.html = html
        self.is_interactive = is_interactive
        t = TranslationContext()
        ann = t.buildannotator()
        ann.build_types(function, annotations)
        if debug_transform:
            DebugTransformer(t).transform_all()
        if view or option.view:
            t.view()
        t.buildrtyper(type_system="ootype").specialize()

        if view or option.view:
            t.view()
        #self.js = JS(t, [function, callback_function], stackless)
        self.js = JS(t, function, stackless)
        self.js.write_source()
        if root is None and use_tg:
            from pypy.translator.js.demo.jsdemo.controllers import Root
            self.root = Root
        else:
            self.root = root
        self.run_browser = run_browser
        self.function_calls = []
    
    def source(self):
        return self.js.tmpfile.open().read()

    def _conv(self, v):
        if isinstance(v, str):
            return repr(v)
        return str(v).lower()

    def __call__(self, *kwds):
        return self.call(None, kwds)
    
    def call(self, entry_function, kwds):
        args = ', '.join([self._conv(kw) for kw in kwds]) #lowerstr for (py)False->(js)false, etc.

        if entry_function is None:
            entry_function = self.js.translator.graphs[0].name
        else:
            entry_function = self.js.translator.annotator.bookkeeper.getdesc(entry_function).cached_graph(None)
        function_call = "%s(%s)" % (entry_function, args)
        self.function_calls.append(function_call)
        #if self.js.stackless:
        #    function_call = "slp_entry_point('%s')" % function_call

        if use_browsertest:
            if not use_tg:
                log("Used html: %r" % self.html)
                output = jstest(self.js.filename, function_call, use_browsertest, self.html, self.is_interactive)
            else:
                global port
                from pypy.translator.js.test.tgtest import run_tgtest
                out = run_tgtest(self, tg_root = self.root, port=port, run_browser=self.run_browser).results
                assert out[1] == 'undefined' or out[1] == ""
                output = out[0]
                port += 1
        else:
#            cmd = 'echo "load(\'%s\'); print(%s)" | js 2>&1' % (self.js.filename, function_call)
#            log(cmd)
#            output = os.popen(cmd).read().strip()
            js = subprocess.Popen(["js"], 
                                  stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            input = "load(%r);\n" % self.js.filename.strpath
            for call in self.function_calls[:-1]:
                input += "%s;\n" % call
            input += "print(%s);\n" % self.function_calls[-1]
            js.stdin.write(input)
            stdout, stderr = js.communicate()
            output = (stderr + stdout).strip()
        for s in output.split('\n'):
            log(s)

        if s == 'false':
            res = False
        elif s == 'true':
            res = True
        elif s == 'undefined':
            res = None
        elif s == 'inf':
            res = 1e300 * 1e300
        elif s == 'NaN':
            res = (1e300 * 1e300) / (1e300 * 1e300)
        elif s.startswith("uncaught exception:"):
            raise LLException(str(s))
        else:
            log('javascript result:', s)
            try:
                res = eval(s)
            except:
                res = str(s)
        return res

class JsTest(BaseRtypingTest, OORtypeMixin):
    #def __init__(self):
    #    self._func = None
    #    self._ann = None
    #    self._cli_func = None

    def _compile(self, fn, args):
        #ann = [lltype_to_annotation(typeOf(x)) for x in args]
        #if self._func is fn and self._ann == ann:
        #    return self._cli_func
        #else:
        #    self._func = fn
        #    self._ann = ann
        #    self._cli_func = compile_function(fn, ann)
        #    return self._cli_func
        source = py.code.Source("""
        def %s():
            from pypy.rlib.nonconst import NonConstant
            res = fn(%s)
            if isinstance(res, type(None)):
                return None
            else:
                return str(res)"""
        % (fn.func_name, ",".join(["NonConstant(%s)" % i for i in args])))
        exec source.compile() in locals()
        return compile_function(locals()[fn.func_name], [])
    
    def interpret(self, fn, args):
        #def f(args):
        #   fn(*args)
        
        f = self._compile(fn, args)
        res = f(*args)
        return res
        #if isinstance(res, ExceptionWrapper):
        #    raise res
        #return res

    def interpret_raises(self, exception, fn, args):
        #import exceptions # needed by eval
        #try:
        #import pdb; pdb.set_trace()
        try:
            res = self.interpret(fn, args)
        except LLException, e:
            s = e.args[0]
            assert s.startswith('uncaught exception:')
            assert re.search(str(exception), s)
        else:
            raise AssertionError("Did not raise, returned %s" % res)
        #except ExceptionWrapper, ex:
        #    assert issubclass(eval(ex.class_name), exception)
        #else:
        #    assert False, 'function did raise no exception at all'

    def ll_to_string(self, s):
        return s

    def ll_to_list(self, l):
        return l

    def class_name(self, value):
        return value.class_name.split(".")[-1] 

    def is_of_instance_type(self, val):
        m = re.match("^<.* instance>$", val)
        return bool(m)

    def read_attr(self, obj, name):
        pass
        #py.test.skip('read_attr not supported on gencli tests')

def check_source_contains(compiled_function, pattern):
    import re
    
    source = compiled_function.js.tmpfile.open().read()
    return re.search(pattern, source)
