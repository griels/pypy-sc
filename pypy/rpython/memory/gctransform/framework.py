from pypy.rpython.memory.gctransform.transform import GCTransformer, var_ispyobj
from pypy.rpython.memory.gctransform.support import find_gc_ptrs_in_type, \
     get_rtti, ll_call_destructor, type_contains_pyobjs
from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython import rmodel
from pypy.rpython.memory import gctypelayout
from pypy.rpython.memory.gc import marksweep
from pypy.rpython.memory.gcheader import GCHeaderBuilder
from pypy.rlib.rarithmetic import ovfcheck
from pypy.rlib.objectmodel import debug_assert
from pypy.translator.backendopt import graphanalyze
from pypy.translator.backendopt.support import var_needsgc
from pypy.annotation import model as annmodel
from pypy.rpython import annlowlevel
from pypy.rpython.rbuiltin import gen_cast
from pypy.rpython.memory.gctypelayout import ll_weakref_deref, WEAKREF
from pypy.rpython.memory.gctypelayout import convert_weakref_to, WEAKREFPTR
from pypy.rpython.memory.gctransform.log import log
from pypy.tool.sourcetools import func_with_new_name
import sys


class CollectAnalyzer(graphanalyze.GraphAnalyzer):
    def operation_is_true(self, op):
        if op.opname in ('gc__collect', 'gc_x_become'):
            return True
        if op.opname in ('malloc', 'malloc_varsize'):
            flags = op.args[1].value
            return flags['flavor'] == 'gc' and not flags.get('nocollect', False)

ADDRESS_VOID_FUNC = lltype.FuncType([llmemory.Address], lltype.Void)

class FrameworkGCTransformer(GCTransformer):
    use_stackless = False
    root_stack_depth = 163840

    def __init__(self, translator):
        from pypy.rpython.memory.support import get_address_linked_list
        from pypy.rpython.memory.gc.base import choose_gc_from_config
        super(FrameworkGCTransformer, self).__init__(translator, inline=True)
        AddressLinkedList = get_address_linked_list()
        if hasattr(self, 'GC_PARAMS'):
            # for tests: the GC choice can be specified as class attributes
            from pypy.rpython.memory.gc.marksweep import MarkSweepGC
            GCClass = getattr(self, 'GCClass', MarkSweepGC)
            GC_PARAMS = self.GC_PARAMS
        else:
            # for regular translation: pick the GC from the config
            GCClass, GC_PARAMS = choose_gc_from_config(translator.config)

        self.FINALIZERTYPE = lltype.Ptr(ADDRESS_VOID_FUNC)
        class GCData(object):
            # types of the GC information tables
            OFFSETS_TO_GC_PTR = lltype.Array(lltype.Signed)
            TYPE_INFO = lltype.Struct("type_info",
                ("isvarsize",   lltype.Bool),
                ("finalizer",   self.FINALIZERTYPE),
                ("fixedsize",   lltype.Signed),
                ("ofstoptrs",   lltype.Ptr(OFFSETS_TO_GC_PTR)),
                ("varitemsize", lltype.Signed),
                ("ofstovar",    lltype.Signed),
                ("ofstolength", lltype.Signed),
                ("varofstoptrs",lltype.Ptr(OFFSETS_TO_GC_PTR)),
                ("weakptrofs",  lltype.Signed),
                )
            TYPE_INFO_TABLE = lltype.Array(TYPE_INFO)

        def q_is_varsize(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].isvarsize

        def q_finalizer(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].finalizer

        def q_offsets_to_gc_pointers(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].ofstoptrs

        def q_fixed_size(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].fixedsize

        def q_varsize_item_sizes(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].varitemsize

        def q_varsize_offset_to_variable_part(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].ofstovar

        def q_varsize_offset_to_length(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].ofstolength

        def q_varsize_offsets_to_gcpointers_in_var_part(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].varofstoptrs

        def q_weakpointer_offset(typeid):
            debug_assert(typeid > 0, "invalid type_id")
            return gcdata.type_info_table[typeid].weakptrofs

        self.layoutbuilder = TransformerLayoutBuilder(self)
        self.get_type_id = self.layoutbuilder.get_type_id

        gcdata = GCData()
        # set up dummy a table, to be overwritten with the real one in finish()
        gcdata.type_info_table = lltype.malloc(GCData.TYPE_INFO_TABLE, 0,
                                               immortal=True)
        # initialize the following two fields with a random non-NULL address,
        # to make the annotator happy.  The fields are patched in finish()
        # to point to a real array (not 'static_roots', another one).
        a_random_address = llmemory.cast_ptr_to_adr(gcdata.type_info_table)
        gcdata.static_root_start = a_random_address      # patched in finish()
        gcdata.static_root_nongcstart = a_random_address # patched in finish()
        gcdata.static_root_end = a_random_address        # patched in finish()
        self.gcdata = gcdata
        self.malloc_fnptr_cache = {}

        sizeofaddr = llmemory.sizeof(llmemory.Address)

        StackRootIterator = self.build_stack_root_iterator()
        gcdata.gc = GCClass(AddressLinkedList, get_roots=StackRootIterator, **GC_PARAMS)
        self.num_pushs = 0
        self.write_barrier_calls = 0

        def frameworkgc_setup():
            # run-time initialization code
            StackRootIterator.setup_root_stack()
            gcdata.gc.setup()
            gcdata.gc.set_query_functions(
                q_is_varsize,
                q_finalizer,
                q_offsets_to_gc_pointers,
                q_fixed_size,
                q_varsize_item_sizes,
                q_varsize_offset_to_variable_part,
                q_varsize_offset_to_length,
                q_varsize_offsets_to_gcpointers_in_var_part,
                q_weakpointer_offset)

        bk = self.translator.annotator.bookkeeper

        # the point of this little dance is to not annotate
        # self.gcdata.type_info_table as a constant.
        data_classdef = bk.getuniqueclassdef(GCData)
        data_classdef.generalize_attr(
            'type_info_table',
            annmodel.SomePtr(lltype.Ptr(GCData.TYPE_INFO_TABLE)))
        data_classdef.generalize_attr(
            'static_roots',
            annmodel.SomePtr(lltype.Ptr(lltype.Array(llmemory.Address))))
        data_classdef.generalize_attr(
            'static_root_start',
            annmodel.SomeAddress())
        data_classdef.generalize_attr(
            'static_root_nongcstart',
            annmodel.SomeAddress())
        data_classdef.generalize_attr(
            'static_root_end',
            annmodel.SomeAddress())

        annhelper = annlowlevel.MixLevelHelperAnnotator(self.translator.rtyper)

        def getfn(ll_function, args_s, s_result, inline=False,
                  minimal_transform=True):
            graph = annhelper.getgraph(ll_function, args_s, s_result)
            if minimal_transform:
                self.need_minimal_transform(graph)
            if inline:
                self.graphs_to_inline[graph] = True
            return annhelper.graph2const(graph)

        self.frameworkgc_setup_ptr = getfn(frameworkgc_setup, [],
                                           annmodel.s_None)
        if StackRootIterator.need_root_stack:
            #self.pop_root_ptr = getfn(StackRootIterator.pop_root, [],
            #                          annmodel.SomeAddress(),
            #                          inline = True)
            #self.push_root_ptr = getfn(StackRootIterator.push_root,
            #                           [annmodel.SomeAddress()],
            #                           annmodel.s_None,
            #                           inline = True)
            self.incr_stack_ptr = getfn(StackRootIterator.incr_stack,
                                       [annmodel.SomeInteger()],
                                       annmodel.SomeAddress(),
                                       inline = True)
            self.decr_stack_ptr = getfn(StackRootIterator.decr_stack,
                                       [annmodel.SomeInteger()],
                                       annmodel.SomeAddress(),
                                       inline = True)
        else:
            #self.push_root_ptr = None
            #self.pop_root_ptr = None
            self.incr_stack_ptr = None
            self.decr_stack_ptr = None
        self.weakref_deref_ptr = self.inittime_helper(
            ll_weakref_deref, [llmemory.WeakRefPtr], llmemory.Address)
        
        classdef = bk.getuniqueclassdef(GCClass)
        s_gc = annmodel.SomeInstance(classdef)
        s_gcref = annmodel.SomePtr(llmemory.GCREF)
        self.malloc_fixedsize_ptr = getfn(
            GCClass.malloc_fixedsize.im_func,
            [s_gc, annmodel.SomeInteger(nonneg=True),
             annmodel.SomeInteger(nonneg=True),
             annmodel.SomeBool(), annmodel.SomeBool(),
             annmodel.SomeBool()], s_gcref,
            inline = False)
        self.malloc_fixedsize_clear_ptr = getfn(
            GCClass.malloc_fixedsize_clear.im_func,
            [s_gc, annmodel.SomeInteger(nonneg=True),
             annmodel.SomeInteger(nonneg=True),
             annmodel.SomeBool(), annmodel.SomeBool(),
             annmodel.SomeBool()], s_gcref,
            inline = False)
##         self.malloc_varsize_ptr = getfn(
##             GCClass.malloc_varsize.im_func,
##             [s_gc] + [annmodel.SomeInteger(nonneg=True) for i in range(5)]
##             + [annmodel.SomeBool(), annmodel.SomeBool()], s_gcref)
        self.malloc_varsize_clear_ptr = getfn(
            GCClass.malloc_varsize_clear.im_func,
            [s_gc] + [annmodel.SomeInteger(nonneg=True) for i in range(5)]
            + [annmodel.SomeBool(), annmodel.SomeBool()], s_gcref)
        self.collect_ptr = getfn(GCClass.collect.im_func,
            [s_gc], annmodel.s_None)

        # in some GCs we can inline the common case of
        # malloc_fixedsize(typeid, size, True, False, False)
        if getattr(GCClass, 'inline_simple_malloc', False):
            # make a copy of this function so that it gets annotated
            # independently and the constants are folded inside
            malloc_fast = func_with_new_name(
                GCClass.malloc_fixedsize.im_func,
                "malloc_fast")
            s_False = annmodel.SomeBool(); s_False.const = False
            s_True  = annmodel.SomeBool(); s_True .const = True
            self.malloc_fast_ptr = getfn(
                malloc_fast,
                [s_gc, annmodel.SomeInteger(nonneg=True),
                 annmodel.SomeInteger(nonneg=True),
                 s_True, s_False,
                 s_False], s_gcref,
                inline = True)
        else:
            self.malloc_fast_ptr = self.malloc_fixedsize_ptr

        if GCClass.moving_gc:
            self.id_ptr = getfn(GCClass.id.im_func,
                                [s_gc, s_gcref], annmodel.SomeInteger(),
                                inline = False,
                                minimal_transform = False)
        else:
            self.id_ptr = None

        if GCClass.needs_write_barrier:
            self.write_barrier_ptr = getfn(GCClass.write_barrier.im_func,
                                           [s_gc, annmodel.SomeAddress(),
                                            annmodel.SomeAddress(),
                                            annmodel.SomeAddress()],
                                           annmodel.s_None,
                                           inline=True)
        else:
            self.write_barrier_ptr = None
        self.statistics_ptr = getfn(GCClass.statistics.im_func,
                                    [s_gc, annmodel.SomeInteger()],
                                    annmodel.SomeInteger())

        # experimental gc_x_* operations
        s_x_pool  = annmodel.SomePtr(marksweep.X_POOL_PTR)
        s_x_clone = annmodel.SomePtr(marksweep.X_CLONE_PTR)
        # the x_*() methods use some regular mallocs that must be
        # transformed in the normal way
        self.x_swap_pool_ptr = getfn(GCClass.x_swap_pool.im_func,
                                     [s_gc, s_x_pool],
                                     s_x_pool,
                                     minimal_transform = False)
        self.x_clone_ptr = getfn(GCClass.x_clone.im_func,
                                 [s_gc, s_x_clone],
                                 annmodel.s_None,
                                 minimal_transform = False)

        self.x_become_ptr = getfn(
            GCClass.x_become.im_func,
            [s_gc, annmodel.SomeAddress(), annmodel.SomeAddress()],
            annmodel.s_None)

        annhelper.finish()   # at this point, annotate all mix-level helpers
        annhelper.backend_optimize()

        self.collect_analyzer = CollectAnalyzer(self.translator)
        self.collect_analyzer.analyze_all()

        s_gc = self.translator.annotator.bookkeeper.valueoftype(GCClass)
        r_gc = self.translator.rtyper.getrepr(s_gc)
        self.c_const_gc = rmodel.inputconst(r_gc, self.gcdata.gc)

        HDR = self._gc_HDR = self.gcdata.gc.gcheaderbuilder.HDR
        self._gc_fields = fields = []
        for fldname in HDR._names:
            FLDTYPE = getattr(HDR, fldname)
            fields.append(('_' + fldname, FLDTYPE))

    def build_stack_root_iterator(self):
        gcdata = self.gcdata
        sizeofaddr = llmemory.sizeof(llmemory.Address)
        rootstacksize = sizeofaddr * self.root_stack_depth

        class StackRootIterator:
            _alloc_flavor_ = 'raw'
            def setup_root_stack():
                stackbase = llmemory.raw_malloc(rootstacksize)
                debug_assert(bool(stackbase), "could not allocate root stack")
                llmemory.raw_memclear(stackbase, rootstacksize)
                gcdata.root_stack_top  = stackbase
                gcdata.root_stack_base = stackbase
            setup_root_stack = staticmethod(setup_root_stack)

            need_root_stack = True
            
            def incr_stack(n):
                top = gcdata.root_stack_top
                gcdata.root_stack_top = top + n*sizeofaddr
                return top
            incr_stack = staticmethod(incr_stack)
            
            def decr_stack(n):
                top = gcdata.root_stack_top - n*sizeofaddr
                gcdata.root_stack_top = top
                return top
            decr_stack = staticmethod(decr_stack)
                
            def push_root(addr):
                top = gcdata.root_stack_top
                top.address[0] = addr
                gcdata.root_stack_top = top + sizeofaddr
            push_root = staticmethod(push_root)

            def pop_root():
                top = gcdata.root_stack_top - sizeofaddr
                gcdata.root_stack_top = top
                return top.address[0]
            pop_root = staticmethod(pop_root)

            def __init__(self, with_static=True):
                self.stack_current = gcdata.root_stack_top
                if with_static:
                    self.static_current = gcdata.static_root_start
                else:
                    self.static_current = gcdata.static_root_nongcstart

            def pop(self):
                while self.static_current != gcdata.static_root_end:
                    result = self.static_current
                    self.static_current += sizeofaddr
                    if result.address[0].address[0] != llmemory.NULL:
                        return result.address[0]
                while self.stack_current != gcdata.root_stack_base:
                    self.stack_current -= sizeofaddr
                    if self.stack_current.address[0] != llmemory.NULL:
                        return self.stack_current
                return llmemory.NULL

        return StackRootIterator

    def consider_constant(self, TYPE, value):
        self.layoutbuilder.consider_constant(TYPE, value, self.gcdata.gc)

    #def get_type_id(self, TYPE):
    #    this method is attached to the instance and redirects to
    #    layoutbuilder.get_type_id().

    def finalizer_funcptr_for_type(self, TYPE):
        return self.layoutbuilder.finalizer_funcptr_for_type(TYPE)

    def gc_fields(self):
        return self._gc_fields

    def gc_field_values_for(self, obj):
        hdr = self.gcdata.gc.gcheaderbuilder.header_of_object(obj)
        HDR = self._gc_HDR
        return [getattr(hdr, fldname) for fldname in HDR._names]

    def finish_tables(self):
        table = self.layoutbuilder.flatten_table()
        log.info("assigned %s typeids" % (len(table), ))
        log.info("added %s push/pop stack root instructions" % (
                     self.num_pushs, ))
        log.info("inserted %s write barrier calls" % (
                     self.write_barrier_calls, ))

        # replace the type_info_table pointer in gcdata -- at this point,
        # the database is in principle complete, so it has already seen
        # the old (empty) array.  We need to force it to consider the new
        # array now.  It's a bit hackish as the old empty array will also
        # be generated in the C source, but that's a rather minor problem.

        # XXX because we call inputconst already in replace_malloc, we can't
        # modify the instance, we have to modify the 'rtyped instance'
        # instead.  horrors.  is there a better way?

        s_gcdata = self.translator.annotator.bookkeeper.immutablevalue(
            self.gcdata)
        r_gcdata = self.translator.rtyper.getrepr(s_gcdata)
        ll_instance = rmodel.inputconst(r_gcdata, self.gcdata).value
        ll_instance.inst_type_info_table = table
        #self.gcdata.type_info_table = table

        addresses_of_static_ptrs = (
            self.layoutbuilder.addresses_of_static_ptrs +
            self.layoutbuilder.addresses_of_static_ptrs_in_nongc)
        log.info("found %s static roots" % (len(addresses_of_static_ptrs), ))
        ll_static_roots_inside = lltype.malloc(lltype.Array(llmemory.Address),
                                               len(addresses_of_static_ptrs),
                                               immortal=True)
        for i in range(len(addresses_of_static_ptrs)):
            ll_static_roots_inside[i] = addresses_of_static_ptrs[i]
        ll_instance.inst_static_root_start = llmemory.cast_ptr_to_adr(ll_static_roots_inside) + llmemory.ArrayItemsOffset(lltype.Array(llmemory.Address))
        ll_instance.inst_static_root_nongcstart = ll_instance.inst_static_root_start + llmemory.sizeof(llmemory.Address) * len(self.layoutbuilder.addresses_of_static_ptrs)
        ll_instance.inst_static_root_end = ll_instance.inst_static_root_start + llmemory.sizeof(llmemory.Address) * len(ll_static_roots_inside)

        newgcdependencies = []
        newgcdependencies.append(table)
        newgcdependencies.append(ll_static_roots_inside)
        self.write_typeid_list()
        return newgcdependencies

    def write_typeid_list(self):
        """write out the list of type ids together with some info"""
        from pypy.tool.udir import udir
        # XXX not ideal since it is not per compilation, but per run
        f = udir.join("typeids.txt").open("w")
        all = [(typeid, TYPE)
               for TYPE, typeid in self.layoutbuilder.id_of_type.iteritems()]
        all.sort()
        for typeid, TYPE in all:
            f.write("%s %s\n" % (typeid, TYPE))

    def gct_direct_call(self, hop):
        if self.collect_analyzer.analyze(hop.spaceop):
            livevars = self.push_roots(hop)
            self.default(hop)
            self.pop_roots(hop, livevars)
        else:
            self.default(hop)

    gct_indirect_call = gct_direct_call

    def gct_fv_gc_malloc(self, hop, flags, TYPE, *args):
        op = hop.spaceop
        flavor = flags['flavor']
        c_can_collect = rmodel.inputconst(lltype.Bool, not flags.get('nocollect', False))

        PTRTYPE = op.result.concretetype
        assert PTRTYPE.TO == TYPE
        type_id = self.get_type_id(TYPE)

        c_type_id = rmodel.inputconst(lltype.Signed, type_id)
        info = self.layoutbuilder.type_info_list[type_id]
        c_size = rmodel.inputconst(lltype.Signed, info["fixedsize"])
        has_finalizer = bool(self.finalizer_funcptr_for_type(TYPE))
        c_has_finalizer = rmodel.inputconst(lltype.Bool, has_finalizer)

        if not op.opname.endswith('_varsize'):
            #malloc_ptr = self.malloc_fixedsize_ptr
            zero = flags.get('zero', False)
            if zero:
                malloc_ptr = self.malloc_fixedsize_clear_ptr
            elif c_can_collect.value and not c_has_finalizer.value:
                malloc_ptr = self.malloc_fast_ptr
            else:
                malloc_ptr = self.malloc_fixedsize_ptr
            args = [self.c_const_gc, c_type_id, c_size, c_can_collect,
                    c_has_finalizer, rmodel.inputconst(lltype.Bool, False)]
        else:
            v_length = op.args[-1]
            c_ofstolength = rmodel.inputconst(lltype.Signed, info['ofstolength'])
            c_varitemsize = rmodel.inputconst(lltype.Signed, info['varitemsize'])
            malloc_ptr = self.malloc_varsize_clear_ptr
##             if op.opname.startswith('zero'):
##                 malloc_ptr = self.malloc_varsize_clear_ptr
##             else:
##                 malloc_ptr = self.malloc_varsize_clear_ptr
            args = [self.c_const_gc, c_type_id, v_length, c_size,
                    c_varitemsize, c_ofstolength, c_can_collect,
                    c_has_finalizer]
        livevars = self.push_roots(hop)
        v_result = hop.genop("direct_call", [malloc_ptr] + args,
                             resulttype=llmemory.GCREF)
        self.pop_roots(hop, livevars)
        return v_result

    gct_fv_gc_malloc_varsize = gct_fv_gc_malloc

    def gct_gc__collect(self, hop):
        op = hop.spaceop
        livevars = self.push_roots(hop)
        hop.genop("direct_call", [self.collect_ptr, self.c_const_gc],
                  resultvar=op.result)
        self.pop_roots(hop, livevars)

    def gct_gc_x_swap_pool(self, hop):
        op = hop.spaceop
        [v_malloced] = op.args
        hop.genop("direct_call",
                  [self.x_swap_pool_ptr, self.c_const_gc, v_malloced],
                  resultvar=op.result)

    def gct_gc_x_clone(self, hop):
        op = hop.spaceop
        [v_clonedata] = op.args
        hop.genop("direct_call",
                  [self.x_clone_ptr, self.c_const_gc, v_clonedata],
                  resultvar=op.result)

    def gct_gc_x_size_header(self, hop):
        op = hop.spaceop
        c_result = rmodel.inputconst(lltype.Signed,
                                     self.gcdata.gc.size_gc_header())
        hop.genop("same_as",
                  [c_result],
                  resultvar=op.result)

    def gct_gc_x_become(self, hop):
        op = hop.spaceop
        [v_target, v_source] = op.args
        livevars = self.push_roots(hop)
        hop.genop("direct_call",
                  [self.x_become_ptr, self.c_const_gc, v_target, v_source],
                  resultvar=op.result)
        self.pop_roots(hop, livevars)

    def gct_zero_gc_pointers_inside(self, hop):
        v_ob = hop.spaceop.args[0]
        TYPE = v_ob.concretetype.TO
        gen_zero_gc_pointers(TYPE, v_ob, hop.llops)

    def gct_weakref_create(self, hop):
        op = hop.spaceop

        type_id = self.get_type_id(WEAKREF)

        c_type_id = rmodel.inputconst(lltype.Signed, type_id)
        info = self.layoutbuilder.type_info_list[type_id]
        c_size = rmodel.inputconst(lltype.Signed, info["fixedsize"])
        malloc_ptr = self.malloc_fixedsize_ptr
        c_has_finalizer = rmodel.inputconst(lltype.Bool, False)
        c_has_weakptr = c_can_collect = rmodel.inputconst(lltype.Bool, True)
        args = [self.c_const_gc, c_type_id, c_size, c_can_collect,
                c_has_finalizer, c_has_weakptr]

        v_instance, = op.args
        v_addr = hop.genop("cast_ptr_to_adr", [v_instance],
                           resulttype=llmemory.Address)
        livevars = self.push_roots(hop)
        v_result = hop.genop("direct_call", [malloc_ptr] + args,
                             resulttype=llmemory.GCREF)
        v_result = hop.genop("cast_opaque_ptr", [v_result],
                            resulttype=WEAKREFPTR)
        self.pop_roots(hop, livevars)
        hop.genop("bare_setfield",
                  [v_result, rmodel.inputconst(lltype.Void, "weakptr"), v_addr])
        v_weakref = hop.genop("cast_ptr_to_weakrefptr", [v_result],
                              resulttype=llmemory.WeakRefPtr)
        hop.cast_result(v_weakref)

    def gct_weakref_deref(self, hop):
        v_wref, = hop.spaceop.args
        v_addr = hop.genop("direct_call",
                           [self.weakref_deref_ptr, v_wref],
                           resulttype=llmemory.Address)
        hop.cast_result(v_addr)

    def gct_gc_id(self, hop):
        if self.id_ptr is not None:
            livevars = self.push_roots(hop)
            [v_ptr] = hop.spaceop.args
            v_ptr = hop.genop("cast_opaque_ptr", [v_ptr],
                              resulttype=llmemory.GCREF)
            hop.genop("direct_call", [self.id_ptr, self.c_const_gc, v_ptr],
                      resultvar=hop.spaceop.result)
            self.pop_roots(hop, livevars)
        else:
            hop.rename('cast_ptr_to_int')     # works nicely for non-moving GCs

    def transform_generic_set(self, hop):
        from pypy.objspace.flow.model import Constant
        v_struct = hop.spaceop.args[0]
        v_newvalue = hop.spaceop.args[-1]
        # XXX for some GCs the skipping if the newvalue is a constant won't be
        # ok
        if self.write_barrier_ptr is None or isinstance(v_newvalue, Constant):
            super(FrameworkGCTransformer, self).transform_generic_set(hop)
        else:
            self.write_barrier_calls += 1
            assert isinstance(v_newvalue.concretetype, lltype.Ptr)
            opname = hop.spaceop.opname
            assert opname in ('setfield', 'setarrayitem', 'setinteriorfield')
            offsets = hop.spaceop.args[1:-1]
            CURTYPE = v_struct.concretetype.TO
            v_currentofs = None
            for ofs in offsets:
                if ofs.concretetype is lltype.Void:
                    # a field in a structure
                    fieldname = ofs.value
                    fieldofs = llmemory.offsetof(CURTYPE, fieldname)
                    v_offset = rmodel.inputconst(lltype.Signed, fieldofs)
                    CURTYPE = getattr(CURTYPE, fieldname)
                else:
                    # an index in an array
                    assert ofs.concretetype is lltype.Signed
                    firstitem = llmemory.ArrayItemsOffset(CURTYPE)
                    itemsize  = llmemory.sizeof(CURTYPE.OF)
                    c_firstitem = rmodel.inputconst(lltype.Signed, firstitem)
                    c_itemsize  = rmodel.inputconst(lltype.Signed, itemsize)
                    v_index = hop.spaceop.args[1]
                    v_offset = hop.genop("int_mul", [c_itemsize, v_index],
                                         resulttype = lltype.Signed)
                    v_offset = hop.genop("int_add", [c_firstitem, v_offset],
                                         resulttype = lltype.Signed)
                    CURTYPE = CURTYPE.OF
                if v_currentofs is None:
                    v_currentofs = v_offset
                else:
                    v_currentofs = hop.genop("int_add",
                                             [v_currentofs, v_offset],
                                             resulttype = lltype.Signed)
            v_newvalue = hop.genop("cast_ptr_to_adr", [v_newvalue],
                                   resulttype = llmemory.Address)
            v_structaddr = hop.genop("cast_ptr_to_adr", [v_struct],
                                     resulttype = llmemory.Address)
            v_fieldaddr = hop.genop("adr_add", [v_structaddr, v_currentofs],
                                    resulttype = llmemory.Address)
            hop.genop("direct_call", [self.write_barrier_ptr,
                                      self.c_const_gc,
                                      v_newvalue,
                                      v_fieldaddr,
                                      v_structaddr])

    def var_needs_set_transform(self, var):
        return var_needsgc(var)

    def push_alive_nopyobj(self, var, llops):
        pass

    def pop_alive_nopyobj(self, var, llops):
        pass

    def push_roots(self, hop):
        if self.incr_stack_ptr is None:
            return
        if self.gcdata.gc.moving_gc:
            # moving GCs don't borrow, so the caller does not need to keep
            # the arguments alive
            livevars = [var for var in hop.livevars_after_op()
                            if not var_ispyobj(var)]
        else:
            livevars = hop.livevars_after_op() + hop.current_op_keeps_alive()
            livevars = [var for var in livevars if not var_ispyobj(var)]
        self.num_pushs += len(livevars)
        if not livevars:
            return []
        c_len = rmodel.inputconst(lltype.Signed, len(livevars) )
        base_addr = hop.genop("direct_call", [self.incr_stack_ptr, c_len ],
                              resulttype=llmemory.Address)
        c_type = rmodel.inputconst(lltype.Void, llmemory.Address)
        for k,var in enumerate(livevars):
            c_k = rmodel.inputconst(lltype.Signed, k)
            v_adr = gen_cast(hop.llops, llmemory.Address, var)
            hop.genop("raw_store", [base_addr, c_type, c_k, v_adr])
        return livevars

    def pop_roots(self, hop, livevars):
        if self.decr_stack_ptr is None:
            return
        if not livevars:
            return
        c_len = rmodel.inputconst(lltype.Signed, len(livevars) )
        base_addr = hop.genop("direct_call", [self.decr_stack_ptr, c_len ],
                              resulttype=llmemory.Address)
        if self.gcdata.gc.moving_gc:
            # for moving collectors, reload the roots into the local variables
            c_type = rmodel.inputconst(lltype.Void, llmemory.Address)
            for k,var in enumerate(livevars):
                c_k = rmodel.inputconst(lltype.Signed, k)
                v_newaddr = hop.genop("raw_load", [base_addr, c_type, c_k],
                                      resulttype=llmemory.Address)
                hop.genop("gc_reload_possibly_moved", [v_newaddr, var])

    def compute_borrowed_vars(self, graph):
        # XXX temporary workaround, should be done more correctly
        if self.gcdata.gc.moving_gc:
            return lambda v: False
        return super(FrameworkGCTransformer, self).compute_borrowed_vars(graph)


class TransformerLayoutBuilder(gctypelayout.TypeLayoutBuilder):

    def __init__(self, transformer):
        super(TransformerLayoutBuilder, self).__init__()
        self.transformer = transformer
        self.offsettable_cache = {}

    def make_finalizer_funcptr_for_type(self, TYPE):
        rtti = get_rtti(TYPE)
        if rtti is not None and hasattr(rtti._obj, 'destructor_funcptr'):
            destrptr = rtti._obj.destructor_funcptr
            DESTR_ARG = lltype.typeOf(destrptr).TO.ARGS[0]
        else:
            destrptr = None
            DESTR_ARG = None

        assert not type_contains_pyobjs(TYPE), "not implemented"
        if destrptr:
            def ll_finalizer(addr):
                v = llmemory.cast_adr_to_ptr(addr, DESTR_ARG)
                ll_call_destructor(destrptr, v)
            fptr = self.transformer.annotate_helper(ll_finalizer,
                                                    [llmemory.Address],
                                                    lltype.Void)
        else:
            fptr = lltype.nullptr(ADDRESS_VOID_FUNC)
        return fptr

    def offsets2table(self, offsets, TYPE):
        try:
            return self.offsettable_cache[TYPE]
        except KeyError:
            gcdata = self.transformer.gcdata
            cachedarray = lltype.malloc(gcdata.OFFSETS_TO_GC_PTR,
                                        len(offsets), immortal=True)
            for i, value in enumerate(offsets):
                cachedarray[i] = value
            self.offsettable_cache[TYPE] = cachedarray
            return cachedarray

    def flatten_table(self):
        self.can_add_new_types = False
        table = lltype.malloc(self.transformer.gcdata.TYPE_INFO_TABLE,
                              len(self.type_info_list), immortal=True)
        for tableentry, newcontent in zip(table, self.type_info_list):
            for key, value in newcontent.items():
                setattr(tableentry, key, value)
        self.offsettable_cache = None
        return table


def gen_zero_gc_pointers(TYPE, v, llops, previous_steps=None):
    if previous_steps is None:
        previous_steps = []
    assert isinstance(TYPE, lltype.Struct)
    for name in TYPE._names:
        c_name = rmodel.inputconst(lltype.Void, name)
        FIELD = getattr(TYPE, name)
        if isinstance(FIELD, lltype.Ptr) and FIELD._needsgc():
            c_null = rmodel.inputconst(FIELD, lltype.nullptr(FIELD.TO))
            if not previous_steps:
                llops.genop('bare_setfield', [v, c_name, c_null])
            else:
                llops.genop('bare_setinteriorfield',
                            [v] + previous_steps + [c_name, c_null])
        elif isinstance(FIELD, lltype.Struct):
            gen_zero_gc_pointers(FIELD, v, llops, previous_steps + [c_name])
