from pypy.rpython import objectmodel


def ll_stackless_stack_frames_depth():
    return objectmodel.stack_frames_depth()
ll_stackless_stack_frames_depth.suggested_primitive = True

def ll_stackless_stack_too_big():
    return objectmodel.stack_too_big()
ll_stackless_stack_too_big.suggested_primitive = True
