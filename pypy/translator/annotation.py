from __future__ import generators

from pypy.translator.annset import AnnotationSet, Cell, deref
from pypy.objspace.flow.model import Variable, Constant, SpaceOperation

#class GraphGlobalVariable(Variable):
#    pass

class Annotator:

    def __init__(self, flowgraph):
        self.flowgraph = flowgraph
        self.simplify_hooks = []

    def build_types(self, input_arg_types):
        input_ann = AnnotationSet()
        for arg, arg_type in zip(self.flowgraph.getargs(), input_arg_types):
            input_ann.set_type(arg, arg_type)
        self.build_annotations(input_ann)

    def build_annotations(self,input_annotations):
        self.annotated = {}
        self.flowin(self.flowgraph.startblock,input_annotations)

    def get_return_value(self):
        "Return the return_value variable."
        return self.flowgraph.returnblock.inputargs[0]

    def get_variables_ann(self):
        """Return a dict {Variable(): AnnotationSet()} mapping each variable
        of the control flow graph to a set of annotations that apply to it."""
        # XXX this assumes that all variables are local to a single block,
        #     and returns for each variable the annotations for that block.
        #     This assumption is clearly false because of the EggBlocks.
        #     This has to be fixed anyway.
        result = {}
        for block, ann in self.annotated.items():
            for v in block.getvariables():
                #XXX assert v not in result, "Variables must not be shared"
                result[v] = ann
        return result

    def simplify_calls(self):
        for block, ann in self.annotated.iteritems():
            newops = []
            for op in block.operations:
                if op.opname == "call":
                    w_func, w_varargs, w_kwargs = op.args
                    c = Cell()
                    ann.match(SpaceOperation('len', [w_varargs], c))
                    if isinstance(c.content, Constant):
                        length = c.content.value
                        args_w = [w_func]
                        for i in range(length):
                            c = Cell()
                            if not ann.match(SpaceOperation('getitem', [
                                w_varargs, Constant(i)], c)):
                                break
                            args_w.append(deref(c))
                        else:
                            op = SpaceOperation('simple_call', args_w, op.result)
                            # XXX check that w_kwargs is empty
                newops.append(op)
            block.operations = tuple(newops)

    def simplify(self):
        self.simplify_calls()
        for hook in self.simplify_hooks:
            hook(self)

    #__________________________________________________

    def flowin(self, block, annotations):
        if block not in self.annotated:
            oldlen = None
            self.annotated[block] = blockannotations = annotations
        else:
            blockannotations = self.annotated[block]
            oldlen = len(blockannotations)
            #import sys; print >> sys.stderr, block, blockannotations
            #import sys; print >> sys.stderr, '/\\', annotations, '==>',
            blockannotations.intersect(annotations)
            #import sys; print >> sys.stderr, blockannotations

        for op in block.operations:
            self.consider_op(op, blockannotations)
        # assert monotonic decrease
        assert (oldlen is None or len(blockannotations) <= oldlen), (
            block, oldlen, blockannotations)
        if len(blockannotations) != oldlen:
            for link in block.exits:
                self.flownext(link,block)
            
    def consider_op(self,op,annotations):
        consider_meth = getattr(self,'consider_op_'+op.opname,None)
        if consider_meth is not None:
            consider_meth(op,annotations)

    def consider_op_add(self,op,annotations):
        arg1,arg2 = op.args
        type1 = annotations.get_type(arg1)
        type2 = annotations.get_type(arg2)
        if type1 == int and type2 == int:
            annotations.set_type(op.result,int)

    consider_op_sub = consider_op_add
    consider_op_and_ = consider_op_add   # don't forget the trailing '_'
    # XXX add more

    def consider_op_not_(self, op, annotations):
        annotations.set_type(op.result, bool)

    def consider_op_lt(self, op, annotations):
        annotations.set_type(op.result, bool)

    consider_op_le = consider_op_lt
    consider_op_eq = consider_op_lt
    consider_op_ne = consider_op_lt
    consider_op_gt = consider_op_lt
    consider_op_ge = consider_op_lt

    def consider_op_newtuple(self,op,annotations):
        annotations.set_type(op.result,tuple)
        ann = SpaceOperation("len",[op.result],Constant(len(op.args)))
        annotations.add(ann)
        for i in range(len(op.args)):
            ann = SpaceOperation("getitem",[op.result,Constant(i)],op.args[i])
            annotations.add(ann)

    def consider_const(self,to_var,const,annotations):
        if getattr(const, 'dummy', False):
            return   # undefined local variables
        annotations.set_type(to_var,type(const.value))
        if isinstance(const.value, list):
            pass # XXX say something about the type of the elements
        elif isinstance(const.value, tuple):
            pass # XXX say something about the elements

    def flownext(self,link,curblock):
        renaming = {}
        newannotations = AnnotationSet()

        for w_from,w_to in zip(link.args,link.target.inputargs):
            if isinstance(w_from,Variable):
                renaming.setdefault(w_from, []).append(w_to)
            else:
                self.consider_const(w_to,w_from,newannotations)        

        #import sys; print >> sys.stderr, self.annotated[curblock]
        #import sys; print >> sys.stderr, renaming
        for ann in self.annotated[curblock].enumerate(renaming):
            newannotations.add(ann)
        #import sys; print >> sys.stderr, newannotations
        self.flowin(link.target,newannotations)
