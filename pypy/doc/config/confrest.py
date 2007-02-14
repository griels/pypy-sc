from pypy.doc.confrest import *
import pypy.config.makerestdoc
from pypy.config.config import Config
from pypy.config import pypyoption, translationoption


all_optiondescrs = [pypyoption.pypy_optiondescription,
                    translationoption.translation_optiondescription,
                   ]

start_to_descr = dict([(descr._name, descr) for descr in all_optiondescrs])

class PyPyPage(PyPyPage): 
    def fill(self):
        super(PyPyPage, self).fill()
        self.menubar[:] = html.div(
            html.a("general documentation", href="../index.html",
                   class_="menu"), " ",
            html.a("translation options", href="translation.html", 
                   class_="menu"), 
            html.a("standard interpreter options", href="objspace.html", 
                   class_="menu"), 
            " ", id="menubar")

class Project(Project): 
    stylesheet = "../style.css"
    title = "PyPy Configuration"
    prefix_title = "PyPy Configuration"
    Page = PyPyPage 

    def get_content(self, txtpath, encoding):
        fullpath = txtpath.purebasename
        start = fullpath.split(".")[0]
        path = fullpath.rsplit(".", 1)[0]
        basedescr = start_to_descr[start]
        if fullpath.count(".") == 0:
            descr = basedescr
            path = ""
        else:
            conf = Config(basedescr)
            subconf, step = conf._cfgimpl_get_home_by_path(
                    fullpath.split(".", 1)[1])
            descr = getattr(subconf._cfgimpl_descr, step)
        text = unicode(descr.make_rest_doc(path).text())
        text += "\nDescription\n==========="
        if txtpath.check(file=True):
            return u"%s\n\n%s" % (text, unicode(txtpath.read(), encoding))
        return text

