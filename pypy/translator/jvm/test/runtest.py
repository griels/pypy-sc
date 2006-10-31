import os
import platform

import py
from py.compat import subprocess
from pypy.tool.udir import udir
from pypy.rpython.test.tool import BaseRtypingTest, OORtypeMixin
from pypy.rpython.lltypesystem.lltype import typeOf
from pypy.rpython.ootypesystem import ootype
from pypy.annotation.model import lltype_to_annotation
from pypy.translator.translator import TranslationContext
from pypy.translator.jvm.genjvm import generate_source_for_function, JvmError
from pypy.translator.jvm.option import getoption

FLOAT_PRECISION = 8

# CLI duplicate
class StructTuple(tuple):
    def __getattr__(self, name):
        if name.startswith('item'):
            i = int(name[len('item'):])
            return self[i]
        else:
            raise AttributeError, name

# CLI duplicate
class OOList(list):
    def ll_length(self):
        return len(self)

    def ll_getitem_fast(self, i):
        return self[i]

# CLI duplicate
class ExceptionWrapper:
    def __init__(self, class_name):
        self.class_name = class_name

    def __repr__(self):
        return 'ExceptionWrapper(%s)' % repr(self.class_name)

# CLI could-be duplicate
class JvmGeneratedSourceWrapper(object):
    def __init__(self, gensrc):
        """ gensrc is an instance of JvmGeneratedSource """
        self.gensrc = gensrc

    def __call__(self, *args):
        if not self.gensrc.compiled:
            py.test.skip("Assembly disabled")

        if getoption('norun'):
            py.test.skip("Execution disabled")

        resstr = self.gensrc.execute(args)
        print "resstr=%s" % repr(resstr)
        res = eval(resstr)
        if isinstance(res, tuple):
            res = StructTuple(res) # so tests can access tuple elements with .item0, .item1, etc.
        elif isinstance(res, list):
            res = OOList(res)
        return res

class JvmTest(BaseRtypingTest, OORtypeMixin):
    def __init__(self):
        self._func = None
        self._ann = None
        self._jvm_src = None

    def _compile(self, fn, args, ann=None):
        if ann is None:
            ann = [lltype_to_annotation(typeOf(x)) for x in args]
        if self._func is fn and self._ann == ann:
            return JvmGeneratedSourceWrapper(self._jvm_src)
        else:
            self._func = fn
            self._ann = ann
            self._jvm_src = generate_source_for_function(fn, ann)
            if not getoption('noasm'):
                self._jvm_src.compile()
            return JvmGeneratedSourceWrapper(self._jvm_src)

    def _skip_win(self, reason):
        if platform.system() == 'Windows':
            py.test.skip('Windows --> %s' % reason)

    def interpret(self, fn, args, annotation=None):
        try:
            src = self._compile(fn, args, annotation)
            res = src(*args)
            if isinstance(res, ExceptionWrapper):
                raise res
            return res
        except JvmError, e:
            e.pretty_print()
            raise

    def interpret_raises(self, exception, fn, args):
        import exceptions # needed by eval
        try:
            self.interpret(fn, args)
        except ExceptionWrapper, ex:
            assert issubclass(eval(ex.class_name), exception)
        else:
            assert False, 'function did not raise any exception at all'

    def float_eq(self, x, y):
        return round(x, FLOAT_PRECISION) == round(y, FLOAT_PRECISION)        

    def ll_to_string(self, s):
        return s

    def ll_to_list(self, l):
        return l

    def class_name(self, value):
        return value.class_name.split(".")[-1] 

    def is_of_instance_type(self, val):
        return isinstance(val, InstanceWrapper)

    def read_attr(self, obj, name):
        py.test.skip('read_attr not supported on genjvm tests')
