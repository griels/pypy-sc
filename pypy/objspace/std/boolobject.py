
class W_BoolObject:
    delegate_once = {}

    def __init__(w_self, boolval):  # please pass in a real bool, not an int
        w_self.boolval = boolval

    def __eq__(w_self, w_other):
        "Implements 'is'."
        # all w_False wrapped values are equal ('is'-identical)
        # and so do all w_True wrapped values
        return (isinstance(w_other, W_BoolObject) and
                w_self.boolval == w_other.boolval)
