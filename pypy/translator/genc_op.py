"""
Low-level operations for C code generation.
"""

from pypy.translator.typer import LLOp

# This file defines one class per possible operation.  But there are families
# of very similar operations (e.g. incref/decref/xdecref).  To make it easy
# to follow which class is really an operation and which class represents a
# family, we introduce a simple mecanism: class attributes that are set to
# PARAMETER are parameters that can be set by calling the class method With().
PARAMETER = object()   # marker


class LoC(LLOp):
    # base class for LLOps that produce C code.

    def write(self):
        "Default write method, delegating to writestr()."
        args = [a.name for a in self.args]
        if self.can_fail:
            args.append(self.errtarget)
        return self.writestr(*args)

    def using(self):
        return self.args    # all locals and constants needed by write()

    def With(cls, **params):
        class subcls(cls):
            pass
        items = params.items()
        items.sort()
        info = [repr(value) for name, value in items]
        subcls.__name__ = '%s.With(%s)' % (cls.__name__, ', '.join(info))
        for name, value in items:
            assert hasattr(cls, name), 'not a parameter: %r' % (name,)
            setattr(subcls, name, value)
        # check that all PARAMETERs, at least from this class,
        # have been given a value
        for name, value in cls.__dict__.items():
            if value is PARAMETER:
                assert name in params, 'missing definition for parameter '+name
        return subcls
    With = classmethod(With)

class LoOptimized(LoC):
    def write(self):
        raise NotImplementedError, 'should be optimized away'

# ____________________________________________________________

class LoStandardOperation(LoC):
    "A standard operation is one defined by a macro in genc.h."
    can_fail = PARAMETER
    llname   = PARAMETER
    def writestr(self, *args):
        return self.llname + '(' + ', '.join(args) + ')'

class LoKnownAnswer(LoOptimized):
    known_answer = PARAMETER
    def optimize(self, typer):
        return self.known_answer

class LoNewList(LoC):
    can_fail = True
    def writestr(self, *stuff):
        content = stuff[:-2]
        result = stuff[-2]
        err = stuff[-1]
        ls = ['if (!(%s = PyList_New(%d))) goto %s;' % (
            result, len(content), err)]
        for i in range(len(content)):
            ls.append('PyList_SET_ITEM(%s, %d, %s); Py_INCREF(%s);' % (
                result, i, content[i], content[i]))
        return '\n'.join(ls)

class LoCallFunction(LoC):
    can_fail = True
    def writestr(self, func, *stuff):
        args = stuff[:-2]
        result = stuff[-2]
        err = stuff[-1]
        format = '"' + 'O' * len(args) + '"'
        args = (func, format) + args
        return ('if (!(%s = PyObject_CallFunction(%s)))'
                ' goto %s;' % (result, ', '.join(args), err))

class LoInstantiate(LoC):
    can_fail = True
    llclass  = PARAMETER
    def writestr(self, res, err):
        return 'INSTANTIATE(%s, %s, %s)' % (
            self.llclass.name, res, err)

class LoAllocInstance(LoC):
    can_fail = True
    llclass  = PARAMETER
    def writestr(self, res, err):
        return 'ALLOC_INSTANCE(%s, %s, %s)' % (
            self.llclass.name, res, err)

class LoConvertTupleItem(LoOptimized):
    source_r = PARAMETER   # tuple-of-hltypes, one per item of the input tuple
    target_r = PARAMETER   # tuple-of-hltypes, one per item of the output tuple
    index    = PARAMETER   # index of the item to convert

    def optimize(self, typer):
        # replace this complex conversion by the simpler conversion of
        # only the indexth item
        llinputs = []
        pos = 0
        for r in self.source_r:
            L = len(r.impl)
            llinputs.append(self.args[pos:pos+L])
            pos += L
        lloutputs = []
        for r in self.target_r:
            L = len(r.impl)
            lloutputs.append(self.args[pos:pos+L])
            pos += L

        llrepr = []     # answer
        for i in range(len(self.source_r)):
            if i == self.index:
                # convert this item
                llrepr += typer.convert(self.source_r[i], llinputs[i],
                                        self.target_r[i], lloutputs[i])
            else:
                # don't convert, just pass this item unchanged to the result
                llrepr += llinputs[i]
        return llrepr

class LoNewTuple(LoC):
    can_fail = True

    def writestr(self, *stuff):
        args   = stuff[:-2]
        result = stuff[-2]
        err    = stuff[-1]
        ls = ['if (!(%s = PyTuple_New(%d))) goto %s;' %
              (result, len(args), err)]
        for i, a in zip(range(len(args)), args):
            ls.append('PyTuple_SET_ITEM(%s, %d, %s); Py_INCREF(%s);' %
                      (result, i, a, a))
        return '\n'.join(ls)

class LoConvertChain(LoOptimized):
    r_from         = PARAMETER
    r_middle       = PARAMETER
    r_to           = PARAMETER
    convert_length = PARAMETER

    def optimize(self, typer):
        half = len(self.r_from.impl)
        assert half + len(self.r_to.impl) == len(self.args)
        input = self.args[:half]
        output = self.args[half:]
        middle = typer.convert(self.r_from, input, self.r_middle)
        return typer.convert(self.r_middle, middle, self.r_to, output)

# ____________________________________________________________

class LoMove(LoC):
    def writestr(self, x, y):
        return '%s = %s;' % (y, x)

class LoGoto(LoC):
    def write(self):
        return 'goto %s;' % self.errtarget

class LoCopy(LoOptimized):
    def optimize(self, typer):
        # the result's llvars is equal to the input's llvars.
        assert len(self.args) % 2 == 0
        half = len(self.args) // 2
        return self.args[:half]

class LoDoSomethingWithRef(LoC):
    do_what = PARAMETER
    def write(self):
        ls = []
        for a in self.args:
            if a.type == 'PyObject*':
                ls.append('%s(%s);' % (self.do_what, a.name))
        return ' '.join(ls)

LoIncref  = LoDoSomethingWithRef.With(do_what = 'Py_INCREF')
LoDecref  = LoDoSomethingWithRef.With(do_what = 'Py_DECREF')
LoXDecref = LoDoSomethingWithRef.With(do_what = 'Py_XDECREF')

class LoComment(LoC):
    def write(self):
        s = self.errtarget
        s = s.replace('/*', '/+')
        s = s.replace('*/', '+/')
        return '/* %s */' % s

# ____________________________________________________________

ERROR_RETVAL = {
    None:        '-1',
    'int':       '-1',
    'PyObject*': 'NULL',
    }

ERROR_CHECK = {
    None:        '< 0',
    'int':       '== -1 && PyErr_Occurred()',
    'PyObject*': '== NULL',
    }

class LoCallPyFunction(LoC):
    can_fail  = True
    llfunc    = PARAMETER
    hlrettype = PARAMETER
    def write(self):
        L = len(self.hlrettype.impl)
        R = len(self.args) - L
        args = [a.name for a in self.args[:R]]
        err = self.errtarget
        if L == 0:  # no return value
            return 'if (%s(%s) %s) goto %s;' % (
                self.llfunc.name, ', '.join(args), ERROR_CHECK[None], err)
        else:
            # the return value is the first return LLVar:
            retvar = self.args[R]
            # if there are several return LLVars, the extra ones are passed
            # in by reference as output arguments
            args += ['&%s' % a.name for a in self.args[R+1:]]
            return ('if ((%s = %s(%s)) %s) goto %s;' % (
                retvar.name, self.llfunc.name, ', '.join(args),
                ERROR_CHECK[retvar.type], err))

class LoReturn(LoC):
    def write(self):
        if not self.args:
            return 'return 0;'
        ls = []
        for extra in self.args[1:]:
            ls.append('*output_%s = %s;' % (extra.name, extra.name))
        ls.append('return %s;' % self.args[0].name)
        return '\n'.join(ls)

# ____________________________________________________________
