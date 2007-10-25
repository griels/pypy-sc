import weakref
from pypy.lang.smalltalk import model, constants

class AbstractShadow(object):
    """A shadow is an optional extra bit of information that
    can be attached at run-time to any Smalltalk object.
    """
    def invalidate(self):
        """XXX This should get called whenever the base Smalltalk
        object changes."""

# ____________________________________________________________ 

POINTERS = 0
BYTES = 1
WORDS = 2
WEAK_POINTERS = 3
COMPILED_METHOD = 4

unwrap_int = model.unwrap_int

class MethodNotFound(Exception):
    pass

class ClassShadowError(Exception):
    pass

class ClassShadow(AbstractShadow):
    """A shadow for Smalltalk objects that are classes
    (i.e. used as the class of another Smalltalk object).
    """
    def __init__(self, w_self):
        self.w_self = w_self
        self.invalidate()

    def invalidate(self):
        self.methoddict = {}
        self.s_superclass = None     # the ClassShadow of the super class
        self.name = None
        self.invalid = True

    def check_for_updates(self):
        if self.invalid:
            self.update_shadow()

    def update_shadow(self):
        "Update the ClassShadow with data from the w_self class."
        from pypy.lang.smalltalk import objtable

        w_self = self.w_self
        # read and painfully decode the format
        classformat = unwrap_int(w_self.fetch(constants.CLASS_FORMAT_INDEX))
        # The classformat in Squeak, as an integer value, is:
        #    <2 bits=instSize//64><5 bits=cClass><4 bits=instSpec>
        #                                    <6 bits=instSize\\64><1 bit=0>
        # In Slang the value is read directly as a boxed integer, so that
        # the code gets a "pointer" whose bits are set as above, but
        # shifted one bit to the left and with the lowest bit set to 1.

        # compute the instance size (really the size, not the number of bytes)
        instsize_lo = (classformat >> 1) & 0x3F
        instsize_hi = (classformat >> (9 + 1)) & 0xC0
        self.instance_size = (instsize_lo | instsize_hi) - 1  # subtract hdr
        # decode the instSpec
        format = (classformat >> 7) & 15
        self.instance_varsized = format >= 2
        if format < 4:
            self.instance_kind = POINTERS
        elif format == 4:
            self.instance_kind = WEAK_POINTERS
        elif format == 6:
            self.instance_kind = WORDS
            if self.instance_size != 0:
                raise ClassShadowError("can't have both words and a non-zero "
                                       "base instance size")
        elif 8 <= format <= 11:
            self.instance_kind = BYTES
            if self.instance_size != 0:
                raise ClassShadowError("can't have both bytes and a non-zero "
                                       "base instance size")
        elif 12 <= format <= 15:
            self.instance_kind = COMPILED_METHOD
        else:
            raise ClassShadowError("unknown format %d" % (format,))
        # read the name
        if w_self.size() > constants.CLASS_NAME_INDEX:
            w_name = w_self.fetch(constants.CLASS_NAME_INDEX)
            if isinstance(w_name, model.W_BytesObject):
                self.name = w_name.as_string()
        # read the methoddict
        w_methoddict = w_self.fetch(constants.CLASS_METHODDICT_INDEX)
        w_values = w_methoddict.fetch(constants.METHODDICT_VALUES_INDEX)
        size = w_methoddict.size() - constants.METHODDICT_NAMES_INDEX
        for i in range(size):
            w_selector = w_methoddict.fetch(constants.METHODDICT_NAMES_INDEX+i)
            if w_selector is not objtable.w_nil:
                if not isinstance(w_selector, model.W_BytesObject):
                    raise ClassShadowError("bogus selector in method dict")
                selector = w_selector.as_string()
                w_compiledmethod = w_values.fetch(i)
                if not isinstance(w_compiledmethod, model.W_CompiledMethod):
                    raise ClassShadowError("the methoddict must contain "
                                           "CompiledMethods only for now")
                self.methoddict[selector] = w_compiledmethod
        # for the rest, we need to reset invalid to False already so
        # that cycles in the superclass and/or metaclass chains don't
        # cause infinite recursion
        self.invalid = False
        # read s_superclass
        w_superclass = w_self.fetch(constants.CLASS_SUPERCLASS_INDEX)
        if w_superclass is objtable.w_nil:
            self.s_superclass = None
        else:
            self.s_superclass = w_superclass.as_class_get_shadow()

    def new(self, extrasize=0):
        from pypy.lang.smalltalk import classtable
        w_cls = self.w_self
        
        if w_cls == classtable.w_BlockContext:
            return model.W_BlockContext(None, None, 0, 0)
        elif w_cls == classtable.w_MethodContext:
            return model.W_MethodContext(None, None, [])
        
        if self.instance_kind == POINTERS:
            return model.W_PointersObject(w_cls, self.instance_size+extrasize)
        elif self.instance_kind == WORDS:
            return model.W_WordsObject(w_cls, extrasize)
        elif self.instance_kind == BYTES:
            return model.W_BytesObject(w_cls, extrasize)
        else:
            raise NotImplementedError(self.instance_kind)

    # _______________________________________________________________
    # Methods for querying the format word, taken from the blue book:
    #
    # included so that we can reproduce code from the reference impl
    # more easily

    def ispointers(self):
        " True if instances of this class have data stored as pointers "
        XXX   # what about weak pointers?
        return self.format == POINTERS

    def iswords(self):
        " True if instances of this class have data stored as numerical words "
        XXX   # what about weak pointers?
        return self.format in (POINTERS, WORDS)

    def isbytes(self):
        " True if instances of this class have data stored as numerical bytes "
        return self.format == BYTES

    def isvariable(self):
        " True if instances of this class have indexed inst variables "
        return self.instance_varsized

    def instsize(self):
        " Number of named instance variables for each instance of this class "
        return self.instance_size

    def inherits_from(self, s_superclass):
        classshadow = self
        while classshadow is not None:
            if classshadow is s_superclass:
                return True
            classshadow = classshadow.s_superclass
        else:
            return False

    # _______________________________________________________________
    # Methods for querying the format word, taken from the blue book:

    def __repr__(self):
        return "<ClassShadow %s>" % (self.name or '?',)

    def lookup(self, selector):
        look_in_shadow = self
        while selector not in look_in_shadow.methoddict:
            look_in_shadow = look_in_shadow.s_superclass
            if look_in_shadow is None:
                raise MethodNotFound
        return look_in_shadow.methoddict[selector]

    def installmethod(self, selector, method):
        "NOT_RPYTHON"     # this is only for testing.
        assert isinstance(method, model.W_CompiledMethod)
        self.methoddict[selector] = method
        method.w_compiledin = self.w_self
