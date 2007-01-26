from pypy.interpreter.baseobjspace import ObjSpace, W_Root, Wrappable
from pypy.interpreter.error import OperationError
from pypy.interpreter.gateway import interp2app
from pypy.interpreter.typedef import TypeDef
from pypy.rpython.ootypesystem import ootype
from pypy.translator.cli.dotnet import CLR, box, unbox, NativeException, native_exc,\
     new_array, init_array, typeof

System = CLR.System
TargetInvocationException = NativeException(CLR.System.Reflection.TargetInvocationException)
AmbiguousMatchException = NativeException(CLR.System.Reflection.AmbiguousMatchException)

def get_method(space, b_type, name, b_paramtypes):
    try:
        return b_type.GetMethod(name, b_paramtypes)
    except AmbiguousMatchException:
        msg = 'Multiple overloads for %s could match' % name
        raise OperationError(space.w_TypeError, space.wrap(msg))


def rewrap_args(space, w_args, startfrom):
    args = space.unpackiterable(w_args)
    paramlen = len(args)-startfrom
    b_args = new_array(System.Object, paramlen)
    b_paramtypes = new_array(System.Type, paramlen)
    for i in range(startfrom, len(args)):
        j = i-startfrom
        b_obj = py2cli(space, args[i])
        b_args[j] = b_obj
        b_paramtypes[j] = b_obj.GetType() # XXX: potentially inefficient
    return b_args, b_paramtypes


def call_method(space, b_obj, b_type, name, w_args, startfrom):
    b_args, b_paramtypes = rewrap_args(space, w_args, startfrom)
    b_meth = get_method(space, b_type, name, b_paramtypes)
    try:
        # for an explanation of the box() call, see the log message for revision 35167
        b_res = box(b_meth.Invoke(b_obj, b_args))
    except TargetInvocationException, e:
        b_inner = native_exc(e).get_InnerException()
        message = str(b_inner.get_Message())
        # TODO: use the appropriate exception, not StandardError
        raise OperationError(space.w_StandardError, space.wrap(message))
    return cli2py(space, b_res)

def call_staticmethod(space, typename, methname, w_args):
    b_type = System.Type.GetType(typename) # XXX: cache this!
    return call_method(space, None, b_type, methname, w_args, 0)
call_staticmethod.unwrap_spec = [ObjSpace, str, str, W_Root]

def py2cli(space, w_obj):
    if space.is_true(space.isinstance(w_obj, space.w_int)):
        return box(space.int_w(w_obj))
    if space.is_true(space.isinstance(w_obj, space.w_float)):
        return box(space.float_w(w_obj))
    else:
        typename = space.type(w_obj).getname(space, '?')
        msg = "Can't convert type %s to .NET" % typename
        raise OperationError(space.w_TypeError, space.wrap(msg))

def cli2py(space, b_obj):
    b_type = b_obj.GetType()
    # TODO: support other types
    if b_type == typeof(System.Int32):
        intval = unbox(b_obj, ootype.Signed)
        return space.wrap(intval)
    elif b_type == typeof(System.Double):
        floatval = unbox(b_obj, ootype.Float)
        return space.wrap(floatval)
    else:
        msg = "Can't convert object %s to Python" % str(b_obj.ToString())
        raise OperationError(space.w_TypeError, space.wrap(msg))


class W_CliObject(Wrappable):
    def __init__(self, space, b_obj):
        self.space = space
        self.b_obj = b_obj

    def call_method(self, name, w_args, startfrom=0):
        return call_method(self.space, self.b_obj, self.b_obj.GetType(), name, w_args, startfrom)
    call_method.unwrap_spec = ['self', str, W_Root, int]


def cli_object_new(space, w_subtype, typename):
    b_type = System.Type.GetType(typename)
    b_ctor = b_type.GetConstructor(init_array(System.Type))
    b_obj = b_ctor.Invoke(init_array(System.Object))
    return space.wrap(W_CliObject(space, b_obj))
cli_object_new.unwrap_spec = [ObjSpace, W_Root, str]


W_CliObject.typedef = TypeDef(
    '_CliObject_internal',
    __new__ = interp2app(cli_object_new),
    call_method = interp2app(W_CliObject.call_method),
    )
