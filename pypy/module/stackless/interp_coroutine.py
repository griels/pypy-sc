from pypy.interpreter.baseobjspace import Wrappable
from pypy.interpreter.argument import Arguments
from pypy.interpreter.typedef import GetSetProperty, TypeDef
from pypy.interpreter.typedef import interp_attrproperty, interp_attrproperty_w
from pypy.interpreter.gateway import interp2app, ObjSpace, W_Root
from pypy.interpreter.error import OperationError
from pypy.rpython.rarithmetic import intmask

from pypy.rpython.rstack import yield_current_frame_to_caller

import sys

class CoState(object):
    def __init__(self):
        self.last = self.current = self.main = Coroutine()
        self.things_to_do = False
        self.temp_exc = None
        self.del_first = None
        self.del_last = None

costate = None

class CoroutineDamage(SystemError):
    pass

class CoroutineExit(SystemExit):
    # XXX SystemExit's __init__ creates problems in bookkeeper.
    # XXX discuss this with the gurus :-)
    def __init__(self):
        pass

class Coroutine(Wrappable):

    def __init__(self):
        self.frame = None
        if costate is None:
            self.parent = self
        else:
            self.parent = costate.main

    def bind(self, thunk):
        if self.frame is not None:
            raise CoroutineDamage
        self.frame = self._bind(thunk)

    def _bind(self, thunk):
        self.parent = costate.current
        costate.last.frame = yield_current_frame_to_caller()
        try:
            thunk.call()
        except CoroutineExit:
            # ignore a shutdown exception
            pass
        except Exception, e:
            # redirect all unhandled exceptions to the parent
            costate.things_to_do = True
            costate.temp_exc = e
        if self.parent.frame is None:
            self.parent = costate.main
        return self._update_state(self.parent)

    def switch(self):
        if self.frame is None:
            raise CoroutineDamage
        costate.last.frame = self._update_state(self).switch()
        # note that last gets updated before assignment!
        if costate.things_to_do:
            do_things_to_do(self)

    def _update_state(new):
        costate.last, costate.current = costate.current, new
        frame, new.frame = new.frame, None
        return frame
    _update_state = staticmethod(_update_state)

    def kill(self):
        self._userdel()
        if costate.current is self:
            raise CoroutineExit
        costate.things_to_do = True
        costate.temp_exc = CoroutineExit()
        self.parent = costate.current
        self.switch()

    def __del__(self):
        # provide the necessary clean-up if this coro is left
        # with a frame.
        # note that AppCoroutine has to take care about this
        # as well, including a check for user-supplied __del__.
        # Additionally note that in the context of __del__, we are
        # not in the position to issue a switch.
        # we defer it completely.
        if self.frame is not None:
            postpone_deletion(self)

    def _userdel(self):
        # override this for exposed coros
        pass

## later:   or self.space.lookup(self, '__del__') is not None

def postpone_deletion(obj):
    costate.things_to_do = True
    if costate.del_first is None:
        costate.del_first = costate.del_last = obj
    costate.del_last.parent = obj
    costate.del_last = obj
    obj.parent = costate.del_first

def do_things_to_do(obj):
    if costate.temp_exc is not None:
        # somebody left an unhandled exception and switched to us.
        # this both provides default exception handling and the
        # way to inject an exception, like CoroutineExit.
        e, costate.temp_exc = costate.temp_exc, None
        costate.things_to_do = costate.del_first is not None
        raise e
    if costate.del_first is not None:
        obj = costate.del_first
        costate.del_first = obj.parent
        obj.parent = costate.current
        if obj is costate.del_last:
            costate.del_first = costate.del_last = None
        obj.kill()
    else:
        costate.things_to_do = False

costate = CoState()


class _AppThunk(object):

    def __init__(self, space, w_callable, args):
        self.space = space
        self.w_func = w_callable
        self.args = args

    def call(self):
        self.space.call_args(self.w_func, self.args)

class AppCoroutine(Coroutine):

    def descr_method__new__(space, w_subtype):
        co = space.allocate_instance(AppCoroutine, w_subtype)
        AppCoroutine.__init__(co)
        co.space = space
        return space.wrap(co)

    def w_bind(self, w_func, __args__):
        thunk = _AppThunk(self.space, w_func, __args__)
        self.bind(thunk)

    def w_switch(self):
        self.switch()

AppCoroutine.typedef = TypeDef("Coroutine",
    __new__ = interp2app(AppCoroutine.descr_method__new__.im_func),
    bind = interp2app(AppCoroutine.w_bind,
                      unwrap_spec=['self', W_Root, Arguments]),
    switch = interp2app(AppCoroutine.w_switch),
)
