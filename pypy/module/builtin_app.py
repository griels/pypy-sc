# XXX kwds yet to come

# Problem: need to decide how to implement iterators,
# which are needed for star args.

def apply(function, args, kwds):
    return function(*args, **kwds)

def map(function, list):
    "docstring"
    return [function(x) for x in list]

def filter(function, list):
    res = []
    if function is None:
       for elem in list:
           if elem:
              res.append(elem)
    else:
       for elem in list:
           if function(elem):
              res.append(elem)
    

def zip(function, list):
    pass

def reduce(function, list, initial = None):
    if initial is None:
       try:
          initial = list.pop(0)
       except IndexError:
          raise TypeError, "reduce() of empty sequence with no initial value"
    for value in list:
       initial = function(initial, value)
    return initial
    
def isinstance(obj, klass_or_tuple):
    objcls = obj.__class__
    if issubclass(klass_or_tuple.__class__, tuple):
       for klass in klass_or_tuple:
           if issubclass(objcls, klass):
              return 1
       return 0
    else:
       try:
          return issubclass(objcls, klass_or_tuple)
       except TypeError:
          raise TypeError, "isinstance() arg 2 must be a class or type"
 
def range(x, y=None, step=1):
    "docstring"

    if y is None:
        start = 0
        stop = x
    else:
        start = x
        stop = y

    arr = []
    i = start
    if step == 0:
        raise ValueError, 'range() arg 3 must not be zero'
    elif step > 0:
        while i < stop:
            arr.append(i)
            i += step
    else:
        while i > stop:
            arr.append(i)
            i += step

    return arr
