# The model produced by the flowobjspace
# this is to be used by the translator mainly.
# 
# the below object/attribute model evolved from
# a discussion in Berlin, 4th of october 2003

class FunctionGraph:
    startblock  # 
    returnblock # 
    name        # function name (possibly mangled already)

class Link:
    exitcase    # Constant (or so)
    args        # mixed list of variable/const
    target      # block 

class Block:
    input_args  # mixed list of variable/const 
    operations  # list of SpaceOperation(s)
    exitswitch  # variable
    exits       # list of Link(s)

class ReturnBlock:
    input_args  # a single variable 
    operations = None # for uniformity
    exits = ()  # ?

class Variable:
    name

class Const:
    value     # a concrete value

class SpaceOperation:
    opname    # operation name
    args      # mixed list of variables/Constants (can be mixed)
    result    # either Variable or Constant instance


