import os

from pypy.rpython.memory.lladdress import NULL
from pypy.rpython.rstack import yield_current_frame_to_caller


# ____________________________________________________________

def wrap_stackless_function(fn):
    from pypy.translator.js.test.runtest import compile_function
    jsfn = compile_function(fn, [], stackless=True)
    return str(jsfn()) + "\n"
# ____________________________________________________________
# For testing
debug_flag = True

# count of loops in tests (set lower to speed up)
loops = 10
    
def debug(s):
    if debug_flag:
        os.write(2, "%s\n" % s)

class Globals:
    def __init__(self):
        pass

globals = Globals()
globals.count = 0


# ____________________________________________________________

class Resumable(object):
    def __init__(self, fn):
        self.fn = fn
        self.alive = False
        
    def start(self):
        self.caller = yield_current_frame_to_caller()
        self.fn(self.name)
        return self.caller

    def set_resumable(self, resumable):
        self.resumable = resumable

    def suspend(self):
        # we suspend ourself
        self.caller = self.caller.switch()  
        
    def resume(self):
        # the caller resumes me
        self.resumable = self.resumable.switch()  
        self.alive = self.resumable is not None
    
class Tasklet(Resumable):
    def __init__(self, name, fn):
        Resumable.__init__(self, fn)
        self.name = name
        self.blocked = 0
        
        # propogates round suspend-resume to tell scheduler in run()
        # XXX too late to think this thru
        self.remove = False

    def suspend_and_remove(self, remove):
        self.remove = remove
        self.suspend()

    def resume(self):
        assert not self.remove
        Resumable.resume(self)
        
        # not sure what to do with alive yetXXX        

        #XXX arggh - why NOT??
        #if not alive:
        #    self.caller = # None / NULL
        return self.alive and not self.remove         

class Channel:
    def __init__(self):
        self.queue = []
        self.balance = 0

    def send(self, value):
        self.balance += 1
        if self.balance <= 0:
            t = self.queue.pop(0)
            t.data = value
            t.blocked = 0
            t.remove = False
            scheduler.run_immediately(t)
            scheduler.schedule()

            # resuming
            t = getcurrent()
            assert t.blocked == 0
            
        else:
            t = getcurrent()
            assert isinstance(t, Tasklet)
            t.data = value
            # let it wait for a receiver to come along
            self.queue.append(t)
            t.blocked = 1
            schedule_remove()

            # resuming
            assert t == getcurrent()
            assert t.blocked == 0
    
    def receive(self):
        self.balance -= 1
        # good to go
        if self.balance >= 0:
            t = self.queue.pop(0)
            t.blocked = 0
            t.remove = False
            data = t.data
            scheduler.add_tasklet(t)
            return data
        else:
            # queue ourself
            t = getcurrent()
            assert isinstance(t, Tasklet)
            self.queue.append(t)

            # block until send has reenabled me
            t.blocked = -1
            schedule_remove()

            # resuming
            assert t == getcurrent()
            assert t.blocked == 0

            return t.data
    
class Scheduler(object):
    def __init__(self):
        self.runnables = []
        self.current_tasklet = None
        self.immediately_schedule = None

    def add_tasklet(self, tasklet):
        self.runnables.append(tasklet)

    def run_immediately(self, tasklet):
        self.immediately_schedule = tasklet

    def run(self):            
        while self.runnables:
            runnables = self.runnables
            self.runnables = []
            count = 0
            for t in runnables:
                assert self.current_tasklet is None

                self.current_tasklet = t
                if t.resume():
                    self.runnables.append(self.current_tasklet)
                self.current_tasklet = None
                count += 1

                if self.immediately_schedule:
                    self.runnables = [self.immediately_schedule] \
                                     + runnables[count:] + self.runnables
                    self.immediately_schedule = None
                    break
                
    def schedule(self, remove=False):
        assert self.current_tasklet is not None
        self.current_tasklet.suspend_and_remove(remove)
        
# ____________________________________________________________

scheduler = Scheduler()
def start_tasklet(tasklet):
    res = tasklet.start()
    tasklet.set_resumable(res)
    scheduler.add_tasklet(tasklet)

def start_tasklet_now(tasklet):
    res = tasklet.start()
    tasklet.set_resumable(res)
    scheduler.run_immediately(tasklet)
        
def schedule():
    scheduler.schedule()

def schedule_remove():
    scheduler.schedule(remove=True)

def run():
    scheduler.run()

def getcurrent():
    return scheduler.current_tasklet

# ____________________________________________________________

def test_simple():
    
    def simple(name):
        for ii in range(5):
            globals.count += 1
            schedule()

    def f():
        for ii in range(loops):
            start_tasklet(Tasklet("T%s" % ii, simple))
        run()
        return globals.count == loops * 5

    res = wrap_stackless_function(f)
    assert res == '1'

def test_multiple_simple():
    
    def simple(name):
        for ii in range(5):
            globals.count += 1
            schedule()

    def simple2(name):
        for ii in range(5):
            globals.count += 1
            schedule()
            globals.count += 1

    def simple3(name):
        schedule()
        for ii in range(10):
            globals.count += 1
            if ii % 2:
                schedule()
        schedule()

    def f():
        for ii in range(loops):
            start_tasklet(Tasklet("T1%s" % ii, simple))
            start_tasklet(Tasklet("T2%s" % ii, simple2))
            start_tasklet(Tasklet("T3%s" % ii, simple3))
        run()
        return globals.count == loops * 25
    
    res = wrap_stackless_function(f)
    assert res == '1'

def test_schedule_remove():
    
    def simple(name):
        for ii in range(20):
            if ii < 10:
                schedule()
            else:
                schedule_remove()
            globals.count += 1

    def f():
        for ii in range(loops):
            start_tasklet(Tasklet("T%s" % ii, simple))
        run()
        for ii in range(loops):
            start_tasklet(Tasklet("T%s" % ii, simple))
        run()
        return globals.count == loops * 10 * 2

    res = wrap_stackless_function(f)
    assert res == '1'

def test_run_immediately():
    globals.intermediate = 0
    globals.count = 0
    def simple(name):
        for ii in range(20):
            globals.count += 1
            schedule()

    def run_immediately(name):
        globals.intermediate = globals.count
        schedule()
    
    def simple2(name):
        for ii in range(20):
            globals.count += 1
            if ii == 10:
                start_tasklet_now(Tasklet("intermediate", run_immediately))
            schedule()

    def f():
        start_tasklet(Tasklet("simple2", simple2))
        for ii in range(loops):
            start_tasklet(Tasklet("T%s" % ii, simple))        
        run()
        total_expected = (loops + 1) * 20
        return (globals.intermediate == total_expected / 2 + 1 and
                globals.count == total_expected)

    res = wrap_stackless_function(f)
    assert res == '1'

def test_channel1():
    ch = Channel()
        
    def f1(name):
        for ii in range(5):
            ch.send(ii)
            
    def f2(name):
        #while True:
        for ii in range(6):
            globals.count += ch.receive()

    def f():
        start_tasklet(Tasklet("f2", f2))
        start_tasklet(Tasklet("f1", f1))
        run()
        return (globals.count == 10)

    res = wrap_stackless_function(f)
    assert res == '1'

def test_channel2():
    ch = Channel()
        
    def f1(name):
        for ii in range(5):
            ch.send(ii)
            
    def f2(name):
        #while True:
        for ii in range(6):
            res = ch.receive()
            globals.count += res
            
    def f():
        start_tasklet(Tasklet("f1", f1))
        start_tasklet(Tasklet("f2", f2))
        run()
        return (globals.count == 10)

    res = wrap_stackless_function(f)
    assert res == '1'


def test_channel3():
    ch = Channel()
        
    def f1(name):
        for ii in range(5):
            ch.send(ii)
            
    def f2(name):
        #while True:
        for ii in range(16):
            res = ch.receive()
            globals.count += res
            
    def f():
        start_tasklet(Tasklet("f1x", f1))
        start_tasklet(Tasklet("f1xx", f1))
        start_tasklet(Tasklet("f1xxx", f1))
        start_tasklet(Tasklet("f2", f2))
        run()
        return (globals.count == 30)

    res = wrap_stackless_function(f)
    assert res == '1'


def test_channel4():
    """ test with something other than int """

    class A:
        pass
    
    class Data(object):
        pass
    
    class IntData(Data):
        def __init__(self, d):
            self.d = d

    class StringData(Data):
        def __init__(self, d):
            self.d = d

    class InstanceAData(Data):
        def __init__(self, d):
            self.d = d

    ch1 = Channel()
    ch2 = Channel()
    ch3 = Channel()
        
    def f1(name):
        for ii in range(5):
            ch1.send(IntData(ii))

    def f2(name):
        for ii in range(5):
            ch2.send(StringData("asda"))

    def f3(name):
        for ii in range(5):
            ch3.send(StringData("asda"))
            
    def fr(name):
        #while True:
        for ii in range(11):
            data3 = ch3.receive()
            globals.count += 1
            data1 = ch1.receive()
            globals.count += 1
            data2 = ch2.receive()
            globals.count += 1
            
    def f():
        start_tasklet(Tasklet("fr", fr))
        start_tasklet(Tasklet("f1", f1))
        start_tasklet(Tasklet("f2", f2))
        start_tasklet(Tasklet("f3", f3))
        run()
        debug("asd %s" % globals.count)
        return (globals.count == 15)

    res = wrap_stackless_function(f)
    assert res == '1'
    
