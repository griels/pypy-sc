
from pypy.rlib.parsing.tree import Nonterminal, Symbol
from makepackrat import PackratParser, BacktrackException, Status as _Status
class Parser(object):
    class _Status_NAME(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def NAME(self):
        return self._NAME().result
    def _NAME(self):
        _key = self._pos
        _status = self._dict_NAME.get(_key, None)
        if _status is None:
            _status = self._dict_NAME[_key] = self._Status_NAME()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self._regex1074651696()
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._NAME()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_SPACE(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def SPACE(self):
        return self._SPACE().result
    def _SPACE(self):
        _key = self._pos
        _status = self._dict_SPACE.get(_key, None)
        if _status is None:
            _status = self._dict_SPACE[_key] = self._Status_SPACE()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self.__chars__(' ')
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._SPACE()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_COMMENT(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def COMMENT(self):
        return self._COMMENT().result
    def _COMMENT(self):
        _key = self._pos
        _status = self._dict_COMMENT.get(_key, None)
        if _status is None:
            _status = self._dict_COMMENT[_key] = self._Status_COMMENT()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self._regex528667127()
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._COMMENT()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_IGNORE(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def IGNORE(self):
        return self._IGNORE().result
    def _IGNORE(self):
        _key = self._pos
        _status = self._dict_IGNORE.get(_key, None)
        if _status is None:
            _status = self._dict_IGNORE[_key] = self._Status_IGNORE()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self._regex1979538501()
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._IGNORE()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_newline(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def newline(self):
        return self._newline().result
    def _newline(self):
        _key = self._pos
        _status = self._dict_newline.get(_key, None)
        if _status is None:
            _status = self._dict_newline[_key] = self._Status_newline()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice0 = self._pos
                try:
                    _call_status = self._COMMENT()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice0
                _choice1 = self._pos
                try:
                    _result = self._regex299149370()
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice1
                    raise self._BacktrackException(_error)
                _result = self._regex299149370()
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._newline()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_REGEX(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def REGEX(self):
        return self._REGEX().result
    def _REGEX(self):
        _key = self._pos
        _status = self._dict_REGEX.get(_key, None)
        if _status is None:
            _status = self._dict_REGEX[_key] = self._Status_REGEX()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self._regex1006631623()
            r = _result
            _result = (Symbol('REGEX', r, None))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._REGEX()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_QUOTE(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def QUOTE(self):
        return self._QUOTE().result
    def _QUOTE(self):
        _key = self._pos
        _status = self._dict_QUOTE.get(_key, None)
        if _status is None:
            _status = self._dict_QUOTE[_key] = self._Status_QUOTE()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self._regex1124192327()
            r = _result
            _result = (Symbol('QUOTE', r, None))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._QUOTE()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_PYTHONCODE(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def PYTHONCODE(self):
        return self._PYTHONCODE().result
    def _PYTHONCODE(self):
        _key = self._pos
        _status = self._dict_PYTHONCODE.get(_key, None)
        if _status is None:
            _status = self._dict_PYTHONCODE[_key] = self._Status_PYTHONCODE()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self._regex291086639()
            r = _result
            _result = (Symbol('PYTHONCODE', r, None))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._PYTHONCODE()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_EOF(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def EOF(self):
        return self._EOF().result
    def _EOF(self):
        _key = self._pos
        _status = self._dict_EOF.get(_key, None)
        if _status is None:
            _status = self._dict_EOF[_key] = self._Status_EOF()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _choice2 = self._pos
            _stored_result3 = _result
            try:
                _result = self.__any__()
            except self._BacktrackException:
                self._pos = _choice2
                _result = _stored_result3
            else:
                raise self._BacktrackException(None)
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._EOF()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_file(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def file(self):
        return self._file().result
    def _file(self):
        _key = self._pos
        _status = self._dict_file.get(_key, None)
        if _status is None:
            _status = self._dict_file[_key] = self._Status_file()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _all4 = []
            while 1:
                _choice5 = self._pos
                try:
                    _call_status = self._IGNORE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all4.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice5
                    break
            _result = _all4
            _call_status = self._list()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            _before_discard6 = _result
            _call_status = self._EOF()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            _result = _before_discard6
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._file()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_list(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def list(self):
        return self._list().result
    def _list(self):
        _key = self._pos
        _status = self._dict_list.get(_key, None)
        if _status is None:
            _status = self._dict_list[_key] = self._Status_list()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _all7 = []
            _call_status = self._production()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            _all7.append(_result)
            while 1:
                _choice8 = self._pos
                try:
                    _call_status = self._production()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all7.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice8
                    break
            _result = _all7
            content = _result
            _result = (Nonterminal('list', content))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._list()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_production(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def production(self):
        return self._production().result
    def _production(self):
        _key = self._pos
        _status = self._dict_production.get(_key, None)
        if _status is None:
            _status = self._dict_production[_key] = self._Status_production()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _call_status = self._NAME()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            name = _result
            _all9 = []
            while 1:
                _choice10 = self._pos
                try:
                    _call_status = self._SPACE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all9.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice10
                    break
            _result = _all9
            _call_status = self._productionargs()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            args = _result
            _result = self.__chars__(':')
            _all11 = []
            while 1:
                _choice12 = self._pos
                try:
                    _call_status = self._IGNORE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all11.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice12
                    break
            _result = _all11
            _call_status = self._or_()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            what = _result
            _all13 = []
            while 1:
                _choice14 = self._pos
                try:
                    _call_status = self._IGNORE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all13.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice14
                    break
            _result = _all13
            _result = self.__chars__(';')
            _all15 = []
            while 1:
                _choice16 = self._pos
                try:
                    _call_status = self._IGNORE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all15.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice16
                    break
            _result = _all15
            _result = (Nonterminal('production', [name, args, what]))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._production()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_productionargs(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def productionargs(self):
        return self._productionargs().result
    def _productionargs(self):
        _key = self._pos
        _status = self._dict_productionargs.get(_key, None)
        if _status is None:
            _status = self._dict_productionargs[_key] = self._Status_productionargs()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice17 = self._pos
                try:
                    _result = self.__chars__('(')
                    _all18 = []
                    while 1:
                        _choice19 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all18.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice19
                            break
                    _result = _all18
                    _all20 = []
                    while 1:
                        _choice21 = self._pos
                        try:
                            _call_status = self._NAME()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _before_discard22 = _result
                            _all23 = []
                            while 1:
                                _choice24 = self._pos
                                try:
                                    _call_status = self._IGNORE()
                                    _result = _call_status.result
                                    _error = self._combine_errors(_call_status.error, _error)
                                    _all23.append(_result)
                                except self._BacktrackException, _exc:
                                    _error = self._combine_errors(_error, _exc.error)
                                    self._pos = _choice24
                                    break
                            _result = _all23
                            _result = self.__chars__(',')
                            _all25 = []
                            while 1:
                                _choice26 = self._pos
                                try:
                                    _call_status = self._IGNORE()
                                    _result = _call_status.result
                                    _error = self._combine_errors(_call_status.error, _error)
                                    _all25.append(_result)
                                except self._BacktrackException, _exc:
                                    _error = self._combine_errors(_error, _exc.error)
                                    self._pos = _choice26
                                    break
                            _result = _all25
                            _result = _before_discard22
                            _all20.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice21
                            break
                    _result = _all20
                    args = _result
                    _call_status = self._NAME()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    arg = _result
                    _all27 = []
                    while 1:
                        _choice28 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all27.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice28
                            break
                    _result = _all27
                    _result = self.__chars__(')')
                    _all29 = []
                    while 1:
                        _choice30 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all29.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice30
                            break
                    _result = _all29
                    _result = (Nonterminal('productionargs', args + [arg]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice17
                _choice31 = self._pos
                try:
                    _result = (Nonterminal('productionargs', []))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice31
                    raise self._BacktrackException(_error)
                _result = (Nonterminal('productionargs', []))
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._productionargs()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_or_(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def or_(self):
        return self._or_().result
    def _or_(self):
        _key = self._pos
        _status = self._dict_or_.get(_key, None)
        if _status is None:
            _status = self._dict_or_[_key] = self._Status_or_()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice32 = self._pos
                try:
                    _all33 = []
                    _call_status = self._commands()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _before_discard34 = _result
                    _result = self.__chars__('|')
                    _all35 = []
                    while 1:
                        _choice36 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all35.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice36
                            break
                    _result = _all35
                    _result = _before_discard34
                    _all33.append(_result)
                    while 1:
                        _choice37 = self._pos
                        try:
                            _call_status = self._commands()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _before_discard38 = _result
                            _result = self.__chars__('|')
                            _all39 = []
                            while 1:
                                _choice40 = self._pos
                                try:
                                    _call_status = self._IGNORE()
                                    _result = _call_status.result
                                    _error = self._combine_errors(_call_status.error, _error)
                                    _all39.append(_result)
                                except self._BacktrackException, _exc:
                                    _error = self._combine_errors(_error, _exc.error)
                                    self._pos = _choice40
                                    break
                            _result = _all39
                            _result = _before_discard38
                            _all33.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice37
                            break
                    _result = _all33
                    l = _result
                    _call_status = self._commands()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    last = _result
                    _result = (Nonterminal('or', l + [last]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice32
                _choice41 = self._pos
                try:
                    _call_status = self._commands()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice41
                    raise self._BacktrackException(_error)
                _call_status = self._commands()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._or_()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_commands(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def commands(self):
        return self._commands().result
    def _commands(self):
        _key = self._pos
        _status = self._dict_commands.get(_key, None)
        if _status is None:
            _status = self._dict_commands[_key] = self._Status_commands()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice42 = self._pos
                try:
                    _call_status = self._command()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    cmd = _result
                    _call_status = self._newline()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all43 = []
                    _call_status = self._command()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _before_discard44 = _result
                    _call_status = self._newline()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _result = _before_discard44
                    _all43.append(_result)
                    while 1:
                        _choice45 = self._pos
                        try:
                            _call_status = self._command()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _before_discard46 = _result
                            _call_status = self._newline()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _result = _before_discard46
                            _all43.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice45
                            break
                    _result = _all43
                    cmds = _result
                    _result = (Nonterminal('commands', [cmd] + cmds))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice42
                _choice47 = self._pos
                try:
                    _call_status = self._command()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice47
                    raise self._BacktrackException(_error)
                _call_status = self._command()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._commands()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_command(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def command(self):
        return self._command().result
    def _command(self):
        _key = self._pos
        _status = self._dict_command.get(_key, None)
        if _status is None:
            _status = self._dict_command[_key] = self._Status_command()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _call_status = self._simplecommand()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._command()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_simplecommand(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def simplecommand(self):
        return self._simplecommand().result
    def _simplecommand(self):
        _key = self._pos
        _status = self._dict_simplecommand.get(_key, None)
        if _status is None:
            _status = self._dict_simplecommand[_key] = self._Status_simplecommand()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice48 = self._pos
                try:
                    _call_status = self._return_()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice48
                _choice49 = self._pos
                try:
                    _call_status = self._if_()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice49
                _choice50 = self._pos
                try:
                    _call_status = self._named_command()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice50
                _choice51 = self._pos
                try:
                    _call_status = self._repetition()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice51
                _choice52 = self._pos
                try:
                    _call_status = self._negation()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice52
                    raise self._BacktrackException(_error)
                _call_status = self._negation()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._simplecommand()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_return_(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def return_(self):
        return self._return_().result
    def _return_(self):
        _key = self._pos
        _status = self._dict_return_.get(_key, None)
        if _status is None:
            _status = self._dict_return_[_key] = self._Status_return_()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self.__chars__('return')
            _all53 = []
            while 1:
                _choice54 = self._pos
                try:
                    _call_status = self._SPACE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all53.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice54
                    break
            _result = _all53
            _call_status = self._PYTHONCODE()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            code = _result
            _all55 = []
            while 1:
                _choice56 = self._pos
                try:
                    _call_status = self._IGNORE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all55.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice56
                    break
            _result = _all55
            _result = (Nonterminal('return', [code]))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._return_()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_if_(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def if_(self):
        return self._if_().result
    def _if_(self):
        _key = self._pos
        _status = self._dict_if_.get(_key, None)
        if _status is None:
            _status = self._dict_if_[_key] = self._Status_if_()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _result = self.__chars__('do')
            _call_status = self._newline()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            _call_status = self._command()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            cmd = _result
            _all57 = []
            while 1:
                _choice58 = self._pos
                try:
                    _call_status = self._SPACE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all57.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice58
                    break
            _result = _all57
            _result = self.__chars__('if')
            _all59 = []
            while 1:
                _choice60 = self._pos
                try:
                    _call_status = self._SPACE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all59.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice60
                    break
            _result = _all59
            _call_status = self._PYTHONCODE()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            condition = _result
            _result = (Nonterminal('if', [cmd, condition]))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._if_()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_commandchain(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def commandchain(self):
        return self._commandchain().result
    def _commandchain(self):
        _key = self._pos
        _status = self._dict_commandchain.get(_key, None)
        if _status is None:
            _status = self._dict_commandchain[_key] = self._Status_commandchain()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _all61 = []
            _call_status = self._simplecommand()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            _all61.append(_result)
            while 1:
                _choice62 = self._pos
                try:
                    _call_status = self._simplecommand()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all61.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice62
                    break
            _result = _all61
            result = _result
            _result = (Nonterminal('commands', result))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._commandchain()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_named_command(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def named_command(self):
        return self._named_command().result
    def _named_command(self):
        _key = self._pos
        _status = self._dict_named_command.get(_key, None)
        if _status is None:
            _status = self._dict_named_command[_key] = self._Status_named_command()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _call_status = self._NAME()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            name = _result
            _all63 = []
            while 1:
                _choice64 = self._pos
                try:
                    _call_status = self._SPACE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all63.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice64
                    break
            _result = _all63
            _result = self.__chars__('=')
            _all65 = []
            while 1:
                _choice66 = self._pos
                try:
                    _call_status = self._SPACE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all65.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice66
                    break
            _result = _all65
            _call_status = self._command()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            cmd = _result
            _result = (Nonterminal('named_command', [name, cmd]))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._named_command()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_repetition(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def repetition(self):
        return self._repetition().result
    def _repetition(self):
        _key = self._pos
        _status = self._dict_repetition.get(_key, None)
        if _status is None:
            _status = self._dict_repetition[_key] = self._Status_repetition()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice67 = self._pos
                try:
                    _call_status = self._enclosed()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    what = _result
                    _all68 = []
                    while 1:
                        _choice69 = self._pos
                        try:
                            _call_status = self._SPACE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all68.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice69
                            break
                    _result = _all68
                    _result = self.__chars__('?')
                    _all70 = []
                    while 1:
                        _choice71 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all70.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice71
                            break
                    _result = _all70
                    _result = (Nonterminal('maybe', [what]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice67
                _choice72 = self._pos
                try:
                    _call_status = self._enclosed()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    what = _result
                    _all73 = []
                    while 1:
                        _choice74 = self._pos
                        try:
                            _call_status = self._SPACE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all73.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice74
                            break
                    _result = _all73
                    while 1:
                        _error = None
                        _choice75 = self._pos
                        try:
                            _result = self.__chars__('*')
                            break
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice75
                        _choice76 = self._pos
                        try:
                            _result = self.__chars__('+')
                            break
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice76
                            raise self._BacktrackException(_error)
                        _result = self.__chars__('+')
                        break
                    repetition = _result
                    _all77 = []
                    while 1:
                        _choice78 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all77.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice78
                            break
                    _result = _all77
                    _result = (Nonterminal('repetition', [repetition, what]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice72
                    raise self._BacktrackException(_error)
                _call_status = self._enclosed()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                what = _result
                _all79 = []
                while 1:
                    _choice80 = self._pos
                    try:
                        _call_status = self._SPACE()
                        _result = _call_status.result
                        _error = self._combine_errors(_call_status.error, _error)
                        _all79.append(_result)
                    except self._BacktrackException, _exc:
                        _error = self._combine_errors(_error, _exc.error)
                        self._pos = _choice80
                        break
                _result = _all79
                while 1:
                    _error = None
                    _choice81 = self._pos
                    try:
                        _result = self.__chars__('*')
                        break
                    except self._BacktrackException, _exc:
                        _error = self._combine_errors(_error, _exc.error)
                        self._pos = _choice81
                    _choice82 = self._pos
                    try:
                        _result = self.__chars__('+')
                        break
                    except self._BacktrackException, _exc:
                        _error = self._combine_errors(_error, _exc.error)
                        self._pos = _choice82
                        raise self._BacktrackException(_error)
                    _result = self.__chars__('+')
                    break
                repetition = _result
                _all83 = []
                while 1:
                    _choice84 = self._pos
                    try:
                        _call_status = self._IGNORE()
                        _result = _call_status.result
                        _error = self._combine_errors(_call_status.error, _error)
                        _all83.append(_result)
                    except self._BacktrackException, _exc:
                        _error = self._combine_errors(_error, _exc.error)
                        self._pos = _choice84
                        break
                _result = _all83
                _result = (Nonterminal('repetition', [repetition, what]))
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._repetition()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_negation(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def negation(self):
        return self._negation().result
    def _negation(self):
        _key = self._pos
        _status = self._dict_negation.get(_key, None)
        if _status is None:
            _status = self._dict_negation[_key] = self._Status_negation()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice85 = self._pos
                try:
                    _result = self.__chars__('!')
                    _all86 = []
                    while 1:
                        _choice87 = self._pos
                        try:
                            _call_status = self._SPACE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all86.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice87
                            break
                    _result = _all86
                    _call_status = self._negation()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    what = _result
                    _all88 = []
                    while 1:
                        _choice89 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all88.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice89
                            break
                    _result = _all88
                    _result = (Nonterminal('negation', [what]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice85
                _choice90 = self._pos
                try:
                    _call_status = self._enclosed()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice90
                    raise self._BacktrackException(_error)
                _call_status = self._enclosed()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._negation()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_enclosed(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def enclosed(self):
        return self._enclosed().result
    def _enclosed(self):
        _key = self._pos
        _status = self._dict_enclosed.get(_key, None)
        if _status is None:
            _status = self._dict_enclosed[_key] = self._Status_enclosed()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice91 = self._pos
                try:
                    _result = self.__chars__('<')
                    _all92 = []
                    while 1:
                        _choice93 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all92.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice93
                            break
                    _result = _all92
                    _call_status = self._primary()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    what = _result
                    _all94 = []
                    while 1:
                        _choice95 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all94.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice95
                            break
                    _result = _all94
                    _result = self.__chars__('>')
                    _all96 = []
                    while 1:
                        _choice97 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all96.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice97
                            break
                    _result = _all96
                    _result = (Nonterminal('exclusive', [what]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice91
                _choice98 = self._pos
                try:
                    _result = self.__chars__('[')
                    _all99 = []
                    while 1:
                        _choice100 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all99.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice100
                            break
                    _result = _all99
                    _call_status = self._or_()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    what = _result
                    _all101 = []
                    while 1:
                        _choice102 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all101.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice102
                            break
                    _result = _all101
                    _result = self.__chars__(']')
                    _all103 = []
                    while 1:
                        _choice104 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all103.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice104
                            break
                    _result = _all103
                    _result = (Nonterminal('ignore', [what]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice98
                _choice105 = self._pos
                try:
                    _before_discard106 = _result
                    _result = self.__chars__('(')
                    _all107 = []
                    while 1:
                        _choice108 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all107.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice108
                            break
                    _result = _all107
                    _result = _before_discard106
                    _call_status = self._or_()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _before_discard109 = _result
                    _result = self.__chars__(')')
                    _all110 = []
                    while 1:
                        _choice111 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all110.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice111
                            break
                    _result = _all110
                    _result = _before_discard109
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice105
                _choice112 = self._pos
                try:
                    _call_status = self._primary()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice112
                    raise self._BacktrackException(_error)
                _call_status = self._primary()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._enclosed()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_primary(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def primary(self):
        return self._primary().result
    def _primary(self):
        _key = self._pos
        _status = self._dict_primary.get(_key, None)
        if _status is None:
            _status = self._dict_primary[_key] = self._Status_primary()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice113 = self._pos
                try:
                    _call_status = self._call()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice113
                _choice114 = self._pos
                try:
                    _call_status = self._REGEX()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _before_discard115 = _result
                    _all116 = []
                    while 1:
                        _choice117 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all116.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice117
                            break
                    _result = _all116
                    _result = _before_discard115
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice114
                _choice118 = self._pos
                try:
                    _call_status = self._QUOTE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _before_discard119 = _result
                    _all120 = []
                    while 1:
                        _choice121 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all120.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice121
                            break
                    _result = _all120
                    _result = _before_discard119
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice118
                    raise self._BacktrackException(_error)
                _call_status = self._QUOTE()
                _result = _call_status.result
                _error = self._combine_errors(_call_status.error, _error)
                _before_discard122 = _result
                _all123 = []
                while 1:
                    _choice124 = self._pos
                    try:
                        _call_status = self._IGNORE()
                        _result = _call_status.result
                        _error = self._combine_errors(_call_status.error, _error)
                        _all123.append(_result)
                    except self._BacktrackException, _exc:
                        _error = self._combine_errors(_error, _exc.error)
                        self._pos = _choice124
                        break
                _result = _all123
                _result = _before_discard122
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._primary()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_call(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def call(self):
        return self._call().result
    def _call(self):
        _key = self._pos
        _status = self._dict_call.get(_key, None)
        if _status is None:
            _status = self._dict_call[_key] = self._Status_call()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            _call_status = self._NAME()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            x = _result
            _call_status = self._arguments()
            _result = _call_status.result
            _error = self._combine_errors(_call_status.error, _error)
            args = _result
            _all125 = []
            while 1:
                _choice126 = self._pos
                try:
                    _call_status = self._IGNORE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    _all125.append(_result)
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice126
                    break
            _result = _all125
            _result = (Nonterminal("call", [x, args]))
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._call()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    class _Status_arguments(_Status):
        def __init__(self):
            self.pos = 0
            self.error = None
            self.status = self.INPROGRESS
            self.result = None
    def arguments(self):
        return self._arguments().result
    def _arguments(self):
        _key = self._pos
        _status = self._dict_arguments.get(_key, None)
        if _status is None:
            _status = self._dict_arguments[_key] = self._Status_arguments()
        elif _status.status == _status.NORMAL:
            self._pos = _status.pos
            return _status
        elif _status.status == _status.ERROR:
            raise self._BacktrackException(_status.error)
        elif (_status.status == _status.INPROGRESS or
              _status.status == _status.LEFTRECURSION):
            _status.status = _status.LEFTRECURSION
            if _status.result is not None:
                self._pos = _status.pos
                return _status
            else:
                raise self._BacktrackException(None)
        elif _status.status == _status.SOMESOLUTIONS:
            _status.status = _status.INPROGRESS
        _startingpos = self._pos
        try:
            _result = None
            _error = None
            while 1:
                _error = None
                _choice127 = self._pos
                try:
                    _result = self.__chars__('(')
                    _all128 = []
                    while 1:
                        _choice129 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all128.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice129
                            break
                    _result = _all128
                    _all130 = []
                    while 1:
                        _choice131 = self._pos
                        try:
                            _call_status = self._PYTHONCODE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _before_discard132 = _result
                            _all133 = []
                            while 1:
                                _choice134 = self._pos
                                try:
                                    _call_status = self._IGNORE()
                                    _result = _call_status.result
                                    _error = self._combine_errors(_call_status.error, _error)
                                    _all133.append(_result)
                                except self._BacktrackException, _exc:
                                    _error = self._combine_errors(_error, _exc.error)
                                    self._pos = _choice134
                                    break
                            _result = _all133
                            _result = self.__chars__(',')
                            _all135 = []
                            while 1:
                                _choice136 = self._pos
                                try:
                                    _call_status = self._IGNORE()
                                    _result = _call_status.result
                                    _error = self._combine_errors(_call_status.error, _error)
                                    _all135.append(_result)
                                except self._BacktrackException, _exc:
                                    _error = self._combine_errors(_error, _exc.error)
                                    self._pos = _choice136
                                    break
                            _result = _all135
                            _result = _before_discard132
                            _all130.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice131
                            break
                    _result = _all130
                    args = _result
                    _call_status = self._PYTHONCODE()
                    _result = _call_status.result
                    _error = self._combine_errors(_call_status.error, _error)
                    last = _result
                    _result = self.__chars__(')')
                    _all137 = []
                    while 1:
                        _choice138 = self._pos
                        try:
                            _call_status = self._IGNORE()
                            _result = _call_status.result
                            _error = self._combine_errors(_call_status.error, _error)
                            _all137.append(_result)
                        except self._BacktrackException, _exc:
                            _error = self._combine_errors(_error, _exc.error)
                            self._pos = _choice138
                            break
                    _result = _all137
                    _result = (Nonterminal("args", args + [last]))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice127
                _choice139 = self._pos
                try:
                    _result = (Nonterminal("args", []))
                    break
                except self._BacktrackException, _exc:
                    _error = self._combine_errors(_error, _exc.error)
                    self._pos = _choice139
                    raise self._BacktrackException(_error)
                _result = (Nonterminal("args", []))
                break
            if _status.status == _status.LEFTRECURSION:
                if _status.result is not None:
                    if _status.pos >= self._pos:
                        _status.status = _status.NORMAL
                        self._pos = _status.pos
                        return _status
                _status.pos = self._pos
                _status.status = _status.SOMESOLUTIONS
                _status.result = _result
                _status.error = _error
                self._pos = _startingpos
                return self._arguments()
            _status.status = _status.NORMAL
            _status.pos = self._pos
            _status.result = _result
            _status.error = _error
            return _status
        except self._BacktrackException, _exc:
            _status.pos = -1
            _status.result = None
            _error = self._combine_errors(_error, _exc.error)
            _status.error = _error
            _status.status = _status.ERROR
            raise self._BacktrackException(_error)
    def __init__(self, inputstream):
        self._dict_NAME = {}
        self._dict_SPACE = {}
        self._dict_COMMENT = {}
        self._dict_IGNORE = {}
        self._dict_newline = {}
        self._dict_REGEX = {}
        self._dict_QUOTE = {}
        self._dict_PYTHONCODE = {}
        self._dict_EOF = {}
        self._dict_file = {}
        self._dict_list = {}
        self._dict_production = {}
        self._dict_productionargs = {}
        self._dict_or_ = {}
        self._dict_commands = {}
        self._dict_command = {}
        self._dict_simplecommand = {}
        self._dict_return_ = {}
        self._dict_if_ = {}
        self._dict_commandchain = {}
        self._dict_named_command = {}
        self._dict_repetition = {}
        self._dict_negation = {}
        self._dict_enclosed = {}
        self._dict_primary = {}
        self._dict_call = {}
        self._dict_arguments = {}
        self._pos = 0
        self._inputstream = inputstream
    def _regex299149370(self):
        _choice140 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_299149370(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice140
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    def _regex1006631623(self):
        _choice141 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_1006631623(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice141
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    def _regex528667127(self):
        _choice142 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_528667127(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice142
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    def _regex291086639(self):
        _choice143 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_291086639(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice143
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    def _regex1074651696(self):
        _choice144 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_1074651696(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice144
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    def _regex1124192327(self):
        _choice145 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_1124192327(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice145
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    def _regex1979538501(self):
        _choice146 = self._pos
        _runner = self._Runner(self._inputstream, self._pos)
        _i = _runner.recognize_1979538501(self._pos)
        if _runner.last_matched_state == -1:
            self._pos = _choice146
            raise self._BacktrackException
        _upto = _runner.last_matched_index + 1
        _result = self._inputstream[self._pos: _upto]
        self._pos = _upto
        return _result
    class _Runner(object):
        def __init__(self, text, pos):
            self.text = text
            self.pos = pos
            self.last_matched_state = -1
            self.last_matched_index = -1
            self.state = -1
        def recognize_299149370(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    runner.last_matched_index = i - 1
                    runner.last_matched_state = state
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return i
                    if char == ' ':
                        state = 1
                    elif char == '\n':
                        state = 2
                    else:
                        break
                if state == 1:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return ~i
                    if char == ' ':
                        state = 1
                        continue
                    elif char == '\n':
                        state = 2
                    else:
                        break
                if state == 2:
                    runner.last_matched_index = i - 1
                    runner.last_matched_state = state
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 2
                        return i
                    if char == '\n':
                        state = 2
                        continue
                    elif char == ' ':
                        state = 2
                        continue
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
        def recognize_1006631623(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return ~i
                    if char == '`':
                        state = 1
                    else:
                        break
                if state == 1:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return ~i
                    if '\x00' <= char <= '[':
                        state = 1
                        continue
                    elif ']' <= char <= '_':
                        state = 1
                        continue
                    elif 'a' <= char <= '\xff':
                        state = 1
                        continue
                    elif char == '\\':
                        state = 2
                    elif char == '`':
                        state = 3
                    else:
                        break
                if state == 2:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 2
                        return ~i
                    if '\x00' <= char <= '\xff':
                        state = 1
                        continue
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
        def recognize_528667127(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return ~i
                    if char == ' ':
                        state = 0
                        continue
                    elif char == '#':
                        state = 1
                    else:
                        break
                if state == 1:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return ~i
                    if '\x00' <= char <= '\t':
                        state = 1
                        continue
                    elif '\x0b' <= char <= '\xff':
                        state = 1
                        continue
                    elif char == '\n':
                        state = 2
                    else:
                        break
                if state == 2:
                    runner.last_matched_index = i - 1
                    runner.last_matched_state = state
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 2
                        return i
                    if char == ' ':
                        state = 0
                        continue
                    elif char == '#':
                        state = 1
                        continue
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
        def recognize_291086639(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return ~i
                    if char == '{':
                        state = 1
                    else:
                        break
                if state == 1:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return ~i
                    if '\x00' <= char <= '\t':
                        state = 1
                        continue
                    elif '\x0b' <= char <= '|':
                        state = 1
                        continue
                    elif '~' <= char <= '\xff':
                        state = 1
                        continue
                    elif char == '}':
                        state = 2
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
        def recognize_1074651696(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return ~i
                    if 'A' <= char <= 'Z':
                        state = 1
                    elif char == '_':
                        state = 1
                    elif 'a' <= char <= 'z':
                        state = 1
                    else:
                        break
                if state == 1:
                    runner.last_matched_index = i - 1
                    runner.last_matched_state = state
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return i
                    if '0' <= char <= '9':
                        state = 1
                        continue
                    elif 'A' <= char <= 'Z':
                        state = 1
                        continue
                    elif char == '_':
                        state = 1
                        continue
                    elif 'a' <= char <= 'z':
                        state = 1
                        continue
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
        def recognize_1124192327(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return ~i
                    if char == "'":
                        state = 1
                    else:
                        break
                if state == 1:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return ~i
                    if '\x00' <= char <= '&':
                        state = 1
                        continue
                    elif '(' <= char <= '\xff':
                        state = 1
                        continue
                    elif char == "'":
                        state = 2
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
        def recognize_1979538501(runner, i):
            assert i >= 0
            input = runner.text
            state = 0
            while 1:
                if state == 0:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 0
                        return ~i
                    if char == '#':
                        state = 1
                    elif char == '\t':
                        state = 2
                    elif char == '\n':
                        state = 2
                    elif char == ' ':
                        state = 2
                    else:
                        break
                if state == 1:
                    if i < len(input):
                        char = input[i]
                        i += 1
                    else:
                        runner.state = 1
                        return ~i
                    if '\x00' <= char <= '\t':
                        state = 1
                        continue
                    elif '\x0b' <= char <= '\xff':
                        state = 1
                        continue
                    elif char == '\n':
                        state = 2
                    else:
                        break
                runner.last_matched_state = state
                runner.last_matched_index = i - 1
                runner.state = state
                if i == len(input):
                    return i
                else:
                    return ~i
                break
            runner.state = state
            return ~i
class PyPackratSyntaxParser(PackratParser):
    def __init__(self, stream):
        self.init_parser(stream)
forbidden = dict.fromkeys(("__weakref__ __doc__ "
                           "__dict__ __module__").split())
initthere = "__init__" in PyPackratSyntaxParser.__dict__
for key, value in Parser.__dict__.iteritems():
    if key not in PyPackratSyntaxParser.__dict__ and key not in forbidden:
        setattr(PyPackratSyntaxParser, key, value)
PyPackratSyntaxParser.init_parser = Parser.__init__.im_func
