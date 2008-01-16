
import _rawffi
from _ctypes.basics import _CData, _CDataMeta, cdata_from_address
from _ctypes.basics import sizeof, byref
from _ctypes.array import Array

DEFAULT_VALUE = object()

class PointerType(_CDataMeta):
    def __new__(self, name, cls, typedict):
        d = dict(
            size       = _rawffi.sizeof('P'),
            align      = _rawffi.alignment('P'),
            length     = 1,
            _ffiletter = 'P'
        )
        # XXX check if typedict['_type_'] is any sane
        # XXX remember about paramfunc
        obj = type.__new__(self, name, cls, typedict)
        for k, v in d.iteritems():
            setattr(obj, k, v)
        if '_type_' in typedict:
            ffiarray = _rawffi.Array('P')
            def __init__(self, value=None):
                self._buffer = ffiarray(1)
                if value is not None:
                    self.contents = value
            obj._ffiarray = ffiarray
        else:
            def __init__(self, value=None):
                raise TypeError("%s has no type" % obj)
        obj.__init__ = __init__
        return obj

    def from_param(self, value):
        if value is None:
            return 0
	# If we expect POINTER(<type>), but receive a <type> instance, accept
	# it by calling byref(<type>).
        if isinstance(value, self._type_):
            return byref(value)
        # Array instances are also pointers when the item types are the same.
        if isinstance(value, Array):
            if issubclass(type(value)._type_, self._type_):
                return value
        return _CDataMeta.from_param(self, value)

    def _sizeofinstances(self):
        return _rawffi.sizeof('P')

    def _is_pointer_like(self):
        return True

    from_address = cdata_from_address

class _Pointer(_CData):
    __metaclass__ = PointerType

    def getcontents(self):
        addr = self._buffer[0]
        if addr == 0:
            raise ValueError("NULL pointer access")
        return self._type_.from_address(addr)

    def setcontents(self, value):
        if not isinstance(value, self._type_):
            raise TypeError("expected %s instead of %s" % (
                self._type_.__name__, type(value).__name__))
        value = value._buffer
        self._buffer[0] = value

    def _subarray(self, index=0):
        """Return a _rawffi array of length 1 whose address is the same as
        the index'th item to which self is pointing."""
        address = self._buffer[0]
        address += index * sizeof(self._type_)
        return self._type_._ffiarray.fromaddress(address, 1)

    def __getitem__(self, index):
        return self._type_._CData_output(self._subarray(index))

    def __setitem__(self, index, value):
        if index != 0:
            raise IndexError
        self._subarray(index)[0] = self._type_._CData_input(value)[0]

    def __nonzero__(self):
        return self._buffer[0] != 0

    contents = property(getcontents, setcontents)


def _cast_addr(obj, _, tp):
    if not (isinstance(obj, _CData) and type(obj)._is_pointer_like()):
        raise TypeError("cast() argument 1 must be a pointer, not %s"
                        % (type(obj),))
    if not (isinstance(tp, _CDataMeta) and tp._is_pointer_like()):
        raise TypeError("cast() argument 2 must be a pointer type, not %s"
                        % (tp,))
    result = tp()
    result._buffer[0] = obj._buffer[0]
    return result