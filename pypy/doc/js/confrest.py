from py.__.doc.confrest import *

class PyPyPage(Page): 
    def fill(self):
        super(PyPyPage, self).fill()
        self.menubar[:] = html.div(
            html.a("news", href="../news.html", class_="menu"), " ",
            html.a("getting-started", 
                   href="../getting-started.html", class_="menu"), " ",
            html.a("documentation", href="../index.html", class_="menu"), " ",
            html.a("svn", href="https://codespeak.net/viewvc/pypy/dist/", class_="menu"), " ", 
            html.a("issues", 
                   href="https://codespeak.net/issue/pypy-dev/", 
                   class_="menu"), 
            html.a("contact", href="../contact.html", class_="menu"), " ", 
            html.a("EU/project", 
                   href="http://pypy.org/", class_="menu"), " ",
            " ", id="menubar")

class Project(Project): 
    title = "PyPy" 
    stylesheet = 'style.css'
    encoding = 'latin1' 
    prefix_title = "PyPy"
    logo = html.div(
        html.a(
            html.img(alt="PyPy", id="pyimg", 
                     src="http://codespeak.net/pypy/img/py-web1.png", 
                     height=110, width=149)))
    Page = PyPyPage 


