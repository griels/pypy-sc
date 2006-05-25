from rdflib import Graph, URIRef, BNode, Literal
from logilab.constraint import  Repository, Solver
from logilab.constraint.fd import  Expression, FiniteDomain as fd
from logilab.constraint.propagation import AbstractDomain, AbstractConstraint, ConsistencyFailure
from constraint_classes import *
import sys, py
from pypy.tool.ansi_print import ansi_log
import time

log = py.log.Producer("Pyontology")
py.log.setconsumer("Pyontology", ansi_log)


namespaces = {
    'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns',
    'rdfs' : 'http://www.w3.org/2000/01/rdf-schema',
    'xmlns' : 'http://www.w3.org/1999/xhtml',
    'owl' : 'http://www.w3.org/2002/07/owl',
}

uris = {}
for k,v in namespaces.items():
    uris[v] = k

Class = URIRef(u'http://www.w3.org/2002/07/owl#Class')
Thing_uri = URIRef(u'http://www.w3.org/2002/07/owl#Thing')
Nothing_uri = URIRef(u'http://www.w3.org/2002/07/owl#Nothing')
rdf_type = URIRef(u'http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
rdf_rest = URIRef(u'http://www.w3.org/1999/02/22-rdf-syntax-ns#rest')
rdf_first = URIRef(u'http://www.w3.org/1999/02/22-rdf-syntax-ns#first')
rdf_nil = URIRef(u'http://www.w3.org/1999/02/22-rdf-syntax-ns#nil')

def getUriref(ns, obj):
    return URIRef(namespaces[ns]+'#'+obj)

def check_format(f):
    if type(f) == str:
        tmp = file(f, "r")
    else:
        tmp = f.open()
    start = tmp.read(10)
    tmp.close()
    if "<" in start:
        format = "xml"
    else:
        format = "n3"
    return format

class ClassDomain(AbstractDomain):
    
    # Class domain is intended as a (abstract/virtual) domain for implementing
    # Class axioms. Working on class descriptions the class domain should allow
    # creation of classes through axioms.
    # The instances of a class can be represented as a FiniteDomain in values (not always see Disjointwith)
    # Properties of a class is in the dictionary "properties"
    # The bases of a class is in the list "bases"
    
    def __init__(self, name='', values=[], bases = []):
        AbstractDomain.__init__(self)
        self.bases = bases+[self]
        self.values = {}
        self.setValues(values)
        self.name = name
        self.property = None
        # The TBox is a dictionary containing terminology constraints
        # on predicates for this class. Keys are predicates, constraint
        # tupples ie. (p,'Carddinality') and values are list, comparison
        # tupples
        self.TBox = {}
        # The ABox contains the constraints the individuals of the class
        # shall comply to
        self.ABox = {}
    
    def __repr__(self):
        return "<%s %s %r>" % (self.__class__, str(self.name),self.getValues())
    
    def __getitem__(self, index):
        return None
    
    def __iter__(self):
        return iter(self.bases)
    
    def size(self):
        return len(self.bases)
    
    __len__ = size
    
    def copy(self):
        return self
    
    def removeValues(self, values):
        for val in values:
            self.values.pop(self.values.index(val))
    
    def getBases(self):
        return self.bases

    def addValue(self, value):
        self.values[value] = True

    def getValues(self):
        return self.values.keys()
    
    def setValues(self, values):
        self.values = dict.fromkeys(values)

class Thing(ClassDomain):
    pass

class List(ClassDomain):
    
    def __init__(self, name='', values=[], bases = []):
        ClassDomain.__init__(self, name, values, bases)
        self.constraint = ListConstraint(name)

class Property(Thing):
    # Property contains the relationship between a class instance and a value
    # - a pair. To accomodate global assertions like 'range' and 'domain' attributes
    # for range and domain must be filled in by rdfs:range and rdfs:domain
    
    def __init__(self, name='', values=[], bases = []):
        ClassDomain.__init__(self, name, values, bases)
        self._dict = {}
        self.range = []
        self.domain = []
    
    def getValues(self):
        items = self._dict.items()
        res = []
        for k,vals in items:
            for v in vals:
                res.append((k,v))
        return res

    def getValuesPrKey(self, key= None):
        if key:
            return self._dict[key]
        return self._dict.items()
    
    def addValue(self, key, val):
        self._dict.setdefault(key, [])
        self._dict[key].append(val)
    
    def setValues(self, values):
        for key, val in values:
            self.addValue(key, val)
    
    def removeValues(self, values):
        for k,v in values:
            vals = self._dict[k]
            if vals == [None]:
                self._dict.pop(k)
            else:
                self._dict[k] = [ x for x in vals if x != v]

    def __contains__(self, (cls, val)):
        if not cls in self._dict.keys():
            return False
        vals = self._dict[cls]
        if val in vals:
            return True
        return False

class ObjectProperty(Property):
    
    pass

class DatatypeProperty(Property):
    pass

class DataRange(ClassDomain):
    pass

class AllDifferent(ClassDomain):
    # A special class whose members are distinct
    # Syntactic sugar
    pass

class Nothing(ClassDomain):

    def __init__(self, name='', values=[], bases = []):
        ClassDomain.__init__(self, name, values, bases)
        self.constraint = NothingConstraint(name)

class FunctionalProperty(Property):
    
    def __init__(self, name='', values=[], bases = []):
        Property.__init__(self, name, values, bases)
        self.constraint = FunctionalCardinality(name)

    def addValue(self, key, val):
        Property.addValue(self, key, val)
#        if len(self._dict[key]) > 1:
#            raise ConsistencyFailure("FunctionalProperties can only have one value")
        
class InverseFunctionalProperty(Property):
    
    def __init__(self, name='', values=[], bases = []):
        Property.__init__(self, name, values, bases)
        self.constraint = InverseFunctionalCardinality(name)

    def addValue(self, key, val):
        Property.addValue(self, key, val)
        valuelist = [set(x) for x in self._dict.values()]
        res = set()
        for vals in valuelist:
            if vals & res:
                raise ConsistencyFailure("Only unique values in InverseFunctionalProperties")
            res = res | vals

class TransitiveProperty(Property):
    
    def __init__(self, name='', values=[], bases = []):
        Property.__init__(self, name, values, bases)
        #self.constraint = TransitiveConstraint(name)

    def addValue(self, key, val):
        Property.addValue(self, key, val)
        if val in self._dict.keys():
            for v in self._dict[val]:
                Property.addValue(self, key, v)
        for k in self._dict.keys():
            if key in self._dict[k]:
                Property.addValue(self, k, val)
                
class SymmetricProperty(Property):
    
    def __init__(self, name='', values=[], bases = []):
        Property.__init__(self, name, values, bases)
#        self.constraint = SymmetricConstraint(name)

    def addValue(self, key, val):
        Property.addValue(self, key, val)
        Property.addValue(self, val, key)

class Restriction(ClassDomain):
    """ A owl:restriction is an anonymous class that links a class to a restriction on a property
        The restriction is only applied to the property in the conntext of the specific task. In order
        to construct a constraint to check the restriction three things are thus needed :
            1. The property to which the restriction applies - this comes from the onProperty tripple.
                the property is saved in the Restriction class' property attribute
            2. The restriction itself. This comes from one of the property restrictions triples (oneOf,
                maxCardinality ....). It adds a constraint class
            3. The class in which context the restriction should be applied. This comes from subClassOf, type...
                The class is saved in the restrictions cls attribute
        """
    def __init__(self, name='', values=[], bases = []):
        ClassDomain.__init__(self, name, values, bases)
        self.property = None

builtin_voc = {
               getUriref('owl', 'Thing') : Thing,
               getUriref('owl', 'Class') : ClassDomain,
               getUriref('owl', 'ObjectProperty') : ObjectProperty,
               getUriref('owl', 'AllDifferent') : AllDifferent ,
               getUriref('owl', 'AnnotationProperty') : Property, #XXX AnnotationProperty,
               getUriref('owl', 'DataRange') : DataRange,
               getUriref('owl', 'DatatypeProperty') : DatatypeProperty,
##               getUriref('owl', 'DeprecatedClass') : DeprecatedClass,
##               getUriref('owl', 'DeprecatedProperty') : DeprecatedProperty,
               getUriref('owl', 'FunctionalProperty') : FunctionalProperty,
               getUriref('owl', 'InverseFunctionalProperty') : InverseFunctionalProperty,
               getUriref('owl', 'Nothing') : Nothing,
##               getUriref('owl', 'Ontology') : Ontology,
##               getUriref('owl', 'OntologyProperty') : OntologyProperty,
               getUriref('owl', 'Restriction') : Restriction,
               getUriref('owl', 'SymmetricProperty') : SymmetricProperty,
               getUriref('owl', 'TransitiveProperty') : TransitiveProperty,
               getUriref('rdf', 'List') : List
              }

class Ontology:
    
    def __init__(self, store = 'default'):
        self.graph = Graph(store)
        self.store = store
        if store != 'default':
            self.graph.open(py.path.local().join("db").strpath)
        self.variables = {}
        self.constraints = []
        self.seen = {}
        self.var2ns ={}
    
    def add(self, triple):
        self.graph.add(triple)

    def add_file(self, f, format=None):
        tmp = Graph('default')
        if not format:
            format = check_format(f)
        tmp.load(f, format=format)
        for triple in tmp.triples((None,)*3):
            self.add(triple)
            
    def load_file(self, f, format=None):
        if not format:
            format = check_format(f)
        self.graph.load(f, format=format)
    
    def attach_fd(self):
        while len(list(self.graph.triples((None,)*3))) != len(self.seen.keys()):
            for (s, p, o) in (self.graph.triples((None,)*3)):
                self.consider_triple((s, p, o))
        log("=============================")
        assert len(list(self.graph.triples((None,)*3))) == len(self.seen.keys())

    def consider_triple(self,(s, p, o)):
        log("Trying %r" % ((s, p, o),))
        if (s, p, o) in self.seen.keys():
            return
        log("Doing %r" % ((s, p, o),))
        self.seen[(s, p, o)] = True
        if p.find('#') != -1:
            ns, func = p.split('#')
        else:
            ns =''
            func = p
        if ns in namespaces.values() and hasattr(self, func):
            #predicate is one of builtin OWL or rdf predicates
            pred = getattr(self, func)
            res = pred(s, o)
            avar = self.make_var(ClassDomain, s)
        else:
            avar = self.make_var(Property, p)
            # Set the values of the property p to o
            self.type(s, Thing_uri)
            sub = self.make_var(Thing, s)
            obj = self.make_var(Thing, o)
            propdom = self.variables[avar]
            res = propdom.addValue(s, o)

    def resolve_item(self, item):
        item_as_subject = self.graph.triples((item, None, None))
        for triple in item_as_subject:
            self.consider_triple(triple)

    def resolve_predicate(self, item):
        item_as_predicate = self.graph.triples(( None, item, None))
        for triple in item_as_predicate:
            self.consider_triple(triple)

    def get_individuals_of(self, item):
        item_as_object = self.graph.triples(( None, rdf_type, item))
        for triple in item_as_object:
            self.consider_triple(triple)

    def make_var(self, cls=fd, a=''):
        log("make_var %r,%r" %(cls,a))
        if a in builtin_voc:
            cls = builtin_voc[a]
        if type(a) == URIRef:
            if a.find('#') != -1:
                ns,name = a.split('#')
            else:
                ns,name = a,''
            if ns not in uris.keys():
                uris[ns] = ns.split('/')[-1]
            a = uris[ns] + '_' + name
            var = str(a.replace('.','_'))
            var = str(a.replace('-','_'))
        else:
            var = a
        if not cls:
            return var
        if not var in self.variables:
            self.variables[var] = cls(var)
        # XXX needed because of old style classes
        elif issubclass(cls, self.variables[var].__class__):
            vals = self.variables[var].getValues()
            tmp = cls(var)
            tmp.setValues(vals)
            tmp.property = self.variables[var].property
            tmp.TBox = self.variables[var].TBox
            self.variables[var] = tmp
        return var

    def evaluate(self, terms):
        # terms is a dictionary of types of restriction and list of values for this restriction
        term = terms
        if len(term) < 1: return    
        mini = maxi = equal = None
        for tp,val in term:
            if tp == '<':
               if not maxi or val < maxi : maxi = val
            elif tp == '>':
               if not mini or val > mini : mini = val
            else:
                if equal:
                    raise ConsistencyFailure
                equal = val

        if mini and maxi and mini > maxi:
            raise ConsistencyFailure
        if mini and equal and equal < mini:        
            raise ConsistencyFailure
        if maxi and equal and equal > maxi:        
            raise ConsistencyFailure

    def check_TBoxes(self):
        for var, cls in self.variables.items():
            for prop, terms in cls.TBox.items():
                if len(terms.get('Cardinality',[])) > 1: 
                    self.evaluate(terms['Cardinality'])
    
    def solve(self,verbose=0):
        rep = Repository(self.variables.keys(), self.variables, self.constraints)
        return Solver().solve(rep, verbose)
    
    def consistency(self, verbose=0):
        self.check_TBoxes()
        self.rep = Repository(self.variables.keys(), self.variables, self.constraints)
        self.rep.consistency(verbose)
    
    def flatten_rdf_list(self, rdf_list):
        res = []
        if not type(rdf_list) == list:
            avar = self.make_var(List, rdf_list)
            lis = list(self.graph.objects(rdf_list, rdf_first))
            if not lis:
                return res
            res.append(lis[0])
            lis = list(self.graph.objects(rdf_list, rdf_rest))[0]
            while lis != rdf_nil:
                res.append(list(self.graph.objects(lis, rdf_first))[0])
                lis = list(self.graph.objects(lis, rdf_rest))[0]
            self.variables[avar].setValues(res)
        else:
            # For testing
            avar = self.make_var(List, BNode('anon_%r'%rdf_list))
            if type(rdf_list[0]) ==  list:
                res = [tuple(x) for x in rdf_list]
            else:
                res = rdf_list
        self.variables[avar].setValues(res)
        return avar
    
#---------------- Implementation ----------------
    
    def comment(self, s, var):
        pass
    
    def label(self, s, var):
        pass

    def type(self, s, var):
        log("type %r %r"%(s, var))
        avar = self.make_var(ClassDomain, var)
        if not var in builtin_voc :
            # var is not one of the builtin classes -> it is a Thing
            self.type(s, Thing_uri)
            svar = self.make_var(self.variables[avar].__class__, s)
            self.variables[avar].addValue(s)
        else:
            # var is a builtin class
            cls = builtin_voc[var]
            if cls == List:
                return
            else:
                svar = self.make_var(None, s)
#            if not (self.variables.has_key(svar) and
#                   isinstance(self.variables[svar], cls)):
            svar = self.make_var(cls, s)
            cls = self.variables[svar]
            if hasattr(cls, 'constraint'):
                self.constraints.append(cls.constraint)
            if not isinstance(self.variables[avar], Property):
                self.variables[avar].addValue(s)
    
    def first(self, s, var):
        pass
    
    def rest(self, s, var):
        pass
    
    def onProperty(self, s, var):
#        self.resolve_predicate(var)
        log("%r onProperty %r "%(s, var))
        svar =self.make_var(Restriction, s)
        avar =self.make_var(Property, var)
        restr = self.variables[svar]
        restr.property = avar

#---Class Axioms---#000000#FFFFFF-----------------------------------------------
    
    def subClassOf(self, s, var):
        # s is a subclass of var means that the
        # class extension of s is a subset of the
        # class extension of var, ie if a indiviual is in
        # the extension of s it must be in the extension of
        # var
        log("%r subClassOf %r "%(s, var))
        self.resolve_item(var)
#        self.resolve_item(s)
        avar = self.make_var(None, var)
        svar = self.make_var(ClassDomain, s)
        obj = self.variables[avar]
        sub = self.variables[svar]
#        assert (not isinstance(obj, Restriction)) or obj.TBox 
        if obj.TBox:
            for key in obj.TBox.keys():
                sub.TBox.setdefault(key,{})
                prop = sub.TBox[key]
                for typ in obj.TBox[key].keys():
                    prop.setdefault(typ, [])
                    prop[typ].extend(obj.TBox[key][typ])

#            if isinstance(self.variables[avar], Restriction):
#                self.variables[avar].TBox = {}
#                self.variables.pop(avar)
        else:
            cons = SubClassConstraint( svar, avar)
            self.constraints.append(cons)
        for item in obj.getValues():
            sub.addValue(item)

    def equivalentClass(self, s, var):
        self.subClassOf(s, var)
        self.subClassOf(var, s)
    
    def disjointWith(self, s, var):
        self.resolve_item(s)
        self.resolve_item(var)
        avar = self.make_var(None, var)
        svar = self.make_var(None, s)
        constrain = DisjointClassConstraint(svar, avar)
        self.constraints.append(constrain)
    
    def complementOf(self, s, var):
        # add constraint of not var
        # i.e. the extension of s shall contain all individuals not in var
        # We need to know all elements and subtract the elements of var
        self.resolve_item(s)
        self.resolve_item(var)
        avar = self.make_var(ClassDomain, var)
        svar = self.make_var(ClassDomain, s)
        vals = self.variables[avar].getValues()
        x_vals = self.variables[svar].getValues()
        for v in x_vals:
            if v in vals:
                raise ConsistencyFailure("%s cannot have the value %s and be \
                                                    complementOf %s" % (s, v, var)) 
        for v in self.variables[self.make_var(None,Thing_uri)].getValues():
            if not v in vals:
                self.variables[svar].addValue(v)
        self.constraints.append(ComplementOfConstraint(svar, avar))       
    
    def oneOf(self, s, var):
        var = self.flatten_rdf_list(var)
        #avar = self.make_var(List, var)
        svar = self.make_var(ClassDomain, s)
        res = self.variables[var].getValues()
        self.variables[svar].setValues(res)
    
    def unionOf(self,s, var):
        var = self.flatten_rdf_list(var)
        vals = self.variables[var].getValues()
        
        res = []
        for val in vals:
            self.get_individuals_of(val)
            var_name = self.make_var(ClassDomain, val)
            val = self.variables[var_name].getValues()
            res.extend([x for x in val])
        svar = self.make_var(ClassDomain, s)
        vals = self.variables[svar].getValues()
        res.extend(vals)
        self.variables[svar].setValues(res)
    
    def intersectionOf(self, s, var):
        var = self.flatten_rdf_list(var)
        vals = [self.make_var(ClassDomain, x) for x in self.variables[var].getValues()]
        
        res = vals[0]
        for l in vals[1:]:
            result = []
            for v in res:
                if v in self.variables[l].getValues() :
                    result.append(v)
            res = result
        svar = self.make_var(ClassDomain, s)
        self.variables[svar].setValues(res)

#---Property Axioms---#000000#FFFFFF--------------------------------------------
    
    def range(self, s, var):
        avar = self.make_var(ClassDomain, var)
        svar = self.make_var(Property, s)
        cons = RangeConstraint(svar, avar)
        self.constraints.append(cons)
    
    def domain(self, s, var):
        # The classes that has this property (s) must belong to the class extension of var
        avar = self.make_var(ClassDomain, var)
        svar = self.make_var(Property, s)
        cons = DomainConstraint(svar, avar)
        self.constraints.append(cons)
    
    def subPropertyOf(self, s, var):
        # s is a subproperty of var
        self.resolve_predicate(var)
        self.resolve_predicate(s)
        avar = self.make_var(Property, var)
        svar = self.make_var(Property, s)
        avals = self.variables[avar].getValues()
        for pair in self.variables[svar].getValues():
            if not pair in avals:
                self.variables[avar].addValue(pair[0], pair[1])

    def equivalentProperty(self, s, var):
        avar = self.make_var(Property, var)
        svar = self.make_var(Property, s)
        cons = EquivalentPropertyConstraint( svar, avar)
        self.constraints.append(cons)
    
    def inverseOf(self, s, var):
        self.resolve_predicate(s)
        self.resolve_predicate(var)
        avar = self.make_var(Property, var)
        svar = self.make_var(Property, s)
#        con = InverseofConstraint(svar, avar)
#        self.constraints.append(con)
        avals = self.variables[avar].getValues()
        svals = self.variables[svar].getValues()
        for pair in avals:
            if not (pair[1], pair[0]) in svals:
	            self.variables[svar].addValue(pair[1], pair[0])
        for pair in svals:
            if not (pair[1], pair[0]) in avals:
	            self.variables[avar].addValue(pair[1], pair[0])

#---Property restrictions------------------------------------------------------
    
    def maxCardinality(self, s, var):
        """ Len of finite domain of the property shall be less than or equal to var"""
        self.resolve_item(s)
        log("%r maxCardinality %r "%(s, var))
        svar =self.make_var(Restriction, s)
        cls = list(self.graph.subjects(None,s))[0]
        self.resolve_item(cls)
        cls_name = self.make_var(ClassDomain, cls)
        prop = self.variables[svar].property
        assert prop
        self.variables[svar].TBox[prop] = {'Cardinality': [( '<', int(var))]}
        self.constraints.append(CardinalityConstraint(prop, cls, var, '<='))

    def minCardinality(self, s, var):
        """ Len of finite domain of the property shall be greater than or equal to var"""
        self.resolve_item(s)
        log("%r minCardinality %r "%(s, var))
        svar =self.make_var(Restriction, s)
        cls = list(self.graph.subjects(None,s))[0]
        cls_name = self.make_var(ClassDomain, cls)
        prop = self.variables[svar].property
        assert prop
        self.variables[svar].TBox[prop] = {'Cardinality': [( '>', int(var))]}

        self.constraints.append(CardinalityConstraint(prop, cls, var, '>='))
    
    def cardinality(self, s, var):
        """ Len of finite domain of the property shall be equal to var"""
        self.resolve_item(s)
        log("%r Cardinality %r "%(s, var))
        svar =self.make_var(Restriction, s)
        cls = list(self.graph.subjects(None,s))[0]
        cls_name = self.make_var(ClassDomain, cls)
        prop = self.variables[svar].property
        assert prop
        self.variables[svar].TBox[prop] = {'Cardinality': [( '=', int(var))]}
        
        self.constraints.append(CardinalityConstraint(prop, cls, var, '=='))
    
    def hasValue(self, s, var):
        self.resolve_item(s)
        self.resolve_item(var)
        svar = self.make_var(Restriction, s)
        avar = self.make_var(None, var)
        prop = self.variables[svar].property
        restr = self.variables[svar]
        restr.TBox[prop] = {'hasValue' : [('hasvalue', var)]}
        for cls,vals in self.variables[prop].getValuesPrKey():
            if var in vals:
                self.variables[svar].addValue(cls)
    
    def allValuesFrom(self, s, var):
        self.resolve_item(s)
        self.resolve_item(var)
        svar = self.make_var(Restriction, s)
        avar = self.make_var(None, var)
        prop = self.variables[svar].property
        restr = self.variables[svar]
        restr.TBox[prop] = {'allValuesFrom' : [('allValuesFrom', avar)]}
        obj = self.variables[avar]
        constrain_vals = set(obj.getValues())
        for cls,vals in self.variables[prop].getValuesPrKey():
            if (set(vals) & constrain_vals) == constrain_vals:
                self.variables[svar].addValue(cls)
    
    def someValuesFrom(self, s, var):
        self.resolve_item(s)
        self.resolve_item(var)
        svar = self.make_var(Restriction, s)
        avar = self.make_var(None, var)
        prop = self.variables[svar].property
        restr = self.variables[svar]
        obj = self.variables.get(avar, None)
        if obj: 
            constrain_vals = set(obj.getValues())
        else:
            constrain_vals = set()
        restr.TBox[prop] = {'someValuesFrom' : [('someValuesFrom', avar)]}
        for cls,vals in self.variables[prop].getValuesPrKey():
            if set(vals) & constrain_vals:
                self.variables[svar].addValue(cls)

# -----------------              ----------------
    
    def imports(self, s, var):
        # Get the url
        url = var
        # add the triples to the graph
        tmp = Graph()
        tmp.load(url)
        for trip in tmp.triples((None,)*3):
            self.add(trip)

    def sameAs(self, s, var):
        s_var = self.make_var(Thing, s)
        var_var = self.make_var(Thing, var)
        constrain = SameasConstraint(s_var, var_var)
        self.constraints.append(constrain)


    def differentFrom(self, s, var):
        s_var = self.make_var(Thing, s)
        var_var = self.make_var(Thing, var)
        constrain = DifferentfromConstraint(s_var, var_var)
        self.constraints.append(constrain)

    def distinctMembers(self, s, var):
        s_var = self.make_var(AllDifferent, s)
        var_var = self.flatten_rdf_list(var)
        #var_var = self.make_var(List, var)
        diff_list = self.variables[var_var].getValues()
        for v in diff_list:
           indx = diff_list.index(v)
           for other in diff_list[indx+1:]:
               self.differentFrom(v, other)
