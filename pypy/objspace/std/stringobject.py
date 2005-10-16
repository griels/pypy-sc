# -*- Coding: Latin-1 -*-

from pypy.objspace.std.objspace import *
from pypy.interpreter import gateway
from pypy.rpython.rarithmetic import intmask, ovfcheck, _hash_string
from pypy.rpython.objectmodel import we_are_translated
from pypy.objspace.std.intobject   import W_IntObject
from pypy.objspace.std.sliceobject import W_SliceObject
from pypy.objspace.std import slicetype
from pypy.objspace.std.listobject import W_ListObject
from pypy.objspace.std.noneobject import W_NoneObject
from pypy.objspace.std.tupleobject import W_TupleObject

# XXX consider reimplementing _value to be a list of characters
#     instead of a plain string


class W_StringObject(W_Object):
    from pypy.objspace.std.stringtype import str_typedef as typedef

    def __init__(w_self, space, str):
        W_Object.__init__(w_self, space)
        w_self._value = str

    def __repr__(w_self):
        """ representation for debugging purposes """
        return "%s(%r)" % (w_self.__class__.__name__, w_self._value)

    def unwrap(w_self):
        return w_self._value


registerimplementation(W_StringObject)


def _is_generic(w_self, fun): 
    space = w_self.space   
    v = w_self._value
    if len(v) == 0:
        return space.w_False
    if len(v) == 1:
        c = v[0]
        return space.newbool(fun(c))
    else:
        for idx in range(len(v)):
            if not fun(v[idx]):
                return space.w_False
        return space.w_True
_is_generic._annspecialcase_ = "specialize:arg1"

def _upper(ch):
    if ch.islower():
        o = ord(ch) - 32
        return chr(o)
    else:
        return ch
    
def _lower(ch):
    if ch.isupper():
        o = ord(ch) + 32
        return chr(o)
    else:
        return ch

_isspace = lambda c: c.isspace()
_isdigit = lambda c: c.isdigit()
_isalpha = lambda c: c.isalpha()
_isalnum = lambda c: c.isalnum()

def str_isspace__String(space, w_self):
    return _is_generic(w_self, _isspace)

def str_isdigit__String(space, w_self):
    return _is_generic(w_self, _isdigit)

def str_isalpha__String(space, w_self):
    return _is_generic(w_self, _isalpha)

def str_isalnum__String(space, w_self):
    return _is_generic(w_self, _isalnum)

def str_isupper__String(space, w_self):
    """Return True if all cased characters in S are uppercase and there is
at least one cased character in S, False otherwise."""
    space = w_self.space   
    v = w_self._value
    if len(v) == 1:
        c = v[0]
        return space.newbool(c.isupper())
    cased = False
    for idx in range(len(v)):
        if v[idx].islower():
            return space.w_False
        elif not cased and v[idx].isupper():
            cased = True
    return space.newbool(cased)

def str_islower__String(space, w_self):
    """Return True if all cased characters in S are lowercase and there is
at least one cased character in S, False otherwise."""
    space = w_self.space   
    v = w_self._value
    if len(v) == 1:
        c = v[0]
        return space.newbool(c.islower())
    cased = False
    for idx in range(len(v)):
        if v[idx].isupper():
            return space.w_False
        elif not cased and v[idx].islower():
            cased = True
    return space.newbool(cased)

def str_istitle__String(space, w_self):
    """Return True if S is a titlecased string and there is at least one
character in S, i.e. uppercase characters may only follow uncased
characters and lowercase characters only cased ones. Return False
otherwise."""
    input = w_self._value
    cased = False
    previous_is_cased = False

    for pos in range(0, len(input)):
        ch = input[pos]
        if ch.isupper():
            if previous_is_cased:
                return space.w_False
            previous_is_cased = True
            cased = True
        elif ch.islower():
            if not previous_is_cased:
                return space.w_False
            cased = True
        else:
            previous_is_cased = False

    return space.newbool(cased)

def str_upper__String(space, w_self):
    self = w_self._value
    res = [' '] * len(self)
    for i in range(len(self)):
        ch = self[i]
        res[i] = _upper(ch)

    return space.wrap("".join(res))

def str_lower__String(space, w_self):
    self = w_self._value
    res = [' '] * len(self)
    for i in range(len(self)):
        ch = self[i]
        res[i] = _lower(ch)

    return space.wrap("".join(res))

def str_swapcase__String(space, w_self):
    self = w_self._value
    res = [' '] * len(self)
    for i in range(len(self)):
        ch = self[i]
        if ch.isupper():
            o = ord(ch) + 32
            res[i] = chr(o)
        elif ch.islower():
            o = ord(ch) - 32
            res[i] = chr(o)
        else:
            res[i] = ch

    return space.wrap("".join(res))

    
def str_capitalize__String(space, w_self):
    input = w_self._value
    buffer = [' '] * len(input)
    if len(input) > 0:
        ch = input[0]
        if ch.islower():
            o = ord(ch) - 32
            buffer[0] = chr(o)
        else:
            buffer[0] = ch

        for i in range(1, len(input)):
            ch = input[i]
            if ch.isupper():
                o = ord(ch) + 32
                buffer[i] = chr(o)
            else:
                buffer[i] = ch

    return space.wrap("".join(buffer))
         
def str_title__String(space, w_self):
    input = w_self._value
    buffer = [' '] * len(input)
    prev_letter=' '

    for pos in range(0, len(input)):
        ch = input[pos]
        if not prev_letter.isalpha():
            buffer[pos] = _upper(ch)
        else:
            buffer[pos] = _lower(ch)

        prev_letter = buffer[pos]

    return space.wrap("".join(buffer))

def str_split__String_None_ANY(space, w_self, w_none, w_maxsplit=-1):
    maxsplit = space.int_w(w_maxsplit)
    res_w = []
    value = w_self._value
    length = len(value)
    i = 0
    while True:
        # find the beginning of the next word
        while i < length:
            if not value[i].isspace():
                break   # found
            i += 1
        else:
            break  # end of string, finished

        # find the end of the word
        if maxsplit == 0:
            j = length   # take all the rest of the string
        else:
            j = i + 1
            while j < length and not value[j].isspace():
                j += 1
            maxsplit -= 1   # NB. if it's already < 0, it stays < 0

        # the word is value[i:j]
        res_w.append(W_StringObject(space, value[i:j]))

        # continue to look from the character following the space after the word
        i = j + 1

    return W_ListObject(space, res_w)


def str_split__String_String_ANY(space, w_self, w_by, w_maxsplit=-1):
    maxsplit = space.int_w(w_maxsplit)
    res_w = []
    start = 0
    value = w_self._value
    by = w_by._value
    bylen = len(by)
    if bylen == 0:
        raise OperationError(space.w_ValueError, space.wrap("empty separator"))

    while maxsplit != 0:
        next = value.find(by, start)
        if next < 0:
            break
        res_w.append(W_StringObject(space, value[start:next]))
        start = next + bylen
        maxsplit -= 1   # NB. if it's already < 0, it stays < 0

    res_w.append(W_StringObject(space, value[start:]))

    return W_ListObject(w_self.space, res_w)

def str_rsplit__String_None_ANY(space, w_self, w_none, w_maxsplit=-1):
    maxsplit = space.int_w(w_maxsplit)
    res_w = []
    value = w_self._value
    i = len(value)-1
    while True:
        # starting from the end, find the end of the next word
        while i >= 0:
            if not value[i].isspace():
                break   # found
            i -= 1
        else:
            break  # end of string, finished

        # find the start of the word
        # (more precisely, 'j' will be the space character before the word)
        if maxsplit == 0:
            j = -1   # take all the rest of the string
        else:
            j = i - 1
            while j >= 0 and not value[j].isspace():
                j -= 1
            maxsplit -= 1   # NB. if it's already < 0, it stays < 0

        # the word is value[j+1:i+1]
        j1 = j + 1
        assert j1 >= 0
        res_w.append(W_StringObject(space, value[j1:i+1]))

        # continue to look from the character before the space before the word
        i = j - 1

    res_w.reverse()
    return W_ListObject(space, res_w)

def str_rsplit__String_String_ANY(space, w_self, w_by, w_maxsplit=-1):
    maxsplit = space.int_w(w_maxsplit)
    res_w = []
    value = w_self._value
    end = len(value)
    by = w_by._value
    bylen = len(by)
    if bylen == 0:
        raise OperationError(space.w_ValueError, space.wrap("empty separator"))

    while maxsplit != 0:
        next = value.rfind(by, 0, end)
        if next < 0:
            break
        res_w.append(W_StringObject(space, value[next+bylen:end]))
        end = next
        maxsplit -= 1   # NB. if it's already < 0, it stays < 0

    res_w.append(W_StringObject(space, value[:end]))
    res_w.reverse()
    return W_ListObject(w_self.space, res_w)

def str_join__String_ANY(space, w_self, w_list):
    list = space.unpackiterable(w_list)
    str_w = space.str_w
    if list:
        self = w_self._value
        firstelem = 1
        listlen = 0
        reslen = 0
        #compute the length of the resulting string 
        for i in range(len(list)):
            if not space.is_true(space.isinstance(list[i], space.w_str)):
                if space.is_true(space.isinstance(list[i], space.w_unicode)):
                    w_u = space.call_function(space.w_unicode, w_self)
                    return space.call_method(w_u, "join", space.newlist(list))
                raise OperationError(
                    space.w_TypeError,
                    space.wrap("sequence item %d: expected string, %s "
                               "found"%(i, space.type(list[i]).name)))
            reslen = reslen + len(str_w(list[i]))
            listlen = listlen + 1

        reslen = reslen + (listlen - 1) * len(self)

        #allocate the string buffer
        res = [' '] * reslen

        pos = 0
        #fill in the string buffer
        for w_item in list:
            item = str_w(w_item)
            if firstelem:
                for i in range(len(item)):
                    res[i+pos] = item[i]
                pos = pos + len(item)
                firstelem = 0
            else:
                for i in range(len(self)):
                    res[i+pos] = self[i]
                pos = pos + len(self)
                 
                for i in range(len(item)):
                    res[i+pos] = item[i]
                pos = pos + len(item)

        return space.wrap("".join(res))
    else:
        return space.wrap("")


def str_rjust__String_ANY_ANY(space, w_self, w_arg, w_fillchar):

    u_arg = space.int_w(w_arg)
    u_self = w_self._value
    fillchar = space.str_w(w_fillchar)
    if len(fillchar) != 1:
        raise OperationError(space.w_TypeError,
            space.wrap("rjust() argument 2 must be a single character"))
    
    d = u_arg - len(u_self)
    if d>0:
        fillchar = fillchar[0]    # annotator hint: it's a single character
        u_self = d * fillchar + u_self
        
    return space.wrap(u_self)


def str_ljust__String_ANY_ANY(space, w_self, w_arg, w_fillchar):

    u_self = w_self._value
    u_arg = space.int_w(w_arg)
    fillchar = space.str_w(w_fillchar)
    if len(fillchar) != 1:
        raise OperationError(space.w_TypeError,
            space.wrap("ljust() argument 2 must be a single character"))

    d = u_arg - len(u_self)
    if d>0:
        fillchar = fillchar[0]    # annotator hint: it's a single character
        u_self += d * fillchar
        
    return space.wrap(u_self)

def _convert_idx_params(space, w_self, w_sub, w_start, w_end):
    self = w_self._value
    sub = w_sub._value
    w_start = slicetype.adapt_bound(space, w_start, space.wrap(len(self)))
    w_end = slicetype.adapt_bound(space, w_end, space.wrap(len(self)))

    start = space.int_w(w_start)
    end = space.int_w(w_end)
    assert start >= 0
    assert end >= 0

    return (self, sub, start, end)

def contains__String_String(space, w_self, w_sub):
    self = w_self._value
    sub = w_sub._value
    return space.newbool(self.find(sub) >= 0)

def str_find__String_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.find(sub, start, end)
    return space.wrap(res)

def str_rfind__String_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.rfind(sub, start, end)
    return space.wrap(res)

def str_index__String_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.find(sub, start, end)
    if res < 0:
        raise OperationError(space.w_ValueError,
                             space.wrap("substring not found in string.index"))

    return space.wrap(res)


def str_rindex__String_String_ANY_ANY(space, w_self, w_sub, w_start, w_end):

    (self, sub, start, end) =  _convert_idx_params(space, w_self, w_sub, w_start, w_end)
    res = self.rfind(sub, start, end)
    if res < 0:
        raise OperationError(space.w_ValueError,
                             space.wrap("substring not found in string.rindex"))

    return space.wrap(res)


def str_replace__String_String_String_ANY(space, w_self, w_sub, w_by, w_maxsplit=-1):

    input = w_self._value
    sub = w_sub._value
    by = w_by._value
    maxsplit = space.int_w(w_maxsplit)   #I don't use it now

    #print "from replace, input: %s, sub: %s, by: %s" % (input, sub, by)

    #what do we have to replace?
    startidx = 0
    indices = []
    foundidx = input.find(sub, startidx)
    while foundidx >= 0 and maxsplit != 0:
        indices.append(foundidx)
        if len(sub) == 0:
            #so that we go forward, even if sub is empty
            startidx = foundidx + 1
        else: 
            startidx = foundidx + len(sub)        
        foundidx = input.find(sub, startidx)
        maxsplit = maxsplit - 1
    indiceslen = len(indices)
    buf = [' '] * (len(input) - indiceslen * len(sub) + indiceslen * len(by))
    startidx = 0

    #ok, so do it
    bufpos = 0
    for i in range(indiceslen):
        for j in range(startidx, indices[i]):
            buf[bufpos] = input[j]
            bufpos = bufpos + 1
 
        for j in range(len(by)):
            buf[bufpos] = by[j]
            bufpos = bufpos + 1

        startidx = indices[i] + len(sub)

    for j in range(startidx, len(input)):
        buf[bufpos] = input[j]
        bufpos = bufpos + 1 
    return space.wrap("".join(buf))

##def _find(self, sub, start, end, dir):

##    length = len(self)

##    #adjust_indicies
##    if (end > length):
##        end = length
##    elif (end < 0):
##        end += length
##    if (end < 0):
##        end = 0
##    if (start < 0):
##        start += length
##    if (start < 0):
##        start = 0

##    if dir > 0:
##        if len(sub) == 0 and start < end:
##            return start

##        end = end - len(sub) + 1

##        for i in range(start, end):
##            match = 1
##            for idx in range(len(sub)):
##                if sub[idx] != self[idx+i]:
##                    match = 0
##                    break
##            if match: 
##                return i
##        return -1
##    else:
##        if len(sub) == 0 and start < end:
##            return end

##        end = end - len(sub)

##        for j in range(end, start-1, -1):
##            match = 1
##            for idx in range(len(sub)):
##                if sub[idx] != self[idx+j]:
##                    match = 0
##                    break
##            if match:
##                return j
##        return -1        


def _strip(space, w_self, w_chars, left, right):
    "internal function called by str_xstrip methods"
    u_self = w_self._value
    u_chars = w_chars._value
    
    lpos = 0
    rpos = len(u_self)
    
    if left:
        #print "while %d < %d and -%s- in -%s-:"%(lpos, rpos, u_self[lpos],w_chars)
        while lpos < rpos and u_self[lpos] in u_chars:
           lpos += 1
       
    if right:
        while rpos > lpos and u_self[rpos - 1] in u_chars:
           rpos -= 1
       
    assert rpos >= lpos    # annotator hint, don't remove
    return space.wrap(u_self[lpos:rpos])

def _strip_none(space, w_self, left, right):
    "internal function called by str_xstrip methods"
    u_self = w_self._value
    
    lpos = 0
    rpos = len(u_self)
    
    if left:
        #print "while %d < %d and -%s- in -%s-:"%(lpos, rpos, u_self[lpos],w_chars)
        while lpos < rpos and u_self[lpos].isspace():
           lpos += 1
       
    if right:
        while rpos > lpos and u_self[rpos - 1].isspace():
           rpos -= 1
       
    assert rpos >= lpos    # annotator hint, don't remove
    return space.wrap(u_self[lpos:rpos])

def str_strip__String_String(space, w_self, w_chars):
    return _strip(space, w_self, w_chars, left=1, right=1)

def str_strip__String_None(space, w_self, w_chars):
    return _strip_none(space, w_self, left=1, right=1)
   
def str_rstrip__String_String(space, w_self, w_chars):
    return _strip(space, w_self, w_chars, left=0, right=1)

def str_rstrip__String_None(space, w_self, w_chars):
    return _strip_none(space, w_self, left=0, right=1)

   
def str_lstrip__String_String(space, w_self, w_chars):
    return _strip(space, w_self, w_chars, left=1, right=0)

def str_lstrip__String_None(space, w_self, w_chars):
    return _strip_none(space, w_self, left=1, right=0)



def str_center__String_ANY_ANY(space, w_self, w_arg, w_fillchar):
    u_self = w_self._value
    u_arg  = space.int_w(w_arg)
    fillchar = space.str_w(w_fillchar)
    if len(fillchar) != 1:
        raise OperationError(space.w_TypeError,
            space.wrap("center() argument 2 must be a single character"))

    d = u_arg - len(u_self) 
    if d>0:
        offset = d//2
        fillchar = fillchar[0]    # annotator hint: it's a single character
        u_centered = offset * fillchar + u_self + (d - offset) * fillchar
    else:
        u_centered = u_self

    return W_StringObject(space, u_centered)

def str_count__String_String_ANY_ANY(space, w_self, w_arg, w_start, w_end): 
    u_self  = w_self._value
    u_arg   = w_arg._value

    w_start = slicetype.adapt_bound(space, w_start, space.wrap(len(u_self)))
    w_end = slicetype.adapt_bound(space, w_end, space.wrap(len(u_self)))
    u_start = space.int_w(w_start)
    u_end = space.int_w(w_end)
    assert u_start >= 0
    assert u_end >= 0

    if len(u_arg) == 0:
        count = len(u_self) + 1
    else:
        count = 0  
        while 1: 
            pos = u_self.find(u_arg, u_start, u_end)
            if pos < 0:
                break
            count += 1
            u_start = pos + len(u_arg)
       
    return W_IntObject(space, count)


def str_endswith__String_String_ANY_ANY(space, w_self, w_suffix, w_start, w_end):
    (u_self, suffix, start, end) = _convert_idx_params(space, w_self,
                                                       w_suffix, w_start, w_end)
    begin = end - len(suffix)
    if begin < start:
        return space.w_False
    for i in range(len(suffix)):
        if u_self[begin+i] != suffix[i]:
            return space.w_False
    return space.w_True
    
    
def str_startswith__String_String_ANY_ANY(space, w_self, w_prefix, w_start, w_end):
    (u_self, prefix, start, end) = _convert_idx_params(space, w_self,
                                                       w_prefix, w_start, w_end)
    stop = start + len(prefix)
    if stop > end:
        return space.w_False
    for i in range(len(prefix)):
        if u_self[start+i] != prefix[i]:
            return space.w_False
    return space.w_True
    
    
def _tabindent(u_token, u_tabsize):
    "calculates distance behind the token to the next tabstop"
    
    distance = u_tabsize
    if u_token:    
        distance = 0
        offset = len(u_token)

        while 1:
            #no sophisticated linebreak support now, '\r' just for passing adapted CPython test
            if u_token[offset-1] == "\n" or u_token[offset-1] == "\r":
                break;
            distance += 1
            offset -= 1
            if offset == 0:
                break
                
        #the same like distance = len(u_token) - (offset + 1)
        #print '<offset:%d distance:%d tabsize:%d token:%s>' % (offset, distance, u_tabsize, u_token)
        distance = (u_tabsize-distance) % u_tabsize
        if distance == 0:
            distance=u_tabsize

    return distance    
    
    
def str_expandtabs__String_ANY(space, w_self, w_tabsize):   
    u_self = w_self._value
    u_tabsize  = space.int_w(w_tabsize)
    
    u_expanded = ""
    if u_self:
        split = u_self.split("\t") #XXX use pypy split
        u_expanded =oldtoken = split.pop(0)

        for token in split:  
            #print  "%d#%d -%s-" % (_tabindent(oldtoken,u_tabsize), u_tabsize, token)
            u_expanded += " " * _tabindent(oldtoken,u_tabsize) + token
            oldtoken = token
            
    return W_StringObject(space, u_expanded)        
 
 
def str_splitlines__String_ANY(space, w_self, w_keepends):
    data = w_self._value
    u_keepends  = space.int_w(w_keepends)  # truth value, but type checked
    selflen = len(data)
    
    L = []
    i = j = 0
    while i < selflen:
        # Find a line and append it
        while i < selflen and data[i] != '\n' and data[i] != '\r':
            i += 1
        # Skip the line break reading CRLF as one line break
        eol = i
        i += 1
        if i < selflen and data[i-1] == '\r' and data[i] == '\n':
            i += 1
        if u_keepends:
            eol = i
        L.append(W_StringObject(space, data[j:eol]))
        j = i

    if j < selflen:
        L.append(W_StringObject(space, data[j:]))

    return W_ListObject(space, L)

def str_zfill__String_ANY(space, w_self, w_width):
    input = w_self._value
    width = space.int_w(w_width)

    if len(input) >= width:
        # cannot return w_self, in case it is a subclass of str
        return space.wrap(input)

    buf = [' '] * width
    if len(input) > 0 and (input[0] == '+' or input[0] == '-'):
        buf[0] = input[0]
        start = 1
        middle = width - len(input) + 1
    else:
        start = 0
        middle = width - len(input)

    for i in range(start, middle):
        buf[i] = '0'

    for i in range(middle, width):
        buf[i] = input[start]
        start = start + 1
    
    return space.wrap("".join(buf))

def str_w__String(space, w_str):
    return w_str._value

def hash__String(space, w_str):
    s = w_str._value
    if we_are_translated():
        x = hash(s)            # to use the hash cache in rpython strings
    else:
        x = _hash_string(s)    # to make sure we get the same hash as rpython
        # (otherwise translation will freeze W_DictObjects where we can't find
        #  the keys any more!)
    return W_IntObject(space, x)

def lt__String_String(space, w_str1, w_str2):
    s1 = w_str1._value
    s2 = w_str2._value
    if s1 < s2:
        return space.w_True
    else:
        return space.w_False    

def le__String_String(space, w_str1, w_str2):
    s1 = w_str1._value
    s2 = w_str2._value
    if s1 <= s2:
        return space.w_True
    else:
        return space.w_False

def eq__String_String(space, w_str1, w_str2):
    s1 = w_str1._value
    s2 = w_str2._value
    if s1 == s2:
        return space.w_True
    else:
        return space.w_False

def ne__String_String(space, w_str1, w_str2):
    s1 = w_str1._value
    s2 = w_str2._value
    if s1 != s2:
        return space.w_True
    else:
        return space.w_False

def gt__String_String(space, w_str1, w_str2):
    s1 = w_str1._value
    s2 = w_str2._value
    if s1 > s2:
        return space.w_True
    else:
        return space.w_False

def ge__String_String(space, w_str1, w_str2):
    s1 = w_str1._value
    s2 = w_str2._value
    if s1 >= s2:
        return space.w_True
    else:
        return space.w_False

def getitem__String_ANY(space, w_str, w_index):
    ival = space.int_w(w_index)
    str = w_str._value
    slen = len(str)
    if ival < 0:
        ival += slen
    if ival < 0 or ival >= slen:
        exc = space.call_function(space.w_IndexError,
                                  space.wrap("string index out of range"))
        raise OperationError(space.w_IndexError, exc)
    return W_StringObject(space, str[ival])

def getitem__String_Slice(space, w_str, w_slice):
    w = space.wrap
    s = w_str._value
    length = len(s)
    start, stop, step, sl = w_slice.indices4(length)
    if sl == 0:
        str = ""
    elif step == 1:
        assert start >= 0 and stop >= 0
        str = s[start:stop]
    else:
        str = "".join([s[start + i*step] for i in range(sl)])
    return W_StringObject(space, str)

def _makebuf(length):
    """This helper needs to be a separate function so that we can safely
    catch the MemoryErrors that it raises."""
    return ['\x00'] * length

def mul_string_times(space, w_str, w_times):
    try:
        mul = space.int_w(w_times)
    except OperationError, e:
        if e.match(space, space.w_TypeError):
            raise FailedToImplement
        raise    
    input = w_str._value
    if mul < 0:
        return space.wrap("")
    input_len = len(input)
    try:
        buffer = _makebuf(ovfcheck(mul*input_len))
    except (MemoryError,OverflowError,ValueError):
        # ugh. ValueError is what you get on 64-bit machines for
        # integers in range(2**31, 2**63).
        raise OperationError( space.w_OverflowError, space.wrap("repeated string is too long: %d %d" % (input_len,mul) ))

    pos = 0
    for i in range(mul):
        for j in range(len(input)):
            buffer[pos] = input[j]
            pos = pos + 1

    return space.wrap("".join(buffer))

def mul__String_ANY(space, w_str, w_times):
    return mul_string_times(space, w_str, w_times)

def mul__ANY_String(space, w_times, w_str):
    return mul_string_times(space, w_str, w_times)

def add__String_String(space, w_left, w_right):
    right = w_right._value
    left = w_left._value
    buf = [' '] * (len(left) + len(right))
    for i in range(len(left)):
        buf[i] = left[i]
    for i in range(len(right)):
        buf[i+len(left)] = right[i]
    return space.wrap("".join(buf))

def len__String(space, w_str):
    return space.wrap(len(w_str._value))

def str__String(space, w_str):
    if type(w_str) is W_StringObject:
        return w_str
    return W_StringObject(space, w_str._value)

def iter__String(space, w_list):
    from pypy.objspace.std import iterobject
    return iterobject.W_SeqIterObject(space, w_list)

def ord__String(space, w_str):
    u_str = w_str._value
    if len(u_str) != 1:
        raise OperationError(
            space.w_TypeError,
            space.wrap("ord() expected a character, but string "
                       "of length %d found"%(len(w_str._value),)))
    return space.wrap(ord(u_str))

def getnewargs__String(space, w_str):
    return space.newtuple([W_StringObject(space, w_str._value)])

   
app = gateway.applevel(r'''
    def str_translate__String_ANY_ANY(s, table, deletechars=''):
        """charfilter - unicode handling is not implemented
        
        Return a copy of the string where all characters occurring 
        in the optional argument deletechars are removed, and the 
        remaining characters have been mapped through the given translation table, 
        which must be a string of length 256"""

        if len(table) < 256:
            raise ValueError("translation table must be 256 characters long")

        L =  [ table[ord(s[i])] for i in range(len(s)) if s[i] not in deletechars ]
        return ''.join(L)

    def repr__String(s):
        quote = "'"
        if quote in s and '"' not in s:
            quote = '"'
        repr = quote
        for c in s:
            if c == '\\' or c == quote: 
                repr += '\\'+c
            elif c == '\t': repr += '\\t'
            elif c == '\r': repr += '\\r'
            elif c == '\n': repr += '\\n'
            elif not '\x20' <= c < '\x7f':
                n = ord(c)
                repr += '\\x'+"0123456789abcdef"[n>>4]+"0123456789abcdef"[n&0xF]
            else:
                repr += c
        repr += quote
        return repr

    def str_decode__String_ANY_ANY(str, encoding=None, errors=None):
        import codecs
        if encoding is None and errors is None:
            return unicode(str)
        elif errors is None:
            return codecs.getdecoder(encoding)(str)[0]
        else:
            return codecs.getdecoder(encoding)(str, errors)[0]

    def str_encode__String_ANY_ANY(str, encoding=None, errors=None):
        import codecs
        if encoding is None and errors is None:
            return unicode(str)
        elif errors is None:
            return codecs.getencoder(encoding)(str)[0]
        else:
            return codecs.getencoder(encoding)(str, errors)[0]
''', filename=__file__) 

# this one should do the import of _formatting:
app2 = gateway.applevel('''
    import _formatting

    def mod__String_ANY(format, values):
        if isinstance(values, tuple):
            return _formatting.format(format, values, None)
        else:
            # CPython's logic for deciding if  ""%values  is
            # an error (1 value, 0 %-formatters) or not
            # (values is of a mapping type)
            if (hasattr(values, '__getitem__')
                and not isinstance(values, basestring)):
                return _formatting.format(format, (values,), values)
            else:
                return _formatting.format(format, (values,), None)
''', filename=__file__)

str_translate__String_ANY_ANY = app.interphook('str_translate__String_ANY_ANY') 
str_decode__String_ANY_ANY = app.interphook('str_decode__String_ANY_ANY') 
str_encode__String_ANY_ANY = app.interphook('str_encode__String_ANY_ANY') 
repr__String = app.interphook('repr__String') 
mod__String_ANY = app2.interphook('mod__String_ANY') 

# register all methods
from pypy.objspace.std import stringtype
register_all(vars(), stringtype)
