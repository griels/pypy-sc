import stackless
if hasattr(stackless,'coroutine'):
    import stackless_ as stackless

DEBUG = False

def print_sched(prev, next):
    try:
        print 'before scheduling. prev: %s, next: %s' % (prev, next)
    except Exception, e:
        print 'Exception in print_sched', e
        print '\tprev:', type(prev)
        print '\tnext:', type(next)
    print

def print_chan(chan, task, sending, willblock):
    print 'channel_action:', chan, task, 's:', sending, ' wb:',
    print willblock
    print

if DEBUG:
    stackless.set_schedule_callback(print_sched)
    stackless.set_channel_callback(print_chan)

def f(outchan):
    for i in range(10):
        print 'T1: sending',i
        outchan.send(i)
        print 'T1: after sending'
    print 'T1: sending -1'
    outchan.send(-1)

def g(inchan):
    while 1:
        print 'T2: before receiving'
        val = inchan.receive()
        print 'T2: received',val
        if val == -1:
            break

ch = stackless.channel()
t1 = stackless.tasklet(f)(ch)
t2 = stackless.tasklet(g)(ch)

stackless.run()
