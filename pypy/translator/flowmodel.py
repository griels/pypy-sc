"""
the objectmodel on which the FlowObjSpace and the translator 
interoperate. While the FlowObjSpace may (and does) use subclasses
of the classes in this module the translator parts will only look 
into the attributes defined here. 
"""
class FlowNode:
    def getedges(self):
        """ return all edges of this node """
        raise NotImplementedError, "Abstract base class"

    def flatten(self):
        """ return a list of all nodes reachable from this node """
        nodedict = self.visit(lambda x: None)
        return nodedict.keys()

    def visit(self, fn, _visited = None):
        """ let the function 'fn' visit the subgraph of this node """
        if _visited is None:
            _visited = {}
        _visited[self] = fn(self)
        for targetnode in self.getedges():
            if not _visited.has_key(targetnode):
                targetnode.visit(fn, _visited)
        return _visited

class BasicBlock(FlowNode):
    has_renaming = True

    def __init__(self, input_args, locals, operations, branch=None):
        self.input_args = input_args
        self.locals = locals
        self.operations = operations
        self.branch = branch

    def getedges(self):
        return [self.branch]

    def replace_branch(self, one, another):
        assert self.branch is one
        self.branch = another

    def closeblock(self, branch):
        self.operations = tuple(self.operations)  # should no longer change
        self.branch = branch

    def getlocals(self):
        locals = {}
        for arg in self.input_args:
            locals[arg] = True
        for op in self.operations:
            for arg in op.args:
                if isinstance(arg, Variable):
                    locals[arg] = True
            if isinstance(op.result, Variable):
                locals[op.result] = True
        return locals

class Variable:
    def __init__(self, pseudoname):
        self.pseudoname = pseudoname

    def __repr__(self):
        return "<%s>" % self.pseudoname

    def get(self):
        return self

class Constant:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Constant) and self.value == other.value

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return str(self.value)

    def get(self):
        return self

class SpaceOperation:
    def __init__(self, opname, args, result):
        self.opname = opname
        self.args = args     # list of variables
        self.result = result # <Variable/Constant instance>

    def __eq__(self, other):
        return (self.__class__ is other.__class__ and
                self.opname == other.opname and
                self.args == other.args and
                self.result == other.result)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.opname,tuple(self.args),self.result))
        

    def __repr__(self):
        return "%s <- %s(%s)" % (self.result, self.opname, ", ".join(map(str, self.args)))

class Branch(FlowNode):
    def __init__(self, args=None, target=None):
        self.set(args, target)

    def getedges(self):
        return [self.target]

    def set(self, args, target):
        self.args = args     # list of variables
        self.target = target # basic block instance

class ConditionalBranch(FlowNode):
    def __init__(self, condition=None, ifbranch=None, elsebranch=None):
        self.set(condition, ifbranch, elsebranch)

    def getedges(self):
        return [self.ifbranch, self.elsebranch]

    def set(self, condition, ifbranch, elsebranch):
        self.condition = condition
        self.ifbranch = ifbranch
        self.elsebranch = elsebranch

    def replace_branch(self, one, another):
        assert self.ifbranch is not self.elsebranch, "please enhance flowobjspace"
        if one is self.ifbranch:
            self.ifbranch = another
        elif one is self.elsebranch:
            self.elsebranch = another
        else:
            raise ValueError, "Don't have this branch %r" % one

class EndBranch(FlowNode):
    def __init__(self, returnvalue):
        self.returnvalue = returnvalue

    def getedges(self):
        return []

class FunctionGraph:
    def __init__(self, startblock, functionname):
        self.startblock = startblock
        self.functionname = functionname

    def get_args(self):
        return self.startblock.input_args

    def flatten(self):
        return self.startblock.flatten()

    def mkentrymap(self):
        """Create a map from nodes in the graph to back edge lists"""
        entrymap = { self.startblock: [self]}
        for node in self.flatten():
            for edge in node.getedges():
                entrymap.setdefault(edge, []).append(node)
        return entrymap
