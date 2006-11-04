
from pypy.lang.js.astgen import *
from pypy.lang.js.context import ExecutionContext
from pypy.lang.js.jsobj import W_Number, W_String, W_Object 
from pypy.lang.js.jsobj import w_Undefined, W_Arguments, W_Boolean
from pypy.lang.js.scope import scope_manager

def writer(x):
    print x

class ExecutionReturned(Exception):
    def __init__(self, value):
        self.value = value

class ThrowException(Exception):
    def __init__(self, exception):
        self.exception = exception
        self.args = self.exception


class __extend__(Array):
    def call(self, context):
        d = dict(enumerate(self.items))
        return W_Array(d)

class __extend__(Assign):
    def call(self, context):
        val = self.expr.call(context)
        self.identifier.put(context,val)

class __extend__(Block):
    def call(self, context):
        try:
            last = w_Undefined
            for node in self.nodes:
                last = node.call(context)
            return last
        except ExecutionReturned, e:
            return e.value

class __extend__(Call):
    def call(self, context):
        name = self.identifier.get_literal()
        if name == 'print':
            writer(",".join([i.ToString() for i in self.arglist.call(context)]))
        else:
            backup_scope = scope_manager.current_scope
            
            w_obj = context.access(name)
            scope_manager.current_scope = w_obj.function.scope
            
            retval = w_obj.Call(context=context, args=[i for i in self.arglist.call(context)])
            scope_manager.current_scope = backup_scope
            return retval

class __extend__(Comma):
    def call(self, context):
        self.left.call(context)
        return self.right.call(context)

class __extend__(Dot):
    def call(self, context=None):
        w_obj = self.left.call(context).GetValue().ToObject()
        name = self.right.get_literal()
        return w_obj.Get(name)
        
    def put(self, context, val, obj=None):
        if isinstance(self.left,Identifier):
            assobj = obj or context
            assobj.assign(self.left.name,val)
        elif isinstance(self.left,Dot):
            assobj = self.left.put(context, val, obj)

        return assobj

        #w_obj = self.left.put(context).GetValue().ToObject()
        #name = self.right.get_literal()
        #w_obj.dict_w[self.name] = val
        

class __extend__(Function):
    def call(self, context=None):
       w_obj = W_Object({}, function=self)
       return w_obj

class __extend__(Identifier):
    def call(self, context=None):
        if self.initialiser is not None:
            scope_manager.set_variable(self.name, self.initialiser.call(context))
        try:
            return context.access(self.name)
        except NameError:
            return scope_manager.get_variable(self.name)

    def put(self, context, val, obj=None):            
        context.assign(self.name, val)
    
    def get_literal(self):
        return self.name

class __extend__(If):
    def call(self, context=None):
        if self.condition.call(context).ToBoolean():
            return self.thenPart.call(context)
        else:
            return self.elsePart.call(context)

class __extend__(Group):
    """The __extend__ class."""
    def call(self, context = None):
        return self.expr.call(context)

def AbstractRelationalLt(value1, value2):
    # TODO: really implement the algorithm
    v1 = value1.ToPrimitive().ToNumber()
    v2 = value2.ToPrimitive().ToNumber()
    return v1<v2

class __extend__(Gt):
    def call(self, context = None):
        left = self.left.call(context).GetValue()
        right = self.right.call(context).GetValue()
        if left != right:
            return W_Boolean(not AbstractRelationalLt(left, right))
        else:
            return W_Boolean(False)

class __extend__(Lt):
    def call(self, context = None):
        left = self.left.call(context).GetValue()
        right = self.right.call(context).GetValue()
        return W_Boolean(AbstractRelationalLt(left, right))

class __extend__(Index):
    def call(self, context=None):
        w_obj = self.left.call(context).GetValue()
        w_member = self.expr.call(context).GetValue()
        w_obj = w_obj.ToObject()
        name = w_member.ToString()
        return w_obj.Get(name)

class __extend__(List):
    def call(self, context=None):
        return [node.call(context) for node in self.nodes]

class __extend__(New):
    def call(self, context=None):
        obj = W_Object({})
        obj.Class = 'Object'
        try:
            constructor = context.access(self.identifier)
        except NameError:
            constructor = scope_manager.get_variable(self.identifier)
        obj.dict_w['prototype'] = constructor.dict_w['prototype']
        nctx = ExecutionContext(context)
        nctx.assign('this',obj)
        constructor.Call(nctx)

        return obj


class __extend__(Number):
    def call(self, context):
        return W_Number(self.num)
    
    def get_literal(self):
        # XXX Think about a shortcut later
        return str(W_Number(self.num))

class __extend__(ObjectInit):
    def call(self, context=None):
        w_obj = W_Object({})
        for property in self.properties:
            name = property.name.get_literal()
            w_expr = property.value.call(context).GetValue()
            w_obj.Put(name, w_expr)
        return w_obj
        #dict_w = {}
        #for property in self.properties:
        #    dict_w[property.name

class __extend__(Plus):
    def call(self, context=None):
        left = self.left.call(context).GetValue()
        right = self.right.call(context).GetValue()
        prim_left = left.ToPrimitive()
        prim_right = right.ToPrimitive()
        # INSANE
        if isinstance(prim_left, W_String) or isinstance(prim_right, W_String):
            str_left = prim_left.ToString()
            str_right = prim_right.ToString()
            return W_String(str_left + str_right)
        else:
            num_left = prim_left.ToNumber()
            num_right = prim_right.ToNumber()
            # XXX: obey all the rules
            return W_Number(num_left + num_right)

class __extend__(Script):
    def call(self, context=None, args=(), params=[]):
        ncontext = ExecutionContext(context)
        for i, item in enumerate(params):
            try:
                temp = args[i]
            except IndexError:
                temp = w_Undefined
            ncontext.assign(item, temp)
        
        w_Arguments = W_Arguments(dict([(str(x),y) for x,y in enumerate(args)]))
        ncontext.assign('arguments', w_Arguments)
        
        try:
            last = w_Undefined
            for node in self.nodes:
                last = node.call(ncontext)
            return last
        except ExecutionReturned, e:
            return e.value

class __extend__(Semicolon):
    def call(self, context=None):
        return self.expr.call(context)

class __extend__(String):
    def call(self, context=None):
        return W_String(self.strval)
    
    def get_literal(self):
        return self.strval

class __extend__(Return):
    def call(self, context=None):
        raise ExecutionReturned(self.expr.call(context))

class __extend__(Throw):
    def call(self, context=None):
        raise ThrowException(self.exception.call(context))

class __extend__(Try):
    def call(self, context=None):
        e = None
        try:
            tryresult = self.tryblock.call(context)
        except ThrowException, excpt:
            e = excpt
            ncontext = ExecutionContext(context)
            ncontext.assign(self.catchparam, e.exception)
            if self.catchblock is not None:
                tryresult = self.catchblock.call(ncontext)
        
        if self.finallyblock is not None:
            tryresult = self.finallyblock.call(context)
        
        #if there is no catchblock reraise the exception
        if (e is not None) and (self.catchblock is None):
            raise e
        
        return tryresult

class __extend__(Undefined):
    def call(self, context=None):
        return None

class __extend__(Vars):
    def call(self, context=None):
        for var in self.nodes:
            var.call(context)

class __extend__(While):
    def call(self, context=None):
        while self.condition.call(context).ToBoolean():
            self.body.call(context)

