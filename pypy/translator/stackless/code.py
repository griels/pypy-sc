from pypy.rpython.lltypesystem import lltype, llmemory
from pypy.rpython import rarithmetic

STATE_HEADER = lltype.Struct('state_header',
                             ('f_back', lltype.Ptr(lltype.ForwardReference())),
                             ('state', lltype.Signed))
STATE_HEADER.f_back.TO.become(STATE_HEADER)

null_state = lltype.nullptr(STATE_HEADER)

class StacklessData:
    def __init__(self):
        self.top = null_state
        self.bottom = null_state
        self.restart_substate = 0
        self.retval_long = 0
        self.retval_longlong = rarithmetic.r_longlong(0)
        self.retval_double = 0.0
        self.retval_void_p = llmemory.fakeaddress(None)
        self.exception = None

global_state = StacklessData()

void_void_func = lltype.Ptr(lltype.FuncType([], lltype.Void))
long_void_func = lltype.Ptr(lltype.FuncType([], lltype.Signed))
longlong_void_func = lltype.Ptr(lltype.FuncType([], lltype.SignedLongLong))
float_void_func = lltype.Ptr(lltype.FuncType([], lltype.Float))
pointer_void_func = lltype.Ptr(lltype.FuncType([], llmemory.Address) )

def call_function(fn, signature):
    if signature == 'void':
        fn2 = llmemory.cast_adr_to_ptr(fn, void_void_func)
        fn2()
    elif signature == 'long':
        fn3 = llmemory.cast_adr_to_ptr(fn, long_void_func)
        global_state.long_retval = fn3()
    elif signature == 'longlong':
        fn3 = llmemory.cast_adr_to_ptr(fn, longlong_void_func)
        global_state.longlong_retval = fn3()
    elif signature == 'float':
        fn3 = llmemory.cast_adr_to_ptr(fn, float_void_func)
        global_state.float_retval = fn3()
    elif signature == 'pointer':
        fn5 = llmemory.cast_adr_to_ptr(fn, pointer_void_func)
        global_state.pointer_retval = fn5()

null_address = llmemory.fakeaddress(None)

def decode_state(state):
    return null_address, 'void', 0

class UnwindException(Exception):
    def __init__(self):
        self.frame_top = null_state   # points to frame that first caught 
                                      # the UnwindException 
        self.frame_bottom = null_state 
        # walking frame_top.f_back.f_back... goes to frame_bottom 
        #

def slp_main_loop():
    currentframe = global_state.top
    
    while currentframe is not None:
        nextframe = currentframe.f_back
        framestate = currentframe.state
        fn, signature, global_state.restart_substate = decode_state(framestate)
        try:
            call_function(fn, signature)
        except UnwindException, u:   #XXX annotation support needed 
            nextframe = u.frame_top 
        except Exception, e:
            global_state.exception = e
        else:
            global_state.exception = None

        currentframe = nextframe 

    if global_state.exception is not None:
        raise global_state.exception


def add_frame_state(u, frame_state):
    if not u.frame_top:
        u.frame_top = u.frame_bottom = frame_state
    else:
        u.frame_bottom.f_back = frame_state
        u.frame_bottom = frame_state
        
