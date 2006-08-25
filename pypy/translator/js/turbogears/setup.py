from setuptools import setup, find_packages
from turbogears.finddata import find_package_data
import os

svninfo = os.popen('svn info rpython2javascript').read().split()
version = int(svninfo[svninfo.index('Revision:') + 1])

setup(
    name="rpython2javascript",
    version="0.%d" % version,
    
    description="RPython to JavaScript translator",
    #description_long="""This is a derivative of the PyPy project. Some words about RPython can be found at http://codespeak.net/pypy/dist/pypy/doc/coding-guide.html#restricted-python""",
    author="PyPy developers, Maciek Fijalkowski, Eric van Riet Paap",
    author_email="pypy-dev@codespeak.net",
    url="http://codespeak.net/pypy",
    download_url="http://codespeak.net/~ericvrp/rpython2javascript/",
    license="MIT",
    
    #install_requires = [
    #    "TurboGears >= 1.1a0",
    #],

    #scripts = [
    #    "start-topl.py"
    #],

    zip_safe=False,

    packages=find_packages(),
    package_data=find_package_data(
                    where='rpython2javascript', package='rpython2javascript',
                    only_in_packages=False, exclude=('*.pyc', '*~', '.*', '*.bak')),

    entry_points="""
        [python.templating.engines]
        asjavascript = rpython2javascript.pypy.translator.js.turbogears.templateplugin:TemplatePlugin""",
        
    #keywords = [
    #    # Use keywords if you'll be adding your package to the
    #    # Python Cheeseshop
    #    
    #    # if this has widgets, uncomment the next line
    #    # 'turbogears.widgets',
    #    
    #    # if this has a tg-admin command, uncomment the next line
    #    # 'turbogears.command',
    #    
    #    # if this has identity providers, uncomment the next line
    #    # 'turbogears.identity.provider',
    #
    #    # If this is a template plugin, uncomment the next line
    #    # 'python.templating.engines',
    #    
    #    # If this is a full application, uncomment the next line
    #    # 'turbogears.app',
    #],

    classifiers = [
        'Development Status :: 3 - Alpha',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        #'Framework :: TurboGears',
        # if this is an application that you'll distribute through
        # the Cheeseshop, uncomment the next line
        # 'Framework :: TurboGears :: Applications',
        
        # if this is a package that includes widgets that you'll distribute
        # through the Cheeseshop, uncomment the next line
        # 'Framework :: TurboGears :: Widgets',
    ],
    #test_suite = 'nose.collector',
    )

