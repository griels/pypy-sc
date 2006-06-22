from pypy.interpreter.gateway import ObjSpace
from pypy.rpython import rgc # Force registration of gc.collect
import gc

def collect(space):
    "Run a full collection."
    gc.collect()
    
collect.unwrap_spec = [ObjSpace]

