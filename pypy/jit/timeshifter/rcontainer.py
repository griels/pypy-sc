import operator
from pypy.rpython.lltypesystem import lltype
from pypy.rpython.annlowlevel import cachedtype, cast_base_ptr_to_instance
from pypy.rpython.annlowlevel import base_ptr_lltype, cast_instance_to_base_ptr
from pypy.jit.timeshifter import rvalue
from pypy.rlib.unroll import unrolling_iterable

from pypy.annotation import model as annmodel
from pypy.rpython.lltypesystem import lloperation, llmemory
debug_print = lloperation.llop.debug_print
debug_pdb = lloperation.llop.debug_pdb

class AbstractContainer(object):
    __slots__ = []

    def op_getfield(self, jitstate, fielddesc):
        raise NotImplementedError

    def op_setfield(self, jitstate, fielddesc, valuebox):
        raise NotImplementedError

    def op_getsubstruct(self, jitstate, fielddesc):
        raise NotImplementedError


class VirtualContainer(AbstractContainer):
    __slots__ = []


class FrozenContainer(AbstractContainer):
    __slots__ = []

    def exactmatch(self, vstruct, outgoingvarboxes, memo):
        raise NotImplementedError
    
    def unfreeze(self, incomingvarboxes, memo):
        raise NotImplementedError

# ____________________________________________________________
from pypy.rpython.lltypesystem.rvirtualizable import VABLEINFOPTR

class StructTypeDesc(object):
    __metaclass__ = cachedtype

    _attrs_ = """firstsubstructdesc arrayfielddesc
                 alloctoken varsizealloctoken
                 materialize
                 base_desc info_desc access_desc
                 redirected_fielddescs
                 gv_access
                 gv_access_is_null_ptr access_is_null_token
              """.split()

    firstsubstructdesc = None
    materialize = None
   
    def __init__(self, hrtyper, TYPE):
        RGenOp = hrtyper.RGenOp
        self.TYPE = TYPE
        self.PTRTYPE = lltype.Ptr(TYPE)
        self.ptrkind = RGenOp.kindToken(self.PTRTYPE)
        innermostdesc = self
        if not TYPE._is_varsize():
            self.alloctoken = RGenOp.allocToken(TYPE)

        # N.B. Closes over descs defined below
        def fill_into(s, base, vinfo):
            i = 0
            for desc in descs:
                v = vinfo.read_field(desc, base, i)
                i += 1
                setattr(s, desc.fieldname, v)
        self.fill_into = fill_into

        fielddescs = []
        fielddesc_by_name = {}
        for name in self.TYPE._names:
            FIELDTYPE = getattr(self.TYPE, name)
            if isinstance(FIELDTYPE, lltype.ContainerType):
                if isinstance(FIELDTYPE, lltype.Array):
                    self.arrayfielddesc = ArrayFieldDesc(hrtyper, FIELDTYPE)
                    self.varsizealloctoken = RGenOp.varsizeAllocToken(TYPE)
                    continue
                substructdesc = StructTypeDesc(hrtyper, FIELDTYPE)
                assert name == self.TYPE._names[0], (
                    "unsupported: inlined substructures not as first field")
                fielddescs.extend(substructdesc.fielddescs)
                self.firstsubstructdesc = substructdesc
                innermostdesc = substructdesc.innermostdesc
            else:
                index = len(fielddescs)
                if FIELDTYPE is lltype.Void:
                    desc = None
                else:
                    desc = StructFieldDesc(hrtyper, self.PTRTYPE, name, index)
                    fielddescs.append(desc)
                fielddesc_by_name[name] = desc
        descs = unrolling_iterable(fielddescs) # Used in fill_into above

        self.fielddescs = fielddescs
        self.fielddesc_by_name = fielddesc_by_name
        self.innermostdesc = innermostdesc

        self.immutable = TYPE._hints.get('immutable', False)
        self.noidentity = TYPE._hints.get('noidentity', False)

        self.null = self.PTRTYPE._defl()
        self.gv_null = RGenOp.constPrebuiltGlobal(self.null)


        if self.immutable and self.noidentity:
            
            def materialize(rgenop, boxes):
                s = lltype.malloc(TYPE)
                i = 0
                for desc in descs:
                    v = rvalue.ll_getvalue(boxes[i], desc.RESTYPE)
                    setattr(s, desc.fieldname, v)
                    i = i + 1
                return rgenop.genconst(s)

            self.materialize = materialize

        self.virtualizable = TYPE._hints.get('virtualizable', False)
        if self.virtualizable:
            self.VStructCls = VirtualizableStruct
            self.base_desc = self.getfielddesc('vable_base')
            self.info_desc = self.getfielddesc('vable_info')
            self.access_desc = self.getfielddesc('vable_access')
            ACCESS = TYPE.ACCESS
            redirected_fields = ACCESS.redirected_fields
            print self.PTRTYPE, redirected_fields
            access = lltype.malloc(ACCESS, immortal=True)
            self.gv_access = RGenOp.constPrebuiltGlobal(access)
            TOPPTR = self.access_desc.PTRTYPE
            s_structtype = annmodel.lltype_to_annotation(TOPPTR)
            annhelper = hrtyper.annhelper
            j = 0
            def make_get_field(T, j):
                def get_field(struc):
                    vable_info = struc.vable_info
                    vable_info = cast_base_ptr_to_instance(VirtualInfo,
                                                           vable_info)
                    return vable_info.read_field(fielddesc,
                                                 struc.vable_base, j)
                return get_field
            
            self.redirected_fielddescs = redirected_fieldescs = []
            i = -1
            my_redirected_names = []
            self.my_redirected_getters = {}
            for fielddesc in fielddescs:
                i += 1
                name = fielddesc.fieldname
                if name not in redirected_fields:
                    continue
                redirected_fieldescs.append((fielddesc, i))
                if fielddesc.PTRTYPE != self.PTRTYPE:
                    continue
                my_redirected_names.append(name)
                get_field = make_get_field(fielddesc, j)
                j += 1
                s_lltype = annmodel.lltype_to_annotation(fielddesc.RESTYPE)
                get_field_ptr = annhelper.delayedfunction(get_field,
                                                          [s_structtype],
                                                          s_lltype,
                                                          needtype = True)
                self.my_redirected_getters[name] = get_field_ptr

            self.fill_access(access)

            def access_is_null(struc):
                assert not struc.vable_access
            access_is_null_ptr = annhelper.delayedfunction(access_is_null,
                                                           [s_structtype],
                                                           annmodel.s_None,
                                                           needtype = True)
            self.gv_access_is_null_ptr = RGenOp.constPrebuiltGlobal(
                                           access_is_null_ptr)
            self.access_is_null_token =  RGenOp.sigToken(
                                     lltype.typeOf(access_is_null_ptr).TO)

            my_redirected_names = unrolling_iterable(my_redirected_names)

            if TOPPTR == self.PTRTYPE:
                _super_collect = None
            else:
                _super_collect = self.firstsubstructdesc._collect_residual_args

            def _collect_residual_args(v): 
                if _super_collect is None:
                    assert not v.vable_access  # xxx need to use access ?
                    t = ()
                else:
                    t = _super_collect(v.super)
                for name in my_redirected_names:
                    t = t + (getattr(v, name),)
                return t

            self._collect_residual_args = _collect_residual_args

            def collect_residual_args(v): 
                t = (v,) + _collect_residual_args(v)
                return t

            self.collect_residual_args = collect_residual_args
        else:
            self.VStructCls = VirtualStruct

        # xxx
        self.gv_make_vinfo_ptr = hrtyper.gv_make_vinfo_ptr
        self.make_vinfo_token = hrtyper.make_vinfo_token

        self.gv_vinfo_set_info_ptr = hrtyper.gv_vinfo_set_info_ptr
        self.vinfo_set_info_token = hrtyper.vinfo_set_info_token
        self.gv_vinfo_append_vinfo_ptr = hrtyper.gv_vinfo_append_vinfo_ptr
        self.vinfo_append_vinfo_token = hrtyper.vinfo_append_vinfo_token
        self.gv_vinfo_skip_vinfo_ptr = hrtyper.gv_vinfo_skip_vinfo_ptr
        self.vinfo_skip_vinfo_token = hrtyper.vinfo_skip_vinfo_token

        self.gv_vinfo_get_vinfo_ptr = hrtyper.gv_vinfo_get_vinfo_ptr
        self.vinfo_get_vinfo_token = hrtyper.vinfo_get_vinfo_token

        self.gv_vinfo_get_shape_ptr = hrtyper.gv_vinfo_get_shape_ptr
        self.vinfo_get_shape_token = hrtyper.vinfo_get_shape_token

        self.gv_vinfo_read_forced_ptr = hrtyper.gv_vinfo_read_forced_ptr
        self.vinfo_read_forced_token = hrtyper.vinfo_read_forced_token

    def fill_access(self, access):
        firstsubstructdesc = self.firstsubstructdesc
        if (firstsubstructdesc is not None and 
            firstsubstructdesc.virtualizable):
            firstsubstructdesc.fill_access(access.parent)
        for name, get_field_ptr in self.my_redirected_getters.iteritems():
            setattr(access, 'get_'+name, get_field_ptr)
        
    def getfielddesc(self, name):
        try:
            return self.fielddesc_by_name[name]
        except KeyError:
            return self.firstsubstructdesc.getfielddesc(name)

    def factory(self):
        vstruct = self.VStructCls(self)
        vstruct.content_boxes = [desc.makedefaultbox()
                                 for desc in self.fielddescs]
        if self.virtualizable:
            outsidebox = rvalue.PtrRedBox(self.innermostdesc.ptrkind,
                                          self.gv_null)
            vstruct.content_boxes.append(outsidebox)     
        box = rvalue.PtrRedBox(self.innermostdesc.ptrkind)
        box.content = vstruct
        vstruct.ownbox = box
        return box

    def ll_factory(self):
        # interface for rtyper.py, specialized for each 'self'
        return self.factory()

    def _freeze_(self):
        return True

    def compact_repr(self): # goes in ll helper names
        return "Desc_%s" % (self.TYPE._short_name(),)
    
# XXX basic field descs for now
class FieldDesc(object):
    __metaclass__ = cachedtype
    allow_void = False
    virtualizable = False
    gv_default = None
    
    def __init__(self, hrtyper, PTRTYPE, RESTYPE):
        RGenOp = hrtyper.RGenOp
        self.PTRTYPE = PTRTYPE
        T = None
        if isinstance(RESTYPE, lltype.ContainerType):
            T = RESTYPE
            RESTYPE = lltype.Ptr(RESTYPE)
        elif isinstance(RESTYPE, lltype.Ptr):
            T = RESTYPE.TO
            if hasattr(T, '_hints'):
                self.virtualizable = T._hints.get('virtualizable', False)
            if not isinstance(T, lltype.ContainerType):
                T = None
        self.RESTYPE = RESTYPE
        self.ptrkind = RGenOp.kindToken(PTRTYPE)
        self.kind = RGenOp.kindToken(RESTYPE)
        if self.RESTYPE is not lltype.Void:
            self.gv_default = RGenOp.constPrebuiltGlobal(self.RESTYPE._defl())
        if RESTYPE is lltype.Void and self.allow_void:
            pass   # no redboxcls at all
        elif self.virtualizable:
            pass
        else:
            self.redboxcls = rvalue.ll_redboxcls(RESTYPE)

        if T is not None and isinstance(T, lltype.Struct): # xxx for now
            self.structdesc = StructTypeDesc(hrtyper, T)
            self.fill_into = self.structdesc.fill_into
            
        self.immutable = PTRTYPE.TO._hints.get('immutable', False)

    def _freeze_(self):
        return True

    def makedefaultbox(self):
        if self.virtualizable:
            return self.structdesc.factory()
        return self.redboxcls(self.kind, self.gv_default)
    
    def makebox(self, jitstate, gvar):
        if self.virtualizable:
            structbox = self.structdesc.factory()
            content = structbox.content
            assert isinstance(content, VirtualizableStruct)
            content.load_from(jitstate, gvar)
            return structbox
        return self.redboxcls(self.kind, gvar)

    
class NamedFieldDesc(FieldDesc):

    def __init__(self, hrtyper, PTRTYPE, name):
        FieldDesc.__init__(self, hrtyper, PTRTYPE, getattr(PTRTYPE.TO, name))
        T = self.PTRTYPE.TO
        self.fieldname = name
        self.fieldtoken = hrtyper.RGenOp.fieldToken(T, name)

    def compact_repr(self): # goes in ll helper names
        return "Fld_%s_in_%s" % (self.fieldname, self.PTRTYPE._short_name())

    def generate_get(self, jitstate, genvar):
        builder = jitstate.curbuilder
        gv_item = builder.genop_getfield(self.fieldtoken, genvar)
        return self.makebox(jitstate, gv_item)

    def generate_set(self, jitstate, genvar, gv_value):
        builder = jitstate.curbuilder
        builder.genop_setfield(self.fieldtoken, genvar, gv_value)

    def generate_getsubstruct(self, jitstate, genvar):
        builder = jitstate.curbuilder
        gv_sub = builder.genop_getsubstruct(self.fieldtoken, genvar)
        return self.makebox(jitstate, gv_sub)

class StructFieldDesc(NamedFieldDesc):

    def __init__(self, hrtyper, PTRTYPE, name, index):
        NamedFieldDesc.__init__(self, hrtyper, PTRTYPE, name)
        self.fieldindex = index

class ArrayFieldDesc(FieldDesc):
    allow_void = True

    def __init__(self, hrtyper, TYPE):
        assert isinstance(TYPE, lltype.Array)
        FieldDesc.__init__(self, hrtyper, lltype.Ptr(TYPE), TYPE.OF)
        RGenOp = hrtyper.RGenOp
        self.arraytoken = RGenOp.arrayToken(TYPE)
        self.varsizealloctoken = RGenOp.varsizeAllocToken(TYPE)
        self.indexkind = RGenOp.kindToken(lltype.Signed)

# ____________________________________________________________

class FrozenVirtualStruct(FrozenContainer):

    def __init__(self, typedesc):
        self.typedesc = typedesc
        #self.fz_content_boxes initialized later

    def exactmatch(self, vstruct, outgoingvarboxes, memo):
        assert isinstance(vstruct, VirtualStruct)
        contmemo = memo.containers
        if self in contmemo:
            ok = vstruct is contmemo[self]
            if not ok:
                outgoingvarboxes.append(vstruct.ownbox)
            return ok
        if vstruct in contmemo:
            assert contmemo[vstruct] is not self
            outgoingvarboxes.append(vstruct.ownbox)
            return False
        if self.typedesc is not vstruct.typedesc:
            if not memo.force_merge:
                raise rvalue.DontMerge
            outgoingvarboxes.append(vstruct.ownbox)
            return False
        contmemo[self] = vstruct
        contmemo[vstruct] = self
        self_boxes = self.fz_content_boxes
        vstruct_boxes = vstruct.content_boxes
        fullmatch = True
        for i in range(len(self_boxes)):
            if not self_boxes[i].exactmatch(vstruct_boxes[i],
                                            outgoingvarboxes,
                                            memo):
                fullmatch = False
        return fullmatch

    def unfreeze(self, incomingvarboxes, memo):
        contmemo = memo.containers
        if self in contmemo:
            return contmemo[self]
        typedesc = self.typedesc
        ownbox = typedesc.factory()
        contmemo[self] = ownbox
        vstruct = ownbox.content
        assert isinstance(vstruct, VirtualStruct)
        self_boxes = self.fz_content_boxes
        for i in range(len(self_boxes)):
            fz_box = self_boxes[i]
            vstruct.content_boxes[i] = fz_box.unfreeze(incomingvarboxes,
                                                       memo)
        return ownbox


class VirtualStruct(VirtualContainer):
    __slots__ = "typedesc content_boxes ownbox".split()

    def __init__(self, typedesc):
        self.typedesc = typedesc
        #self.content_boxes = ... set in factory()
        #self.ownbox = ... set in factory()

    def enter_block(self, incoming, memo):
        contmemo = memo.containers
        if self not in contmemo:
            contmemo[self] = None
            for box in self.content_boxes:
                box.enter_block(incoming, memo)

    def force_runtime_container(self, jitstate):
        typedesc = self.typedesc
        builder = jitstate.curbuilder
        boxes = self.content_boxes
        self.content_boxes = None
        if typedesc.materialize is not None:
            for box in boxes:
                if box is None or not box.is_constant():
                    break
            else:
                gv = typedesc.materialize(builder.rgenop, boxes)
                self.ownbox.genvar = gv
                self.ownbox.content = None
                return
        debug_print(lltype.Void, "FORCE CONTAINER: "+ typedesc.TYPE._name)
        #debug_pdb(lltype.Void)
        genvar = builder.genop_malloc_fixedsize(typedesc.alloctoken)
        # force the box pointing to this VirtualStruct
        self.ownbox.genvar = genvar
        self.ownbox.content = None
        fielddescs = typedesc.fielddescs
        for i in range(len(fielddescs)):
            fielddesc = fielddescs[i]
            box = boxes[i]
            fielddesc.generate_set(jitstate, genvar, box.getgenvar(jitstate))

    def freeze(self, memo):
        contmemo = memo.containers
        assert self not in contmemo     # contmemo no longer used
        result = contmemo[self] = FrozenVirtualStruct(self.typedesc)
        frozens = [box.freeze(memo) for box in self.content_boxes]
        result.fz_content_boxes = frozens
        return result

    def copy(self, memo):
        typedesc = self.typedesc
        contmemo = memo.containers
        assert self not in contmemo     # contmemo no longer used
        result = contmemo[self] = typedesc.VStructCls(typedesc)
        result.content_boxes = [box.copy(memo)
                                for box in self.content_boxes]
        result.ownbox = self.ownbox.copy(memo)
        return result

    def replace(self, memo):
        contmemo = memo.containers
        assert self not in contmemo     # contmemo no longer used
        contmemo[self] = None
        content_boxes = self.content_boxes
        for i in range(len(content_boxes)):
            content_boxes[i] = content_boxes[i].replace(memo)
        self.ownbox = self.ownbox.replace(memo)

    def op_getfield(self, jitstate, fielddesc):
        return self.content_boxes[fielddesc.fieldindex]

    def op_setfield(self, jitstate, fielddesc, valuebox):
        self.content_boxes[fielddesc.fieldindex] = valuebox

    def op_getsubstruct(self, jitstate, fielddesc):
        return self.ownbox

    def make_vinfo(self, jitstate, memo):
        try:
            return memo.containers[self]
        except KeyError:
            pass
        typedesc = self.typedesc
        builder = jitstate.curbuilder
        gv_bitmask = builder.rgenop.genconst(1<<memo.bitcount)
        memo.bitcount += 1
        gv_vinfo = builder.genop_call(typedesc.make_vinfo_token,
                           typedesc.gv_make_vinfo_ptr,
                           [gv_bitmask])
        memo.containers[self] = gv_vinfo
        vars_gv = []
        for box in self.content_boxes:
            if box.genvar:
                vars_gv.append(box.genvar)
                builder.genop_call(typedesc.vinfo_skip_vinfo_token,
                           typedesc.gv_vinfo_skip_vinfo_ptr,
                           [gv_vinfo])

            else:
                vars_gv.append(None)
                assert isinstance(box, rvalue.PtrRedBox)
                content = box.content
                assert isinstance(content, VirtualStruct) # XXX for now
                gv_vinfo1 = content.make_vinfo(jitstate, memo)
                builder.genop_call(typedesc.vinfo_append_vinfo_token,
                           typedesc.gv_vinfo_append_vinfo_ptr,
                           [gv_vinfo, gv_vinfo1])


        gv_info = builder.get_frame_info(vars_gv)
        builder.genop_call(typedesc.vinfo_set_info_token,
                           typedesc.gv_vinfo_set_info_ptr,
                           [gv_vinfo, gv_info])
        return gv_vinfo


    def reshape(self, jitstate, gv_vinfo, shapemask, memo):
        if self in memo.containers:
            return
        typedesc = self.typedesc
        builder = jitstate.curbuilder        
        memo.containers[self] = None
        bitmask = 1<<memo.bitcount
        memo.bitcount += 1
        boxes = self.content_boxes
        if bitmask&shapemask:
            gv_ptr = builder.genop_call(typedesc.vinfo_read_forced_token,
                                        typedesc.gv_vinfo_read_forced_ptr,
                                        [gv_vinfo])
            self.content_boxes = None
            self.ownbox.genvar = gv_ptr
            self.ownbox.content = None

        for i in range(len(boxes)): # xxx duplication
            box = boxes[i]
            if not box.genvar:
                gv_vinfo1 = builder.genop_call(typedesc.vinfo_get_vinfo_token,
                                               typedesc.gv_vinfo_get_vinfo_ptr,
                                               [gv_vinfo, builder.rgenop.genconst(i)])
                assert isinstance(box, rvalue.PtrRedBox)
                content = box.content
                assert isinstance(content, VirtualStruct) # xxx for now
                content.reshape(jitstate, gv_vinfo1, shapemask, memo)        
        


class VirtualInfo(object):

    def __init__(self, RGenOp, bitmask):
        self.RGenOp = RGenOp
        self.vinfos = []
        self.s = lltype.nullptr(llmemory.GCREF.TO)
        self.bitmask = bitmask
        
    def read_field(self, fielddesc, base, index):
        T = fielddesc.RESTYPE
        vinfo = self.vinfos[index]
        if vinfo is None:
            return self.RGenOp.read_frame_var(T, base,
                                              self.info, index)
        assert isinstance(T, lltype.Ptr)
        return vinfo.get_forced(fielddesc, base)
    read_field._annspecialcase_ = "specialize:arg(1)"

    def get_forced(self, fielddesc, base):
        T = fielddesc.RESTYPE
        assert isinstance(T, lltype.Ptr)
        if self.s:
            return lltype.cast_opaque_ptr(T, self.s)
        S = T.TO
        s = lltype.malloc(S)
        self.s = lltype.cast_opaque_ptr(llmemory.GCREF, s)
        fielddesc.fill_into(s, base, self)
        return s
    get_forced._annspecialcase_ = "specialize:arg(1)"

    def read_forced(self):
        assert self.s
        return self.s
    
    def get_shape(self):
        if self.s:
            return self.bitmask
        else:
            return 0

class VirtualizableStruct(VirtualStruct):

    def force_runtime_container(self, jitstate):
        assert 0

    def getgenvar(self, jitstate):
        typedesc = self.typedesc
        builder = jitstate.curbuilder
        gv_outside = self.content_boxes[-1].genvar
        if gv_outside is typedesc.gv_null:
            gv_outside = builder.genop_malloc_fixedsize(typedesc.alloctoken)
            self.content_boxes[-1].genvar = gv_outside
            jitstate.add_virtualizable(self.ownbox)
        return gv_outside

    def store_back(self, jitstate):
        typedesc = self.typedesc
        boxes = self.content_boxes
        gv_outside = boxes[-1].genvar
        for fielddesc, i in typedesc.redirected_fielddescs:
            box = boxes[i]
            fielddesc.generate_set(jitstate, gv_outside,
                                   box.getgenvar(jitstate))

    def load_from(self, jitstate, gv_outside):
        typedesc = self.typedesc
        boxes = self.content_boxes
        boxes[-1].genvar = gv_outside
        builder = jitstate.curbuilder
        builder.genop_call(typedesc.access_is_null_token,
                           typedesc.gv_access_is_null_ptr,
                           [gv_outside])
        for fielddesc, i in typedesc.redirected_fielddescs:
            boxes[i] = fielddesc.generate_get(jitstate, gv_outside)
        jitstate.add_virtualizable(self.ownbox)

    def prepare_for_residual_call(self, jitstate, gv_base, memo):
        typedesc = self.typedesc
        builder = jitstate.curbuilder
        gv_outside = self.content_boxes[-1].genvar
        if gv_outside is not typedesc.gv_null:
            if self in memo.containers:
                return
            base_desc = typedesc.base_desc
            base_token = base_desc.fieldtoken
            builder.genop_setfield(base_token, gv_outside, gv_base)
            # xxx aliasing
            boxes = self.content_boxes
            vars_gv = []
            n = len(boxes)
            gv_zeromask = builder.rgenop.genconst(0)
            gv_vinfo = builder.genop_call(typedesc.make_vinfo_token,
                               typedesc.gv_make_vinfo_ptr,
                               [gv_zeromask])
            memo.containers[self] = gv_vinfo
            
            for _, i in typedesc.redirected_fielddescs:
                box = boxes[i]
                if box.genvar:
                    vars_gv.append(box.genvar)
                    builder.genop_call(typedesc.vinfo_skip_vinfo_token,
                               typedesc.gv_vinfo_skip_vinfo_ptr,
                               [gv_vinfo])
                    
                else:
                    vars_gv.append(None)
                    assert isinstance(box, rvalue.PtrRedBox)
                    content = box.content
                    assert isinstance(content, VirtualStruct) # XXX for now
                    gv_vinfo1 = content.make_vinfo(jitstate, memo)
                    builder.genop_call(typedesc.vinfo_append_vinfo_token,
                               typedesc.gv_vinfo_append_vinfo_ptr,
                               [gv_vinfo, gv_vinfo1])
                    
                    
            gv_info = builder.get_frame_info(vars_gv)
            builder.genop_call(typedesc.vinfo_set_info_token,
                               typedesc.gv_vinfo_set_info_ptr,
                               [gv_vinfo, gv_info])
            info_token = typedesc.info_desc.fieldtoken
            builder.genop_setfield(info_token, gv_outside,
                                   gv_vinfo)
            access_token = typedesc.access_desc.fieldtoken
            builder.genop_setfield(access_token, gv_outside,
                                   typedesc.gv_access)

    def after_residual_call(self, jitstate):
        typedesc = self.typedesc
        builder = jitstate.curbuilder
        gv_outside = self.content_boxes[-1].genvar
        if gv_outside is not typedesc.gv_null:
            base_desc = typedesc.base_desc
            base_token = typedesc.base_desc.fieldtoken
            info_token = typedesc.info_desc.fieldtoken
            access_token = typedesc.access_desc.fieldtoken
            gv_base_null = typedesc.base_desc.gv_default
            gv_access_null = typedesc.access_desc.gv_default
            builder.genop_setfield(base_token, gv_outside, gv_base_null)
            builder.genop_setfield(access_token, gv_outside, gv_access_null)

    def reshape(self, jitstate, gv_vinfo, shapemask, memo):
        typedesc = self.typedesc
        builder = jitstate.curbuilder
        gv_outside = self.content_boxes[-1].genvar
        if gv_outside is not typedesc.gv_null:
            info_desc = typedesc.info_desc
            if self in memo.containers:
                return
            # xxx we can avoid traversing the full tree
            memo.containers[self] = None

            assert gv_vinfo is None # xxx
            info_token = info_desc.fieldtoken
            gv_vinfo = builder.genop_getfield(info_token, gv_outside)            
            boxes = self.content_boxes
            j = 0
            for _, i in typedesc.redirected_fielddescs:
                box = boxes[i]
                if not box.genvar:
                    gv_vinfo1 = builder.genop_call(typedesc.vinfo_get_vinfo_token,
                                                   typedesc.gv_vinfo_get_vinfo_ptr,
                                                   [gv_vinfo, builder.rgenop.genconst(j)])
                    assert isinstance(box, rvalue.PtrRedBox)
                    content = box.content
                    assert isinstance(content, VirtualStruct) # xxx for now
                    content.reshape(jitstate, gv_vinfo1, shapemask, memo)
                j += 1
                    
# ____________________________________________________________

class FrozenPartialDataStruct(AbstractContainer):

    def __init__(self):
        self.fz_data = []

    def getfzbox(self, searchindex):
        for index, fzbox in self.fz_data:
            if index == searchindex:
                return fzbox
        else:
            return None

    def match(self, box, partialdatamatch):
        content = box.content
        if not isinstance(content, PartialDataStruct):
            return False

        cankeep = {}
        for index, subbox in content.data:
            selfbox = self.getfzbox(index)
            if selfbox is not None and selfbox.is_constant_equal(subbox):
                cankeep[index] = None
        fullmatch = len(cankeep) == len(self.fz_data)
        try:
            prevkeep = partialdatamatch[box]
        except KeyError:
            partialdatamatch[box] = cankeep
        else:
            if prevkeep is not None:
                d = {}
                for index in prevkeep:
                    if index in cankeep:
                        d[index] = None
                partialdatamatch[box] = d
        return fullmatch


class PartialDataStruct(AbstractContainer):

    def __init__(self):
        self.data = []

    def op_getfield(self, jitstate, fielddesc):
        searchindex = fielddesc.fieldindex
        for index, box in self.data:
            if index == searchindex:
                return box
        else:
            return None

    def remember_field(self, fielddesc, box):
        searchindex = fielddesc.fieldindex
        for i in range(len(self.data)):
            if self.data[i][0] == searchindex:
                self.data[i] = searchindex, box
                return
        else:
            self.data.append((searchindex, box))

    def partialfreeze(self, memo):
        contmemo = memo.containers
        assert self not in contmemo     # contmemo no longer used
        result = contmemo[self] = FrozenPartialDataStruct()
        for index, box in self.data:
            if box.is_constant():
                frozenbox = box.freeze(memo)
                result.fz_data.append((index, frozenbox))
        if len(result.fz_data) == 0:
            return None
        else:
            return result

    def copy(self, memo):
        result = PartialDataStruct()
        for index, box in self.data:
            result.data.append((index, box.copy(memo)))
        return result

    def replace(self, memo):
        for i in range(len(self.data)):
            index, box = self.data[i]
            box = box.replace(memo)
            self.data[i] = index, box

    def enter_block(self, incoming, memo):
        contmemo = memo.containers
        if self not in contmemo:
            contmemo[self] = None
            for index, box in self.data:
                box.enter_block(incoming, memo)

    def cleanup_partial_data(self, keep):
        if keep is None:
            return None
        j = 0
        data = self.data
        for i in range(len(data)):
            item = data[i]
            if item[0] in keep:
                data[j] = item
                j += 1
        if j == 0:
            return None
        del data[j:]
        return self
