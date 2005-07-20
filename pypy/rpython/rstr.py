from weakref import WeakValueDictionary
from pypy.annotation.pairtype import pairtype
from pypy.annotation import model as annmodel
from pypy.rpython.rmodel import Repr, TyperError, IntegerRepr
from pypy.rpython.rmodel import StringRepr, CharRepr, inputconst, UniCharRepr
from pypy.rpython.rarithmetic import intmask
from pypy.rpython.robject import PyObjRepr, pyobj_repr
from pypy.rpython.rtuple import TupleRepr
from pypy.rpython import rint
from pypy.rpython.rslice import SliceRepr
from pypy.rpython.rslice import startstop_slice_repr, startonly_slice_repr
from pypy.rpython.rslice import minusone_slice_repr
from pypy.rpython.lltype import GcStruct, Signed, Array, Char, Ptr, malloc
from pypy.rpython.lltype import Bool, Void, GcArray, nullptr, typeOf, pyobjectptr
from pypy.rpython.rclass import InstanceRepr


# ____________________________________________________________
#
#  Concrete implementation of RPython strings:
#
#    struct str {
#        hash: Signed
#        chars: array of Char
#    }

STR = GcStruct('rpy_string', ('hash',  Signed),
                             ('chars', Array(Char)))

SIGNED_ARRAY = GcArray(Signed)


class __extend__(annmodel.SomeString):
    def rtyper_makerepr(self, rtyper):
        return string_repr
    def rtyper_makekey(self):
        return self.__class__,

class __extend__(annmodel.SomeChar):
    def rtyper_makerepr(self, rtyper):
        return char_repr
    def rtyper_makekey(self):
        return self.__class__,

class __extend__(annmodel.SomeUnicodeCodePoint):
    def rtyper_makerepr(self, rtyper):
        return unichar_repr
    def rtyper_makekey(self):
        return self.__class__,

CONST_STR_CACHE = WeakValueDictionary()
string_repr = StringRepr()
char_repr   = CharRepr()
unichar_repr = UniCharRepr()


class __extend__(StringRepr):
    lowleveltype = Ptr(STR)

    def convert_const(self, value):
        if value is None:
            return nullptr(STR)
        #value = getattr(value, '__self__', value)  # for bound string methods
        if not isinstance(value, str):
            raise TyperError("not a str: %r" % (value,))
        try:
            return CONST_STR_CACHE[value]
        except KeyError:
            p = malloc(STR, len(value))
            for i in range(len(value)):
                p.chars[i] = value[i]
            ll_strhash(p)   # precompute the hash
            CONST_STR_CACHE[value] = p
            return p

    def get_ll_eq_function(self):
        return ll_streq

    def rtype_len(_, hop):
        v_str, = hop.inputargs(string_repr)
        return hop.gendirectcall(ll_strlen, v_str)

    def rtype_is_true(self, hop):
        s_str = hop.args_s[0]
        if s_str.can_be_None:
            v_str, = hop.inputargs(string_repr)
            return hop.gendirectcall(ll_str_is_true, v_str)
        else:
            # defaults to checking the length
            return super(StringRepr, self).rtype_is_true(hop)

    def rtype_ord(_, hop):
        v_str, = hop.inputargs(string_repr)
        c_zero = inputconst(Signed, 0)
        v_chr = hop.gendirectcall(ll_stritem_nonneg, v_str, c_zero)
        return hop.genop('cast_char_to_int', [v_chr], resulttype=Signed)

    def rtype_hash(_, hop):
        v_str, = hop.inputargs(string_repr)
        return hop.gendirectcall(ll_strhash, v_str)

    def rtype_method_startswith(_, hop):
        v_str, v_value = hop.inputargs(string_repr, string_repr)
        return hop.gendirectcall(ll_startswith, v_str, v_value)

    def rtype_method_endswith(_, hop):
        v_str, v_value = hop.inputargs(string_repr, string_repr)
        return hop.gendirectcall(ll_endswith, v_str, v_value)

    def rtype_method_find(_, hop):
        v_str, v_value = hop.inputargs(string_repr, string_repr)
        return hop.gendirectcall(ll_find, v_str, v_value)

    def rtype_method_upper(_, hop):
        v_str, = hop.inputargs(string_repr)
        return hop.gendirectcall(ll_upper, v_str)
        
    def rtype_method_lower(_, hop):
        v_str, = hop.inputargs(string_repr)
        return hop.gendirectcall(ll_lower, v_str)
        
    def rtype_method_join(_, hop):
        if hop.s_result.is_constant():
            return inputconst(string_repr, hop.s_result.const)
        r_lst = hop.args_r[1]
        v_str, v_lst = hop.inputargs(string_repr, r_lst)
        cname = inputconst(Void, "items")
        v_items = hop.genop("getfield", [v_lst, cname],
                            resulttype=r_lst.lowleveltype.TO.items)
        if hop.args_s[0].is_constant() and hop.args_s[0].const == '':
            if r_lst.item_repr == string_repr:
                llfn = ll_join_strs
            elif r_lst.item_repr == char_repr:
                llfn = ll_join_chars
            else:
                raise TyperError("''.join() of non-string list: %r" % r_lst)
            return hop.gendirectcall(llfn, v_items)
        else:
            if r_lst.item_repr == string_repr:
                llfn = ll_join
            else:
                raise TyperError("sep.join() of non-string list: %r" % r_lst)
            return hop.gendirectcall(llfn, v_str, v_items)

    def rtype_method_split(_, hop):
        v_str, v_chr = hop.inputargs(string_repr, char_repr)
        c = hop.inputconst(Void, hop.r_result.lowleveltype)
        return hop.gendirectcall(ll_split_chr, c, v_str, v_chr)

    def rtype_method_replace(_, hop):
        if not (hop.args_r[1] == char_repr and hop.args_r[2] == char_repr):
            raise TyperError, 'replace only works for char args'
        v_str, v_c1, v_c2 = hop.inputargs(string_repr, char_repr, char_repr)
        return hop.gendirectcall(ll_replace_chr_chr, v_str, v_c1, v_c2)

    def rtype_int(_, hop):
	if hop.nb_args == 1:
	    v_str, = hop.inputargs(string_repr)
	    c_base = inputconst(Signed, 10)
	    return hop.gendirectcall(ll_int, v_str, c_base)
        if not hop.args_r[1] == rint.signed_repr:
            raise TyperError, 'base needs to be an int'
	v_str, v_base= hop.inputargs(string_repr, rint.signed_repr)
	return hop.gendirectcall(ll_int, v_str, v_base)

    def ll_str(s, r):
        if typeOf(s) == Char:
            return ll_chr2str(s)
        else:
            return s
    ll_str = staticmethod(ll_str)
        
    def make_iterator_repr(self):
        return string_iterator_repr

class __extend__(pairtype(StringRepr, IntegerRepr)):
    def rtype_getitem(_, hop):
        v_str, v_index = hop.inputargs(string_repr, Signed)
        if hop.args_s[1].nonneg:
            llfn = ll_stritem_nonneg
        else:
            llfn = ll_stritem
        return hop.gendirectcall(llfn, v_str, v_index)

    def rtype_mod(_, hop):
        return do_stringformat(hop, [(hop.args_v[1], hop.args_r[1])])


class __extend__(pairtype(StringRepr, SliceRepr)):

    def rtype_getitem((_, r_slic), hop):
        if r_slic == startonly_slice_repr:
            v_str, v_start = hop.inputargs(string_repr, startonly_slice_repr)
            return hop.gendirectcall(ll_stringslice_startonly, v_str, v_start)
        if r_slic == startstop_slice_repr:
            v_str, v_slice = hop.inputargs(string_repr, startstop_slice_repr)
            return hop.gendirectcall(ll_stringslice, v_str, v_slice)
        if r_slic == minusone_slice_repr:
            v_str, v_ignored = hop.inputargs(string_repr, minusone_slice_repr)
            return hop.gendirectcall(ll_stringslice_minusone, v_str)
        raise TyperError(r_slic)


class __extend__(pairtype(StringRepr, StringRepr)):
    def rtype_add(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        return hop.gendirectcall(ll_strconcat, v_str1, v_str2)
    rtype_inplace_add = rtype_add

    def rtype_eq(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        return hop.gendirectcall(ll_streq, v_str1, v_str2)
    
    def rtype_ne(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        vres = hop.gendirectcall(ll_streq, v_str1, v_str2)
        return hop.genop('bool_not', [vres], resulttype=Bool)

    def rtype_lt(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        vres = hop.gendirectcall(ll_strcmp, v_str1, v_str2)
        return hop.genop('int_lt', [vres, hop.inputconst(Signed, 0)],
                         resulttype=Bool)

    def rtype_le(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        vres = hop.gendirectcall(ll_strcmp, v_str1, v_str2)
        return hop.genop('int_le', [vres, hop.inputconst(Signed, 0)],
                         resulttype=Bool)

    def rtype_ge(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        vres = hop.gendirectcall(ll_strcmp, v_str1, v_str2)
        return hop.genop('int_ge', [vres, hop.inputconst(Signed, 0)],
                         resulttype=Bool)

    def rtype_gt(_, hop):
        v_str1, v_str2 = hop.inputargs(string_repr, string_repr)
        vres = hop.gendirectcall(ll_strcmp, v_str1, v_str2)
        return hop.genop('int_gt', [vres, hop.inputconst(Signed, 0)],
                         resulttype=Bool)

    def rtype_mod(_, hop):
        return do_stringformat(hop, [(hop.args_v[1], hop.args_r[1])])

class __extend__(pairtype(StringRepr, CharRepr)):
    def rtype_contains(_, hop):
        v_str, v_chr = hop.inputargs(string_repr, char_repr)
        return hop.gendirectcall(ll_contains, v_str, v_chr)
    
def parse_fmt_string(fmt):
    # we support x, d, s, f, [r]

    it = iter(fmt)
    r = []
    curstr = ''
    for c in it:
        if c == '%':
            f = it.next()
            if f == '%':
                curstr += '%'
                continue

            if curstr:
                r.append(curstr)
            curstr = ''
            if f not in 'xdosrf':
                raise TyperError("Unsupported formatting specifier: %r in %r" % (f, fmt))

            r.append((f,))
        else:
            curstr += c
    if curstr:
        r.append(curstr)
    return r
            

def do_stringformat(hop, sourcevarsrepr):
    s_str = hop.args_s[0]
    assert s_str.is_constant()
    s = s_str.const
    things = parse_fmt_string(s)
    size = inputconst(Signed, len(things)) # could be unsigned?
    TEMP = GcArray(Ptr(STR))
    cTEMP = inputconst(Void, TEMP)
    vtemp = hop.genop("malloc_varsize", [cTEMP, size],
                      resulttype=Ptr(TEMP))
    r_tuple = hop.args_r[1]
    v_tuple = hop.args_v[1]

    argsiter = iter(sourcevarsrepr)
    
    for i, thing in enumerate(things):
        if isinstance(thing, tuple):
            code = thing[0]
            vitem, r_arg = argsiter.next()
            rep = inputconst(Void, r_arg)
            if not hasattr(r_arg, 'll_str'):
                raise TyperError("ll_str unsupported for: %r" % r_arg)
            if code == 's' or (code == 'r' and isinstance(r_arg, InstanceRepr)):
                vchunk = hop.gendirectcall(r_arg.ll_str, vitem, rep)
            elif code == 'd':
                assert isinstance(r_arg, IntegerRepr)
                vchunk = hop.gendirectcall(r_arg.ll_str, vitem, rep)
            elif code == 'f':
                #assert isinstance(r_arg, FloatRepr)
                vchunk = hop.gendirectcall(r_arg.ll_str, vitem, rep)
            elif code == 'x':
                assert isinstance(r_arg, IntegerRepr)
                vchunk = hop.gendirectcall(rint.ll_int2hex, vitem,
                                           inputconst(Bool, False))
            elif code == 'o':
                assert isinstance(r_arg, IntegerRepr)
                vchunk = hop.gendirectcall(rint.ll_int2oct, vitem,
                                           inputconst(Bool, False))
            else:
                assert 0
        else:
            vchunk = inputconst(string_repr, thing)
        i = inputconst(Signed, i)
        hop.genop('setarrayitem', [vtemp, i, vchunk])

    return hop.gendirectcall(ll_join_strs, vtemp)
    

class __extend__(pairtype(StringRepr, TupleRepr)):
    def rtype_mod(_, hop):
        r_tuple = hop.args_r[1]
        v_tuple = hop.args_v[1]

        sourcevars = []
        for fname, r_arg in zip(r_tuple.fieldnames, r_tuple.items_r):
            cname = hop.inputconst(Void, fname)
            vitem = hop.genop("getfield", [v_tuple, cname],
                              resulttype=r_arg)
            sourcevars.append((vitem, r_arg))

        return do_stringformat(hop, sourcevars)
                

class __extend__(CharRepr):

    def convert_const(self, value):
        if not isinstance(value, str) or len(value) != 1:
            raise TyperError("not a character: %r" % (value,))
        return value

    def get_ll_eq_function(self):
        return None 

    def rtype_len(_, hop):
        return hop.inputconst(Signed, 1)

    def rtype_is_true(_, hop):
        assert not hop.args_s[0].can_be_None
        return hop.inputconst(Bool, True)

    def rtype_ord(_, hop):
        vlist = hop.inputargs(char_repr)
        return hop.genop('cast_char_to_int', vlist, resulttype=Signed)

    def rtype_method_isspace(_, hop):
        vlist = hop.inputargs(char_repr)
        return hop.gendirectcall(ll_char_isspace, vlist[0])

class __extend__(pairtype(CharRepr, IntegerRepr)):
    
    def rtype_mul(_, hop):
        v_char, v_int = hop.inputargs(char_repr, Signed)
        return hop.gendirectcall(ll_char_mul, v_char, v_int)
    rtype_inplace_mul = rtype_mul

class __extend__(pairtype(IntegetRepr, CharRepr)):
    def rtype_mul(_, hop):
        v_int, v_char = hop.inputargs(Signed, char_repr)
        return hop.gendirectcall(ll_char_mul, v_char, v_int)
    rtype_inplace_mul = rtype_mul

class __extend__(pairtype(CharRepr, CharRepr)):
    def rtype_eq(_, hop): return _rtype_compare_template(hop, 'eq')
    def rtype_ne(_, hop): return _rtype_compare_template(hop, 'ne')
    def rtype_lt(_, hop): return _rtype_compare_template(hop, 'lt')
    def rtype_le(_, hop): return _rtype_compare_template(hop, 'le')
    def rtype_gt(_, hop): return _rtype_compare_template(hop, 'gt')
    def rtype_ge(_, hop): return _rtype_compare_template(hop, 'ge')

#Helper functions for comparisons

def _rtype_compare_template(hop, func):
    vlist = hop.inputargs(char_repr, char_repr)
    return hop.genop('char_'+func, vlist, resulttype=Bool)

class __extend__(UniCharRepr):

    def convert_const(self, value):
        if not isinstance(value, unicode) or len(value) != 1:
            raise TyperError("not a unicode character: %r" % (value,))
        return value

    def get_ll_eq_function(self):
        return None 

##    def rtype_len(_, hop):
##        return hop.inputconst(Signed, 1)
##
##    def rtype_is_true(_, hop):
##        assert not hop.args_s[0].can_be_None
##        return hop.inputconst(Bool, True)

    def rtype_ord(_, hop):
        vlist = hop.inputargs(unichar_repr)
        return hop.genop('cast_unichar_to_int', vlist, resulttype=Signed)


class __extend__(pairtype(UniCharRepr, UniCharRepr)):
    def rtype_eq(_, hop): return _rtype_unchr_compare_template(hop, 'eq')
    def rtype_ne(_, hop): return _rtype_unchr_compare_template(hop, 'ne')
##    def rtype_lt(_, hop): return _rtype_unchr_compare_template(hop, 'lt')
##    def rtype_le(_, hop): return _rtype_unchr_compare_template(hop, 'le')
##    def rtype_gt(_, hop): return _rtype_unchr_compare_template(hop, 'gt')
##    def rtype_ge(_, hop): return _rtype_unchr_compare_template(hop, 'ge')

#Helper functions for comparisons

def _rtype_unchr_compare_template(hop, func):
    vlist = hop.inputargs(unichar_repr, unichar_repr)
    return hop.genop('unichar_'+func, vlist, resulttype=Bool)


#
# _________________________ Conversions _________________________

class __extend__(pairtype(CharRepr, StringRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        if r_from == char_repr and r_to == string_repr:
            return llops.gendirectcall(ll_chr2str, v)
        return NotImplemented

class __extend__(pairtype(StringRepr, CharRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        if r_from == string_repr and r_to == char_repr:
            c_zero = inputconst(Signed, 0)
            return llops.gendirectcall(ll_stritem_nonneg, v, c_zero)
        return NotImplemented

class __extend__(pairtype(PyObjRepr, StringRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        v_len = llops.gencapicall('PyString_Size', [v], resulttype=Signed)
        cstr = inputconst(Void, STR)
        v_result = llops.genop('malloc_varsize', [cstr, v_len],
                               resulttype=Ptr(STR))
        cchars = inputconst(Void, "chars")
        v_chars = llops.genop('getsubstruct', [v_result, cchars],
                              resulttype=Ptr(STR.chars))
        llops.gencapicall('PyString_ToLLCharArray', [v, v_chars])
        v_result = llops.convertvar(v_result, string_repr, r_to)
        return v_result

class __extend__(pairtype(StringRepr, PyObjRepr)):
    def convert_from_to((r_from, r_to), v, llops):
        v = llops.convertvar(v, r_from, string_repr)
        cchars = inputconst(Void, "chars")
        v_chars = llops.genop('getsubstruct', [v, cchars],
                              resulttype=Ptr(STR.chars))
        v_size = llops.genop('getarraysize', [v_chars],
                             resulttype=Signed)
        # xxx put in table        
        return llops.gencapicall('PyString_FromLLCharArrayAndSize',
                                 [v_chars, v_size],
                                 resulttype=pyobj_repr,
                                 _callable= lambda chars, sz: pyobjectptr(''.join(chars)))

# ____________________________________________________________
#
#  Low-level methods.  These can be run for testing, but are meant to
#  be direct_call'ed from rtyped flow graphs, which means that they will
#  get flowed and annotated, mostly with SomePtr.
#
def ll_char_isspace(ch):
    # XXX: 
    #return ord(ch) in (9, 10, 11, 12, 13, 32)
    c = ord(ch) 
    return 9 <= c <= 13 or c == 32 

def ll_char_mul(ch, times):
    newstr = malloc(STR, times)
    j = 0
    while j < times:
        newstr.chars[j] = ch
        j += 1
    return newstr

def ll_strlen(s):
    return len(s.chars)

def ll_stritem_nonneg(s, i):
    return s.chars[i]

def ll_stritem(s, i):
    if i < 0:
        i += len(s.chars)
    return s.chars[i]

def ll_str_is_true(s):
    # check if a string is True, allowing for None
    return bool(s) and len(s.chars) != 0

def ll_chr2str(ch):
    s = malloc(STR, 1)
    s.chars[0] = ch
    return s

def ll_strhash(s):
    # unlike CPython, there is no reason to avoid to return -1
    # but our malloc initializes the memory to zero, so we use zero as the
    # special non-computed-yet value.
    x = s.hash
    if x == 0:
        length = len(s.chars)
        if length == 0:
            x = -1
        else:
            x = ord(s.chars[0]) << 7
            i = 0
            while i < length:
                x = (1000003*x) ^ ord(s.chars[i])
                i += 1
            x ^= length
            if x == 0:
                x = -1
        s.hash = intmask(x)
    return x

def ll_strconcat(s1, s2):
    len1 = len(s1.chars)
    len2 = len(s2.chars)
    newstr = malloc(STR, len1 + len2)
    j = 0
    while j < len1:
        newstr.chars[j] = s1.chars[j]
        j += 1
    i = 0
    while i < len2:
        newstr.chars[j] = s2.chars[i]
        i += 1
        j += 1
    return newstr

def ll_strcmp(s1, s2):
    chars1 = s1.chars
    chars2 = s2.chars
    len1 = len(chars1)
    len2 = len(chars2)

    if len1 < len2:
        cmplen = len1
    else:
        cmplen = len2
    i = 0
    while i < cmplen:
        diff = ord(chars1[i]) - ord(chars2[i])
        if diff != 0:
            return diff
        i += 1
    return len1 - len2

def ll_streq(s1, s2):
    len1 = len(s1.chars)
    len2 = len(s2.chars)
    if len1 != len2:
        return False
    j = 0
    chars1 = s1.chars
    chars2 = s2.chars
    while j < len1:
        if chars1[j] != chars2[j]:
            return False
        j += 1

    return True

def ll_startswith(s1, s2):
    len1 = len(s1.chars)
    len2 = len(s2.chars)
    if len1 < len2:
        return False
    j = 0
    chars1 = s1.chars
    chars2 = s2.chars
    while j < len2:
        if chars1[j] != chars2[j]:
            return False
        j += 1

    return True

def ll_endswith(s1, s2):
    len1 = len(s1.chars)
    len2 = len(s2.chars)
    if len1 < len2:
        return False
    j = 0
    chars1 = s1.chars
    chars2 = s2.chars
    offset = len1 - len2
    while j < len2:
        if chars1[offset + j] != chars2[j]:
            return False
        j += 1

    return True

def ll_find(s1, s2):
    """Knuth Morris Prath algorithm for substring match"""
    len1 = len(s1.chars)
    len2 = len(s2.chars)
    # Construct the array of possible restarting positions
    # T = Array_of_ints [-1..len2]
    # T[-1] = -1 s2.chars[-1] is supposed to be unequal to everything else
    T = malloc( SIGNED_ARRAY, len2 )
    i = 0
    j = -1
    while i<len2:
        if j>=0 and s2.chars[i] == s2.chars[j]:
            j += 1
            T[i] = j
            i += 1
        elif j>0:
            j = T[j-1]
        else:
            T[i] = 0
            i += 1
            j = 0

    # Now the find algorithm
    i = 0
    m = 0
    while m+i<len1:
        if s1.chars[m+i]==s2.chars[i]:
            i += 1
            if i==len2:
                return m
        else:
            # mismatch, go back to the last possible starting pos
            if i==0:
                e = -1
            else:
                e = T[i-1]
            m = m + i - e
            if i>0:
                i = e
    return -1
    
emptystr = string_repr.convert_const("")

def ll_upper(s):
    s_chars = s.chars
    s_len = len(s_chars)
    if s_len == 0:
        return emptystr
    i = 0
    result = malloc(STR, s_len)
    while i < s_len:
        ochar = ord(s_chars[i])
        if ochar >= 97 and ochar <= 122:
            upperchar = ochar - 32
        else:
            upperchar = ochar
        result.chars[i] = chr(upperchar)
        i += 1
    return result

def ll_lower(s):
    s_chars = s.chars
    s_len = len(s_chars)
    if s_len == 0:
        return emptystr
    i = 0
    result = malloc(STR, s_len)
    while i < s_len:
        ochar = ord(s_chars[i])
        if ochar >= 65 and ochar <= 96:
            lowerchar = ochar + 32
        else:
            lowerchar = ochar
        result.chars[i] = chr(lowerchar)
        i += 1
    return result

def ll_join(s, items):
    s_chars = s.chars
    s_len = len(s_chars)
    num_items = len(items)
    if num_items == 0:
        return emptystr
    itemslen = 0
    i = 0
    while i < num_items:
        itemslen += len(items[i].chars)
        i += 1
    result = malloc(STR, itemslen + s_len * (num_items - 1))
    res_chars = result.chars
    res_index = 0
    i = 0
    item_chars = items[i].chars
    item_len = len(item_chars)
    j = 0
    while j < item_len:
        res_chars[res_index] = item_chars[j]
        j += 1
        res_index += 1
    i += 1
    while i < num_items:
        j = 0
        while j < s_len:
            res_chars[res_index] = s_chars[j]
            j += 1
            res_index += 1

        item_chars = items[i].chars
        item_len = len(item_chars)
        j = 0
        while j < item_len:
            res_chars[res_index] = item_chars[j]
            j += 1
            res_index += 1
        i += 1
    return result

def ll_join_strs(items):
    num_items = len(items)
    itemslen = 0
    i = 0
    while i < num_items:
        itemslen += len(items[i].chars)
        i += 1
    result = malloc(STR, itemslen)
    res_chars = result.chars
    res_index = 0
    i = 0
    while i < num_items:
        item_chars = items[i].chars
        item_len = len(item_chars)
        j = 0
        while j < item_len:
            res_chars[res_index] = item_chars[j]
            j += 1
            res_index += 1
        i += 1
    return result

def ll_join_chars(chars):
    num_chars = len(chars)
    result = malloc(STR, num_chars)
    res_chars = result.chars
    i = 0
    while i < num_chars:
        res_chars[i] = chars[i]
        i += 1
    return result

def ll_stringslice_startonly(s1, start):
    len1 = len(s1.chars)
    newstr = malloc(STR, len1 - start)
    j = 0
    while start < len1:
        newstr.chars[j] = s1.chars[start]
        start += 1
        j += 1
    return newstr

def ll_stringslice(s1, slice):
    start = slice.start
    stop = slice.stop
    newstr = malloc(STR, stop - start)
    j = 0
    while start < stop:
        newstr.chars[j] = s1.chars[start]
        start += 1
        j += 1
    return newstr

def ll_stringslice_minusone(s1):
    newlen = len(s1.chars) - 1
    assert newlen >= 0
    newstr = malloc(STR, newlen)
    j = 0
    while j < newlen:
        newstr.chars[j] = s1.chars[j]
        j += 1
    return newstr

def ll_split_chr(LISTPTR, s, c):
    chars = s.chars
    strlen = len(chars)
    count = 1
    i = 0
    while i < strlen:
        if chars[i] == c:
            count += 1
        i += 1
    res = malloc(LISTPTR.TO)
    items = res.items = malloc(LISTPTR.TO.items.TO, count)

    i = 0
    j = 0
    resindex = 0
    while j < strlen:
        if chars[j] == c:
            item = items[resindex] = malloc(STR, j - i)
            newchars = item.chars
            k = i
            while k < j:
                newchars[k - i] = chars[k]
                k += 1
            resindex += 1
            i = j + 1
        j += 1
    item = items[resindex] = malloc(STR, j - i)
    newchars = item.chars
    k = i
    while k < j:
        newchars[k - i] = chars[k]
        k += 1
    resindex += 1

    return res

def ll_replace_chr_chr(s, c1, c2):
    length = len(s.chars)
    newstr = malloc(STR, length)
    src = s.chars
    dst = newstr.chars
    j = 0
    while j < length:
        c = src[j]
        if c == c1:
            c = c2
        dst[j] = c
        j += 1
    return newstr

def ll_contains(s, c):
    chars = s.chars
    strlen = len(chars)
    i = 0
    while i < strlen:
        if chars[i] == c:
            return True
        i += 1
    return False

def ll_int(s, base):
    if not 2 <= base <= 36:
	raise ValueError
    chars = s.chars
    strlen = len(chars)
    i = 0
    #XXX: only space is allowed as white space for now
    while i < strlen and chars[i] == ' ':
	i += 1
    if not i < strlen:
	raise ValueError
    #check sign
    sign = 1
    if chars[i] == '-':
	sign = -1
	i += 1
    elif chars[i] == '+':
	i += 1;
    #now get digits
    val = 0
    while i < strlen:
	c = ord(chars[i])
	if ord('a') <= c <= ord('z'):
	    digit = c - ord('a') + 10
	elif ord('A') <= c <= ord('Z'):
	    digit = c - ord('A') + 10
	elif ord('0') <= c <= ord('9'):
	    digit = c - ord('0')
	else:
	    break
	if digit >= base:
	    break
	val = val * base + digit
	i += 1
    #skip trailing whitespace
    while i < strlen and chars[i] == ' ':
	i += 1
    if not i == strlen:
	raise ValueError
    return sign * val

# ____________________________________________________________
#
#  Iteration.

class StringIteratorRepr(Repr):
    lowleveltype = Ptr(GcStruct('stringiter',
                                ('string', string_repr.lowleveltype),
                                ('index', Signed)))
    def newiter(self, hop):
        v_str, = hop.inputargs(string_repr)
        return hop.gendirectcall(ll_striter, v_str)

    def rtype_next(self, hop):
        v_iter, = hop.inputargs(self)
        return hop.gendirectcall(ll_strnext, v_iter)

string_iterator_repr = StringIteratorRepr()

def ll_striter(string):
    iter = malloc(string_iterator_repr.lowleveltype.TO)
    iter.string = string
    iter.index = 0
    return iter

def ll_strnext(iter):
    chars = iter.string.chars
    index = iter.index
    if index >= len(chars):
        raise StopIteration
    iter.index = index + 1
    return chars[index]

# these should be in rclass, but circular imports prevent (also it's
# not that insane that a string constant is built in this file).

instance_str_prefix = string_repr.convert_const("<")
instance_str_suffix = string_repr.convert_const(" object>")

list_str_open_bracket = string_repr.convert_const("[")
list_str_close_bracket = string_repr.convert_const("]")
list_str_sep = string_repr.convert_const(", ")
