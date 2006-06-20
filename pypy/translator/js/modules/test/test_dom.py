""" test of DOM related functions
"""

import py

from pypy.translator.js.test.runtest import compile_function
from pypy.translator.js.modules.dom import Node, get_document, setTimeout, alert
from pypy.translator.js.modules.xmlhttp import XMLHttpRequest
from pypy.translator.js import conftest
#from pypy.rpython.rjs import jseval

import time

if not conftest.option.browser:
    py.test.skip("Works only in browser (right now?)")

def test_document_base():
    def f():
        return get_document().getElementById("dupa")
        #document.getElementById("dupa").setInnerHTML("<h1>Fire!</h1>")
        #return document.getElementById("dupa")
    
    fn = compile_function(f, [], html = 'html/test.html')
    assert fn() == '[object HTMLHeadingElement]'

class Mover(object):
    def __init__(self, elem):
        self.x = 0
        self.y = 0
        self.dir = 1
        self.elem = elem#get_document().getElementById(elem)
    
    def move_it_by(self, obj, dx, dy):
        if self.dir < 0:
            dx = -dx
            dy = -dy
        self.x += dx
        self.y += dy
        if self.x > 100:
            self.dir = -1
        if self.x < 0:
            self.dir = 1
        obj.style.left = str(int(obj.style.left) + dx) + "px"
        obj.style.top = str(int(obj.style.top) + dy) + "px"

    def move_it(self):
        #self.move_it_by(self.elem, 3, 3)
        self.move_it_by(get_document().getElementById(self.elem), 3, 3)
        setTimeout(move_it, 10)

movers = [Mover("anim_img"), Mover("anim_img2")]
movers[1].x = 20

def move_it():
    movers[0].move_it()
    #movers[1].move_it()

def test_anim_f():  
    def anim_fun():
        obj = get_document().createElement('img')
        obj.id = 'anim_img'
        obj.setAttribute('style', 'position:absolute; top:0; left:0;')
        obj.src = '/static/gfx/BubBob.gif'
        get_document().body.appendChild(obj)
        #obj2 = get_document().getElementById("anim_img2")
        #obj2.setAttribute('style', 'position: absolute; top: 50; left: 0;')
        move_it()
        setTimeout(move_it, 10)
        return get_document().getElementById("anim_img").style.left
    
    fn = compile_function(anim_fun, [], html = 'html/anim.html')
    assert fn() == '3px'

xml = XMLHttpRequest()

def t_xml_fun():
    if xml.readyState == 4:
        alert('Wow!')
        
def test_xmlhttp():
    """ Low level XMLHttpRequest test
    """
    def xml_fun():
        xml.open('GET', 'http://localhost:8080/get_some_info?info=dupa', True)
        xml.onreadystatechange = t_xml_fun
        #return xml.readyState
        xml.send(None)
    
    fn = compile_function(xml_fun, [])
    fn()

##def ping_fun():
##    if xml.readyState == 4:
##        null = None
##        if xml.responseText:
##            data = seval(xml.responseText)
##            alert(data['message'])
##        #for i in data:
##        #    alert(i)
##        send_ping_request()
##
##def send_ping_request():
##    xml.open('GET', 'http://localhost:8080/ping', True)
##    xml.onreadystatechange = ping_fun
##    xml.send(None)

def got_ping_request(data):
    return data['a']

def test_bnb():
    """ Higher level XMLHttpRequest
    """
    def bnb_fun():
        from pypy.translator.js.proxy.testme.controllers import RootInstance
        RootInstance.ping(got_ping_request)
    
    from pypy.translator.js.proxy.testme.controllers import Root
    fn = compile_function(bnb_fun, [], root = Root)
    fn()
