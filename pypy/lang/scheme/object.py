import py

class SchemeException(Exception):
    pass

class UnboundVariable(SchemeException):
    def __str__(self):
        return "Unbound variable %s" % (self.args[0], )

class NotCallable(SchemeException):
    def __str__(self):
        return "%s is not a callable" % (self.args[0].to_string(), )

class WrongArgsNumber(SchemeException):
    def __str__(self):
        return "Wrong number of args"

class WrongArgType(SchemeException):
    def __str__(self):
        return "Wrong argument type: %s is not %s" % \
                (self.args[0].to_string(), self.args[1])

class SchemeSyntaxError(SchemeException):
    def __str__(self):
        return "Syntax error"

class SchemeQuit(SchemeException):
    """raised on (quit) evaluation"""
    pass

class W_Root(object):
    __slots__ = []

    def to_string(self):
        return ''

    def to_boolean(self):
        return True

    def __repr__(self):
        return "<W_Root " + self.to_string() + ">"

    def eval(self, ctx):
        w_expr = self
        while ctx is not None:
            (w_expr, ctx) = w_expr.eval_tr(ctx)

        assert isinstance(w_expr, W_Root)
        return w_expr
        #return self

    def eval_tr(self, ctx):
        return (self, None)

class W_Symbol(W_Root):
    def __init__(self, val):
        self.name = val

    def to_string(self):
        return self.name

    def __repr__(self):
        return "<W_symbol " + self.name + ">"

class W_Identifier(W_Symbol):
    def __init__(self, val):
        self.name = val

    def to_string(self):
        return self.name

    def __repr__(self):
        return "<W_Identifier " + self.name + ">"

    def eval_tr(self, ctx):
        w_obj = ctx.get(self.name)
        return (w_obj, None)

class W_Boolean(W_Root):
    def __init__(self, val):
        self.boolval = bool(val)

    def to_string(self):
        if self.boolval:
            return "#t"
        return "#f"

    def to_boolean(self):
        return self.boolval

    def __repr__(self):
        return "<W_Boolean " + str(self.boolval) + " >"

class W_String(W_Root):
    def __init__(self, val):
        self.strval = val

    def to_string(self):
        return self.strval

    def __repr__(self):
        return "<W_String " + self.strval + " >"

class W_Real(W_Root):
    def __init__(self, val):
        self.exact = False
        self.realval = val

    def to_string(self):
        return str(self.realval)

    def to_number(self):
        return self.to_float()

    def to_fixnum(self):
        return int(self.realval)

    def to_float(self):
        return self.realval

    def round(self):
        int_part = int(self.realval)
        if self.realval > 0:
            if self.realval >= (int_part + 0.5):
                return int_part + 1

            return int_part

        else:
            if self.realval <= (int_part - 0.5):
                return int_part - 1

            return int_part

    def is_integer(self):
        return self.realval == self.round()

W_Number = W_Real

class W_Integer(W_Real):
    def __init__(self, val):
        self.intval = val
        self.realval = val
        self.exact = True

    def to_string(self):
        return str(self.intval)

    def to_number(self):
        return self.to_fixnum()

    def to_fixnum(self):
        return self.intval

    def to_float(self):
        return float(self.intval)

class W_List(W_Root):
    pass

class W_Pair(W_List):
    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def to_string(self):
        # XXX This should do things differently if (list? self).
        car = self.car.to_string()
        cdr = self.cdr.to_string()
        return "(" + car + " . " + cdr + ")"

    def eval_tr(self, ctx):
        oper = self.car.eval(ctx)
        if not isinstance(oper, W_Callable):
            raise NotCallable(oper)

        #a propper (oper args ...) call
        # self.cdr has to be a proper list
        cdr = self.cdr
        if isinstance(cdr, W_List):
            return oper.call_tr(ctx, cdr)
        else:
            raise SchemeSyntaxError

    def get_car_as_pair(self):
        res = self.car
        if not isinstance(res, W_Pair):
            raise SchemeSyntaxError
        return res

    def get_cdr_as_pair(self):
        res = self.cdr
        if not isinstance(res, W_Pair):
            raise SchemeSyntaxError
        return res

class W_Nil(W_List):
    def to_string(self):
        return "()"

class W_Callable(W_Root):
    def call_tr(self, ctx, lst):
        #usually tail-recursive call is normal call
        # which returns tuple with no further ExecutionContext
        return (self.call(ctx, lst), None)

    def call(self, ctx, lst):
        raise NotImplementedError

    def eval_body(self, ctx, body):
        body_expression = body
        while True:
            if not isinstance(body_expression, W_Pair):
                raise SchemeSyntaxError
            elif isinstance(body_expression.cdr, W_Nil):
                return (body_expression.car, ctx)
            else:
                body_expression.car.eval(ctx)

            body_expression = body_expression.cdr

class W_Procedure(W_Callable):
    def __init__(self, pname=""):
        self.pname = pname

    def to_string(self):
        return "#<primitive-procedure %s>" % (self.pname,)

    def call_tr(self, ctx, lst):
        #evaluate all arguments into list
        arg_lst = []
        arg = lst
        while not isinstance(arg, W_Nil):
            if not isinstance(arg, W_Pair):
                raise SchemeSyntaxError
            w_obj = arg.car.eval(ctx)
            arg_lst.append(w_obj)
            arg = arg.cdr

        return self.procedure_tr(ctx, arg_lst)

    def procedure(self, ctx, lst):
        raise NotImplementedError

    def procedure_tr(self, ctx, lst):
        #usually tail-recursive procedure is normal procedure
        # which returns tuple with no further ExecutionContext
        return (self.procedure(ctx, lst), None)

class W_Macro(W_Callable):
    def __init__(self, pname=""):
        self.pname = pname

    def to_string(self):
        return "#<primitive-macro %s>" % (self.pname,)

class Formal(object):
    def __init__(self, name, islist=False):
        self.name = name
        self.islist = islist

class W_Lambda(W_Procedure):
    def __init__(self, args, body, closure, pname="#f"):
        self.args = []
        arg = args
        while not isinstance(arg, W_Nil):
            if isinstance(arg, W_Identifier):
                self.args.append(Formal(arg.to_string(), True))
                break
            else:
                if not isinstance(arg, W_Pair):
                    raise SchemeSyntaxError
                if not isinstance(arg.car, W_Identifier):
                    raise WrongArgType(arg.car, "Identifier")
                #list of argument names, not evaluated
                self.args.append(Formal(arg.car.to_string(), False))
                arg = arg.cdr

        self.body = body
        self.pname = pname
        self.closure = closure

    def to_string(self):
        return "#<procedure %s>" % (self.pname,)

    def procedure_tr(self, ctx, lst):
        """must be tail-recursive aware, uses eval_body"""
        #ctx is a caller context, which is joyfully ignored

        local_ctx = self.closure.copy()

        #set lambda arguments
        for idx in range(len(self.args)):
            formal = self.args[idx]
            if formal.islist:
                local_ctx.put(formal.name, plst2lst(lst[idx:]))
            else:
                local_ctx.put(formal.name, lst[idx])

        return self.eval_body(local_ctx, self.body)

def plst2lst(plst):
    """coverts python list() of W_Root into W_Pair scheme list"""
    w_cdr = W_Nil()
    plst.reverse()
    for w_obj in plst:
        w_cdr = W_Pair(w_obj, w_cdr)

    return w_cdr

class W_Promise(W_Root):
    def __init__(self, expr, ctx):
        self.expr = expr
        self.result = None
        self.closure = ctx

    def to_string(self):
        return "#<promise: %s>" % self.expr.to_string()

    def force(self, ctx):
        if self.result is None:
            self.result = self.expr.eval(self.closure.copy())

        return self.result

##
# operations
##
class ListOper(W_Procedure):
    def procedure(self, ctx, lst):
        if len(lst) == 0:
            if self.default_result is None:
                raise WrongArgsNumber()

            return self.default_result

        if len(lst) == 1:
            if not isinstance(lst[0], W_Number):
                raise WrongArgType(lst[0], "Number")
            return self.unary_oper(lst[0])

        acc = None
        for arg in lst:
            if not isinstance(arg, W_Number):
                raise WrongArgType(arg, "Number")
            if acc is None:
                acc = arg
            else:
                acc = self.oper(acc, arg)

        return acc

    def unary_oper(self, x):
        if isinstance(x, W_Integer):
            return W_Integer(self.do_unary_oper(x.to_fixnum()))
        elif isinstance(x, W_Number):
            return W_Real(self.do_unary_oper(x.to_float()))
        else:
            raise WrongArgType(x, "Number")

    def oper(self, x, y):
        if isinstance(x, W_Integer) and isinstance(y, W_Integer):
            return W_Integer(self.do_oper(x.to_fixnum(), y.to_fixnum()))
        elif isinstance(x, W_Number) or isinstance(y, W_Number):
            return W_Real(self.do_oper(x.to_float(), y.to_float()))
        else:
            raise WrongArgType(x, "Number")

    def do_oper(self, x, y):
        raise NotImplementedError

    def do_unary_oper(self, x):
        raise NotImplementedError

def create_op_class(oper, unary_oper, title, default_result=None):
    class Op(ListOper):
        pass

    local_locals = {}
    attr_name = "do_oper"

    code = py.code.Source("""
    def %s(self, x, y):
        return x %s y
        """ % (attr_name, oper))

    exec code.compile() in local_locals
    local_locals[attr_name]._annspecialcase_ = 'specialize:argtype(1)'
    setattr(Op, attr_name, local_locals[attr_name])

    attr_name = "do_unary_oper"
    code = py.code.Source("""
    def %s(self, x):
        return %s x
        """ % (attr_name, unary_oper))

    exec code.compile() in local_locals
    local_locals[attr_name]._annspecialcase_ = 'specialize:argtype(1)'
    setattr(Op, attr_name, local_locals[attr_name])

    if default_result is None:
        Op.default_result = None
    else:
        Op.default_result = W_Integer(default_result)

    Op.__name__ = "Op" + title
    return Op

Add = create_op_class('+', '', "Add", 0)
Sub = create_op_class('-', '-', "Sub")
Mul = create_op_class('*', '', "Mul", 1)
Div = create_op_class('/', '1 /', "Div")

class Equal(W_Procedure):
    def procedure(self, ctx, lst):
        if len(lst) < 2:
            return W_Boolean(True)

        prev = lst[0]
        if not isinstance(prev, W_Number):
            raise WrongArgType(prev, "Number")

        for arg in lst[1:]:
            if not isinstance(arg, W_Number):
                raise WrongArgType(arg, "Number")

            if prev.to_number() != arg.to_number():
                return W_Boolean(False)
            prev = arg

        return W_Boolean(True)

class List(W_Procedure):
    def procedure(self, ctx, lst):
        return plst2lst(lst)

class Cons(W_Procedure):
    def procedure(self, ctx, lst):
        w_car = lst[0]
        w_cdr = lst[1]
        #cons is always creating a new pair
        return W_Pair(w_car, w_cdr)

class Car(W_Procedure):
    def procedure(self, ctx, lst):
        w_pair = lst[0]
        if not isinstance(w_pair, W_Pair):
            raise WrongArgType(w_pair, "Pair")
        return w_pair.car

class Cdr(W_Procedure):
    def procedure(self, ctx, lst):
        w_pair = lst[0]
        if not isinstance(w_pair, W_Pair):
            raise WrongArgType(w_pair, "Pair")
        return w_pair.cdr

class Quit(W_Procedure):
    def procedure(self, ctx, lst):
        raise SchemeQuit

class Force(W_Procedure):
    def procedure(self, ctx, lst):
        if len(lst) != 1:
            raise WrongArgsNumber

        w_promise = lst[0]
        if not isinstance(w_promise, W_Promise):
            raise WrongArgType(w_promise, "Promise")

        return w_promise.force(ctx)

##
# Predicate
##
class PredicateNumber(W_Procedure):
    def procedure(self, ctx, lst):
        if len(lst) != 1:
            raise WrongArgsNumber

        w_obj = lst[0]
        if not isinstance(w_obj, W_Number):
            raise WrongArgType(w_obj, 'Number')

        return W_Boolean(self.predicate(w_obj))

    def predicate(self, w_obj):
        raise NotImplementedError

class IntegerP(PredicateNumber):
    def predicate(self, w_obj):
        if not w_obj.exact:
            return w_obj.is_integer()

        return True

class RealP(PredicateNumber):
    def predicate(self, w_obj):
        return isinstance(w_obj, W_Real)

class NumberP(PredicateNumber):
    def predicate(self, w_obj):
        return isinstance(w_obj, W_Number)

class ExactP(PredicateNumber):
    def predicate(self, w_obj):
        return w_obj.exact

class InexactP(PredicateNumber):
    def predicate(self, w_obj):
        return not w_obj.exact

class ZeroP(PredicateNumber):
    def predicate(self, w_obj):
        return w_obj.to_number() == 0.0

class OddP(PredicateNumber):
    def predicate(self, w_obj):
        if not w_obj.is_integer():
            raise WrongArgType(w_obj, "Integer")

        return w_obj.round() % 2 != 0

class EvenP(PredicateNumber):
    def predicate(self, w_obj):
        if not w_obj.is_integer():
            raise WrongArgType(w_obj, "Integer")

        return w_obj.round() % 2 == 0

##
# Macro
##
class Define(W_Macro):
    def call(self, ctx, lst):
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError
        w_first = lst.car
        w_second = lst.get_cdr_as_pair()
        if isinstance(w_first, W_Identifier):
            w_val = w_second.car.eval(ctx)
            ctx.set(w_first.name, w_val)
            return w_val
        elif isinstance(w_first, W_Pair):
            #we have lambda definition here!
            w_name = w_first.car
            if not isinstance(w_name, W_Identifier):
                raise SchemeSyntaxError

            formals = w_first.cdr #isinstance of W_List
            body = w_second
            w_lambda = W_Lambda(formals, body, ctx, pname=w_name.name)
            ctx.set(w_name.name, w_lambda)
            return w_lambda
        else:
            raise WrongArgType(w_first, "Identifier")

class Sete(W_Macro):
    def call(self, ctx, lst):
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError
        w_identifier = lst.car
        if not isinstance(w_identifier, W_Identifier):
            raise WrongArgType(w_identifier, "Identifier")

        w_val = lst.get_cdr_as_pair().car.eval(ctx)
        ctx.sete(w_identifier.name, w_val)
        return w_val

class MacroIf(W_Macro):
    def call_tr(self, ctx, lst):
        """if needs to be tail-recursive aware"""
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError
        w_condition = lst.car
        lst_cdr = lst.get_cdr_as_pair()
        w_then = lst_cdr.car
        if isinstance(lst_cdr.cdr, W_Nil):
            w_else = W_Boolean(False)
        else:
            w_else = lst_cdr.get_cdr_as_pair().car

        w_cond_val = w_condition.eval(ctx)
        if w_cond_val.to_boolean() is True:
            return (w_then, ctx)
        else:
            return (w_else, ctx)

class Lambda(W_Macro):
    def call(self, ctx, lst):
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError(lst, "Pair")
        w_args = lst.car
        w_body = lst.cdr
        return W_Lambda(w_args, w_body, ctx)

class Let(W_Macro):
    def call_tr(self, ctx, lst):
        """let uses eval_body, so it is tail-recursive aware"""
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError
        local_ctx = ctx.copy()
        w_formal = lst.car
        while isinstance(w_formal, W_Pair):
            w_def = w_formal.get_car_as_pair()
            name = w_def.car.to_string()
            #evaluate the values in caller ctx
            w_val = w_def.get_cdr_as_pair().car.eval(ctx)
            local_ctx.put(name, w_val)
            w_formal = w_formal.cdr

        return self.eval_body(local_ctx, lst.cdr)

class LetStar(W_Macro):
    def call_tr(self, ctx, lst):
        """let* uses eval_body, so it is tail-recursive aware"""
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError
        local_ctx = ctx.copy()
        w_formal = lst.car
        while isinstance(w_formal, W_Pair):
            w_def = w_formal.get_car_as_pair()
            name = w_def.car.to_string()
            #evaluate the values in local ctx
            w_val = w_def.get_cdr_as_pair().car.eval(local_ctx)
            local_ctx.put(name, w_val)
            w_formal = w_formal.cdr

        return self.eval_body(local_ctx, lst.cdr)

class Letrec(W_Macro):
    def call_tr(self, ctx, lst):
        """let uses eval_body, so it is tail-recursive aware"""
        if not isinstance(lst, W_Pair):
            raise SchemeSyntaxError
        local_ctx = ctx.copy()
        map_name_expr = {}
        w_formal = lst.car
        while isinstance(w_formal, W_Pair):
            w_def = w_formal.get_car_as_pair()
            name = w_def.car.to_string()
            map_name_expr[name] = w_def.get_cdr_as_pair().car
            local_ctx.bound(name)
            w_formal = w_formal.cdr

        map_name_val = {}
        for (name, expr) in map_name_expr.items():
            map_name_val[name] = expr.eval(local_ctx)

        for (name, w_val) in map_name_val.items():
            local_ctx.sete(name, w_val)

        return self.eval_body(local_ctx, lst.cdr)

def literal(sexpr):
    return W_Pair(W_Identifier('quote'), W_Pair(sexpr, W_Nil()))

class Quote(W_Macro):
    def call(self, ctx, lst):
        if not isinstance(lst, W_List):
            raise SchemeSyntaxError

        return lst.car

class Delay(W_Macro):
    def call(self, ctx, lst):
        if not isinstance(lst, W_List):
            raise SchemeSyntaxError

        return W_Promise(lst.car, ctx)

