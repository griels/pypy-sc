from pypy.lang.smalltalk import shadow

def bootstrap_class(instsize, w_superclass=None, w_metaclass=None,
                    name='?', format=shadow.POINTERS, varsized=False):
    from pypy.lang.smalltalk import model
    w_class = model.W_PointersObject(None, 0) # a dummy placeholder for testing
    s = shadow.ClassShadow(w_class)
    s.methoddict = {}
    if w_superclass is not None:
        s.s_superclass = w_superclass.as_class_get_shadow()
    if w_metaclass is not None:
        s.s_metaclass = w_metaclass.as_class_get_shadow()
    s.name = name
    s.instance_size = instsize
    s.instance_kind = format
    s.instance_varsized = varsized or format != shadow.POINTERS
    s.invalid = False
    w_class._shadow = s
    return w_class

# ___________________________________________________________________________
# Core Bootstrapping Objects

classtable = {}
def create_classtable():
    def define_core_cls(name, w_superclass, w_metaclass):
        assert name.startswith('w_')
        shadow = bootstrap_class(instsize=0,    # XXX
                                 w_superclass=w_superclass,
                                 w_metaclass=w_metaclass,
                                 name=name[2:])
        classtable[name] = shadow
        globals()[name] = shadow
        return shadow
    
    #    Class Name            Super class name
    cls_nm_tbl = [
        ["w_Object",           "w_ProtoObject"],
        ["w_Behavior",         "w_Object"],
        ["w_ClassDescription", "w_Behavior"],
        ["w_Class",            "w_ClassDescription"],
        ["w_Metaclass",        "w_ClassDescription"],
        ]
    define_core_cls("w_ProtoObjectClass", None, None)
    define_core_cls("w_ProtoObject", None, w_ProtoObjectClass)
    for (cls_nm, super_cls_nm) in cls_nm_tbl:
        meta_nm = cls_nm + "Class"
        meta_super_nm = super_cls_nm + "Class"
        w_metacls = define_core_cls(meta_nm, classtable[meta_super_nm], None)
        define_core_cls(cls_nm, classtable[super_cls_nm], w_metacls)
    w_ProtoObjectClass.as_class_get_shadow().s_superclass = \
        w_Class.as_class_get_shadow()
    # at this point, all classes that still lack a w_metaclass are themselves
    # metaclasses
    for nm, w_cls_obj in classtable.items():
        s = w_cls_obj.as_class_get_shadow()
        if s.s_metaclass is None:
            s.s_metaclass = w_Metaclass.as_class_get_shadow()
create_classtable()

# ___________________________________________________________________________
# Other classes

def define_cls(cls_nm, supercls_nm, instvarsize=0, format=shadow.POINTERS):
    assert cls_nm.startswith("w_")
    meta_nm = cls_nm + "Class"
    meta_super_nm = supercls_nm + "Class"
    w_meta_cls = globals()[meta_nm] = classtable[meta_nm] = \
                 bootstrap_class(0,   # XXX
                                 classtable[meta_super_nm],
                                 w_Metaclass,
                                 name=meta_nm[2:])
    w_cls = globals()[cls_nm] = classtable[cls_nm] = \
                 bootstrap_class(instvarsize,
                                 classtable[supercls_nm],
                                 w_meta_cls,
                                 format=format,
                                 name=cls_nm[2:])

define_cls("w_Magnitude", "w_Object")
define_cls("w_Character", "w_Magnitude", instvarsize=1)
define_cls("w_Number", "w_Magnitude")
define_cls("w_Integer", "w_Number")
define_cls("w_SmallInteger", "w_Integer")
define_cls("w_Float", "w_Number", format=shadow.BYTES)
define_cls("w_Collection", "w_Object")
define_cls("w_SequencableCollection", "w_Collection")
define_cls("w_ArrayedCollection", "w_SequencableCollection")
define_cls("w_String", "w_ArrayedCollection")
define_cls("w_ByteString", "w_String", format=shadow.BYTES)
define_cls("w_UndefinedObject", "w_Object")
define_cls("w_Boolean", "w_Object")
define_cls("w_True", "w_Boolean")
define_cls("w_False", "w_Boolean")
define_cls("w_ByteArray", "w_ArrayedCollection", format=shadow.BYTES)
define_cls("w_CompiledMethod", "w_ByteArray", format=shadow.COMPILED_METHOD)
