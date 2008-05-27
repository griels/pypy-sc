
import ctypes
import ctypes.util
from ctypes_configure import configure
from ctypes import c_char_p, c_int, c_void_p, POINTER, c_char

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

info = configure.configure(CConfigure)
XML_Char = info['XML_Char']
XML_COMBINED_VERSION = info['XML_COMBINED_VERSION']
XML_Parser = ctypes.c_void_p # an opaque pointer
assert XML_Char is ctypes.c_char # this assumption is everywhere in
# cpython's expat, let's explode
XML_ParserCreate = lib.XML_ParserCreate
XML_ParserCreate.args = [ctypes.c_char_p]
XML_ParserCreate.result = XML_Parser
XML_ParserCreateNS = lib.XML_ParserCreateNS
XML_ParserCreateNS.args = [c_char_p, c_char]
XML_ParserCreateNS.result = XML_Parser
XML_Parse = lib.XML_Parse
XML_Parse.args = [XML_Parser, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
XML_Parse.result = ctypes.c_int
currents = ['CurrentLineNumber', 'CurrentColumnNumber',
            'CurrentByteIndex']
for name in currents:
    func = getattr(lib, 'XML_Get' + name)
    func.args = [XML_Parser]
    func.result = c_int

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
    pass

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
        self.storage = {}
        self.buffer = None
        self.buffer_size = 8192
        self.character_data_handler = None

    def _flush_character_buffer(self):
        if not self.buffer:
            return
        res = self._call_character_handler(''.join(self.buffer))
        self.buffer = []
        return res

    def _call_character_handler(self, buf):
        if self.character_data_handler:
            self.character_data_handler(buf)

    def Parse(self, data, is_final):
        res = XML_Parse(self.itself, data, len(data), is_final)
        if res == 0:
            xxx
        self._flush_character_buffer()
        return res

    def _sethandler(self, name, real_cb):
        setter = setters[name]
        try:
            cb = self.storage[(name, real_cb)]
        except KeyError:
            cb = getattr(self, 'get_cb_for_%s' % name)(real_cb)
            self.storage[(name, real_cb)] = cb
        setter(self.itself, cb)

    def get_cb_for_StartElementHandler(self, real_cb):
        def StartElement(unused, name, attrs):
            # unpack name and attrs
            conv = self.conv
            self._flush_character_buffer()
            if self.specified_attributes:
                import pdb
                pdb.set_trace()
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
                if lgt > self.buffer_size:
                    self._call_character_handler(s[:lgt])
                    self.buffer = []
                else:
                    self.buffer.append(s[:lgt])
        CB = ctypes.CFUNCTYPE(None, c_void_p, POINTER(c_char), c_int)
        return CB(CharacterData)

    def _new_callback_for_string_len(name, sign):
        def get_callback_for_(self, real_cb):
            def func(unused, s, len):
                self._flush_character_buffer()
                arg = self.conv(s[:len])
                real_cb(arg)
            func.func_name = name
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
            CB = ctypes.CFUNCTYPE(*sign)
            return CB(func)
        get_callback_for_.func_name = 'get_cb_for_' + name
        return get_callback_for_
    
    for name, num in [
        ('EndElementHandler', 1),
        ('ProcessingInstructionHandler', 2),
        ('UnparsedEntityDeclHandler', 5),
        ('NotationDeclHandler', 4),
        ('StartNamespaceDeclHandler', 2),
        ('EndNamespaceDeclHandler', 1),
        ('CommentHandler', 1),
        ('StartCdataSectionHandler', 0),
        ('EndCdataSectionHandler', 0)]:
        sign = [None, c_void_p] + [c_char_p] * num
        name = 'get_cb_for_' + name
        locals()[name] = _new_callback_for_starargs(name, sign)

    def conv_unicode(self, s):
        if s is None:
            return s
        return s.decode(self.encoding)

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
        elif name == 'namespace_prefixes':
            xxx
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

    def __getattr__(self, name):
        if name == 'buffer_text':
            return self.buffer is not None
        elif name in currents:
            return getattr(lib, 'XML_Get' + name)(self.itself)
        return self.__dict__[name]

    def ParseFile(self, file):
        return self.Parse(file.read(), False)

def ErrorString(errno):
    xxx

def ParserCreate(encoding=None, namespace_separator=None):
    if (not isinstance(namespace_separator, str) and
        not namespace_separator is None):
        raise TypeError("ParserCreate() argument 2 must be string or None, not %s" % namespace_separator.__class__.__name__)
    if namespace_separator is not None:
        if len(namespace_separator) > 1:
            raise ValueError('namespace_separator must be at most one character, omitted, or None')
        if len(namespace_separator) == 0:
            namespace_separator = None
    return XMLParserType(encoding, namespace_separator)
