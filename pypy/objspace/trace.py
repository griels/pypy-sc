""" 
   Trace object space traces operations and bytecode execution
   in frames. 

"""

from pypy.tool import pydis 
from pypy.interpreter.baseobjspace import ObjSpace

# __________________________________________________________________________
#
# Tracing Events 
# __________________________________________________________________________
#

class ExecBytecode(object):
    """ bytecode trace. """
    def __init__(self, frame):
        self.frame = frame 
        self.code = frame.code 
        self.index = frame.next_instr

class EnterFrame(object):
    def __init__(self, frame):
        self.frame = frame

class LeaveFrame(object):
    def __init__(self, frame):
        self.frame = frame

class CallInfo(object):
    """ encapsulates a function call with its arguments. """
    def __init__(self, name, func, args, kwargs):
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs

class CallBegin(object):
    def __init__(self, callinfo):
        self.callinfo = callinfo

class CallFinished(object):
    def __init__(self, callinfo, res):
        self.callinfo = callinfo
        self.res = res
        
class CallException(object):
    def __init__(self, callinfo, e):
        self.callinfo = callinfo
        self.ex = e

class TraceResult(object):
    """ this is the state of tracing-in-progress. """
    def __init__(self, tracespace):
        self.events = []  
        self.tracespace = tracespace

    def append(self, arg):
        self.events.append(arg)

    def getdisresult(self, frame, _cache = {}):
        """ return (possibly cached) pydis result for the given frame. """
        try:
            return _cache[id(frame.code)]
        except KeyError:
            res = _cache[id(frame.code)] = pydis.pydis(frame.code)
            assert res is not None
            return res

    def getbytecodes(self):
        for event in self.events:
            if isinstance(event, ExecBytecode):
                disres = self.getdisresult(event.frame)
                yield disres.getbytecode(event.index)
               
    def getoperations(self):
        for event in self.events:
            if isinstance(event, (CallBegin, CallFinished, CallException)):
                yield event
                
    def getevents(self):
        for event in self.events:
            yield event

# __________________________________________________________________________
#
# Tracer Proxy objects 
# __________________________________________________________________________
#

class ExecutionContextTracer(object):
    def __init__(self, result, ec):
        self.__ec = ec
        self.__result = result

    def __getattr__(self, name):
        """ generically pass through everything else ... """
        return getattr(self.__ec, name)

    def enter(self, frame):
        """ called just before (continuing to) evaluating a frame. """
        self.__result.append(EnterFrame(frame))
        return self.__ec.enter(frame)

    def leave(self, previous_ec):
        """ called just after evaluating of a frame is suspended/finished. """
        frame = self.__ec.framestack.top()
        self.__result.append(LeaveFrame(frame))
        return self.__ec.leave(previous_ec)

    def bytecode_trace(self, frame):
        """ called just before execution of a bytecode. """
        self.__result.append(ExecBytecode(frame))

class CallableTracer(object):
    def __init__(self, result, name, func):
        self.__result = result
        self.__name = name
        self.__func = func

    def __call__(self, *args, **kwargs):
        callinfo = CallInfo(self.__name, self.__func, args, kwargs) 
        self.__result.append(CallBegin(callinfo))

        try:
            res = self.__func(*args, **kwargs)
        except Exception, e:
            self.__result.append(CallException(callinfo, e))
            raise 
        else:
            self.__result.append(CallFinished(callinfo, res))
            return res

    def __getattr__(self, name):
        """ generically pass through everything we don't intercept. """
        return getattr(self.__func, name)

    def __str__(self):
        return "%s - CallableTracer(%s)" % (self.__name, self.__func)
    __repr = __str__
# __________________________________________________________________________
#
# Tracer factory 
# __________________________________________________________________________
#            

operations = None
def get_operations():
    global operations
    if operations is None:
        operations = dict([(r[0], r[0]) for r in ObjSpace.MethodTable])
        for name in ["is_true", "newtuple", "newlist", "newstring", "newdict",
                     "newslice", "call_args", "is_", "get_and_call_function",
                     "wrap", "unwrap"]:
            operations[name] = name

    return operations

def create_trace_space(space = None, operations = None):    
    """ Will create a trace object space if no space supplied.  Otherwise
    will turn the supplied into a tracable space by extending its class."""

    # Don't trace an already tracable space
    if hasattr(space, "__pypytrace___"):
        return space
    
    if space is None:
        # make up a TrivialObjSpace by default
        # ultimately, remove this hack and fix the -P option of tests
        from pypy.objspace import trivial
        space = trivial.TrivialObjSpace()

    if operations is None:
        operations = get_operations()

    class Trace(space.__class__):

        def __getattribute__(self, name):
            obj = super(Trace, self).__getattribute__(name)
            if name in operations:
                assert callable(obj)
                obj = CallableTracer(self._result, name, obj)
            return obj

        def __pypytrace___(self):
            pass

        def settrace(self):
            self._result = TraceResult(self)

        def getresult(self):
            return self._result
            
        def getexecutioncontext(self):
            ec = super(Trace, self).getexecutioncontext()
            assert not isinstance(ec, ExecutionContextTracer)
            return ExecutionContextTracer(self._result, ec)
        
        def reset_trace(self):
            """ Returns the class to it's original form. """
            space.__class__ = space.__oldclass___
            del space.__oldclass___

            if hasattr(self, "_result"):
                del self._result            

    trace_clz = type("Trace" + space.__class__.__name__, (Trace,), {})
    space.__oldclass___, space.__class__ = space.__class__, trace_clz
    space.settrace()
    return space

# ______________________________________________________________________
# End of trace.py

