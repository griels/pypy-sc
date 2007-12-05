
from pypy.rpython.extregistry import ExtRegistryEntry

def ll_assert(x, msg):
    """After translation to C, this becomes an RPyAssert."""
    assert x, msg

class Entry(ExtRegistryEntry):
    _about_ = ll_assert

    def compute_result_annotation(self, s_x, s_msg):
        assert s_msg.is_constant(), ("ll_assert(x, msg): "
                                     "the msg must be constant")
        return None

    def specialize_call(self, hop):
        from pypy.rpython.lltypesystem import lltype
        vlist = hop.inputargs(lltype.Bool, lltype.Void)
        hop.genop('debug_assert', vlist)


def llinterpcall(RESTYPE, pythonfunction, *args):
    """When running on the llinterp, this causes the llinterp to call to
    the provided Python function with the run-time value of the given args.
    The Python function should return a low-level object of type RESTYPE.
    This should never be called after translation: use this only if
    running_on_llinterp is true.
    """
    raise NotImplementedError

class Entry(ExtRegistryEntry):
    _about_ = llinterpcall

    def compute_result_annotation(self, s_RESTYPE, s_pythonfunction, *args_s):
        from pypy.annotation import model as annmodel
        from pypy.rpython.lltypesystem import lltype
        assert s_RESTYPE.is_constant()
        assert s_pythonfunction.is_constant()
        s_result = s_RESTYPE.const
        if isinstance(s_result, lltype.LowLevelType):
            s_result = annmodel.lltype_to_annotation(s_result)
        assert isinstance(s_result, annmodel.SomeObject)
        return s_result

    def specialize_call(self, hop):
        from pypy.annotation import model as annmodel
        from pypy.rpython.lltypesystem import lltype
        RESTYPE = hop.args_s[0].const
        if not isinstance(RESTYPE, lltype.LowLevelType):
            assert isinstance(RESTYPE, annmodel.SomeObject)
            r_result = hop.rtyper.getrepr(RESTYPE)
            RESTYPE = r_result.lowleveltype
        pythonfunction = hop.args_s[1].const
        c_pythonfunction = hop.inputconst(lltype.Void, pythonfunction)
        args_v = [hop.inputarg(hop.args_r[i], arg=i)
                  for i in range(2, hop.nb_args)]
        return hop.genop('debug_llinterpcall', [c_pythonfunction] + args_v,
                         resulttype=RESTYPE)


def check_annotation(arg, checker):
    """ Function checking if annotation is as expected when translating,
    does nothing when just run. Checker is supposed to be a constant
    callable which checks if annotation is as expected,
    arguments passed are (current annotation, bookkeeper)
    """
    pass

class Entry(ExtRegistryEntry):
    _about_ = check_annotation

    def compute_result_annotation(self, s_arg, s_checker):
        if not s_checker.is_constant():
            raise ValueError("Second argument of check_annotation must be constant")
        checker = s_checker.const
        checker(s_arg, self.bookkeeper)
        from pypy.annotation import model
        return s_arg

    def specialize_call(self, hop):
        hop.exception_cannot_occur()
        vlist = [hop.inputarg(hop.args_r[0], arg=0)]
        return hop.genop("same_as", vlist, resulttype=hop.r_result)

