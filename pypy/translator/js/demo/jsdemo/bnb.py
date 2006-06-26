
""" xmlhttp controllers, usefull for testing
"""

import turbogears
import cherrypy
from pypy.translator.js.demo.jsdemo.controllers import Root
from pypy.rpython.ootypesystem.bltregistry import BasicExternal, MethodDesc

from pypy.translator.js.proxy.testme.servermessage import log, ServerMessage, PMSG_INLINE_FRAME, PMSG_DEF_ICON
from pypy.translator.js.proxy.testme.msgstruct import *
from cherrypy import session

import re, time, sys, os, urllib, socket, copy

class SortY(object):
    def __init__(self, data):
        self.data = data
    
    def __cmp__(self, other):
        return cmp(self.data['y'], other.data['y'])


class SpriteManager(object):
    def __init__(self):
        self.sprite_sets = {}
        self.positions = {}
        self.num = 0
        self.next_pos = {}
        self.last_seen = set()
        self.seen = set()
    
    def def_icon(self, icon_code):
        self.sprite_sets[icon_code] = []
    
    def get_sprite(self, icon_code, x, y):
        try:
            to_ret = self.positions[(icon_code, x, y)]
            del self.positions[(icon_code, x, y)]
            self.next_pos[(icon_code, x, y)] = to_ret
            self.seen.add((icon_code, to_ret))
            return "still", to_ret
        except KeyError:
            try:
                try:
                    to_ret = self.sprite_sets[icon_code].pop()
                except KeyError:
                    self.def_icon(icon_code)
                    raise IndexError
                self.next_pos[(icon_code, x, y)] = to_ret
                self.seen.add((icon_code, to_ret))
                return "move", to_ret
            except IndexError:
                next = self.num
                self.num += 1
                self.next_pos[(icon_code, x, y)] = next
                self.seen.add((icon_code, next))
                return "new", next
    
    def end_frame(self):
        self.positions = copy.deepcopy(self.next_pos)
        self.next_pos = {}
        to_ret = []
        #import pdb;pdb.set_trace()
        for ic, i in self.last_seen - self.seen:
            self.sprite_sets[ic].append(i)
            to_ret.append(i)
        self.last_seen = self.seen
        self.seen = set()
        return to_ret

# Needed double inheritance for both server job
# and semi-transparent communication proxy
class BnbRoot(Root, BasicExternal):
    _serverMessage = {}

    host = 'localhost'
    try:
        port = re.findall('value=".*"', urllib.urlopen('http://%s:8000' % host).read())[0]
    except IOError:
        log("ERROR: Can't connect to BnB server on %s:8000" % host)
        sys.exit()
    except IndexError:
        log("ERROR: Connected to BnB server but unable to detect a running game")
        sys.exit()
    port = int(port[7:-1])
    
    _methods = {
        'get_message' : MethodDesc( [('callback', (lambda : None))] , {'aa':[{'aa':'bb'}]})
    }
    
    
    def serverMessage(self):
        sessionid = session['_id']
        if sessionid not in self._serverMessage:
            self._serverMessage[sessionid] = ServerMessage('static/images/')
        return self._serverMessage[sessionid]
    
    @turbogears.expose(html="jsdemo.templates.bnb")
    def index(self):
        import time
        sessionid = session['_id']
        self._serverMessage[sessionid] = ServerMessage('static/images')
        self.new_sprites = 0
        self.sm = SpriteManager()
        return dict(now=time.ctime(), onload=self.jsname, code=self.jssource)
    
    def sessionSocket(self, close=False):
        sm = self.serverMessage()
        if sm.socket is None:
            player_id = 0 #XXX hardcoded for now
            sm.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sm.socket.connect((self.host, self.port))
            sm.socket.send(message(CMSG_PROTO_VERSION, 2))  #, version a kuku
            sm.socket.send(message(CMSG_ENABLE_SOUND, 0))   #, has_sound
            sm.socket.send(message(CMSG_ENABLE_MUSIC, 0))   #, has_music
            sm.socket.send(message(CMSG_UDP_PORT, "\\"))    #, port
            sm.socket.send(message(CMSG_PING))              #so server starts sending data
            #sm.socket.send(message(CMSG_ADD_PLAYER, player_id))
            #sm.socket.send(message(CMSG_PLAYER_NAME, player_id, 'PyPy'))
            #XXX todo: session.socket.close() after a timeout
        return sm.socket
    
    @turbogears.expose(format="json")
    def get_message(self):
        #XXX hangs if not first sending CMSG_PING!
        sm   = self.serverMessage()
        data = sm.data
        sock = self.sessionSocket()
        while True:
            try:
                data += sock.recv(4096, socket.MSG_DONTWAIT)
            except:    
                break
        while sm.n_header_lines > 0 and '\n' in data:
            sm.n_header_lines -= 1
            header_line, data = data.split('\n',1)
            #log('RECEIVED HEADER LINE: %s' % header_line)

        #log('RECEIVED DATA CONTAINS %d BYTES' % len(data))
        messages = []
        while data:
            values, data = decodemessage(data)
            if not values:
                break  # incomplete message
            messageOutput = sm.dispatch(*values)
            if messageOutput:
                if type(messageOutput) is type([]):
                    messages += messageOutput
                else:
                    messages.append(messageOutput)
        sm.data = data
        #log('RECEIVED DATA REMAINING CONTAINS %d BYTES' % len(data))

        len_before = len(messages)
        #XXX we could do better by not generating only the last inline_frame message anyway!
        inline_frames = [i for i,msg in enumerate(messages) if msg['type'] == PMSG_INLINE_FRAME]
        for i in reversed(inline_frames[:-1]):
            del messages[i]

        #if messages:
        #    log('MESSAGES:lenbefore=%d, inline_frames=%s, lenafter=%d' % (
        #        len_before, inline_frames, len(messages)))
        to_append = []
        for i, msg in enumerate(messages):
            if msg['type'] == PMSG_INLINE_FRAME:
                for next in msg['sprites']:
                    new_sprite, s_num = self.sm.get_sprite(*next)
                    if new_sprite == 'new':
                        #if self.new_sprites < 100:
                        to_append.append({'type':'ns', 's':s_num, 'icon_code':str(next[0]), 'x':str(next[1]), 'y':str(next[2])})
                        self.new_sprites += 1
                    elif new_sprite == 'move':
                        to_append.append({'type':'sm', 's':str(s_num), 'x':str(next[1]), 'y':str(next[2])})
                del messages[i]

        for i in self.sm.end_frame():
            to_append.append({'type':'ds', 's':str(i)})
        messages += to_append
        #messages.append(to_append[0])
        #print len(messages)
        return dict(messages=messages)

BnbRootInstance = BnbRoot()
