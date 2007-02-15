import py
from py.__.rest.rst import Rest, Paragraph, Strong, ListItem, Title, Link
from py.__.rest.rst import Directive, Em, Quote, Text

from pypy.config.config import ChoiceOption, BoolOption, StrOption, IntOption
from pypy.config.config import FloatOption, OptionDescription, Option, Config
from pypy.config.config import ArbitraryOption, DEFAULT_OPTION_NAME
from pypy.config.config import _getnegation

def get_fullpath(opt, path):
    if path:
        return "%s.%s" % (path, opt._name)
    else:
        return opt._name


def get_cmdline(cmdline, fullpath):
    if cmdline is DEFAULT_OPTION_NAME:
        return '--%s' % (fullpath.replace('.', '-'),)
    else:
        return cmdline


class __extend__(Option):
    def make_rest_doc(self, path=""):
        fullpath = get_fullpath(self, path)
        result = Rest(
            Title(fullpath, abovechar="=", belowchar="="),
            Directive("contents"),
            Paragraph(Link("back to parent", path + ".html")),
            Title("Basic Option Information"),
            ListItem(Strong("name:"), self._name),
            ListItem(Strong("description:"), self.doc))
        if self.cmdline is not None:
            cmdline = get_cmdline(self.cmdline, fullpath)
            result.add(ListItem(Strong("command-line:"), cmdline))
        return result

class __extend__(ChoiceOption):
    def make_rest_doc(self, path=""):
        content = super(ChoiceOption, self).make_rest_doc(path)
        content.add(ListItem(Strong("option type:"), "choice option"))
        content.add(ListItem(Strong("possible values:"),
                             *[ListItem(str(val)) for val in self.values]))
        if self.default is not None:
            content.add(ListItem(Strong("default:"), str(self.default)))

        requirements = []
        
        for val in self.values:
            if val not in self._requires:
                continue
            req = self._requires[val]
            requirements.append(ListItem("value '%s' requires:" % (val, ),
                *[ListItem(Link(opt, opt + ".html"),
                           "to be set to '%s'" % (rval, ))
                      for (opt, rval) in req]))
        if requirements:
            content.add(ListItem(Strong("requirements:"), *requirements))
        return content

class __extend__(BoolOption):
    def make_rest_doc(self, path=""):
        content = super(BoolOption, self).make_rest_doc(path)
        fullpath = get_fullpath(self, path)
        if self.negation and self.cmdline is not None:
            if self.cmdline is DEFAULT_OPTION_NAME:
                cmdline = '--%s' % (fullpath.replace('.', '-'),)
            else:
                cmdline = self.cmdline
            neg_cmdline = ["--" + _getnegation(argname.lstrip("-"))
                               for argname in cmdline.split()
                                   if argname.startswith("--")][0]
            content.add(ListItem(Strong("command-line for negation:"),
                                 neg_cmdline))
        content.add(ListItem(Strong("option type:"), "boolean option"))
        if self.default is not None:
            content.add(ListItem(Strong("default:"), str(self.default)))
        if self._requires is not None:
            requirements = [ListItem(Link(opt, opt + ".html"),
                               "must be set to '%s'" % (rval, ))
                                for (opt, rval) in self._requires]
            if requirements:
                content.add(ListItem(Strong("requirements:"), *requirements))
        if self._suggests is not None:
            suggestions = [ListItem(Link(opt, opt + ".html"),
                              "should be set to '%s'" % (rval, ))
                               for (opt, rval) in self._suggests]
            if suggestions:
                content.add(ListItem(Strong("suggestions:"), *suggestions))
        return content

class __extend__(IntOption):
    def make_rest_doc(self, path=""):
        content = super(IntOption, self).make_rest_doc(path)
        content.add(ListItem(Strong("option type:"), "integer option"))
        if self.default is not None:
            content.add(ListItem(Strong("default:"), str(self.default)))
        return content

class __extend__(FloatOption):
    def make_rest_doc(self, path=""):
        content = super(FloatOption, self).make_rest_doc(path)
        content.add(ListItem(Strong("option type:"), "float option"))
        if self.default is not None:
            content.add(ListItem(Strong("default:"), str(self.default)))
        return content

class __extend__(StrOption):
    def make_rest_doc(self, path=""):
        content = super(StrOption, self).make_rest_doc(path)
        content.add(ListItem(Strong("option type:"), "string option"))
        if self.default is not None:
            content.add(ListItem(Strong("default:"), str(self.default)))
        return content

class __extend__(ArbitraryOption):
    def make_rest_doc(self, path=""):
        content = super(ArbitraryOption, self).make_rest_doc(path)
        content.add(ListItem(Strong("option type:"),
                             "arbitrary option (mostly internal)"))
        if self.default is not None:
            content.add(ListItem(Strong("default:"), str(self.default)))
        elif self.defaultfactory is not None:
            content.add(ListItem(Strong("factory for the default value:"),
                                 str(self.defaultfactory)))
        return content

class __extend__(OptionDescription):
    def make_rest_doc(self, path=""):
        fullpath = get_fullpath(self, path)
        content = Rest(
            Title(fullpath, abovechar="=", belowchar="="),
            Directive("contents"))
        if path:
            content.add(
                Paragraph(Link("back to parent", path + ".html")))
        content.join(
            Title("Basic Option Information"),
            ListItem(Strong("name:"), self._name),
            ListItem(Strong("description:"), self.doc),
            Title("Sub-Options"))
        stack = []
        prefix = fullpath
        curr = content
        config = Config(self)
        for ending in self.getpaths(include_groups=True):
            subpath = fullpath + "." + ending
            while not (subpath.startswith(prefix) and
                       subpath[len(prefix)] == "."):
                curr, prefix = stack.pop()
            print subpath, fullpath, ending, curr
            sub, step = config._cfgimpl_get_home_by_path(ending)
            doc = getattr(sub._cfgimpl_descr, step).doc
            if doc:
                new = curr.add(ListItem(Link(subpath + ":", subpath + ".html"),
                                        Em(doc)))
            else:
                new = curr.add(ListItem(Link(subpath + ":", subpath + ".html")))
            stack.append((curr, prefix))
            prefix = subpath
            curr = new
        return content


def make_cmdline_overview(descr):
    content = Rest(
        Title("Overwiew of Command Line Options for '%s'" % (descr._name, ),
              abovechar="=", belowchar="="))
    cmdlines = []
    config = Config(descr)
    for path in config.getpaths(include_groups=False):
        subconf, step = config._cfgimpl_get_home_by_path(path)
        fullpath = (descr._name + "." + path)
        prefix = fullpath.rsplit(".", 1)[0]
        subdescr = getattr(subconf._cfgimpl_descr, step)
        cmdline = get_cmdline(subdescr.cmdline, fullpath)
        if cmdline is not None:
            cmdlines.append((cmdline, fullpath, subdescr))
    cmdlines.sort(key=lambda t: t[0].strip("-"))
    for cmdline, fullpath, subdescr in cmdlines:
        content.add(ListItem(Link(cmdline + ":", fullpath + ".html"),
                             Text(subdescr.doc)))
    return content
    

