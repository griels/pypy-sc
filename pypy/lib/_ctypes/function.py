
import types
from _ctypes.basics import _CData, _CDataMeta

class CFuncPtrType(_CDataMeta):
    # XXX write down here defaults and such things
    pass

class CFuncPtr(_CData):
    __metaclass__ = CFuncPtrType

    _argtypes_ = None
    _restype_ = None

    def _getargtypes(self):
        return self._argtypes_
    def _setargtypes(self, argtypes):
        self._argtypes_ = argtypes    
    argtypes = property(_getargtypes, _setargtypes)

    def _getrestype(self):
        return self._restype_
    def _setrestype(self, restype):
        self._restype_ = restype    
    restype = property(_getrestype, _setrestype)    

    def __init__(self, address_or_name_and_dll=0):
        if isinstance(address_or_name_and_dll, tuple):
            self.name, self.dll = address_or_name_and_dll
        else:
            self.address = address_or_name_and_dll
            self.name = None

    def __call__(self, *args):
        if self.name is None:
            if isinstance(self.address, types.FunctionType):
                # special hack to support to way a few functions like
                # ctypes.cast() are implemented in ctypes/__init__.py
                return self.address(*args)
            raise NotImplementedError("Creation of function pointer to pure addresses is not implemented")
        argtypes = self._argtypes_
        if argtypes is None:
            argtypes = self._guess_argtypes(args)
        restype = self._restype_
        funcptr = self._getfuncptr(argtypes, restype)
        resarray = funcptr(*self._wrap_args(argtypes, args))
        if restype is not None:
            return restype._CData_output(resarray)

    def _getfuncptr(self, argtypes, restype):
        argletters = [arg._ffiletter for arg in argtypes]
        return self.dll._handle.ptr(self.name, argletters, restype._ffiletter)

    def _guess_argtypes(self, args):
        from _ctypes import _CData
        res = []
        for arg in args:
            assert isinstance(arg, _CData)
            res.append(type(arg))
        return res

    def _wrap_args(self, argtypes, args):
        return [argtype._CData_input(arg) for argtype, arg in
                zip(argtypes, args)]
