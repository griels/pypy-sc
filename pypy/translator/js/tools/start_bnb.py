#!/usr/bin/env python
""" bub-n-bros testing utility
"""

import autopath

import py

from pypy.translator.js import conftest

conftest.option.tg = True
conftest.option.browser = "default"

from pypy.translator.js.test.runtest import compile_function
from pypy.translator.js.modules.dom import Node, get_document, setTimeout, alert
from pypy.translator.js.modules.xmlhttp import XMLHttpRequest
from pypy.translator.js.modules.mochikit import log, logWarning, createLoggingPane
from pypy.translator.js.modules.dom import get_document, set_on_keydown, set_on_keyup
from pypy.translator.js.modules.bltns import date

import time
import os

os.chdir("../demo/jsdemo")

#if not conftest.option.browser:
#    py.test.skip("Works only in browser (right now?)")

from pypy.translator.js.demo.jsdemo.bnb import BnbRootInstance

##def msg_dispatcher(data):
##    for i in data['messages']:
##        log(i['type'])
##    BnbRootInstance.get_message(msg_dispatcher)
##
##def test_mochikit():
##    def mochikit():
##        createLoggingPane(True)
##        BnbRootInstance.get_message(msg_dispatcher)
##
##    from pypy.translator.js.proxy.testme.controllers import Root
##    fn = compile_function(mochikit, [], root = Root)
##    fn()

class Stats(object):
    """ Class containing some statistics
    """
    def __init__(self):
        self.starttime = 0
        self.n_received_inline_frames = 0
        self.n_rendered_inline_frames = 0
        self.n_rendered_dynamic_sprites = 0
        self.fps = 0
        self.starttime = 0.0
        self.n_sprites = 0 #why is inline frame broken up?
    
    def register_frame(self):
        self.n_rendered_inline_frames += 1
        if self.n_rendered_inline_frames >= 10:
            next_time = date()
            self.fps = 10000/(next_time - self.starttime)
            self.n_rendered_inline_frames = 0
            self.starttime = next_time

stats = Stats()

class SpriteManager(object):
    def __init__(self):
        self.sprites = {}
        self.filenames = {}

    def add_icon(self, icon_code, filename):
        self.filenames[icon_code] = filename
        #self.sprite_queues[icon_code] = []
        #self.used[icon_code] = []
        # FIXME: Need to write down DictIterator once...
        #self.icon_codes.append(icon_code)

    def add_sprite(self, s, icon_code, x, y):
        #try:
        #    img = self.sprite_queues[icon_code].pop()
        #except IndexError:
        stats.n_sprites += 1
        img = get_document().createElement("img")
        img.setAttribute("src", self.filenames[icon_code])
        img.setAttribute("style", 'position:absolute; left:'+x+'px; top:'+y+'px; visibility:visible')
        get_document().getElementById("playfield").appendChild(img)
        self.sprites[s] = img
        return img

    def move_sprite(self, s, x, y):
        i = self.sprites[s]
        i.style.top = y + 'px'
        i.style.left = x + 'px'
        i.style.visibility = 'visible'

    def hide_sprite(self, s):
        i = self.sprites[s]
        i.style.visibility = "hidden"
        #pass
    
    #def show_sprite(self, s):
    #    i = self.sprites[s]
    #    i.style.visibility = "visible"

sm = SpriteManager()

def process_message(msg):
    if msg['type'] == 'def_playfield':
        bgcolor = '#000000'
        get_document().body.setAttribute('bgcolor', bgcolor)
        div = get_document().createElement("div")
        div.setAttribute("id", "playfield")
        div.setAttribute('width', msg['width'])
        div.setAttribute('height', msg['height'])
        div.setAttribute('style', 'position:absolute; top:0px; left:0px')
        get_document().body.appendChild(div)
    elif msg['type'] == 'def_icon':
##        img = get_document().createElement("img")
##        img.setAttribute("src", msg["filename"])
##        img.setAttribute("style", 'position:absolute; left:0; top:0')
##        img.setAttribute("id", msg["icon_code"])
##        get_document().getElementById("playfield").appendChild(img)
        sm.add_icon(msg['icon_code'], msg['filename'])
    elif msg['type'] == 'ns':
        sm.add_sprite(msg['s'], msg['icon_code'], msg['x'], msg['y'])
    elif msg['type'] == 'sm':
        sm.move_sprite(msg['s'], msg['x'], msg['y'])
    elif msg['type'] == 'ds':
        sm.hide_sprite(msg['s'])
    #elif msg['type'] == 'ss':
    #    sm.show_sprite(msg['s'])


def keydown(key):
    #c = chr(int(key.keyCode)).lower()
    #c = int(key.keyCode)
    c = key.keyCode
    if c == '65': #ord('A'):
        #BnbRootInstance.add_player0(bnb_dispatcher)
        log("adding player")
        BnbRootInstance.add_player(0, bnb_dispatcher)
    elif c == '82': #ord('R'):
        #BnbRootInstance.remove_player0(bnb_dispatcher)
        BnbRootInstance.remove_player(0, bnb_dispatcher)
    elif c == '68': #ord('D'):  #right
        BnbRootInstance.key0(bnb_dispatcher)
        log('start right')
    elif c == '83': #ord('S'):  #left
        BnbRootInstance.key1(bnb_dispatcher)
        log('start left')
    elif c == '69': #ord('E'):  #up
        BnbRootInstance.key2(bnb_dispatcher)
        log('start up')
    elif c == '88': #ord('X'):  #fire
        BnbRootInstance.key3(bnb_dispatcher)
        log('start fire')
    else:
        logWarning('unknown keydown: ' + c)


def keyup(key):
    c = key.keyCode
    if c in ('65', '82'): #Ignore A&R
        pass
    elif c == '68': #ord('D'):  #right
        BnbRootInstance.key4(bnb_dispatcher)
        log('stop right')
    elif c == '83': #ord('S'):  #left
        BnbRootInstance.key5(bnb_dispatcher)
        log('stop left')
    elif c == '69': #ord('E'):  #up
        BnbRootInstance.key6(bnb_dispatcher)
        log('stop up')
    elif c == '88': #ord('X'):  #fire
        BnbRootInstance.key7(bnb_dispatcher)
        log('stop fire')
    else:
        logWarning('unknown keyup: ' + c)


def bnb_dispatcher(msgs):
    BnbRootInstance.get_message(bnb_dispatcher)
    for msg in msgs['messages']:
        process_message(msg)
    stats.register_frame()
    get_document().title = str(stats.n_sprites) + " sprites " + str(stats.fps)
    #sc.revive()
    
def run_bnb():
    def bnb():
        #get_document().
        createLoggingPane(True)
        log("keys: <a>dd player, <r>emove player and <e><s><d><x> to walk around")
        BnbRootInstance.get_message(bnb_dispatcher)
        set_on_keydown(keydown)
        set_on_keyup(keyup)
    
    from pypy.translator.js.demo.jsdemo.bnb import BnbRoot
    fn = compile_function(bnb, [], root = BnbRoot, run_browser = False)
    fn()

if __name__ == '__main__':
    run_bnb()
