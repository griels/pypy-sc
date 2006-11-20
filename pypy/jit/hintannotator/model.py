from pypy.annotation import model as annmodel
from pypy.annotation.pairtype import pair, pairtype
from pypy.jit.hintannotator.bookkeeper import getbookkeeper
from pypy.rpython.lltypesystem import lltype, lloperation

UNARY_OPERATIONS = """same_as hint getfield setfield getsubstruct getarraysize
                      cast_pointer
                      direct_call
                      indirect_call
                      int_is_true int_neg
                      uint_is_true
                      cast_int_to_char
                      cast_int_to_uint
                      cast_uint_to_int
                      cast_char_to_int
                      cast_bool_to_int
                      ptr_nonzero
                      ptr_iszero
                      debug_assert""".split()

BINARY_OPERATIONS = """int_add int_sub int_mul int_mod int_and int_rshift int_floordiv int_xor int_or
                       uint_add uint_sub uint_mul uint_mod uint_and uint_lshift uint_rshift uint_floordiv
                       char_gt char_lt char_le char_ge char_eq char_ne
                       int_gt int_lt int_le int_ge int_eq int_ne
                       uint_gt uint_lt uint_le uint_ge uint_eq uint_ne 
                       getarrayitem setarrayitem
                       getarraysubstruct
                       ptr_eq ptr_ne""".split()

class HintError(Exception):
    pass

class OriginFlags(object):

    fixed = False
    read_positions = None
    greenargs_cached = None
    is_call_result = False

    def __init__(self, bookkeeper=None, spaceop=None):
        self.bookkeeper = bookkeeper
        self.spaceop = spaceop

    def __repr__(self):
        if self.fixed:
            s = "fixed "
        else:
            s = ""
        return "<%sorigin>" % (s,)

    def read_fixed(self):
        if self.read_positions is None:
            self.read_positions = {}
        self.read_positions[getbookkeeper().position_key] = True
        return self.fixed

    def set_fixed(self):
        if not self.fixed:
            self.fixed = True
            if self.read_positions:
                annotator = getbookkeeper().annotator
                for p in self.read_positions:
                    annotator.reflowfromposition(p)

    def greenargs(self, frame=None):
        annotator = self.bookkeeper.annotator
        if frame is None:
            if self.greenargs_cached is not None:
                return self.greenargs_cached
            frame = GreenHandlerFrame(annotator)
        if self.is_call_result:
            return frame.greencallresult(self.spaceop)
        else:
            for v in self.spaceop.args:
                if not frame.greenvar(v):
                    return False
            return True


class GreenHandlerFrame(object):

    def __init__(self, annotator, parentframe=None):
        self.annotator = annotator
        self.parentframe = parentframe
        self.inputarg2actualarg = {}    # {origin: annotation}

    def greenvar(self, v):
        hs = self.annotator.binding(v)
        if isinstance(hs, SomeLLAbstractConstant) and len(hs.origins) == 1:
            [o] = hs.origins.keys()
            if o in self.inputarg2actualarg:
                hs_actual = self.inputarg2actualarg[o]
                return hs_actual.is_green(self.parentframe)
        return hs.is_green(self)

    def greencallresult(self, spaceop):
##        print spaceop
##        if str(spaceop.result) == 'v58':
##            import pdb; pdb.set_trace()
        args_hs = [self.annotator.binding(v) for v in spaceop.args]
        hs_result = self.annotator.binding(spaceop.result)
        if not isinstance(hs_result, SomeLLAbstractConstant):
            return False     # was generalized, e.g. to SomeLLAbstractVariable
        hs_f1 = args_hs.pop(0)
        fnobj = hs_f1.const._obj
        if (getattr(self.annotator.policy, 'oopspec', False) and
            hasattr(fnobj._callable, 'oopspec')):
            assert False     # XXX?

        input_args_hs = list(args_hs)
        bk = self.annotator.bookkeeper
        graph = bk.get_graph_for_call(fnobj.graph,
                                      hs_result.is_fixed(),
                                      input_args_hs)
        newframe = GreenHandlerFrame(self.annotator, parentframe=self)
        for hs_inp_arg, hs_arg in zip(input_args_hs, args_hs):
            if isinstance(hs_arg, SomeLLAbstractConstant):
                assert len(hs_inp_arg.origins) == 1
                [o] = hs_inp_arg.origins.keys()
                newframe.inputarg2actualarg[o] = hs_arg
        return newframe.greenvar(graph.getreturnvar())

# ____________________________________________________________


class SomeLLAbstractValue(annmodel.SomeObject):

    def __init__(self, T, deepfrozen=False):
        self.concretetype = T
        assert self.__class__ != SomeLLAbstractValue
        self.deepfrozen = deepfrozen

    def is_green(self, frame=None):
        return False


class SomeLLAbstractConstant(SomeLLAbstractValue):
    " color: dont know yet.. "

    def __init__(self, T, origins, eager_concrete=False, myorigin=None,
                 deepfrozen=False):
        SomeLLAbstractValue.__init__(self, T, deepfrozen)
        self.origins = origins
        self.eager_concrete = eager_concrete
        self.myorigin = myorigin
        assert myorigin is None or myorigin.spaceop is not None

    def fmt_origins(self, origins):
        counts = {}
        for o in origins:
            x = repr(o)
            counts[x] = counts.get(x, 0) + 1
        items = counts.items()
        items.sort()
        lst = []
        for key, count in items:
            s = ''
            if count > 1:
                s += '%d*' % count
            s += key
            lst.append(s)
        return '<%s>' % (', '.join(lst),)

    def fmt_myorigin(self, myorigin):
        if myorigin is None:
            return None
        else:
            return str(myorigin.spaceop.result)

    def is_fixed(self):
        for o in self.origins:
            if not o.fixed:
                return False
        return True

    def is_green(self, frame=None):
        return (self.is_fixed() or self.eager_concrete or
                self.concretetype is lltype.Void or
                (self.myorigin is not None and
                 self.myorigin.greenargs(frame)))

    def annotationcolor(self):
        """Compute the color of the variables with this annotation
        for the pygame viewer
        """
        if self.eager_concrete:
            return (0,100,0)     # green
        elif self.is_green():
            return (50,140,0)    # green-dark-cyan
        else:
            return None
    annotationcolor = property(annotationcolor)


class SomeLLAbstractVariable(SomeLLAbstractValue):
    " color: hopelessly red"
    pass


class SomeLLAbstractContainer(SomeLLAbstractValue):
    deepfrozen = False     # XXX for now

    def __init__(self, contentdef):
        self.contentdef = contentdef
        self.concretetype = lltype.Ptr(contentdef.T)

    def annotationcolor(self):
        """Compute the color of the variables with this annotation
        for the pygame viewer
        """
        if getattr(self.contentdef, 'degenerated', False):
            return None
        else:
            return (0,60,160)  # blue
    annotationcolor = property(annotationcolor)


setunion = annmodel.setunion

def setadd(set, newitem):
    if newitem not in set:
        set = set.copy()
        set[newitem] = True
    return set

def newset(set, *sets):
    set = set.copy()
    for s2 in sets:
        set.update(s2)
    return set

def reorigin(hs_v1, *deps_hs):
    """Make a copy of hs_v1 with its origins removed and replaced by myorigin().
    Optionally, the origins of other annotations can also be added.
    """
    if isinstance(hs_v1, SomeLLAbstractConstant):
        deps_origins = [hs_dep.origins for hs_dep in deps_hs
                        if isinstance(hs_dep, SomeLLAbstractConstant)]
        d = newset({getbookkeeper().myorigin(): True},
                   *deps_origins)
        return SomeLLAbstractConstant(hs_v1.concretetype, d,
                                      eager_concrete=hs_v1.eager_concrete,
                                      deepfrozen=hs_v1.deepfrozen)
    else:
        return hs_v1

def originalconcretetype(hs):
    if isinstance(hs, annmodel.SomeImpossibleValue):
        return lltype.Void
    else:
        return hs.concretetype

def deepunfreeze(hs):
    if hs.deepfrozen:
        hs1 = annmodel.SomeObject()
        hs1.__class__ = hs.__class__
        hs1.__dict__ = hs.__dict__.copy()
        hs1.deepfrozen = False
        hs = hs1
    return hs

# ____________________________________________________________
# operations

class __extend__(SomeLLAbstractValue):

    def same_as(hs_v1):
        return hs_v1

    def hint(hs_v1, hs_flags):
        if hs_flags.const.get('variable', False): # only for testing purposes!!!
            return SomeLLAbstractVariable(hs_v1.concretetype)
        if hs_flags.const.get('forget', False):
            # turn a variable to a constant
            origin = getbookkeeper().myorigin()
            return SomeLLAbstractConstant(hs_v1.concretetype, {origin: True})
        if hs_flags.const.get('promote', False):
            hs_concrete = SomeLLAbstractConstant(hs_v1.concretetype, {})
            hs_concrete.eager_concrete = True
            return hs_concrete 
        for name in ["reverse_split_queue", "global_merge_point"]:
            if hs_flags.const.get(name, False):
                return

        raise HintError("hint %s makes no sense on %r" % (hs_flags.const,
                                                          hs_v1))

    def debug_assert(hs_v1, *args_hs):
        pass

    def getfield(hs_v1, hs_fieldname):
        S = hs_v1.concretetype.TO
        FIELD_TYPE = getattr(S, hs_fieldname.const)
        return SomeLLAbstractVariable(FIELD_TYPE, hs_v1.deepfrozen)

    def setfield(hs_v1, hs_fieldname, hs_value):
        pass

    def getsubstruct(hs_v1, hs_fieldname):
        S = hs_v1.concretetype.TO
        FIELD_TYPE = getattr(S, hs_fieldname.const)
        return SomeLLAbstractVariable(lltype.Ptr(FIELD_TYPE), hs_v1.deepfrozen)

##    def getarrayitem(hs_v1, hs_index):
##        ARRAY = hs_v1.concretetype.TO
##        return SomeLLAbstractVariable(ARRAY.OF)

##    def setarrayitem(hs_v1, hs_index, hs_value):
##        pass

##    def getarraysubstruct(hs_v1, hs_index):
##        ARRAY = hs_v1.concretetype.TO
##        return SomeLLAbstractVariable(lltype.Ptr(ARRAY.OF))

    def indirect_call(hs_v1, *args_hs):
        hs_graph_list = args_hs[-1]
        args_hs = args_hs[:-1]
        assert hs_graph_list.is_constant()
        graph_list = hs_graph_list.const
        assert graph_list      # XXX for now

        bookkeeper = getbookkeeper()
        fixed = bookkeeper.myorigin().read_fixed()
        hs_res = bookkeeper.graph_family_call(graph_list, fixed, args_hs)

        if isinstance(hs_res, SomeLLAbstractConstant):
            hs_res.myorigin = bookkeeper.myorigin()

        # we need to make sure that hs_res does not become temporarily less
        # general as a result of calling another specialized version of the
        # function
        return annmodel.unionof(hs_res, bookkeeper.current_op_binding())


class __extend__(SomeLLAbstractConstant):

    def same_as(hs_c1):
        # this is here to prevent setup() below from adding a different
        # version of same_as()
        return hs_c1

    def hint(hs_c1, hs_flags):
        if hs_flags.const.get('concrete', False):
            for o in hs_c1.origins:
                o.set_fixed()
            hs_concrete = reorigin(hs_c1)
            hs_concrete.eager_concrete = True
            return hs_concrete 
        if hs_flags.const.get('forget', False):
            assert isinstance(hs_c1, SomeLLAbstractConstant)
            return reorigin(hs_c1)
        if hs_flags.const.get('deepfreeze', False):
            return SomeLLAbstractConstant(hs_c1.concretetype,
                                          hs_c1.origins,
                                          deepfrozen = True)
        return SomeLLAbstractValue.hint(hs_c1, hs_flags)

    def debug_assert(hs_c1, *args_hs):
        pass

    def direct_call(hs_f1, *args_hs):
        bookkeeper = getbookkeeper()
        fnobj = hs_f1.const._obj
        if (getattr(bookkeeper.annotator.policy, 'oopspec', False) and
            hasattr(fnobj._callable, 'oopspec')):
            # try to handle the call as a high-level operation
            try:
                return handle_highlevel_operation(bookkeeper, fnobj._callable,
                                                  *args_hs)
            except NotImplementedError:
                pass
        # don't try to annotate suggested_primitive graphs
        if getattr(getattr(fnobj, '_callable', None), 'suggested_primitive', False):
            return SomeLLAbstractVariable(lltype.typeOf(fnobj).RESULT)

        # normal call
        if not hasattr(fnobj, 'graph'):
            raise NotImplementedError("XXX call to externals or primitives")

        fixed = bookkeeper.myorigin().read_fixed()
        hs_res = bookkeeper.graph_call(fnobj.graph, fixed, args_hs)

        if isinstance(hs_res, SomeLLAbstractConstant):
            hs_res.myorigin = bookkeeper.myorigin()
            hs_res.myorigin.is_call_result = True
            
        # we need to make sure that hs_res does not become temporarily less
        # general as a result of calling another specialized version of the
        # function
        return annmodel.unionof(hs_res, bookkeeper.current_op_binding())

    def getfield(hs_c1, hs_fieldname):
        S = hs_c1.concretetype.TO
        FIELD_TYPE = getattr(S, hs_fieldname.const)
        if S._hints.get('immutable', False) or hs_c1.deepfrozen:
            origin = getbookkeeper().myorigin()
            d = setadd(hs_c1.origins, origin)
            return SomeLLAbstractConstant(FIELD_TYPE, d,
                                          eager_concrete=hs_c1.eager_concrete,
                                          myorigin=origin,
                                          deepfrozen=hs_c1.deepfrozen)
        else:
            return SomeLLAbstractVariable(FIELD_TYPE)

    def getsubstruct(hs_c1, hs_fieldname):
        S = hs_c1.concretetype.TO
        SUB_TYPE = getattr(S, hs_fieldname.const)
        origin = getbookkeeper().myorigin()
        d = setadd(hs_c1.origins, origin)
        return SomeLLAbstractConstant(lltype.Ptr(SUB_TYPE), d,
                                      myorigin=origin,
                                      deepfrozen=hs_c1.deepfrozen)    


class __extend__(SomeLLAbstractContainer):

    def setfield(hs_s1, hs_fieldname, hs_value):
        hs_s1.contentdef.generalize_field(hs_fieldname.const, hs_value)

    def getfield(hs_s1, hs_fieldname):
        return hs_s1.contentdef.read_field(hs_fieldname.const)

    getsubstruct = getfield

    def setarrayitem(hs_a1, hs_index, hs_value):
        hs_a1.contentdef.generalize_item(hs_value)

    def getarraysize(hs_a1):
        origin = getbookkeeper().myorigin()
        return SomeLLAbstractConstant(lltype.Signed, {origin: True})

    def cast_pointer(hs_s1):
        TO = getbookkeeper().current_op_concretetype()
        res_vstruct =hs_s1.contentdef.cast(TO)
        return SomeLLAbstractContainer(res_vstruct)

    def ptr_nonzero(hs_s1):
        return getbookkeeper().immutablevalue(True)

    def ptr_iszero(hs_s1):
        return getbookkeeper().immutablevalue(False)


# ____________________________________________________________
# binary

class __extend__(pairtype(SomeLLAbstractValue, SomeLLAbstractValue)):

    def getarrayitem((hs_v1, hs_v2)):
        return SomeLLAbstractVariable(hs_v1.concretetype.TO.OF,
                                      hs_v1.deepfrozen)

    def setarrayitem((hs_v1, hs_v2), hs_v3):
        pass

    def getarraysubstruct((hs_v1, hs_v2)):
        return SomeLLAbstractVariable(lltype.Ptr(hs_v1.concretetype.TO.OF),
                                      hs_v1.deepfrozen)

    def union((hs_v1, hs_v2)):
        if hs_v1.deepfrozen != hs_v2.deepfrozen:
            hs_v1 = deepunfreeze(hs_v1)
            hs_v2 = deepunfreeze(hs_v2)
            if hs_v1 == hs_v2:
                return hs_v1
        return pair(hs_v1, hs_v2).union_frozen_equal()

    def invalid_union((hs_v1, hs_v2)):
        raise annmodel.UnionError("%s %s don't mix" % (hs_v1, hs_v2))

    union_frozen_equal = invalid_union


class __extend__(pairtype(SomeLLAbstractVariable, SomeLLAbstractConstant),
                 pairtype(SomeLLAbstractConstant, SomeLLAbstractVariable)):

    def union_frozen_equal((hs_v1, hs_v2)):
        assert hs_v1.concretetype == hs_v2.concretetype
        if (getattr(hs_v1, 'eager_concrete', False) or
            getattr(hs_v2, 'eager_concrete', False)):
            pair(hs_v1, hs_v2).invalid_union()
        return SomeLLAbstractVariable(hs_v1.concretetype, hs_v1.deepfrozen)


class __extend__(pairtype(SomeLLAbstractConstant, SomeLLAbstractConstant)):

    def union_frozen_equal((hs_c1, hs_c2)):
        assert hs_c1.concretetype == hs_c2.concretetype
        d = newset(hs_c1.origins, hs_c2.origins)
        if hs_c1.myorigin is hs_c2.myorigin:
            myorigin = hs_c1.myorigin
        else:
            myorigin = None
        return SomeLLAbstractConstant(hs_c1.concretetype, d,
                                      eager_concrete = hs_c1.eager_concrete and
                                                       hs_c2.eager_concrete,
                                      myorigin = myorigin,
                                      deepfrozen = hs_c1.deepfrozen)


    def getarrayitem((hs_c1, hs_index)):
        A = hs_c1.concretetype.TO
        READ_TYPE = A.OF
        if A._hints.get('immutable', False) or hs_c1.deepfrozen:
            origin = getbookkeeper().myorigin()
            d = newset(hs_c1.origins, hs_index.origins, {origin: True})
            return SomeLLAbstractConstant(READ_TYPE, d,
                                          eager_concrete=hs_c1.eager_concrete,
                                          myorigin=origin,
                                          deepfrozen=hs_c1.deepfrozen)
        else:
            return SomeLLAbstractVariable(READ_TYPE)

    def getarraysubstruct((hs_c1, hs_index)):
        A = hs_c1.concretetype.TO
        SUB_TYPE = A.OF
        origin = getbookkeeper().myorigin()
        d = newset(hs_c1.origins, hs_index.origins, {origin: True})
        return SomeLLAbstractConstant(lltype.Ptr(SUB_TYPE), d,
                                      myorigin=origin,
                                      deepfrozen=hs_c1.deepfrozen)    
        
class __extend__(pairtype(SomeLLAbstractContainer, SomeLLAbstractContainer)):

    def union_frozen_equal((hs_cont1, hs_cont2)):
        contentdef = hs_cont1.contentdef.union(hs_cont2.contentdef)
        return SomeLLAbstractContainer(contentdef)   # XXX deepfrozen?

    def ptr_eq((hs_cont1, hs_cont2)):
        return SomeLLAbstractConstant(lltype.Bool, {})

    def ptr_ne((hs_cont1, hs_cont2)):
        return SomeLLAbstractConstant(lltype.Bool, {})


class __extend__(pairtype(SomeLLAbstractContainer, SomeLLAbstractValue)):
    def union_frozen_equal((hs_cont1, hs_val2)):
        hs_cont1.contentdef.mark_degenerated()
        assert hs_cont1.concretetype == hs_val2.concretetype
        return SomeLLAbstractVariable(hs_cont1.concretetype) # XXX deepfrozen?


class __extend__(pairtype(SomeLLAbstractValue, SomeLLAbstractContainer)):
    def union_frozen_equal((hs_val1, hs_cont2)):
        return pair(hs_cont2, hs_val1).union_frozen_equal()


class __extend__(pairtype(SomeLLAbstractContainer, SomeLLAbstractValue),
                 pairtype(SomeLLAbstractValue, SomeLLAbstractContainer)):

    def ptr_eq(_):
        return getbookkeeper().immutablevalue(False)

    def ptr_ne(_):
        return getbookkeeper().immutablevalue(True)


class __extend__(pairtype(SomeLLAbstractContainer, SomeLLAbstractConstant)):

    def getarrayitem((hs_a1, hs_index)):
        hs_res = hs_a1.contentdef.read_item()
        return reorigin(hs_res, hs_res, hs_index)

# ____________________________________________________________

def handle_highlevel_operation(bookkeeper, ll_func, *args_hs):
    if getattr(bookkeeper.annotator.policy, 'novirtualcontainer', False):
        # "blue variables" disabled, we just return a red var all the time.
        RESULT = bookkeeper.current_op_concretetype()
        if RESULT is lltype.Void:
            return None
        else:
            return SomeLLAbstractVariable(RESULT)

    # parse the oopspec and fill in the arguments
    operation_name, args = ll_func.oopspec.split('(', 1)
    assert args.endswith(')')
    args = args[:-1] + ','     # trailing comma to force tuple syntax
    argnames = ll_func.func_code.co_varnames[:len(args_hs)]
    d = dict(zip(argnames, args_hs))
    argtuple = eval(args, d)
    args_hs = []
    for hs in argtuple:
        if not isinstance(hs, SomeLLAbstractValue):
            hs = bookkeeper.immutablevalue(hs)
        args_hs.append(hs)
    # end of rather XXX'edly hackish parsing

    if operation_name == 'newlist':
        from pypy.jit.hintannotator.vlist import oop_newlist
        handler = oop_newlist
    else:
        # dispatch on the 'self' argument if it is virtual
        hs_self = args_hs[0]
        args_hs = args_hs[1:]
        type_name, operation_name = operation_name.split('.')
        if not isinstance(hs_self, SomeLLAbstractContainer):
            raise NotImplementedError
        if getattr(hs_self.contentdef, 'type_name', None) != type_name:
            raise NotImplementedError
        try:
            handler = getattr(hs_self.contentdef, 'oop_' + operation_name)
        except AttributeError:
            bookkeeper.warning('missing handler: oop_%s' % (operation_name,))
            raise NotImplementedError

    hs_result = handler(*args_hs)   # which may raise NotImplementedError
    return hs_result

# ____________________________________________________________
#
# Register automatically simple operations

def var_unary(hs_v, *rest_hs):
    RESTYPE = getbookkeeper().current_op_concretetype()
    return SomeLLAbstractVariable(RESTYPE)

def var_binary((hs_v1, hs_v2), *rest_hs):
    RESTYPE = getbookkeeper().current_op_concretetype()
    return SomeLLAbstractVariable(RESTYPE)

def const_unary(hs_c1):
    #XXX unsure hacks
    bk = getbookkeeper()
    origin = bk.myorigin()
    d = setadd(hs_c1.origins, origin)
    RESTYPE = bk.current_op_concretetype()
    return SomeLLAbstractConstant(RESTYPE, d,
                                  eager_concrete = hs_c1.eager_concrete,
                                  myorigin = origin)
                                  #deepfrozen = hs_c1.deepfrozen)

def const_binary((hs_c1, hs_c2)):
    #XXX unsure hacks
    bk = getbookkeeper()
    origin = bk.myorigin()
    d = newset(hs_c1.origins, hs_c2.origins, {origin: True})
    RESTYPE = bk.current_op_concretetype()
    return SomeLLAbstractConstant(RESTYPE, d,
                                  eager_concrete = hs_c1.eager_concrete or
                                                   hs_c2.eager_concrete,
                                  myorigin = origin)
                                  #deepfrozen = hs_c1.deepfrozen and hs_c2.deepfrozen)

def setup(oplist, ValueCls, var_fn, ConstantCls, const_fn):
    for name in oplist:
        llop = getattr(lloperation.llop, name)
        if not llop.sideeffects:
            if name not in ValueCls.__dict__:
                setattr(ValueCls, name, var_fn)
            if llop.canfold:
                if name not in ConstantCls.__dict__:
                    setattr(ConstantCls, name, const_fn)
setup(UNARY_OPERATIONS,
      SomeLLAbstractValue, var_unary,
      SomeLLAbstractConstant, const_unary)
setup(BINARY_OPERATIONS,
      pairtype(SomeLLAbstractValue, SomeLLAbstractValue), var_binary,
      pairtype(SomeLLAbstractConstant, SomeLLAbstractConstant), const_binary)
del setup
