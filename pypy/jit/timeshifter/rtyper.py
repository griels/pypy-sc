import types
from pypy.objspace.flow import model as flowmodel
from pypy.annotation import model as annmodel
from pypy.annotation.pairtype import pair, pairtype
from pypy.rpython import annlowlevel
from pypy.rpython.rtyper import RPythonTyper, LowLevelOpList, TyperError
from pypy.rpython.rmodel import Repr, inputconst
from pypy.rpython.lltypesystem.rstr import string_repr
from pypy.rpython.typesystem import LowLevelTypeSystem
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.jit.hintannotator import model as hintmodel
from pypy.jit.hintannotator import container as hintcontainer
from pypy.jit.timeshifter import rtimeshift, rvalue, rcontainer

class HintTypeSystem(LowLevelTypeSystem):
    name = "hinttypesystem"

    offers_exceptiondata = False
    
    def perform_normalizations(self, hrtyper):
        from pypy.rpython import normalizecalls
        hannotator = hrtyper.annotator
        call_families = hannotator.bookkeeper.tsgraph_maximal_call_families
        while True:
            progress = False
            for callfamily in call_families.infos():
                graphs = callfamily.tsgraphs.keys()
                progress |= normalizecalls.normalize_calltable_row_annotation(
                    hannotator,
                    graphs)
            if not progress:
                break   # done

HintTypeSystem.instance = HintTypeSystem()

# ___________________________________________________________


def originalconcretetype(hs):
    if isinstance(hs, annmodel.SomeImpossibleValue):
        return lltype.Void
    else:
        return hs.concretetype

class HintRTyper(RPythonTyper):

    def __init__(self, hannotator, timeshifter):
        RPythonTyper.__init__(self, hannotator, 
                              type_system=HintTypeSystem.instance)
        self.green_reprs = PRECOMPUTED_GREEN_REPRS.copy()
        self.red_reprs = {}
        self.color_cache = {}
        self.timeshifter = timeshifter
        self.RGenOp = timeshifter.RGenOp

    originalconcretetype = staticmethod(originalconcretetype)

    def make_new_lloplist(self, block):
        return HintLowLevelOpList(self.timeshifter)

    def getgreenrepr(self, lowleveltype):
        try:
            return self.green_reprs[lowleveltype]
        except KeyError:
            r = GreenRepr(lowleveltype)
            self.green_reprs[lowleveltype] = r
            return r

    def getredrepr(self, lowleveltype):
        try:
            return self.red_reprs[lowleveltype]
        except KeyError:
            assert not isinstance(lowleveltype, lltype.ContainerType)
            redreprcls = RedRepr
            if isinstance(lowleveltype, lltype.Ptr):
                if isinstance(lowleveltype.TO, lltype.Struct):
                    redreprcls = RedStructRepr
            r = redreprcls(lowleveltype, self.timeshifter)
            self.red_reprs[lowleveltype] = r
            return r

    def gethscolor(self, hs):
        try:
            return self.color_cache[id(hs)]
        except KeyError:
            if hs.is_green():
                color = "green"
            else:
                color = "red"
            self.color_cache[id(hs)] = color
            return color

    def generic_translate_operation(self, hop, force=False):
        # detect constant-foldable all-green operations
        if not force and hop.spaceop.opname not in rtimeshift.FOLDABLE_OPS:
            return None
        green = True
        for r_arg in hop.args_r:
            green = green and isinstance(r_arg, GreenRepr)
        if green and isinstance(hop.r_result, GreenRepr):
            # Just generate the same operation in the timeshifted graph.
            hop.llops.append(hop.spaceop)
            return hop.spaceop.result
        else:
            print "RED op", hop.spaceop
            return None

    def default_translate_operation(self, hop):
        # by default, a red operation converts all its arguments to
        # genop variables, and emits a call to a helper that will generate
        # the same operation at run-time
        opdesc = rtimeshift.make_opdesc(hop)
        if opdesc.nb_args == 1:
            ll_generate = rtimeshift.ll_gen1
        elif opdesc.nb_args == 2:
            ll_generate = rtimeshift.ll_gen2
        ts = self.timeshifter
        c_opdesc = inputconst(lltype.Void, opdesc)
        s_opdesc = ts.rtyper.annotator.bookkeeper.immutablevalue(opdesc)
        v_jitstate = hop.llops.getjitstate()
        args_v = hop.inputargs(*[self.getredrepr(originalconcretetype(hs))
                                for hs in hop.args_s])
        args_s = [ts.s_RedBox] * len(args_v)
        return hop.llops.genmixlevelhelpercall(ll_generate,
                                               [s_opdesc, ts.s_JITState] + args_s,
                                               [c_opdesc, v_jitstate]    + args_v,
                                               ts.s_RedBox)

    def translate_op_hint(self, hop):
        # don't try to generate hint operations, just discard them
        hints = hop.args_v[-1].value
        if hints.get('forget', False):
            T = originalconcretetype(hop.args_s[0])
            v_redbox = hop.inputarg(self.getredrepr(T), arg=0)
            assert isinstance(hop.r_result, GreenRepr)
            ts = self.timeshifter
            c_T = hop.inputconst(lltype.Void, T)
            s_T = ts.rtyper.annotator.bookkeeper.immutablevalue(T)
            s_res = annmodel.lltype_to_annotation(T)
            return hop.llops.genmixlevelhelpercall(rvalue.ll_getvalue,
                                                   [ts.s_RedBox, s_T],
                                                   [v_redbox,    c_T],
                                                   s_res)
                                                   
        return hop.inputarg(hop.r_result, arg=0)

    def translate_op_debug_log_exc(self, hop): # don't timeshift debug_log_exc
        pass

    def translate_op_keepalive(self,hop):
        pass

    def translate_op_same_as(self, hop):
        [v] = hop.inputargs(hop.r_result)
        return v

    def translate_op_getfield(self, hop):
        if isinstance(hop.args_r[0], BlueRepr):
            return hop.args_r[0].timeshift_getfield(hop)
        ts = self.timeshifter
        if hop.args_v[0] == ts.cexcdata:
            # reading one of the exception boxes (exc_type or exc_value)
            fieldname = hop.args_v[1].value
            if fieldname.endswith('exc_type'):
                reader = rtimeshift.getexctypebox
            elif fieldname.endswith('exc_value'):
                reader = rtimeshift.getexcvaluebox
            else:
                raise Exception("getfield(exc_data, %r)" % (fieldname,))
            v_jitstate = hop.llops.getjitstate()
            return hop.llops.genmixlevelhelpercall(reader,
                                                   [ts.s_JITState],
                                                   [v_jitstate   ],
                                                   ts.s_RedBox)
        # non virtual case        
        PTRTYPE = originalconcretetype(hop.args_s[0])
        if PTRTYPE.TO._hints.get('immutable', False): # foldable if all green
            res = self.generic_translate_operation(hop, force=True)
            if res is not None:
                return res
            
        v_argbox, c_fieldname = hop.inputargs(self.getredrepr(PTRTYPE),
                                              green_void_repr)
        structdesc = rcontainer.StructTypeDesc(self.RGenOp, PTRTYPE.TO)
        fielddesc = structdesc.getfielddesc(c_fieldname.value)
        c_fielddesc = inputconst(lltype.Void, fielddesc)
        s_fielddesc = ts.rtyper.annotator.bookkeeper.immutablevalue(fielddesc)
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(rtimeshift.ll_gengetfield,
            [ts.s_JITState, s_fielddesc, ts.s_RedBox],
            [v_jitstate,    c_fielddesc, v_argbox   ],
            ts.s_RedBox)

    def translate_op_getarrayitem(self, hop):
        PTRTYPE = originalconcretetype(hop.args_s[0])
        if PTRTYPE.TO._hints.get('immutable', False): # foldable if all green
            res = self.generic_translate_operation(hop, force=True)
            if res is not None:
                return res

        ts = self.timeshifter
        v_argbox, v_index = hop.inputargs(self.getredrepr(PTRTYPE),
                                          self.getredrepr(lltype.Signed))
        fielddesc = rcontainer.ArrayFieldDesc(self.RGenOp, PTRTYPE.TO)
        c_fielddesc = inputconst(lltype.Void, fielddesc)
        s_fielddesc = ts.rtyper.annotator.bookkeeper.immutablevalue(fielddesc)
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(
            rtimeshift.ll_gengetarrayitem,
            [ts.s_JITState, s_fielddesc, ts.s_RedBox, ts.s_RedBox],
            [v_jitstate,    c_fielddesc, v_argbox,    v_index    ],
            ts.s_RedBox)

    def translate_op_getarraysize(self, hop):
        res = self.generic_translate_operation(hop, force=True)
        if res is not None:
            return res
        
        PTRTYPE = originalconcretetype(hop.args_s[0])
        ts = self.timeshifter
        [v_argbox] = hop.inputargs(self.getredrepr(PTRTYPE))
        
        fielddesc = rcontainer.ArrayFieldDesc(self.RGenOp, PTRTYPE.TO)
        c_fielddesc = inputconst(lltype.Void, fielddesc)
        s_fielddesc = ts.rtyper.annotator.bookkeeper.immutablevalue(fielddesc)
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(
            rtimeshift.ll_gengetarraysize,
            [ts.s_JITState, s_fielddesc, ts.s_RedBox],
            [v_jitstate,    c_fielddesc, v_argbox   ],
            ts.s_RedBox)


    def translate_op_setfield(self, hop):
        if isinstance(hop.args_r[0], BlueRepr):
            return hop.args_r[0].timeshift_setfield(hop)
        ts = self.timeshifter        
        PTRTYPE = originalconcretetype(hop.args_s[0])
        VALUETYPE = originalconcretetype(hop.args_s[2])
        if hop.args_v[0] == ts.cexcdata:
            # reading one of the exception boxes (exc_type or exc_value)
            fieldname = hop.args_v[1].value
            if fieldname.endswith('exc_type'):
                writer = rtimeshift.setexctypebox
            elif fieldname.endswith('exc_value'):
                writer = rtimeshift.setexcvaluebox
            else:
                raise Exception("setfield(exc_data, %r)" % (fieldname,))
            v_valuebox = hop.inputarg(self.getredrepr(VALUETYPE), arg=2)
            v_jitstate = hop.llops.getjitstate()
            hop.llops.genmixlevelhelpercall(writer,
                                            [ts.s_JITState, ts.s_RedBox],
                                            [v_jitstate,    v_valuebox ],
                                            annmodel.s_None)
            return
        # non virtual case ...
        v_destbox, c_fieldname, v_valuebox = hop.inputargs(self.getredrepr(PTRTYPE),
                                                           green_void_repr,
                                                           self.getredrepr(VALUETYPE)
                                                           )
        structdesc = rcontainer.StructTypeDesc(self.RGenOp, PTRTYPE.TO)
        fielddesc = structdesc.getfielddesc(c_fieldname.value)
        c_fielddesc = inputconst(lltype.Void, fielddesc)
        s_fielddesc = ts.rtyper.annotator.bookkeeper.immutablevalue(fielddesc)
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(rtimeshift.ll_gensetfield,
            [ts.s_JITState, s_fielddesc, ts.s_RedBox, ts.s_RedBox],
            [v_jitstate,    c_fielddesc, v_destbox,   v_valuebox],
            annmodel.s_None)

    def translate_op_setarrayitem(self, hop):
        PTRTYPE = originalconcretetype(hop.args_s[0])
        VALUETYPE = PTRTYPE.TO.OF
        ts = self.timeshifter
        v_argbox, v_index, v_valuebox= hop.inputargs(self.getredrepr(PTRTYPE),
                                                     self.getredrepr(lltype.Signed),
                                                     self.getredrepr(VALUETYPE))
        fielddesc = rcontainer.ArrayFieldDesc(self.RGenOp, PTRTYPE.TO)
        c_fielddesc = inputconst(lltype.Void, fielddesc)
        s_fielddesc = ts.rtyper.annotator.bookkeeper.immutablevalue(fielddesc)
        v_jitstate = hop.llops.getjitstate()
        hop.llops.genmixlevelhelpercall(rtimeshift.ll_gensetarrayitem,
            [ts.s_JITState, s_fielddesc, ts.s_RedBox, ts.s_RedBox, ts.s_RedBox],
            [v_jitstate,    c_fielddesc, v_argbox,    v_index    , v_valuebox ],
            ts.s_RedBox)

    def translate_op_getsubstruct(self, hop):
        ##if isinstance(hop.args_r[0], BlueRepr):
        ##    return hop.args_r[0].timeshift_getsubstruct(hop)
        ts = self.timeshifter
        PTRTYPE = originalconcretetype(hop.args_s[0])
        v_argbox, c_fieldname = hop.inputargs(self.getredrepr(PTRTYPE),
                                              green_void_repr)
        fielddesc = rcontainer.NamedFieldDesc(self.RGenOp, PTRTYPE,
                                              c_fieldname.value)
        c_fielddesc = inputconst(lltype.Void, fielddesc)
        s_fielddesc = ts.rtyper.annotator.bookkeeper.immutablevalue(fielddesc)
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(rtimeshift.ll_gengetsubstruct,
            [ts.s_JITState, s_fielddesc, ts.s_RedBox],
            [v_jitstate,    c_fielddesc, v_argbox   ],
            ts.s_RedBox)

    def translate_op_cast_pointer(self, hop):
        FROM_TYPE = originalconcretetype(hop.args_s[0])
        [v_argbox] = hop.inputargs(self.getredrepr(FROM_TYPE))
        return v_argbox

    def translate_op_malloc(self, hop):
        r_result = hop.r_result
        return r_result.create(hop)

    def translate_op_malloc_varsize(self, hop):
        ts = self.timeshifter
        assert isinstance(hop.r_result, RedRepr)
        PTRTYPE = originalconcretetype(hop.s_result)
        TYPE = PTRTYPE.TO
        if isinstance(TYPE, lltype.Struct):
            contdesc = rcontainer.StructTypeDesc(self.RGenOp, TYPE)
        else:
            contdesc = rcontainer.ArrayFieldDesc(self.RGenOp, TYPE)
        c_contdesc = inputconst(lltype.Void, contdesc)
        s_contdesc = ts.rtyper.annotator.bookkeeper.immutablevalue(contdesc)
        v_jitstate = hop.llops.getjitstate()
        v_size = hop.inputarg(self.getredrepr(lltype.Signed), arg=1)
        return hop.llops.genmixlevelhelpercall(rtimeshift.ll_genmalloc_varsize,
                   [ts.s_JITState, s_contdesc, ts.s_RedBox],
                   [v_jitstate,    c_contdesc, v_size     ], ts.s_RedBox)
        
        
    def translate_op_ptr_nonzero(self, hop, reverse=False):
        ts = self.timeshifter
        PTRTYPE = originalconcretetype(hop.args_s[0])
        v_argbox, = hop.inputargs(self.getredrepr(PTRTYPE))
        v_jitstate = hop.llops.getjitstate()
        c_reverse = hop.inputconst(lltype.Bool, reverse)
        return hop.llops.genmixlevelhelpercall(rtimeshift.ll_genptrnonzero,
            [ts.s_JITState, ts.s_RedBox, annmodel.SomeBool()],
            [v_jitstate,    v_argbox,    c_reverse          ],
            ts.s_RedBox)

    def translate_op_ptr_iszero(self, hop):
        return self.translate_op_ptr_nonzero(hop, reverse=True)


    def guess_call_kind(self, spaceop):
        if spaceop.opname == 'indirect_call':
            return 'red'  # for now
        assert spaceop.opname == 'direct_call'
        c_func = spaceop.args[0]
        fnobj = c_func.value._obj
        s_result = self.annotator.binding(spaceop.result)
        r_result = self.getrepr(s_result)
        if hasattr(fnobj._callable, 'oopspec'):
            return 'oopspec'
        elif (originalconcretetype(s_result) is not lltype.Void and
              isinstance(r_result, GreenRepr)):
            return 'green'
        else:
            return 'red'

    def translate_op_direct_call(self, hop):
        kind = self.guess_call_kind(hop.spaceop)
        meth = getattr(self, 'handle_%s_call' % (kind,))
        return meth(hop)

    def translate_op_indirect_call(self, hop):
        bk = self.annotator.bookkeeper
        ts = self.timeshifter
        v_jitstate = hop.llops.getjitstate()
        v_funcbox = hop.args_v[0]
        graph_list = hop.args_v[-1].value
        hop.r_s_pop(0)
        hop.r_s_pop()
        args_hs = hop.args_s[:]
        # fixed is always false here
        specialization_key = bk.specialization_key(False, args_hs)
        FUNC = ts.originalconcretetype(v_funcbox)

        mapper, TS_FUNC, args_r, tsgraphs = ts.get_timeshift_mapper(
            FUNC, specialization_key, graph_list)
        args_v = hop.inputargs(*args_r)

        v_tsfunc = hop.llops.genmixlevelhelpercall(mapper,
                                                   [ts.s_RedBox],
                                                   [v_funcbox],
                                                   annmodel.SomePtr(TS_FUNC))
        args_v[:0] = [v_tsfunc, v_jitstate]
        RESULT = v_tsfunc.concretetype.TO.RESULT
        args_v.append(hop.inputconst(lltype.Void, tsgraphs))
        v_newjitstate = hop.genop('indirect_call', args_v, RESULT)
        hop.llops.setjitstate(v_newjitstate)


    def translate_op_save_locals(self, hop):
        ts = self.timeshifter
        v_jitstate = hop.llops.getjitstate()
        v_boxes = ts.build_box_list(hop.llops, hop.args_v)
        hop.llops.genmixlevelhelpercall(rtimeshift.save_locals,
                                        [ts.s_JITState, ts.s_box_list],
                                        [v_jitstate,    v_boxes],
                                        annmodel.s_None)

    def translate_op_restore_local(self, hop):
        ts = self.timeshifter
        assert isinstance(hop.args_v[0], flowmodel.Constant)
        index = hop.args_v[0].value
        v_jitstate = hop.llops.getjitstate()
        return ts.read_out_box(hop.llops, v_jitstate, index)

    def translate_op_fetch_return(self, hop):
        ts = self.timeshifter
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(rtimeshift.getreturnbox,
                                               [ts.s_JITState],
                                               [v_jitstate   ],
                                               ts.s_RedBox)

    def handle_oopspec_call(self, hop):
        # special-cased call, for things like list methods
        from pypy.jit.timeshifter.oop import OopSpecDesc, Index

        c_func = hop.args_v[0]
        fnobj = c_func.value._obj
        oopspecdesc = OopSpecDesc(self, fnobj)
        hop.r_s_popfirstarg()

        args_v = []
        for obj in oopspecdesc.argtuple:
            if isinstance(obj, Index):
                hs = hop.args_s[obj.n]
                r_arg = self.getredrepr(originalconcretetype(hs))
                v = hop.inputarg(r_arg, arg=obj.n)
            else:
                v = hop.inputconst(self.getredrepr(lltype.typeOf(obj)), obj)
            args_v.append(v)

        # if the ll_handler() takes more arguments, it must be 'None' defaults.
        # Pass them as constant Nones.
        ts = self.timeshifter
        ll_handler = oopspecdesc.ll_handler
        missing_args = ((ll_handler.func_code.co_argcount - 2) -
                        len(oopspecdesc.argtuple))
        assert missing_args >= 0
        if missing_args > 0:
            assert (ll_handler.func_defaults[-missing_args:] ==
                    (None,) * missing_args)
            ll_None = lltype.nullptr(ts.r_RedBox.lowleveltype.TO)
            args_v.extend([hop.llops.genconst(ll_None)] * missing_args)

        args_s = [ts.s_RedBox] * len(args_v)
        RESULT = originalconcretetype(hop.s_result)
        if RESULT is lltype.Void:
            s_result = annmodel.s_None
        else:
            s_result = ts.s_RedBox

        s_oopspecdesc  = ts.s_OopSpecDesc
        ll_oopspecdesc = ts.annhelper.delayedconst(ts.r_OopSpecDesc,
                                                   oopspecdesc)
        c_oopspecdesc  = hop.llops.genconst(ll_oopspecdesc)
        v_jitstate = hop.llops.getjitstate()
        return hop.llops.genmixlevelhelpercall(ll_handler,
                                      [ts.s_JITState, s_oopspecdesc] + args_s,
                                      [v_jitstate,    c_oopspecdesc] + args_v,
                                      s_result)

    def handle_green_call(self, hop):
        # green-returning call, for now (XXX) we assume it's an
        # all-green function that we can just call
        for r_arg in hop.args_r:
            assert isinstance(r_arg, GreenRepr)
        v = hop.genop('direct_call', hop.args_v, hop.r_result.lowleveltype)
        return v

    def handle_red_call(self, hop):
        bk = self.annotator.bookkeeper
        ts = self.timeshifter
        v_jitstate = hop.llops.getjitstate()
        c_func = hop.args_v[0]
        fnobj = c_func.value._obj
        hop.r_s_popfirstarg()
        args_hs = hop.args_s[:]
        # fixed is always false here
        specialization_key = bk.specialization_key(False, args_hs)
        fnptr, args_r = ts.get_timeshifted_fnptr(fnobj.graph,
                                                 specialization_key)
        args_v = hop.inputargs(*args_r)
        args_v[:0] = [hop.llops.genconst(fnptr), v_jitstate]
        RESULT = lltype.typeOf(fnptr).TO.RESULT
        v_newjitstate = hop.genop('direct_call', args_v, RESULT)
        hop.llops.setjitstate(v_newjitstate)


class HintLowLevelOpList(LowLevelOpList):
    """Warning: the HintLowLevelOpList's rtyper is the *original*
    rtyper, while the HighLevelOp's rtyper is actually our HintRTyper...
    """
    def __init__(self, timeshifter):
        LowLevelOpList.__init__(self, timeshifter.rtyper)
        self.timeshifter = timeshifter

    def hasparentgraph(self):
        return False   # for now

    def genmixlevelhelpercall(self, function, args_s, args_v, s_result):
        # XXX first approximation, will likely need some fine controlled
        # specialisation for these helpers too

        if isinstance(function, types.MethodType):
            if function.im_self is not None:
                # bound method => function and an extra first argument
                bk = self.rtyper.annotator.bookkeeper
                s_self = bk.immutablevalue(function.im_self)
                r_self = self.rtyper.getrepr(s_self)
                v_self = inputconst(r_self.lowleveltype,
                                    r_self.convert_const(function.im_self))
                args_s = [s_self] + args_s
                args_v = [v_self] + args_v
            function = function.im_func

        graph = self.timeshifter.annhelper.getgraph(function, args_s, s_result)
        self.record_extra_call(graph) # xxx

        c = self.timeshifter.annhelper.graph2const(graph)

        # build the 'direct_call' operation
        rtyper = self.timeshifter.rtyper
        try:
            RESULT = annmodel.annotation_to_lltype(s_result)
        except ValueError:
            RESULT = rtyper.getrepr(s_result).lowleveltype
        return self.genop('direct_call', [c]+args_v,
                          resulttype = RESULT)

    def getjitstate(self):
        return self.genop('getjitstate', [],
                          resulttype = self.timeshifter.r_JITState)

    def setjitstate(self, v_newjitstate):
        self.genop('setjitstate', [v_newjitstate])

# ____________________________________________________________

class __extend__(pairtype(HintTypeSystem, hintmodel.SomeLLAbstractValue)):

    def rtyper_makerepr((ts, hs_c), hrtyper):
        if hrtyper.gethscolor(hs_c) == 'green':
            return hrtyper.getgreenrepr(hs_c.concretetype)
        else:
            return hrtyper.getredrepr(hs_c.concretetype)

    def rtyper_makekey((ts, hs_c), hrtyper):
        color = hrtyper.gethscolor(hs_c)
        return hs_c.__class__, color, hs_c.concretetype

class __extend__(pairtype(HintTypeSystem, hintmodel.SomeLLAbstractContainer)):

    def rtyper_makerepr((ts, hs_container), hrtyper):
        vstructdef = hs_container.contentdef
        assert isinstance(vstructdef, hintcontainer.VirtualStructDef)
        if vstructdef.degenerated:
            # fall back to a red repr
            return hrtyper.getredrepr(hs_container.concretetype)
        return BlueStructRepr(hs_container.concretetype, vstructdef,
                              hrtyper.timeshifter)

    def rtyper_makekey((ts, hs_container), hrtyper):        
        vstructdef = hs_container.contentdef
        assert isinstance(vstructdef, hintcontainer.VirtualStructDef)
        if vstructdef.degenerated:
            # fall back to a red repr
            return hs_container.__class__, "red", hs_container.concretetype

        T = None
        if vstructdef.vparent is not None:
            T = vstructdef.vparent.T

        key = [hs_container.__class__, vstructdef.T, T, vstructdef.vparentindex]
        for name in vstructdef.names:
            fielditem = vstructdef.fields[name]
            key.append(fielditem)

        return tuple(key)

class __extend__(pairtype(HintTypeSystem, annmodel.SomeImpossibleValue)):

    def rtyper_makerepr((ts, hs_c), hrtyper):
        return green_void_repr

    def rtyper_makekey((ts, hs_c), hrtyper):
        return hs_c.__class__,

class RedRepr(Repr):
    def __init__(self, original_concretetype, timeshifter):
        assert original_concretetype is not lltype.Void, (
            "cannot make red boxes for the lltype Void")
        self.original_concretetype = original_concretetype
        self.lowleveltype = timeshifter.r_RedBox.lowleveltype
        self.timeshifter = timeshifter

    def get_genop_var(self, v, llops):
        ts = self.timeshifter
        v_jitstate = hop.llops.getjitstate()
        return llops.genmixlevelhelpercall(rtimeshift.ll_gvar_from_redbox,
                       [ts.s_JITState, llops.timeshifter.s_RedBox],
                       [v_jitstate,    v],
                       ts.s_ConstOrVar)

    def convert_const(self, ll_value):
        RGenOp = self.timeshifter.RGenOp
        redbox = rvalue.redbox_from_prebuilt_value(RGenOp, ll_value)
        timeshifter = self.timeshifter
        return timeshifter.annhelper.delayedconst(timeshifter.r_RedBox, redbox)

    def residual_values(self, ll_value):
        return [ll_value]


class RedStructRepr(RedRepr):
    typedesc = None

    def create(self, hop):
        ts = self.timeshifter
        if self.typedesc is None:
            T = self.original_concretetype.TO
            self.typedesc = rcontainer.StructTypeDesc(ts.RGenOp, T)
        return hop.llops.genmixlevelhelpercall(self.typedesc.ll_factory,
            [], [], ts.s_RedBox)


class BlueRepr(Repr):
    # XXX todo
    pass


class GreenRepr(Repr):
    def __init__(self, lowleveltype):
        self.lowleveltype = lowleveltype
        self.original_concretetype = lowleveltype        

    def annotation(self):
        return annmodel.lltype_to_annotation(self.lowleveltype)

    def erased_annotation(self):
        T = self.lowleveltype
        if isinstance(T, lltype.Ptr):
            return annmodel.SomeAddress()
        elif T is lltype.Float:
            return annmodel.SomeFloat()
        elif T is lltype.Void:
            return annmodel.s_ImpossibleValue
        else:
            return annmodel.SomeInteger()

    def get_genop_var(self, v, llops):
        ts = self.timeshifter
        v_jitstate = hop.llops.getjitstate()
        return llops.genmixlevelhelpercall(rtimeshift.ll_gvar_from_constant,
                                           [ts.s_JITState, self.annotation()],
                                           [v_jitstate,    v],
                                           ts.s_ConstOrVar)

    def convert_const(self, ll_value):
        return ll_value

    def residual_values(self, ll_value):
        return []

    #def timeshift_getsubstruct(self, hop):
    #    ...

green_signed_repr = GreenRepr(lltype.Signed)
green_void_repr   = GreenRepr(lltype.Void)

# collect the global precomputed reprs
PRECOMPUTED_GREEN_REPRS = {}
for _r in globals().values():
    if isinstance(_r, GreenRepr):
        PRECOMPUTED_GREEN_REPRS[_r.lowleveltype] = _r


class __extend__(pairtype(GreenRepr, RedRepr)):

    def convert_from_to((r_from, r_to), v, llops):
        assert r_from.lowleveltype == r_to.original_concretetype
        ts = llops.timeshifter
        v_jitstate = llops.getjitstate()
        return llops.genmixlevelhelpercall(rvalue.ll_fromvalue,
                        [ts.s_JITState, r_from.annotation()],
                        [v_jitstate,    v],
                        llops.timeshifter.s_RedBox)

# ____________________________________________________________

def opname2vstr(name):
    lls = string_repr.convert_const(name)
    return inputconst(string_repr.lowleveltype, lls)
