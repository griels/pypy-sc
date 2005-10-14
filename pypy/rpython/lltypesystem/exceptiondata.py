from pypy.annotation import model as annmodel
from pypy.rpython.lltypesystem import rclass
from pypy.rpython.annlowlevel import annotate_lowlevel_helper
from pypy.rpython.lltype import Array, malloc, Ptr, PyObject, pyobjectptr
from pypy.rpython.lltype import FuncType, functionptr, Signed
from pypy.rpython.extfunctable import standardexceptions
from pypy.annotation.classdef import FORCE_ATTRIBUTES_INTO_CLASSES

class ExceptionData:
    """Public information for the code generators to help with exceptions."""
    standardexceptions = standardexceptions

    def __init__(self, rtyper):
        self.make_standard_exceptions(rtyper)
        # (NB. rclass identifies 'Exception' and 'object')
        r_type = rclass.getclassrepr(rtyper, None)
        r_instance = rclass.getinstancerepr(rtyper, None)
        r_type.setup()
        r_instance.setup()
        self.r_exception_type  = r_type
        self.r_exception_value = r_instance
        self.lltype_of_exception_type  = r_type.lowleveltype
        self.lltype_of_exception_value = r_instance.lowleveltype


    def make_helpers(self, rtyper):
        # create helper functions
        self.ll_exception_match  = self.make_exception_matcher(rtyper)
        self.ll_type_of_exc_inst = self.make_type_of_exc_inst(rtyper)
        self.ll_pyexcclass2exc   = self.make_pyexcclass2exc(rtyper)
        self.ll_raise_OSError    = self.make_raise_OSError(rtyper)


    def make_standard_exceptions(self, rtyper):
        bk = rtyper.annotator.bookkeeper
        for cls in self.standardexceptions:
            classdef = bk.getclassdef(cls)
            rclass.getclassrepr(rtyper, classdef).setup()


    def make_exception_matcher(self, rtyper):
        # ll_exception_matcher(real_exception_vtable, match_exception_vtable)
        s_typeptr = annmodel.SomePtr(self.lltype_of_exception_type)
        dontcare, spec_function = annotate_lowlevel_helper(
            rtyper.annotator, rclass.ll_issubclass, [s_typeptr, s_typeptr])
        return spec_function


    def make_raise_OSError(self, rtyper):
        # ll_raise_OSError(errno)
        def ll_raise_OSError(errno):
            raise OSError(errno, None)
        dontcare, spec_function = annotate_lowlevel_helper(
            rtyper.annotator, ll_raise_OSError, [annmodel.SomeInteger()])
        return spec_function


    def make_type_of_exc_inst(self, rtyper):
        # ll_type_of_exc_inst(exception_instance) -> exception_vtable
        s_excinst = annmodel.SomePtr(self.lltype_of_exception_value)
        dontcare, spec_function = annotate_lowlevel_helper(
            rtyper.annotator, rclass.ll_type, [s_excinst])
        return spec_function


    def make_pyexcclass2exc(self, rtyper):
        # ll_pyexcclass2exc(python_exception_class) -> exception_instance
        table = {}
        for clsdef in rtyper.class_reprs:
            if (clsdef and clsdef.cls is not Exception
                and issubclass(clsdef.cls, Exception)):
                cls = clsdef.cls
                if cls in self.standardexceptions and cls not in FORCE_ATTRIBUTES_INTO_CLASSES:
                    is_standard = True
                    assert not clsdef.attrs, (
                        "%r should not have grown atributes" % (cls,))
                else:
                    is_standard = (cls.__module__ == 'exceptions'
                                   and not clsdef.attrs)
                if is_standard:
                    r_inst = rclass.getinstancerepr(rtyper, clsdef)
                    r_inst.setup()
                    example = malloc(r_inst.lowleveltype.TO, immortal=True)
                    example = rclass.ll_cast_to_object(example)
                    example.typeptr = r_inst.rclass.getvtable()
                    table[cls] = example
                #else:
                #    assert cls.__module__ != 'exceptions', (
                #        "built-in exceptions should not grow attributes")
        r_inst = rclass.getinstancerepr(rtyper, None)
        r_inst.setup()
        default_excinst = malloc(self.lltype_of_exception_value.TO,
                                 immortal=True)
        default_excinst.typeptr = r_inst.rclass.getvtable()

        # build the table in order base classes first, subclasses last
        sortedtable = []
        def add_class(cls):
            if cls in table:
                for base in cls.__bases__:
                    add_class(base)
                sortedtable.append((cls, table[cls]))
                del table[cls]
        for cls in table.keys():
            add_class(cls)
        assert table == {}
        #print sortedtable

        A = Array(('pycls', Ptr(PyObject)),
                  ('excinst', self.lltype_of_exception_value))
        pycls2excinst = malloc(A, len(sortedtable), immortal=True)
        for i in range(len(sortedtable)):
            cls, example = sortedtable[i]
            pycls2excinst[i].pycls   = pyobjectptr(cls)
            pycls2excinst[i].excinst = example

        FUNCTYPE = FuncType([Ptr(PyObject), Ptr(PyObject)], Signed)
        PyErr_GivenExceptionMatches = functionptr(
            FUNCTYPE, "PyErr_GivenExceptionMatches", external="C",
            _callable=lambda pyobj1, pyobj2:
                          int(issubclass(pyobj1._obj.value, pyobj2._obj.value)))

        initial_value_of_i = len(pycls2excinst)-1

        def ll_pyexcclass2exc(python_exception_class):
            """Return an RPython instance of the best approximation of the
            Python exception identified by its Python class.
            """
            i = initial_value_of_i
            while i >= 0:
                if PyErr_GivenExceptionMatches(python_exception_class,
                                               pycls2excinst[i].pycls):
                    return pycls2excinst[i].excinst
                i -= 1
            return default_excinst

        s_pyobj = annmodel.SomePtr(Ptr(PyObject))
        dontcare, spec_function = annotate_lowlevel_helper(
            rtyper.annotator, ll_pyexcclass2exc, [s_pyobj])
        return spec_function
