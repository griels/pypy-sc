
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

# XXX We do not make any garbage collection. We'll need it at some point

"""
TODO list:

1. Move it to more than one file
2. Refactor it a bit (split class into logical/bookkeeper one)
3. Add some garbage collection
4. Add caching of objects that are presented (even on name level)
"""

from pypymagic import pypy_repr

import types
from marshal import dumps

class AbstractProtocol(object):
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
        'n' : types.NoneType,
        'lst' : list,
        'fun' : types.FunctionType,
        'cus' : object,
        'meth' : types.MethodType,
        'type' : type,
        'tp' : None,
    }
    type_letters = dict([(value, key) for key, value in letter_types.items()])
    assert len(type_letters) == len(letter_types)
    
    def __init__(self):
        self.remote_objects = {} # a dictionary controller --> id
        self.objs = [] # we just store everything, maybe later
           # we'll need some kind of garbage collection
    
    def register_obj(self, obj):
        self.objs.append(obj)
        return len(self.objs) - 1

    def wrap(self, obj):
        """ Wrap an object as sth prepared for sending
        """
        tp = type(obj)
        ctrl = get_transparent_controller(obj)
        if ctrl:
            return "tp", self.remote_objects[ctrl]
        elif obj is None:
            return self.type_letters[tp]
        elif tp in (str, int, float, long, unicode, bool):
            # simple, immutable object, just copy
            return (self.type_letters[tp], obj)
        elif tp is tuple:
            # we just pack all of the items
            return ('t', tuple([self.wrap(elem) for elem in obj]))
        elif tp in (list, dict, types.FunctionType):
            id = self.register_obj(obj)
            return (self.type_letters[tp], id)
        elif tp is type:
            id = self.register_type(obj)
            return (self.type_letters[tp], id)
        elif tp is types.MethodType:
            type_id = self.register_type(obj.im_class)
            w_func = self.wrap(obj.im_func)
            w_self = self.wrap(obj.im_self)
            return (self.type_letters[tp], (type_id, \
                self.wrap(obj.im_func.func_name), w_func, w_self))
        else:
            id = self.register_obj(obj)
            type_id = self.register_type(tp)
            return ("cus", (type_id, id))
    
    def unwrap(self, data):
        """ Unwrap an object
        """
        if data == 'n':
            return None
        tp_letter, obj_data = data
        tp = self.letter_types[tp_letter]
        if tp is None:
            return self.objs[obj_data]
        elif tp in (str, int, float, long, unicode, bool):
            return obj_data # this is the object
        elif tp is tuple:
            return tuple([self.unwrap(i) for i in obj_data])
        elif tp in (list, dict, types.FunctionType):
            id = obj_data
            ro = RemoteObject(self, id)
            self.remote_objects[ro.perform] = id
            return proxy(tp, ro.perform)
        elif tp is types.MethodType:
            type_id, w_name, w_func, w_self = obj_data
            tp = self.get_type(type_id)
            name = self.unwrap(w_name)
            self_ = self.unwrap(w_self)
            if self_:
                return getattr(tp, name).__get__(self_, tp)
            func = self.unwrap(w_func)
            setattr(tp, name, func)
            return getattr(tp, name)
        elif tp is type:
            id = obj_data
            elem = self.get_type(obj_data)
            return elem
        elif tp is object:
            # we need to create a proper type
            type_id, id = obj_data
            real_tp = self.get_type(type_id)
            ro = RemoteObject(self, id)
            self.remote_objects[ro.perform] = id
            return proxy(real_tp, ro.perform)
        else:
            raise NotImplementedError("Cannot unwrap %s" % (data,))
    
    def perform(self, *args, **kwargs):
        raise NotImplementedError("Abstract only protocol")
    
    # some simple wrappers
    def pack_args(self, args, kwargs):
        args = [self.wrap(i) for i in args]
        kwargs = dict([(self.wrap(key), self.wrap(val)) for key, val in kwargs.items()])
        return args, kwargs
    
    def unpack_args(self, args, kwargs):
        args = [self.unwrap(i) for i in args]
        kwargs = dict([(self.unwrap(key), self.unwrap(val)) for key, val in kwargs.items()])
        return args, kwargs
    
class LocalProtocol(AbstractProtocol):
    """ This is stupid protocol for testing purposes only
    """
    def __init__(self):
        super(LocalProtocol, self).__init__()
        self.types = []
   
    def perform(self, id, name, *args, **kwargs):
        obj = self.objs[id]
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
            send(("finished", wrap(protocol.exported_names[data])))
        elif command == 'call':
            id, name, args, kwargs = data
            args, kwargs = protocol.unpack_args(args, kwargs)
            retval = getattr(protocol.objs[id], name)(*args, **kwargs)
            send(("finished", wrap(retval)))
        elif command == 'finished':
            return unwrap(data)
        elif command == 'type_reg':
            type_id, name, _dict = data
            protocol.register_fake_type(type_id, name, _dict)
        else:
            raise NotImplementedError("command %s" % command)

class RemoteProtocol(AbstractProtocol):
    #def __init__(self, gateway, remote_code):
    #    self.gateway = gateway
    def __init__(self, send, receive, exported_names={}):
        super(RemoteProtocol, self).__init__()
        self.exported_names = exported_names
        self.send = send
        self.receive = receive
        self.type_cache = {}
        self.type_id = 0
        self.remote_types = {}
    
    def perform(self, id, name, *args, **kwargs):
        args, kwargs = self.pack_args(args, kwargs)
        self.send(('call', (id, name, args, kwargs)))
        retval = remote_loop(self)
        return retval
    
    def get_remote(self, name):
        self.send(("get", name))
        retval = remote_loop(self)
        return retval
    
    def register_type(self, tp):
        try:
            return self.type_cache[tp]
        except KeyError:
            print "Registering type %s as %s" % (tp, self.type_id)
            self.type_cache[tp] = self.type_id
            tp_id = self.type_id
            self.type_id += 1
        
        # XXX: We don't support inheritance here, nor recursive types
        #      shall we???
        _dict = dict([(key, self.wrap(getattr(tp, key))) for key in dir(tp) 
            if key not in ('__dict__', '__weakref__', '__class__', '__new__',
                '__base__', '__flags__', '__mro__', '__bases__')])
        self.send(("type_reg", (tp_id, 
            tp.__name__, _dict)))
        return tp_id
    
    def register_fake_type(self, type_id, _name, _dict):
        print "Faking type %s as %s" % (_name, type_id)
        # create and register new type
        d = dict([(key, None) for key in _dict])
        if '__doc__' in _dict:
            d['__doc__'] = self.unwrap(_dict['__doc__'])
        tp = type(_name, (object,), d)
        self.remote_types[type_id] = tp
        for key, value in _dict.items():
            if key != '__doc__':
                try:
                    setattr(tp, key, self.unwrap(value))
                except TypeError:
                    import pdb;pdb.set_trace()
    
    def get_type(self, id):
        try:
            return self.remote_types[id]
        except KeyError:
            print "Warning!!! Type %d is not present by now" % id
            return object

class RemoteObject(object):
    def __init__(self, protocol, id):
        self.id = id
        self.protocol = protocol
    
    def perform(self, name, *args, **kwargs):
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
