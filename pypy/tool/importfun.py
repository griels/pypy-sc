import sys
import opcode
import dis
import imp
import os
import __builtin__
import time

"""
so design goal:

i want to take a pile of source code and analyze each module for the
names it defines and the modules it imports and the names it uses from
them.

then i can find things like:

- things which are just plain not used anywhere
- things which are defined in one module and only used in another
- importing of names from modules where they are just imported from
  somewhere else
- cycles in the import graph
- unecessary imports

finding imports at top level is fairly easy, although the variety of
types of import statement can be baffling.  a mini reference:

import foo

->

LOAD_CONST None
IMPORT_NAME foo
STORE_NAME foo


import foo as bar

->

LOAD_CONST None
IMPORT_NAME foo
STORE_NAME bar

from foo import bar

->

LOAD_CONST  ('bar',)
IMPORT_NAME foo
IMPORT_FROM bar
STORE_NAME  bar
POP_TOP

from foo import bar, baz

->

LOAD_CONST  ('bar','baz')
IMPORT_NAME foo
IMPORT_FROM bar
STORE_NAME  bar
IMPORT_FROM baz
STORE_NAME  baz
POP_TOP

from foo.baz import bar

->

LOAD_CONST  ('bar',)
IMPORT_NAME foo.baz
IMPORT_FROM bar
STORE_NAME  bar
POP_TOP


import foo.bar

->

LOAD_CONST  None
IMPORT_NAME foo.bar
STORE_NAME  foo

(I hate this style)

there are other forms, but i don't support them (should hit an
assertion rather than silently fail).

"""

class System:
    def __init__(self):
        self.modules = {}
        self.pendingmodules = {}

class Scope(object):
    def __init__(self, parent=None):
        self.modvars = {} # varname -> absolute module name
        self.parent = parent
        self.varsources = {}

    def mod_for_name(self, name):
        if name in self.modvars:
            return self.modvars[name]
        elif self.parent is not None:
            return self.parent.mod_for_name(name)
        else:
            return None

    def var_source(self, name):
        if name in self.varsources:
            return self.varsources[name]
        elif self.parent is not None:
            return self.parent.var_source(name)
        else:
            return None, None


class Module(object):
    def __init__(self, name, system):
        self.name = name
        self.system = system
        self._imports = {} # {modname:{name:was-it-used?}}
        self.definitions = ['__file__']
        if name == 'pypy.objspace.std.objspace':
            self.definitions.extend([
                'W_NoneObject', 'W_BoolObject', 'W_BoolObject', 'W_TypeObject',
                'W_TypeObject', 'W_TypeObject', 'W_IntObject',
                'W_StringObject', 'W_UnicodeObject', 'W_FloatObject',
                'W_TupleObject', 'W_ListObject', 'W_LongObject', 'W_SliceObject',
                'W_IntObject', 'W_FloatObject', 'W_LongObject', 'W_TupleObject',
                'W_ListObject', 'W_DictObject', 'W_SliceObject',
                'W_StringObject', 'W_UnicodeObject', 'W_SeqIterObject',
                'W_TupleObject', 'W_DictObject', 'W_DictObject'])
        self.toplevelscope = Scope()
        self.importers = []
    def import_(self, modname):
        if modname not in self._imports:
            if recursive and modname not in self.system.modules:
                self.system.pendingmodules[modname] = None
            self._imports[modname] = {}
        return self._imports[modname]

def iteropcodes(codestring):
    n = len(codestring)
    i = 0
    while i < n:
        op = ord(codestring[i])
        i += 1
        oparg = None
        assert op != opcode.EXTENDED_ARG
        if op >= opcode.HAVE_ARGUMENT:
            oparg = ord(codestring[i]) + ord(codestring[i+1])*256
            i += 2
        yield op, oparg

STORE_DEREF = opcode.opmap["STORE_DEREF"]
STORE_FAST = opcode.opmap["STORE_FAST"]
STORE_GLOBAL = opcode.opmap["STORE_GLOBAL"]
STORE_NAME = opcode.opmap["STORE_NAME"]
IMPORT_NAME = opcode.opmap["IMPORT_NAME"]
IMPORT_FROM = opcode.opmap["IMPORT_FROM"]
LOAD_CONST = opcode.opmap["LOAD_CONST"]
LOAD_ATTR = opcode.opmap["LOAD_ATTR"]

LOAD_DEREF = opcode.opmap["LOAD_DEREF"]
LOAD_FAST = opcode.opmap["LOAD_FAST"]
LOAD_NAME = opcode.opmap["LOAD_NAME"]
LOAD_GLOBAL = opcode.opmap["LOAD_GLOBAL"]

MAKE_CLOSURE = opcode.opmap["MAKE_CLOSURE"]
MAKE_FUNCTION = opcode.opmap["MAKE_FUNCTION"]

POP_TOP = opcode.opmap['POP_TOP']

def process(r, codeob, scope, toplevel=False):
    opcodes = list(iteropcodes(codeob.co_code))

    i = 0

    codeobjs = []

    while i < len(opcodes):
        op, oparg = opcodes[i]

        if op == IMPORT_NAME:
            preop, preoparg = opcodes[i-1]
            assert preop == LOAD_CONST

            fromlist = codeob.co_consts[preoparg]

            modname = codeob.co_names[oparg]

            if fromlist is None:
                # this is the 'import foo' case
                r.import_(modname)

                postop, postoparg = opcodes[i+1]

                # ban 'import foo.bar' (it's dubious style anyway, imho)

                #assert not '.' in modname

                assert postop in [STORE_NAME, STORE_FAST, STORE_DEREF, STORE_GLOBAL]
                if postop == STORE_FAST:
                    storename = codeob.co_varnames[postoparg]
                elif postop == STORE_DEREF:
                    if postoparg < len(codeob.co_cellvars):
                        storename = codeob.co_cellvars[postoparg]
                    else:
                        storename = codeob.co_freevars[postoparg - len(codeob.co_cellvars)]
                else:
                    storename = codeob.co_names[postoparg]

                scope.modvars[storename] = modname.split('.')[0]
                i += 1
            elif fromlist == ('*',):
                assert toplevel
                if modname.startswith('pypy.'):
                    if modname not in r.system.modules:
                        if modname in r.system.pendingmodules:
                            del r.system.pendingmodules[modname]
                        process_module(modname, r.system)
                    M = r.system.modules[modname]
                    for d in M.definitions + list(M.toplevelscope.modvars) + \
                            [a[1] for a in M.toplevelscope.varsources.itervalues()]:
                        if d[0] != '_':
                            #print '* got ', d
                            scope.varsources[d] = modname, d
                            r.import_(modname)[d] = -1
                r.import_(modname)['*'] = True
            else:
                # ok, this is from foo import bar
                path = None
                try:
                    for part in modname.split('.'):
                        path = [imp.find_module(part, path)[1]]
                except ImportError:
                    path = -1
                i += 1
                for f in fromlist:
                    op, oparg = opcodes[i]
                    assert op == IMPORT_FROM
                    assert codeob.co_names[oparg] == f
                    i += 1

                    if path == -1:
                        i += 1
                        continue

                    var = mod = None

                    try:
                        imp.find_module(f, path)
                    except ImportError:
                        var = True
                        r.import_(modname)[f] = False
                    else:
                        mod = True
                        submod = modname + '.' + f
                        r.import_(submod)

                    op, oparg = opcodes[i]

                    assert op in [STORE_NAME, STORE_FAST, STORE_DEREF, STORE_GLOBAL]
                    if op == STORE_FAST:
                        storename = codeob.co_varnames[oparg]
                    elif op == STORE_DEREF:
                        if oparg < len(codeob.co_cellvars):
                            storename = codeob.co_cellvars[oparg]
                        else:
                            storename = codeob.co_freevars[oparg - len(codeob.co_cellvars)]
                    else:
                        storename = codeob.co_names[oparg]


                    if mod:
                        scope.modvars[storename] = submod
                    else:
                        scope.varsources[storename] = modname, f
                    i += 1
                op, oparg = opcodes[i]
                assert op == POP_TOP
        elif op == STORE_NAME and toplevel or op == STORE_GLOBAL:
            r.definitions.append(codeob.co_names[oparg])
        elif op == LOAD_ATTR:
            preop, preoparg = opcodes[i-1]
            if preop in [LOAD_NAME, LOAD_GLOBAL]:
                m = scope.mod_for_name(codeob.co_names[preoparg])
                if m:
                    r.import_(m)[codeob.co_names[oparg]] = True
            elif preop in [LOAD_FAST]:
                m = scope.mod_for_name(codeob.co_varnames[preoparg])
                if m:
                    r.import_(m)[codeob.co_names[oparg]] = True
        elif op in [LOAD_NAME, LOAD_GLOBAL]:
            name = codeob.co_names[oparg]
            m, a = scope.var_source(name)
            if m:
                assert a in r.import_(m)
                r.import_(m)[a] = True
##             else:
##                 if name not in r.definitions \
##                        and scope.mod_for_name(name) is None \
##                        and scope.var_source(name) == (None, None) \
##                        and name not in __builtin__.__dict__ \
##                        and (op == LOAD_GLOBAL or toplevel):
##                     print 'where did', name, 'come from?'
        elif op in [LOAD_FAST]:
            name = codeob.co_varnames[oparg]
            m, a = scope.var_source(name)
            if m:
                assert a in r.import_(m)
                r.import_(m)[a] = True
        elif op in [LOAD_DEREF]:
            if oparg < len(codeob.co_cellvars):
                name = codeob.co_cellvars[oparg]
            else:
                name = codeob.co_freevars[oparg - len(codeob.co_cellvars)]
            m, a = scope.var_source(name)
            if m:
                assert a in r.import_(m)
                r.import_(m)[a] = True
        elif op in [MAKE_FUNCTION, MAKE_CLOSURE]:
            preop, preoparg = opcodes[i-1]
            assert preop == LOAD_CONST
            codeobjs.append(codeob.co_consts[preoparg])

        i += 1
    for c in codeobjs:
        process(r, c, Scope(scope))

def process_module(dottedname, system):
    if dottedname.endswith('.py'):
        path = dottedname
        dottedname = path.lstrip('./').rstrip()[:-3].replace('/', '.')
    else:
        path = find_from_dotted_name(dottedname)

    ispackage = False
    if os.path.isdir(path):
        ispackage = True
        path += '/__init__.py'
    r = Module(dottedname, system)
    r.ispackage = ispackage

    if dottedname in system.modules:
        return system.modules[dottedname]

    try:
        code = compile(open(path, "U").read(), path, 'exec')
        process(r, code, r.toplevelscope, True)
    except (ImportError, AssertionError, SyntaxError), e:
        print "failed!", e
    else:
        if dottedname in system.pendingmodules:
            print
            del system.pendingmodules[dottedname]

        system.modules[dottedname] = r

    return r

def find_from_dotted_name(modname):
    path = None
    for part in modname.split('.'):
        try:
            path = [imp.find_module(part, path)[1]]
        except ImportError:
            print modname
            raise
    return path[0]

def report_unused_symbols(system):
    for name, mod in sorted(system.modules.iteritems()):
        printed = False
        if not 'pypy.' in name or '_cache' in name:
            continue
        u = {}
        for n in mod._imports:
            if n in ('autopath', '__future__'):
                continue
            usedany = False
            for field, used in mod._imports[n].iteritems():
                if n in system.modules:
                    M = system.modules[n]
                    if not M.ispackage and field != '*' and field not in M.definitions \
                           and used != -1:
                        if not printed:
                            print '*', name
                            printed = True
                        sourcemod, nam = M.toplevelscope.var_source(field)
                        print '   ', field, 'used from', n, 'but came from', sourcemod
                if not used:
                    u.setdefault(n, []).append(field)
                else:
                    usedany = True
            if not usedany:
                if n in u:
                    u[n].append('(i.e. entirely)')
                else:
                    u[n] = 'entirely'
        if u:
            if not printed:
                print '*', name
                printed = True
            for k, v in u.iteritems():
                print '   ', k, v

def find_cycles(system):
    from pypy.tool.algo import graphlib
    vertices = dict.fromkeys(system.modules)
    edges = {}
    for m in system.modules:
        edges[m] = []
        for n in system.modules[m]._imports:
            edges[m].append(graphlib.Edge(m, n))
    cycles = []
    for component in graphlib.strong_components(vertices, edges):
        random_vertex = component.iterkeys().next()
        cycles.extend(graphlib.all_cycles(random_vertex, component, edges))

    ncycles = []
    for cycle in cycles:
        packs = {}
        for edge in cycle:
            package = edge.source.rsplit('.', 1)[0]
            packs[package] = True
        if len(packs) > 1:
            ncycles.append(cycle)
    cycles = ncycles

    for cycle in cycles:
        l = len(cycle[0].source)
        print cycle[0].source, '->', cycle[0].target
        for edge in cycle[1:]:
            print ' '*l, '->', edge.target
    print len(cycles), 'inter-package cycles'

def summary(system):
    mcount = float(len(system.modules))
    importcount = 0
    importstars = 0
    importstarusage = 0
    defcount = 0
    importedcount = 0
    for m in system.modules:
        m = system.modules[m]
        defcount += len(m.definitions)
        importedcount += len(m.importers)
        importcount += len(m._imports)
        for n in m._imports:
            if '*' in m._imports[n]:
                importstars += 1
                importstarusage += len([o for (o, v) in m._imports[n].iteritems() if v == True])
    print
    print 'the average module'
    print 'was imported %.2f times'%(importedcount/mcount)
    print 'imported %.2f other modules'%(importcount/mcount)
    print 'defined %.2f names'%(defcount/mcount)
    print
    print 'there were %d import *s'%(importstars)
    print 'the average one produced %.2f names that were actually used'\
          %((1.0*importstarusage)/importstars)

def not_imported(system):
    for m, M in sorted(system.modules.iteritems()):
        if not M.importers and 'test' not in m and '__init__' not in m:
            print m

def import_stars(system):
    for m in sorted(system.modules):
        m = system.modules[m]
        for n in sorted(m._imports):
            if '*' in m._imports[n]:
                print m.name, 'imports * from', n
                used = [o for (o, v) in m._imports[n].iteritems() if v == True and o != '*']
                print len(used), 'out of', len(m._imports[n]) - 1, 'names are used'
                print '    ', ', '.join(sorted(used))

def find_varargs_users(system):
    for m in sorted(system.modules):
        m = system.modules[m]
        if 'pypy.interpreter.pycode' in m._imports:
            if m._imports['pypy.interpreter.pycode'].get('CO_VARARGS') == True:
                print m.name


def html_for_module(module):
    from py.xml import html
    out = open('importfunhtml/%s.html'%module.name, 'w')
    head = [html.title(module.name)]
    body = [html.h1(module.name)]
    body.append(html.p('This module defines these names:'))
    listbody = []
    for d in module.definitions:
        if not d.startswith('_'):
            listbody.append(html.li(
                html.a(d, href=module.name+'-'+d+'.html')))
    body.append(html.ul(listbody))
    body.append(html.p('This module imports the following:'))
    listbody1 = []
    for n in sorted(module._imports):
        if n in module.system.modules:
            listbody2 = [html.a(n, href=n+'.html')]
        else:
            listbody2 = [n]
        listbody3 = []
        for o in sorted(module._imports[n]):
            if module._imports[n][o] == True:
                if n in module.system.modules:
                    listbody3.append(
                        html.li(html.a(o, href=n+'-'+o+'.html')))
                else:
                    listbody3.append(html.li(o))
        if listbody3:
            listbody2.append(html.ul(listbody3))
        listbody1.append(html.li(listbody2))
    body.append(html.ul(listbody1))
    body.append(html.p('This module is imported by the following:'))
    listbody1 = []
    for n in module.importers:
        licontents = [html.a(n, href=n+'.html')]
        contents = []
        for o in sorted(module.system.modules[n]._imports[module.name]):
            contents.append(html.li(html.a(o, href=module.name+'-'+o+'.html')))
        if contents:
            licontents.append(html.ul(contents))
        listbody1.append(html.li(licontents))
    body.append(html.ul(listbody1))

    out.write(html.html(head, body).unicode())

    for d in module.definitions:
        out = open('importfunhtml/%s-%s.html'%(module.name, d), 'w')
        head = [html.title(module.name + '.' + d)]
        body = [html.h1([html.a(module.name, href=module.name+'.html'), '.' + d])]

        contents = []

        for n in module.importers:
            if module.system.modules[n]._imports[module.name].get(d) == True:
                contents.append(html.li(html.a(n, href=n+'.html')))

        if contents:
            body.append(html.p('This name is used in'))
            body.append(html.ul(contents))
        else:
            body.append(html.p('This name is not used outside the module.'))
        
        out.write(html.html(head, body).unicode())

def make_html_report(system):
    if os.path.isdir('importfunhtml'):
        os.system('rm -rf importfunhtml')
    os.mkdir('importfunhtml')
    for m in system.modules.itervalues():
        html_for_module(m)

def main(*paths):
    system = System()

    for path in paths:
        system.pendingmodules[path] = None

    T = time.time()

    while system.pendingmodules:
        path, d = system.pendingmodules.popitem()
        print '\r', len(system.pendingmodules), path, '        ',
        sys.stdout.flush()
        if '._cache' in path or '/_cache' in path:
            continue
        if '/' not in path and not path.startswith('pypy.'):
            continue
        process_module(path, system)

    print
    print 'analysed', len(system.modules), 'modules in %.2f seconds'%(time.time() - T)
    print '------'

    # record importer information
    for name, mod in system.modules.iteritems():
        for n in mod._imports:
            if n in system.modules:
                system.modules[n].importers.append(name)

    make_html_report(system)

    if interactive:
        import pdb
        pdb.set_trace()

recursive = False
interactive = False

if __name__=='__main__':
    if '-r' in sys.argv:
        recursive = True
        sys.argv.remove('-r')
    if '-i' in sys.argv:
        interactive = True
        sys.argv.remove('-i')
    if len(sys.argv) > 1:
        main(*sys.argv[1:])
    else:
        paths = []
        for line in os.popen("find pypy -name '*.py'"):
            paths.append(line[:-1])
        main(*paths)
