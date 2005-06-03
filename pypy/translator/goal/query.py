# functions to query information out of the translator and annotator from the debug prompt of translate_pypy
import types

import pypy.annotation.model as annmodel
import pypy.objspace.flow.model as flowmodel

#def sources(translator):
#    annotator = translator.annotator
#    d = {}
#    for v, s in annotator.bindings.iteritems():
#        if s.__class__ == annmodel.SomeObject and s.knowntype != type:
#            if s.origin:
#                d[s.origin[0]] = 1
#    for func in d:
#        print func.__module__ or '?', func.__name__
#    print len(d)
#    return d.keys()

class Found(Exception):
    pass

def sovars(translator, g):
    annotator = translator.annotator
    def visit(block):
        if isinstance(block, flowmodel.Block):
            for v in block.getvariables():
                s = annotator.binding(v, extquery=True)
                if s and s.__class__ == annmodel.SomeObject and s.knowntype != type:
                    print v,s
    flowmodel.traverse(visit, g)

def polluted(translator):
    """list functions with still real SomeObject variables"""
    annotator = translator.annotator
    def visit(block):
        if isinstance(block, flowmodel.Block):
            for v in block.getvariables():
                s = annotator.binding(v, extquery=True)
                if s and s.__class__ == annmodel.SomeObject and s.knowntype != type:
                    raise Found
    c = 0
    for f,g in translator.flowgraphs.iteritems():
        try:
            flowmodel.traverse(visit, g)
        except Found:
            print prettycallable((None, f))
            c += 1
    print c

class typerep(object):
    
    def __init__(self, x):
        self.typ = getattr(x, '__class__', type(x))
        self.bound = None
        if hasattr(x, 'im_self'):
            self.bound = x.im_self is not None
        elif hasattr(x, '__self__'):
            self.bound = x.__self__ is not None

    def __hash__(self):
        return hash(self.typ)

    def __cmp__(self, other):
        return cmp((self.typ.__name__, self.bound, self.typ), (other.typ.__name__, other.bound, other.typ))

    def __str__(self):
        if self.bound is None:
            s = self.typ.__name__
        elif self.bound:
            s = 'bound-%s' % self.typ.__name__
        else:
            s = 'unbound-%s' % self.typ.__name__

        if self.typ.__module__ == '__builtin__':
            s = "*%s*" % s

        return s

def typereps(bunch):
    t = dict.fromkeys([typerep(x) for x in bunch]).keys()
    t.sort()
    return t

def roots(classes):
    # find independent hierarchy roots in classes,
    # preserve None if it's part of classes
    work = list(classes)
    res = []

    notbound = False
    
    while None in work:
        work.remove(None)
        notbound = True

    if len(work) == 1:
        return notbound, classes[0]

    while work:
        cand = work.pop()
        for cls in work:
            if issubclass(cls, cand):
                continue
            if issubclass(cand, cls):
                cand = cls
                continue
        res.append(cand)
        work = [cls for cls in work if not issubclass(cls, cand)]


    for x in res:
        for y in res:
            if x != y:
                assert not issubclass(x, y), "%s %s %s" % (classes, x,y)
                assert not issubclass(y, x), "%s %s %s" % (classes, x,y)

    return notbound, tuple(res)
            
def callablereps(bunch):
    callables = [func for clsdef, func in bunch]
    classes = [clsdef and clsdef.cls for clsdef, func in bunch]
    return roots(classes), tuple(typereps(callables))

def prettycallable((cls, obj)):
    if cls is None or cls == (True, ()):
        cls = None
    else:
        notbound = False
        if isinstance(cls, tuple) and isinstance(cls[0], bool):
            notbound, cls = cls
        if isinstance(cls, tuple):
            cls = "[%s]" % '|'.join([x.__name__ for x in cls])
        else:
            cls = cls.__name__
        if notbound:
            cls = "_|%s" % cls

    if isinstance(obj, types.FunctionType):
        obj = "(%s)%s" % (getattr(obj, '__module__', None) or '?', getattr(obj, '__name__', None) or 'UNKNOWN')
    elif isinstance(obj, tuple):
        obj = "[%s]" % '|'.join([str(x) for x in obj])
    else:
        obj = str(obj)
        if obj.startswith('<'):
            obj = obj[1:-1]

    if cls is None:
        return str(obj)
    else:
        return "%s::%s" % (cls, obj)


def prettybunch(bunch):
    if len(bunch) == 1:
        parts = ["one", iter(bunch).next()]
    else:
        parts = ["of type(s)"] + typereps(bunch)
    return ' '.join(map(str, parts))

def pbcaccess(translator):
    annotator = translator.annotator
    for inf in annotator.getpbcaccesssets().root_info.itervalues():
        objs = inf.objects
        print len(objs), prettybunch(objs), inf.attrs.keys()

# PBCs
def pbcs(translator):
    bk = translator.annotator.bookkeeper
    xs = bk.pbccache.keys()
    funcs = [x for x in xs if isinstance(x, types.FunctionType)]
    staticmethods = [x for x in xs if isinstance(x, staticmethod)]
    binstancemethods = [x for x in xs if isinstance(x, types.MethodType) and x.im_self]
    ubinstancemethods = [x for x in xs if isinstance(x, types.MethodType) and not x.im_self]
    typs = [x for x in xs if isinstance(x, (type, types.ClassType))]
    rest = [x for x in xs if not isinstance(x, (types.FunctionType, staticmethod, types.MethodType, type, types.ClassType))]
    for objs in (funcs, staticmethods, binstancemethods, ubinstancemethods, typs, rest):
        print len(objs), prettybunch(objs)

# mutable captured "constants")
def mutables(translator):
    bk = translator.annotator.bookkeeper
    xs = bk.seen_mutable.keys()
    print len(xs), prettybunch(xs)

def prettypatt(patts):
    accum = []
    patts.sort()
    for (sh_cnt, sh_ks, sh_st, sh_stst)  in patts:
        arg = []
        arg.append("+%d" % sh_cnt)
        for kw in sh_ks:
            arg.append("%s=" % kw)
        if sh_st:
           arg.append('*')
        if sh_stst:
           arg.append('**')
        accum.append("(%s)" % ', '.join(arg))
    return ' '.join(accum)
        

def pbccall(translator):
    fams = translator.annotator.getpbccallfamilies().root_info.itervalues()
    one_pattern_fams = {}
    rest = []
    for fam in fams:
        shapes = fam.patterns

        if len(shapes) != 1:
            rest.append((len(fam.objects), fam.objects, shapes.keys()))
        else:
            kinds = callablereps(fam.objects)

            flavor = tuple(kinds), shapes.keys()[0]
                
            cntrs = one_pattern_fams.setdefault(flavor, [0,0])
            cntrs[0] += 1
            cntrs[1] += len(fam.objects)

    def pretty_nfam(nfam):
        if nfam == 1:
            return "1 family"
        else:
            return "%d families" % nfam

    def pretty_nels(kinds, nels, nfam):
        if nels == 1 or nels == nfam:
            return "one %s" % prettycallable(kinds)
        else:
            return "in total %d %s" % (nels, prettycallable(kinds))

    def pretty_els(objs):
        accum = []
        for classdef, obj in objs:
            cls = classdef and classdef.cls
            accum.append(prettycallable((cls, obj)))
        els = ' '.join(accum)
        if len(accum) == 1:
            return els
        else:
            return "{%s}" % els

    items = one_pattern_fams.items()

    items.sort(lambda a,b: cmp((a[0][1],a[1][1]), (b[0][1],b[1][1]))) # sort by pattern and then by els

    for (kinds, patt), (nfam, nels) in items:
        print pretty_nfam(nfam), "with", pretty_nels(kinds, nels, nfam), "with one call-pattern:",  prettypatt([patt])

    print "- * -"

    rest.sort(lambda a,b: cmp((a[0],a[2]), (b[0],b[2])))

    for n, objs, patts in rest:
        print "family of", pretty_els(objs), "with call-patterns:", prettypatt(patts)

# debug helper
def tryout(f, *args):
    try:
        f(*args)
    except:
        import traceback
        traceback.print_exc()
