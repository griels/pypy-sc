function ll_stack_too_big_helper(depth) {
    if (depth > 0) {
        ll_stack_too_big_helper(depth-1)
    }
}

function ll_stack_too_big() {
    try {
        ll_stack_too_big_helper(10); //XXX
    } catch (e) {   //stack overflow when recursing some more
        return true;
    }
    return false;
}
ll_stack_too_big__ = ll_stack_too_big;

function ll_stack_unwind() {
    throw "Recursion limit exceeded";
}
ll_stack_unwind__ = ll_stack_unwind;
