
""" Distributed controller(s) for use with transparent proxy objects

First idea:

1. We use py.execnet to create a connection to wherever
2. We run some code there (RSync in advance makes some sense)
3. We access remote objects like normal ones, with a special protocol

Local side:
  - Request an object from remote side from global namespace as simple
    --- request(name) --->
  - Receive an object which is in protocol described below which is
    constructed as shallow copy of the remote type.

    Shallow copy is defined as follows:

    - for interp-level object that we know we can provide transparent proxy
      we just do that

    - for others we fake or fail depending on object

    - for user objects, we create a class which fakes all attributes of
      a class as transparent proxies of remote objects, we create an instance
      of that class and populate __dict__

    - for immutable types, we just copy that

Remote side:
  - we run code, whatever we like
  - additionally, we've got thread exporting stuff (or just exporting
    globals, whatever)
  - for every object, we just send an object, or provide a protocol for
    sending it in a different way.

"""

try:
    from pypymagic import transparent_proxy as proxy
    from pypymagic import get_transparent_controller
except ImportError:
    raise ImportError("Cannot work without transparent proxy functional")

from distributed.objkeeper import ObjKeeper
import sys

# XXX We do not make any garbage collection. We'll need it at some point

"""
TODO list:

1. Add some garbage collection
2. Add caching of objects that are presented (even on name level)
3. Add exceptions, frames and error handling
"""

from pypymagic import pypy_repr

import types
from marshal import dumps

class AbstractProtocol(object):
    immutable_primitives = (str, int, float, long, unicode, bool, types.NotImplementedType)
    mutable_primitives = (list, dict, types.FunctionType, types.FrameType)
    
    letter_types = {
        'l' : list,
        'd' : dict,
        't' : tuple,
        'i' : int,
        'b' : bool,
        'f' : float,
        'u' : unicode,
        'l' : long,
        's' : str,
        'ni' : types.NotImplementedType,
        'n' : types.NoneType,
        'lst' : list,
        'fun' : types.FunctionType,
        'cus' : object,
        'meth' : types.MethodType,
        'type' : type,
        'tp' : None,
        'fr' : types.FrameType,
    }
    type_letters = dict([(value, key) for key, value in letter_types.items()])
    assert len(type_letters) == len(letter_types)
    
    def __init__(self, exported_names={}):
        self.keeper = ObjKeeper(exported_names)
        #self.remote_objects = {} # a dictionary controller --> id
        #self.objs = [] # we just store everything, maybe later
        #   # we'll need some kind of garbage collection

    def wrap(self, obj):
        """ Wrap an object as sth prepared for sending
        """
        tp = type(obj)
        ctrl = get_transparent_controller(obj)
        if ctrl:
            return "tp", self.keeper.get_remote_object(ctrl)
        elif obj is None:
            return self.type_letters[tp]
        elif tp in self.immutable_primitives:
            # simple, immutable object, just copy
            return (self.type_letters[tp], obj)
        elif tp is tuple:
            # we just pack all of the items
            return ('t', tuple([self.wrap(elem) for elem in obj]))
        elif tp in self.mutable_primitives:
            id = self.keeper.register_object(obj)
            return (self.type_letters[tp], id)
        elif tp is type:
            try:
                return self.type_letters[tp], self.type_letters[obj]
            except KeyError:
                id = self.register_type(obj)
                return (self.type_letters[tp], id)
        elif tp is types.MethodType:
            w_class = self.wrap(obj.im_class)
            w_func = self.wrap(obj.im_func)
            w_self = self.wrap(obj.im_self)
            return (self.type_letters[tp], (w_class, \
                self.wrap(obj.im_func.func_name), w_func, w_self))
        else:
            id = self.keeper.register_object(obj)
            w_tp = self.wrap(tp)
            return ("cus", (w_tp, id))
    
    def unwrap(self, data):
        """ Unwrap an object
        """
        if data == 'n':
            return None
        tp_letter, obj_data = data
        tp = self.letter_types[tp_letter]
        if tp is None:
            return self.keeper.get_object(obj_data)
        elif tp in self.immutable_primitives:
            return obj_data # this is the object
        elif tp is tuple:
            return tuple([self.unwrap(i) for i in obj_data])
        elif tp in self.mutable_primitives:
            id = obj_data
            ro = RemoteBuiltinObject(self, id)
            self.keeper.register_remote_object(ro.perform, id)
            p = proxy(tp, ro.perform)
            ro.obj = p
            return p
        elif tp is types.MethodType:
            w_class, w_name, w_func, w_self = obj_data
            tp = self.unwrap(w_class)
            name = self.unwrap(w_name)
            self_ = self.unwrap(w_self)
            if self_:
                return getattr(tp, name).__get__(self_, tp)
            func = self.unwrap(w_func)
            setattr(tp, name, func)
            return getattr(tp, name)
        elif tp is type:
            if isinstance(obj_data, str):
                return self.letter_types[obj_data]
            id = obj_data
            return self.get_type(obj_data)
        elif tp is object:
            # we need to create a proper type
            w_tp, id = obj_data
            real_tp = self.unwrap(w_tp)
            ro = RemoteObject(self, id)
            self.keeper.register_remote_object(ro.perform, id)
            p = proxy(real_tp, ro.perform)
            ro.obj = p
            return p
        else:
            raise NotImplementedError("Cannot unwrap %s" % (data,))
    
    def perform(self, *args, **kwargs):
        raise NotImplementedError("Abstract only protocol")
    
    # some simple wrappers
    def pack_args(self, args, kwargs):
        return self.pack_list(args), self.pack_dict(kwargs)
    
    def pack_list(self, lst):
        return [self.wrap(i) for i in lst]
    
    def pack_dict(self, d):
        return dict([(self.wrap(key), self.wrap(val)) for key, val in d.items()])
    
    def unpack_args(self, args, kwargs):
        return self.unpack_list(args), self.unpack_dict(kwargs)
    
    def unpack_list(self, lst):
        return [self.unwrap(i) for i in lst]
    
    def unpack_dict(self, d):
        return dict([(self.unwrap(key), self.unwrap(val)) for key, val in d.items()])
    
    def register_type(self, tp):
        return self.keeper.register_type(self, tp)
    
    def get_type(self, id):
        return self.keeper.get_type(id)
    
class LocalProtocol(AbstractProtocol):
    """ This is stupid protocol for testing purposes only
    """
    def __init__(self):
        super(LocalProtocol, self).__init__()
        self.types = []
   
    def perform(self, id, name, *args, **kwargs):
        obj = self.keeper.get_object(id)
        # we pack and than unpack, for tests
        args, kwargs = self.pack_args(args, kwargs)
        assert isinstance(name, str)
        dumps((args, kwargs))
        args, kwargs = self.unpack_args(args, kwargs)
        return getattr(obj, name)(*args, **kwargs)
    
    def register_type(self, tp):
        self.types.append(tp)
        return len(self.types) - 1
    
    def get_type(self, id):
        return self.types[id]

def remote_loop(protocol):
    # the simplest version possible, without any concurrency and such
    wrap = protocol.wrap
    unwrap = protocol.unwrap
    send = protocol.send
    receive = protocol.receive
    # we need this for wrap/unwrap
    while 1:
        command, data = receive()
        if command == 'get':
            # XXX: Error recovery anyone???
            send(("finished", wrap(protocol.keeper.exported_names[data])))
        elif command == 'call':
            id, name, args, kwargs = data
            args, kwargs = protocol.unpack_args(args, kwargs)
            retval = getattr(protocol.keeper.get_object(id), name)(*args, **kwargs)
            send(("finished", wrap(retval)))
        elif command == 'finished':
            return unwrap(data)
        elif command == 'type_reg':
            type_id, name, _dict = data
            protocol.keeper.fake_remote_type(protocol, type_id, name, _dict)
        elif command == 'force':
            obj = protocol.keeper.get_object(data)
            w_obj = protocol.pack(obj)
            send(("forced", w_obj))
        elif command == 'forced':
            obj = protocol.unpack(data)
            return obj
        else:
            raise NotImplementedError("command %s" % command)

class RemoteProtocol(AbstractProtocol):
    #def __init__(self, gateway, remote_code):
    #    self.gateway = gateway
    def __init__(self, send, receive, exported_names={}):
        super(RemoteProtocol, self).__init__(exported_names)
        #self.exported_names = exported_names
        self.send = send
        self.receive = receive
        #self.type_cache = {}
        #self.type_id = 0
        #self.remote_types = {}
    
    def perform(self, id, name, *args, **kwargs):
        args, kwargs = self.pack_args(args, kwargs)
        self.send(('call', (id, name, args, kwargs)))
        retval = remote_loop(self)
        return retval
    
    def get_remote(self, name):
        self.send(("get", name))
        retval = remote_loop(self)
        return retval
    
    def force(self, id):
        self.send(("force", id))
        retval = remote_loop(self)
        return retval
    
    def pack(self, obj):
        if isinstance(obj, list):
            return "l", self.pack_list(obj)
        elif isinstance(obj, dict):
            return "d", self.pack_dict(obj)
        else:
            raise NotImplementedError("Cannot pack %s" % obj)
        
    def unpack(self, data):
        letter, w_obj = data
        if letter == 'l':
            return self.unpack_list(w_obj)
        elif letter == 'd':
            return self.unpack_dict(w_obj)
        else:
            raise NotImplementedError("Cannot unpack %s" % (data,))

class RemoteObject(object):
    def __init__(self, protocol, id):
        self.id = id
        self.protocol = protocol
    
    def perform(self, name, *args, **kwargs):
        return self.protocol.perform(self.id, name, *args, **kwargs)

class RemoteBuiltinObject(RemoteObject):
    def __init__(self, protocol, id):
        self.id = id
        self.protocol = protocol
        self.forced = False
    
    def perform(self, name, *args, **kwargs):
        # XXX: Check who really goes here
        if self.forced:
            return getattr(self.obj, name)(*args, **kwargs)
        if name in ('__eq__', '__ne__', '__lt__', '__gt__', '__ge__', '__le__',
            '__cmp__'):
            self.obj = self.protocol.force(self.id)
            return getattr(self.obj, name)(*args, **kwargs)
        return self.protocol.perform(self.id, name, *args, **kwargs)

def test_env(exported_names):
    from stackless import channel, tasklet, run
    # XXX: This is a hack, proper support for recursive type is needed
    inp, out = channel(), channel()
    remote_protocol = RemoteProtocol(inp.send, out.receive, exported_names)
    t = tasklet(remote_loop)(remote_protocol)
    return RemoteProtocol(out.send, inp.receive)

#def bootstrap(gw):
#    import py
#    import sys
#    return gw.remote_exec(py.code.Source(sys.modules[__name__], "remote_loop(channel.send, channel.receive)"))
