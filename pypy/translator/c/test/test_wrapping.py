from pypy.translator.translator import TranslationContext
from pypy import conftest
from py.test import raises
from pypy.rpython import extregistry
from pypy.annotation import model as annmodel
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.objectmodel import instantiate
from pypy.rpython import robject, rclass

import sys

P = False  # debug printing

def get_annotation(func):
    argstypelist = []
    if func.func_defaults:
        for spec in func.func_defaults:
            if isinstance(spec, tuple):
                # use the first type only for the tests
                spec = spec[0]
            argstypelist.append(spec)
    missing = [object] * (func.func_code.co_argcount - len(argstypelist))
    return missing + argstypelist

def get_compiled_module(func, view=conftest.option.view, inline_threshold=0*1,
                use_boehm=False, exports=None):
    from pypy.translator.translator import TranslationContext
    from pypy.translator.backendopt.all import backend_optimizations

    from pypy.translator.c import gc
    from pypy.translator.c.genc import CExtModuleBuilder

    global t # allow us to view later
    t = TranslationContext(do_imports_immediately=False)
    t.buildannotator()
    rtyper = t.buildrtyper()
    bk = rtyper.annotator.bookkeeper
    instantiators = {}
    t.annotator.build_types(func, get_annotation(func))
    if not exports:
        exports = []
    all = [obj.__name__ for obj in exports]
    exports = exports + [('__all__', all)]
    for obj in exports:
        if isinstance(obj, type):
            cls = obj
            def make():
                obj = instantiate(cls)
                return obj
            make.__name__ = cls.__name__ + '__new__'
            t.annotator.build_types(make, [])
            instantiators[cls] = make
            clsdef = bk.getuniqueclassdef(cls)
            rtyper.add_wrapper(clsdef)
        elif callable(obj):
            t.annotator.build_types(obj, get_annotation(obj))
    if view:
        t.viewcg()
    rtyper.specialize()
    if view:
        t.viewcg()
    t.checkgraphs()

    gcpolicy = None
    if use_boehm:
        gcpolicy = gc.BoehmGcPolicy

    backend_optimizations(t, inline_threshold=inline_threshold)
    if view:
        t.viewcg()

    cbuilder = CExtModuleBuilder(t, func, gcpolicy=gcpolicy)
    # explicit build of database
    db = cbuilder.build_database(exports=exports, instantiators=instantiators)
    cbuilder.generate_source(db)
    cbuilder.compile()

    if view:
        t.viewcg()
    return cbuilder.import_module()

def getcompiled(func, *args, **kwds):
    module = get_compiled_module(func, *args, **kwds)
    return getattr(module, func.__name__)

# _______________________________________________-
# stubs for special annotation/rtyping


def wrap_obj(thing):
    RaiseNameError

def unwrap_obj(pyobj, typ):
    RaiseNameError
unwrap_obj._annspecialcase_ = 'specialize:arg(1)'

def call_destructor(thing, savedrepr):
    ll_call_destructor(thing, savedrepr)

def ll_call_destructor(thang, savedtrpr):
    return 42 # really not relevant

"""
creating a wrapper object with its destructor.
Note that we need annotate_helper_fn, because
the destructor is never explicitly called.
Note also the "hand specialization" which passes the repr through!
This was only possible with Samuele's hints.
"""

def rtype_destruct_object(hop):
    v_any, c_spec = hop.inputargs(*hop.args_r)
    repr = c_spec.value
    if repr.has_wrapper:
        null = hop.inputconst(lltype.Ptr(lltype.PyObject), lltype.nullptr(lltype.PyObject))
        # XXX this is a hack! We need an operation to remove a broken PyObject
        repr.setfield(v_any, '_wrapper_', null, hop.llops, opname='bare_setfield')
    hop.genop('gc_unprotect', [v_any])

def rtype_unwrap_object(hop):
    pyptr = hop.args_r[0]
    klass = hop.args_s[1].const
    classdef = hop.rtyper.annotator.bookkeeper.getuniqueclassdef(klass)
    repr = rclass.getinstancerepr(hop.rtyper, classdef, True)
    v_pyobj, v_type = hop.inputargs(*hop.args_r)
    if repr.has_wrapper:
        c_self = hop.inputconst(robject.pyobj_repr, '__self__')
        v_pyobj = hop.genop('getattr', [v_pyobj, c_self], resulttype=pyptr)
    v_adr = hop.llops.gencapicall('PyCObject_AsVoidPtr', [v_pyobj], resulttype=hop.r_result)
    hop.genop('gc_protect', [v_adr])
    return v_adr

def rtype_wrap_object(hop):
    v_any, = hop.inputargs(*hop.args_r)
    repr = hop.args_r[0]
    c_repr = hop.inputconst(lltype.Void, repr)
    if repr.has_wrapper:
        return hop.gendirectcall(ll_wrap_object, v_any, c_repr)
    else:
        return hop.gendirectcall(create_pywrapper, v_any, c_repr)

def ll_wrap_object(obj, repr):
    ret = fetch_pywrapper(obj, repr)
    if not ret:
        ret = create_pywrapper(obj, repr)
    return ret

def create_pywrapper(thing, repr):
    return ll_create_pywrapper(thing, repr)

def ll_create_pywrapper(thing, repr):
    return 42

def fetch_pywrapper(thing, repr):
    return ll_fetch_pywrapper(thing, repr)

def ll_fetch_pywrapper(thing, repr):
    return 42

def rtype_wrap_object_create(hop):
    gencapi = hop.llops.gencapicall
    pyptr = hop.r_result
    v_any, c_spec = hop.inputargs(*hop.args_r)
    repr = c_spec.value
    f = call_destructor
    hop.genop('gc_protect', [v_any])
    ARG = repr.lowleveltype
    reprPBC = hop.rtyper.annotator.bookkeeper.immutablevalue(repr)
    fp_dtor = hop.rtyper.annotate_helper_fn(f, [ARG, reprPBC])
    FUNC = lltype.FuncType([ARG, lltype.Void], lltype.Void)
    c_dtor = hop.inputconst(lltype.Ptr(FUNC), fp_dtor)
    res = gencapi('PyCObject_FromVoidPtr', [v_any, c_dtor], resulttype=pyptr)
    if repr.has_wrapper:
        cobj = res
        c_cls = hop.inputconst(robject.pyobj_repr, repr.classdef.classdesc.pyobj)
        c_0 = hop.inputconst(lltype.Signed, 0)
        res = gencapi('PyType_GenericAlloc', [c_cls, c_0], resulttype=pyptr)
        c_self = hop.inputconst(robject.pyobj_repr, '__self__')
        hop.genop('setattr', [res, c_self, cobj], resulttype=pyptr)
        repr.setfield(v_any, '_wrapper_', res, hop.llops)
        hop.genop('gc_unprotect', [res]) # yes a weak ref
    return res

def rtype_wrap_object_fetch(hop):
    v_any, c_spec = hop.inputargs(*hop.args_r)
    repr = c_spec.value
    if repr.has_wrapper:
        return repr.getfield(v_any, '_wrapper_', hop.llops)
    else:
        null = hop.inputconst(lltype.Ptr(lltype.PyObject), lltype.nullptr(lltype.PyObject))
        return null


def compute_annotation_unwrap(s_wrapper, s_class):
    assert hasattr(s_class, 'descriptions'), 'need a class in unwrap 2nd arg'
    descs = s_class.descriptions
    assert len(descs) == 1, 'missing specialisation, classdesc not unique!'
    for desc in descs.keys():
        classdef = desc.getuniqueclassdef()
    return annmodel.SomeInstance(classdef)

extregistry.register_value(ll_create_pywrapper, 
    compute_result_annotation=annmodel.SomePtr(lltype.Ptr(lltype.PyObject)), 
    specialize_call=rtype_wrap_object_create)

extregistry.register_value(ll_fetch_pywrapper, 
    compute_result_annotation=annmodel.SomePtr(lltype.Ptr(lltype.PyObject)), 
    specialize_call=rtype_wrap_object_fetch)

extregistry.register_value(ll_call_destructor, 
    compute_result_annotation=lambda *args: None,
    specialize_call=rtype_destruct_object)

extregistry.register_value(wrap_obj, 
    compute_result_annotation=annmodel.SomeObject(),
    specialize_call=rtype_wrap_object)

extregistry.register_value(unwrap_obj, 
    compute_result_annotation=compute_annotation_unwrap,
    specialize_call=rtype_unwrap_object)

# _______________________________________________-
# the actual tests

# track __del__ calls
class DelMonitor(object):
    def __init__(self):
        self.reset()
    def reset(self):
        self.deletions = 0
    def notify(self):
        self.deletions += 1
    def report(self):
        return self.deletions

delmonitor = DelMonitor()

class DemoBaseNotExposed(object):
    pass

# a trivial class to be exposed
class DemoClass(DemoBaseNotExposed):
    def __init__(self, a, b):
        self.a = a
        self.b = b
        if P:print 'init'

    def demo(self):
        if P:print 'demo'
        return self.a + self.b

    def demonotcalled(self):
        return self.demo() + 42

    def __del__(self):
        delmonitor.notify()
        if P:print 'del'

# see if we get things exported with subclassing
class DemoSubclass(DemoClass):
    def __init__(self, a, b, c):
        #super(DemoSubclass, self).__init__(a, b)
        DemoClass.__init__(self, b, a)
        self.c = c

#    def demo(self, *other):
        #if other: print other
 #       return float(DemoClass.demo(self))
    
    def otherdemo(self):
        return 'this is the DemoSubclass', self.a, self.b

    def __del__(self):
        pass # this is intentionally another thing

# see how classes are handled that were not annotated
class DemoNotAnnotated(object):
    def __init__(self):
        self.hugo = 42
    def retrieve(self):
        return self.hugo

# we have more helper functions here than needed.
# this was to make the debugging easier.

def call_wrap_obj(inst):
    return wrap_obj(inst)
call_wrap_obj._annspecialcase_ = 'specialize:argtype(0)'

def call_unwrap_obj(pyobj, klass):
    return unwrap_obj(pyobj, klass)
call_unwrap_obj._annspecialcase_ = 'specialize:arg(1)'

def democlass_helper_sub(a, b):
    # prevend inlining
    if a == -42:
        return democlass_helper_sub(a-1, b)
    inst = DemoClass(a, b)
    pyobj = call_wrap_obj(inst)
    obj = call_unwrap_obj(pyobj, DemoClass)
    ret = obj.demo()
    inst = DemoSubclass(a, b, 42)
    pyobj = call_wrap_obj(inst)
    obj = call_unwrap_obj(pyobj, DemoSubclass)
    ret = obj.demo()
    return ret

def democlass_helper(a=int, b=int):
    delmonitor.reset()
    ret = democlass_helper_sub(a, b)
    return delmonitor.report(), ret, long(42)

def democlass_helper2(a=int, b=int):
    self = DemoClass(a, b)
    self.demo()
    self2 = DemoSubclass(a, b, 42)
    return self

# _______________________________________________
# creating our own setup function for the module

def do_the_import():
    from twisted.internet import reactor    
    return reactor

def rtype_wraptest(hop):
    #v_obj, = hop.inputargs((robject.pyobj_repr, ))
    from pypy.objspace.flow.model import Constant
    v_obj = Constant(hop.args_s[0].const)
    v = hop.genop('simple_call', [v_obj], resulttype = robject.pyobj_repr)
    return v

def wraptest(obj):
    return obj
extregistry.register_value(wraptest,
        compute_result_annotation = annmodel.SomeObject(),
        specialize_call = rtype_wraptest)

# not sure what to do with the above.
# use genpickle facility to produce a plain function?
# create a space and run geninterp on it?
# tweak flow space to delay the imports for this func?

### XXX write up the rules how to use this ###

def t2():
    global sys
    import sys

def setup_new_module(mod, modname):
    # note the name clash with py.test on setup_module
    #t1()
    #t2()
    return
    from types import module
    m = module(modname)
    allobjs = mod.__dict__.values()
    funcs = eval('[]') # or import list from __builtin__
    from twisted.internet import reactor    
    print dir(reactor)
    #whow this works
    for obj in allobjs:
        print obj, dir(obj)
        if hasattr(42, 'func_name'):
            funcs.append( (obj.func_name, obj) )
    print 'funcs=', funcs
    funcs.sort()
    for name, func in funcs:
        print name, func
    for name in mod.__all__:
        obj = getattr(mod, name)
        #if isinstance(obj, type):
        # careful, this gives a class!
        if hasattr(mod, '__bases__'):
            print name
        setattr(m, name, obj)
    return m


# creating an object, wrapping, unwrapping, call function, check whether __del__ is called
def test_wrap_call_dtor():
    f = getcompiled(democlass_helper, use_boehm=not True, exports=[DemoSubclass])
    ret = f(2, 3)
    if P: print ret
    assert ret[0] == 1

# exposing and using classes from a generasted extension module
def test_expose_classes():
    m = get_compiled_module(democlass_helper2, use_boehm=not True, exports=[
        DemoClass, DemoSubclass, DemoNotAnnotated, setup_new_module])
    obj = m.DemoClass(2, 3)
    res = obj.demo()
    assert res == DemoClass(2, 3).demo()

if __name__=='__main__':
    test_expose_classes()
    
