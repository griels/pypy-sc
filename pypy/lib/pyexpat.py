
import ctypes
import ctypes.util
from ctypes_configure import configure
from ctypes import c_char_p, c_int, c_void_p, POINTER, c_char, c_wchar_p
import sys

lib = ctypes.CDLL(ctypes.util.find_library('expat'))

class CConfigure:
    _compilation_info_ = configure.ExternalCompilationInfo(
        includes = ['expat.h'],
        libraries = ['expat'],
        pre_include_lines = [
        '#define XML_COMBINED_VERSION (10000*XML_MAJOR_VERSION+100*XML_MINOR_VERSION+XML_MICRO_VERSION)'],
        )

    XML_Char = configure.SimpleType('XML_Char', ctypes.c_char)
    XML_COMBINED_VERSION = configure.ConstantInteger('XML_COMBINED_VERSION')
    for name in ['XML_PARAM_ENTITY_PARSING_NEVER',
                 'XML_PARAM_ENTITY_PARSING_UNLESS_STANDALONE',
                 'XML_PARAM_ENTITY_PARSING_ALWAYS']:
        locals()[name] = configure.ConstantInteger(name)

    XML_Encoding = configure.Struct('XML_Encoding',[
                                    ('data', c_void_p),
                                    ('convert', c_void_p),
                                    ('release', c_void_p),
                                    ('map', c_int * 256)])
    XML_Content = configure.Struct('XML_Content',[
        ('numchildren', c_int),
        ('children', c_void_p),
        ('name', c_char_p),
        ('type', c_int),
        ('quant', c_int),
    ])
    # this is insanely stupid
    XML_FALSE = configure.ConstantInteger('XML_FALSE')
    XML_TRUE = configure.ConstantInteger('XML_TRUE')

info = configure.configure(CConfigure)
for k, v in info.items():
    globals()[k] = v

XML_Content.children = POINTER(XML_Content)
XML_Parser = ctypes.c_void_p # an opaque pointer
assert XML_Char is ctypes.c_char # this assumption is everywhere in
# cpython's expat, let's explode

def declare_external(name, args, res):
    func = getattr(lib, name)
    func.args = args
    func.result = res
    globals()[name] = func

declare_external('XML_ParserCreate', [c_char_p], XML_Parser)
declare_external('XML_ParserCreateNS', [c_char_p, c_char], XML_Parser)
declare_external('XML_Parse', [XML_Parser, c_char_p, c_int, c_int], c_int)
currents = ['CurrentLineNumber', 'CurrentColumnNumber',
            'CurrentByteIndex']
for name in currents:
    func = getattr(lib, 'XML_Get' + name)
    func.args = [XML_Parser]
    func.result = c_int

declare_external('XML_SetReturnNSTriplet', [XML_Parser, c_int], None)
declare_external('XML_GetSpecifiedAttributeCount', [XML_Parser], c_int)
declare_external('XML_SetParamEntityParsing', [XML_Parser, c_int], None)
declare_external('XML_GetErrorCode', [XML_Parser], c_int)
declare_external('XML_StopParser', [XML_Parser, c_int], None)
lib.XML_ErrorString.args = [c_int]
lib.XML_ErrorString.result = c_int
declare_external('XML_SetBase', [XML_Parser, c_char_p], None)

declare_external('XML_SetUnknownEncodingHandler', [XML_Parser, c_void_p,
                                                   c_void_p], None)
declare_external('XML_FreeContentModel', [XML_Parser, POINTER(XML_Content)],
                 None)

def XML_ErrorString(code):
    res = lib.XML_ErrorString(code)
    p = c_char_p()
    p.value = res
    return p.value

handler_names = [
    'StartElement',
    'EndElement',
    'ProcessingInstruction',
    'CharacterData',
    'UnparsedEntityDecl',
    'NotationDecl',
    'StartNamespaceDecl',
    'EndNamespaceDecl',
    'Comment',
    'StartCdataSection',
    'EndCdataSection',
    'Default',
    'DefaultHandlerExpand',
    'NotStandalone',
    'ExternalEntityRef',
    'StartDoctypeDecl',
    'EndDoctypeDecl',
    'EntityDecl',
    'XmlDecl',
    'ElementDecl',
    'AttlistDecl',
    ]
if XML_COMBINED_VERSION >= 19504:
    handler_names.append('SkippedEntity')
setters = {}

for name in handler_names:
    if name == 'DefaultHandlerExpand':
        newname = 'XML_SetDefaultHandlerExpand'
    else:
        name += 'Handler'
        newname = 'XML_Set' + name
    cfunc = getattr(lib, newname)
    cfunc.args = [XML_Parser, ctypes.c_void_p]
    cfunc.result = ctypes.c_int
    setters[name] = cfunc

class ExpatError(Exception):
    def __str__(self):
        return self.s

error = ExpatError

class XMLParserType(object):
    specified_attributes = 0
    ordered_attributes = 0
    returns_unicode = 1
    encoding = 'utf-8'
    def __init__(self, encoding, namespace_separator):
        self.returns_unicode = 1
        if encoding:
            self.encoding = encoding
        if namespace_separator is None:
            self.itself = XML_ParserCreate(encoding)
        else:
            self.itself = XML_ParserCreateNS(encoding, ord(namespace_separator))
        if not self.itself:
            raise RuntimeError("Creating parser failed")
        self._set_unknown_encoding_handler()
        self.storage = {}
        self.buffer = None
        self.buffer_size = 8192
        self.character_data_handler = None
        self.intern = {}

    def _flush_character_buffer(self):
        if not self.buffer:
            return
        res = self._call_character_handler(''.join(self.buffer))
        self.buffer = []
        return res

    def _call_character_handler(self, buf):
        if self.character_data_handler:
            self.character_data_handler(buf)

    def _set_unknown_encoding_handler(self):
        def UnknownEncoding(encodingData, name, info_p):
            info = info_p.contents
            s = ''.join([chr(i) for i in range(256)])
            u = s.decode(self.encoding, 'replace')
            for i in range(len(u)):
                if u[i] == u'\xfffd':
                    info.map[i] = -1
                else:
                    info.map[i] = ord(u[i])
            info.data = None
            info.convert = None
            info.release = None
            return 1
        
        CB = ctypes.CFUNCTYPE(c_int, c_void_p, c_char_p, POINTER(XML_Encoding))
        cb = CB(UnknownEncoding)
        self._unknown_encoding_handler = (cb, UnknownEncoding)
        XML_SetUnknownEncodingHandler(self.itself, cb, None)

    def _set_error(self, code):
        e = ExpatError()
        e.code = code
        lineno = lib.XML_GetCurrentLineNumber(self.itself)
        colno = lib.XML_GetCurrentColumnNumber(self.itself)
        e.offset = colno
        e.lineno = lineno
        err = XML_ErrorString(code)[:200]
        e.s = "%s: line: %d, column: %d" % (err, lineno, colno)
        self._error = e

    def Parse(self, data, is_final=0):
        res = XML_Parse(self.itself, data, len(data), is_final)
        if res == 0:
            self._set_error(XML_GetErrorCode(self.itself))
            raise self.__exc_info[0], self.__exc_info[1], self.__exc_info[2]
        self._flush_character_buffer()
        return res

    def _sethandler(self, name, real_cb):
        setter = setters[name]
        try:
            cb = self.storage[(name, real_cb)]
        except KeyError:
            cb = getattr(self, 'get_cb_for_%s' % name)(real_cb)
            self.storage[(name, real_cb)] = cb
        except TypeError:
            # weellll...
            cb = getattr(self, 'get_cb_for_%s' % name)(real_cb)
        setter(self.itself, cb)

    def _wrap_cb(self, cb):
        def f(*args):
            try:
                return cb(*args)
            except:
                self.__exc_info = sys.exc_info()
                XML_StopParser(self.itself, XML_FALSE)
        return f

    def get_cb_for_StartElementHandler(self, real_cb):
        def StartElement(unused, name, attrs):
            # unpack name and attrs
            conv = self.conv
            self._flush_character_buffer()
            if self.specified_attributes:
                max = XML_GetSpecifiedAttributeCount(self.itself)
            else:
                max = 0
            while attrs[max]:
                max += 2 # copied
            if self.ordered_attributes:
                res = [attrs[i] for i in range(max)]
            else:
                res = {}
                for i in range(0, max, 2):
                    res[conv(attrs[i])] = conv(attrs[i + 1])
            real_cb(conv(name), res)
        StartElement = self._wrap_cb(StartElement)
        CB = ctypes.CFUNCTYPE(None, c_void_p, c_char_p, POINTER(c_char_p))
        return CB(StartElement)

    def get_cb_for_ExternalEntityRefHandler(self, real_cb):
        def ExternalEntity(unused, context, base, sysId, pubId):
            self._flush_character_buffer()
            conv = self.conv
            res = real_cb(conv(context), conv(base), conv(sysId),
                          conv(pubId))
            if res is None:
                return 0
            return res
        ExternalEntity = self._wrap_cb(ExternalEntity)
        CB = ctypes.CFUNCTYPE(c_int, c_void_p, *([c_char_p] * 4))
        return CB(ExternalEntity)

    def get_cb_for_CharacterDataHandler(self, real_cb):
        def CharacterData(unused, s, lgt):
            if self.buffer is None:
                self._call_character_handler(self.conv(s[:lgt]))
            else:
                if len(self.buffer) + lgt > self.buffer_size:
                    self._flush_character_buffer()
                    if self.character_data_handler is None:
                        return
                if lgt >= self.buffer_size:
                    self._call_character_handler(s[:lgt])
                    self.buffer = []
                else:
                    self.buffer.append(s[:lgt])
        CharacterData = self._wrap_cb(CharacterData)
        CB = ctypes.CFUNCTYPE(None, c_void_p, POINTER(c_char), c_int)
        return CB(CharacterData)

    def get_cb_for_NotStandaloneHandler(self, real_cb):
        def NotStandaloneHandler(unused):
            return real_cb()
        NotStandaloneHandler = self._wrap_cb(NotStandaloneHandler)
        CB = ctypes.CFUNCTYPE(c_int, c_void_p)
        return CB(NotStandaloneHandler)

    def get_cb_for_EntityDeclHandler(self, real_cb):
        def EntityDecl(unused, ename, is_param, value, value_len, base,
                       system_id, pub_id, not_name):
            self._flush_character_buffer()
            if not value:
                value = None
            else:
                value = value[:value_len]
            args = [ename, is_param, value, base, system_id,
                    pub_id, not_name]
            args = [self.conv(arg) for arg in args]
            real_cb(*args)
        EntityDecl = self._wrap_cb(EntityDecl)
        CB = ctypes.CFUNCTYPE(None, c_void_p, c_char_p, c_int, c_char_p,
                               c_int, c_char_p, c_char_p, c_char_p, c_char_p)
        return CB(EntityDecl)

    def _conv_content_model(self, model):
        children = tuple([self._conv_content_model(model.children[i])
                          for i in range(model.numchildren)])
        return (model.type, model.quant, self.conv(model.name),
                children)

    def get_cb_for_ElementDeclHandler(self, real_cb):
        def ElementDecl(unused, name, model):
            self._flush_character_buffer()
            modelobj = self._conv_content_model(model[0])
            real_cb(name, modelobj)
            XML_FreeContentModel(self.itself, model)

        ElementDecl = self._wrap_cb(ElementDecl)
        CB = ctypes.CFUNCTYPE(None, c_void_p, c_char_p, POINTER(XML_Content))
        return CB(ElementDecl)

    def _new_callback_for_string_len(name, sign):
        def get_callback_for_(self, real_cb):
            def func(unused, s, len):
                self._flush_character_buffer()
                arg = self.conv(s[:len])
                real_cb(arg)
            func.func_name = name
            func = self._wrap_cb(func)
            CB = ctypes.CFUNCTYPE(*sign)
            return CB(func)
        get_callback_for_.func_name = 'get_cb_for_' + name
        return get_callback_for_
    
    for name in ['DefaultHandlerExpand',
                 'DefaultHandler']:
        sign = [None, c_void_p, POINTER(c_char), c_int]
        name = 'get_cb_for_' + name
        locals()[name] = _new_callback_for_string_len(name, sign)

    def _new_callback_for_starargs(name, sign):
        def get_callback_for_(self, real_cb):
            def func(unused, *args):
                self._flush_character_buffer()
                args = [self.conv(arg) for arg in args]
                real_cb(*args)
            func.func_name = name
            func = self._wrap_cb(func)
            CB = ctypes.CFUNCTYPE(*sign)
            return CB(func)
        get_callback_for_.func_name = 'get_cb_for_' + name
        return get_callback_for_
    
    for name, num_or_sign in [
        ('EndElementHandler', 1),
        ('ProcessingInstructionHandler', 2),
        ('UnparsedEntityDeclHandler', 5),
        ('NotationDeclHandler', 4),
        ('StartNamespaceDeclHandler', 2),
        ('EndNamespaceDeclHandler', 1),
        ('CommentHandler', 1),
        ('StartCdataSectionHandler', 0),
        ('EndCdataSectionHandler', 0),
        ('StartDoctypeDeclHandler', [None, c_void_p] + [c_char_p] * 3 + [c_int]),
        ('XmlDeclHandler', [None, c_void_p, c_char_p, c_char_p, c_int]),
        ('AttlistDeclHandler', [None, c_void_p] + [c_char_p] * 4 + [c_int]),
        ('EndDoctypeDeclHandler', 0),
        ('SkippedEntityHandler', [None, c_void_p, c_char_p, c_int]),
        ]:
        if isinstance(num_or_sign, int):
            sign = [None, c_void_p] + [c_char_p] * num_or_sign
        else:
            sign = num_or_sign
        name = 'get_cb_for_' + name
        locals()[name] = _new_callback_for_starargs(name, sign)

    def conv_unicode(self, s):
        if s is None or isinstance(s, int):
            return s
        return s.decode(self.encoding, "strict")

    def __setattr__(self, name, value):
        # forest of ifs...
        if name in ['ordered_attributes',
                    'returns_unicode', 'specified_attributes']:
            if value:
                if name == 'returns_unicode':
                    self.conv = self.conv_unicode
                self.__dict__[name] = 1
            else:
                if name == 'returns_unicode':
                    self.conv = lambda s: s
                self.__dict__[name] = 0
        elif name == 'buffer_text':
            if value:
                self.buffer = []
            else:
                self._flush_character_buffer()
                self.buffer = None
        elif name == 'buffer_size':
            if not isinstance(value, int):
                raise TypeError("Expected int")
            if value <= 0:
                raise ValueError("Expected positive int")
            self.__dict__[name] = value
        elif name == 'namespace_prefixes':
            XML_SetReturnNSTriplet(self.itself, int(bool(value)))
        elif name in setters:
            if name == 'CharacterDataHandler':
                # XXX we need to flush buffer here
                self._flush_character_buffer()
                self.character_data_handler = value
            #print name
            #print value
            #print
            self._sethandler(name, value)
        else:
            self.__dict__[name] = value

    def SetParamEntityParsing(self, arg):
        XML_SetParamEntityParsing(self.itself, arg)

    def __getattr__(self, name):
        if name == 'buffer_text':
            return self.buffer is not None
        elif name in currents:
            return getattr(lib, 'XML_Get' + name)(self.itself)
        elif name == 'ErrorColumnNumber':
            return lib.XML_GetCurrentColumnNumber(self.itself)
        elif name == 'ErrorLineNumber':
            return lib.XML_GetCurrentLineNumber(self.itself)
        return self.__dict__[name]

    def ParseFile(self, file):
        return self.Parse(file.read(), False)

    def SetBase(self, base):
        XML_SetBase(self.itself, base)

def ErrorString(errno):
    xxx

def ParserCreate(encoding=None, namespace_separator=None, intern=None):
    if (not isinstance(encoding, str) and
        not encoding is None):
        raise TypeError("ParserCreate() argument 1 must be string or None, not %s" % encoding.__class__.__name__)
    if (not isinstance(namespace_separator, str) and
        not namespace_separator is None):
        raise TypeError("ParserCreate() argument 2 must be string or None, not %s" % namespace_separator.__class__.__name__)
    if namespace_separator is not None:
        if len(namespace_separator) > 1:
            raise ValueError('namespace_separator must be at most one character, omitted, or None')
        if len(namespace_separator) == 0:
            namespace_separator = None
    return XMLParserType(encoding, namespace_separator)
