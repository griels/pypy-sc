from pypy.annotation.pairtype import pairtype
from pypy.annotation import model as annmodel
from pypy.rpython.rmodel import Repr, IteratorRepr, inputconst
from pypy.rpython.lltypesystem import lltype
from pypy.rpython import robject


class __extend__(annmodel.SomeList):
    def rtyper_makerepr(self, rtyper):
        from pypy.rpython import rrange
        listitem = self.listdef.listitem
        s_value = listitem.s_value
        if listitem.range_step is not None and not listitem.mutated:
            return rrange.RangeRepr(listitem.range_step)
        elif (s_value.__class__ is annmodel.SomeObject and s_value.knowntype == object):
            return robject.pyobj_repr
        else:
            # cannot do the rtyper.getrepr() call immediately, for the case
            # of recursive structures -- i.e. if the listdef contains itself
            rlist = rtyper.type_system.rlist
            if self.listdef.listitem.resized:
                return rlist.ListRepr(rtyper,
                        lambda: rtyper.getrepr(listitem.s_value), listitem)
            else:
                return rlist.FixedSizeListRepr(rtyper,
                        lambda: rtyper.getrepr(listitem.s_value), listitem)

    def rtyper_makekey(self):
        return self.__class__, self.listdef.listitem


class AbstractBaseListRepr(Repr):

    def recast(self, llops, v):
        return llops.convertvar(v, self.item_repr, self.external_item_repr)

class AbstractListRepr(AbstractBaseListRepr):
    
    pass

def rtype_newlist(hop):
    nb_args = hop.nb_args
    r_list = hop.r_result
    if r_list == robject.pyobj_repr: # special case: SomeObject lists!
        clist = hop.inputconst(robject.pyobj_repr, list)
        v_result = hop.genop('simple_call', [clist], resulttype = robject.pyobj_repr)
        cname = hop.inputconst(robject.pyobj_repr, 'append')
        v_meth = hop.genop('getattr', [v_result, cname], resulttype = robject.pyobj_repr)
        for i in range(nb_args):
            v_item = hop.inputarg(robject.pyobj_repr, arg=i)
            hop.genop('simple_call', [v_meth, v_item], resulttype = robject.pyobj_repr)
        return v_result
    r_listitem = r_list.item_repr
    items_v = [hop.inputarg(r_listitem, arg=i) for i in range(nb_args)]
    return hop.rtyper.type_system.rlist.newlist(hop.llops, r_list, items_v)


def dum_checkidx(): pass
def dum_nocheck(): pass


class __extend__(pairtype(AbstractBaseListRepr, AbstractBaseListRepr)):

    def rtype_add((r_lst1, r_lst2), hop):
        v_lst1, v_lst2 = hop.inputargs(r_lst1, r_lst2)
        cRESLIST = hop.inputconst(lltype.Void, hop.r_result.LIST)
        return hop.gendirectcall(hop.r_result.ll_concat, cRESLIST, v_lst1, v_lst2)

class __extend__(pairtype(AbstractListRepr, AbstractBaseListRepr)):

    def rtype_inplace_add((r_lst1, r_lst2), hop):
        v_lst1, v_lst2 = hop.inputargs(r_lst1, r_lst2)
        hop.gendirectcall(r_lst1.ll_extend, v_lst1, v_lst2)
        return v_lst1

# ____________________________________________________________
#
#  Iteration.

class AbstractListIteratorRepr(IteratorRepr):

    def newiter(self, hop):
        v_lst, = hop.inputargs(self.r_list)
        citerptr = hop.inputconst(lltype.Void, self.lowleveltype)
        return hop.gendirectcall(self.ll_listiter, citerptr, v_lst)

    def rtype_next(self, hop):
        v_iter, = hop.inputargs(self)
        hop.has_implicit_exception(StopIteration) # record that we know about it
        hop.exception_is_here()
        v_res = hop.gendirectcall(self.ll_listnext, v_iter)
        return self.r_list.recast(hop.llops, v_res)

