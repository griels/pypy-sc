from __future__ import generators
import autopath
import os, time, sys
import pygame
from pygame.locals import *
from drawgraph import GraphRenderer


METAKEYS = dict([
    (ident[len('KMOD_'):].lower(), getattr(pygame.locals, ident))
    for ident in dir(pygame.locals) if ident.startswith('KMOD_') and ident != 'KMOD_NONE'
])

if sys.platform == 'darwin':
    PMETA = 'lmeta'
else:
    PMETA = 'lalt'

METAKEYS['meta'] = METAKEYS[PMETA]
METAKEYS['shift'] = METAKEYS['lshift']

KEYS = dict([
    (ident[len('K_'):].lower(), getattr(pygame.locals, ident))
    for ident in dir(pygame.locals) if ident.startswith('K_')
])

class Display(object):
    
    def __init__(self, (w,h)=(800,680)):
        pygame.init()
        self.resize((w,h))

    def resize(self, (w,h)):
        self.width = w
        self.height = h
        self.screen = pygame.display.set_mode((w, h), HWSURFACE|RESIZABLE, 32)


class GraphDisplay(Display):
    STATUSBARFONT = os.path.join(autopath.this_dir, 'VeraMoBd.ttf')
    ANIM_STEP = 0.07

    KEYS = {
        'meta -' : ('zoom', 0.5),
        'meta =' : ('zoom', 2.0),
        'meta 0' : 'zoom_actual_size',
        'meta 1' : 'zoom_to_fit',
        'meta q' : 'quit',
        'escape' : 'quit',
        'meta f4' : 'quit',
        'meta right' : 'layout_forward',
        'meta left': 'layout_back',
        'p' : 'layout_back',
        'backspace' : 'layout_back',
        'left' : ('pan', (-1, 0)),
        'right' : ('pan', (1, 0)),
        'up' : ('pan', (0, -1)),
        'down' : ('pan', (0, 1)),
        'shift left' : ('fast_pan', (-1, 0)),
        'shift right' : ('fast_pan', (1, 0)),
        'shift up' : ('fast_pan', (0, -1)),
        'shift down' : ('fast_pan', (0, 1)),
    }
        
        
    def __init__(self, layout):
        super(GraphDisplay, self).__init__()
        self.font = pygame.font.Font(self.STATUSBARFONT, 16)
        self.viewers_history = []
        self.forward_viewers_history = []
        self.viewer = None
        self.method_cache = {}
        self.key_cache = {}
        self.status_bar_height = 0
        self.initialize_keys()
        self.setlayout(layout)

    def initialize_keys(self):
        for strnames, methodname in self.KEYS.iteritems():
            names = strnames.split()
            mod = 0
            key = 0
            if not isinstance(methodname, basestring):
                methodname, args = methodname[0], methodname[1:]
            else:
                args = ()
            for name in names:
                if name in METAKEYS:
                    mod |= METAKEYS[name]
                elif name in KEYS:
                    key = KEYS[name]
                else:
                    assert len(name) == 1
                    key = ord(name)
            method = getattr(self, methodname, None)
            if method is None:
                print 'Can not implement key mapping %r, %s.%s does not exist' % (
                        strnames, self.__class__.__name__, methodname)
            self.key_cache[(key, mod)] = (method, args)
    
    def setlayout(self, layout):
        if self.viewer:
            self.viewers_history.append(self.viewer)
            del self.forward_viewers_history[:]
        self.layout = layout
        self.viewer = GraphRenderer(self.screen, layout)
        self.zoom_to_fit()

    def zoom_actual_size(self):
        self.viewer.shiftscale(self.viewer.SCALEMAX / self.viewer.scale)
        self.updated_viewer()

    def calculate_zoom_to_fit(self):
        return min(float(self.width) / self.viewer.width,
                float(self.height - self.status_bar_height) / self.viewer.height,
                1.0)
    
    def zoom_to_fit(self):
        """
        center and scale to view the whole graph
        """

        # XXX - HACK HACK HACK
        self.update_status_bar()
        self.drawstatusbar()

        f = self.calculate_zoom_to_fit()
        self.viewer.shiftscale(f)
        self.viewer.setoffset((self.viewer.width - self.width) // 2,
                              (self.viewer.height - (self.height - self.status_bar_height)) // 2)
        self.updated_viewer()

    def zoom(self, scale):
        self.viewer.shiftscale(max(scale, self.calculate_zoom_to_fit()))
        self.updated_viewer()

    def pan(self, (x, y)):
        self.viewer.shiftoffset(x * (self.width // 8), y * (self.height // 8))
        self.updated_viewer()

    def fast_pan(self, (x, y)):
        self.pan((x * 4, y * 4))
    
    def update_status_bar(self):
        self.statusbarinfo = None
        self.must_redraw = True
        if self.viewers_history:
            info = 'Press Left Arrow to go back to previous screen'
        else:
            info = ('Click to move around, or drag mouse buttons '
                    '(left to zoom, right to scroll)')
        self.setstatusbar(info)
    
    def updated_viewer(self):
        self.sethighlight()
        self.statusbarinfo = None
        self.must_redraw = True
        self.update_status_bar()

    def layout_back(self):
        if self.viewers_history:
            self.forward_viewers_history.append(self.viewer)
            self.viewer = self.viewers_history.pop()
            self.layout = self.viewer.graphlayout
            self.updated_viewer()

    def layout_forward(self):
        if self.forward_viewers_history:
            self.viewers_history.append(self.viewer)
            self.viewer = self.forward_viewers_history.pop()
            self.layout = self.viewer.graphlayout
            self.updated_viewer()

    def setstatusbar(self, text, fgcolor=(255,255,80), bgcolor=(128,0,0)):
        info = (text, fgcolor, bgcolor)
        if info != self.statusbarinfo:
            self.statusbarinfo = info
            self.must_redraw = True

    def drawstatusbar(self):
        text, fgcolor, bgcolor = self.statusbarinfo
        words = text.split(' ')
        lines = []
        totalh = 0
        while words:
            line = words.pop(0)
            img = self.font.render(line, 1, fgcolor)
            while words:
                longerline = line + ' ' + words[0]
                longerimg = self.font.render(longerline, 1, fgcolor)
                w, h = longerimg.get_size()
                if w > self.width:
                    break
                words.pop(0)
                line = longerline
                img = longerimg
            lines.append(img)
            w, h = img.get_size()
            totalh += h
        
        y = self.height - totalh
        self.status_bar_height = totalh + 16
        block = pygame.Surface((self.width, self.status_bar_height), SWSURFACE | SRCALPHA)
        block.fill(bgcolor)
        sy = 16
        for img in lines:
            w, h = img.get_size()
            block.blit(img, ((self.width-w)//2, sy-8))
            sy += h
        block.set_alpha(int(255 * 0.75))
        self.screen.blit(block, (0, y-16))

    def notifymousepos(self, pos):
        word = self.viewer.at_position(pos)
        if word in self.layout.links:
            info = self.layout.links[word]
            self.setstatusbar(info)
            self.sethighlight(word)

    def notifyclick(self, pos):
        word = self.viewer.at_position(pos)
        if word in self.layout.links:
            newlayout = self.layout.followlink(word)
            if newlayout is not None:
                self.setlayout(newlayout)
                return
        node = self.viewer.node_at_position(pos)
        if node:
            self.look_at_node(node)
        else:
            edge = self.viewer.edge_at_position(pos)
            if edge:
                if (self.distance_to_node(edge.head) >=
                    self.distance_to_node(edge.tail)):
                    self.look_at_node(edge.head)
                else:
                    self.look_at_node(edge.tail)

    def sethighlight(self, word=None):
        self.viewer.highlightwords = {}
        for name in self.layout.links:
            self.viewer.highlightwords[name] = ((128,0,0), None)
        if word:
            self.viewer.highlightwords[word] = ((255,255,80), (128,0,0))

    def animation(self, expectedtime=0.6):
        start = time.time()
        step = 0.0
        n = 0
        while True:
            step += self.ANIM_STEP
            if step >= expectedtime:
                break
            yield step / expectedtime
            n += 1
            now = time.time()
            frametime = (now-start) / n
            self.ANIM_STEP = self.ANIM_STEP * 0.9 + frametime * 0.1
        yield 1.0

    def distance_to_node(self, node):
        cx1, cy1 = self.viewer.getcenter()
        cx2, cy2 = node.x, node.y
        return (cx2-cx1)*(cx2-cx1) + (cy2-cy1)*(cy2-cy1)

    def look_at_node(self, node):
        """Shift the node in view."""
        endscale = min(float(self.width-40) / node.w,
                       float(self.height-40) / node.h,
                       75)
        startscale = self.viewer.scale
        cx1, cy1 = self.viewer.getcenter()
        cx2, cy2 = node.x, node.y
        moving = (abs(startscale-endscale) + abs(cx1-cx2) + abs(cy1-cy2)
                  > 0.4)
        if moving:
            # if the target is far off the window, reduce scale along the way
            tx, ty = self.viewer.map(cx2, cy2)
            offview = max(-tx, -ty, tx-self.width, ty-self.height)
            middlescale = endscale * (0.999 ** offview)
            if offview > 150 and middlescale < startscale:
                bumpscale = 4.0 * (middlescale - 0.5*(startscale+endscale))
            else:
                bumpscale = 0.0
            self.statusbarinfo = None
            self.sethighlight(None)
            for t in self.animation():
                self.viewer.setscale(startscale*(1-t) + endscale*t +
                                     bumpscale*t*(1-t))
                self.viewer.setcenter(cx1*(1-t) + cx2*t, cy1*(1-t) + cy2*t)
                self.viewer.render()
                pygame.display.flip()
        return moving

    def peek(self, typ):
        for event in self.events:
            if event.type == typ:
                return True
        return False

    def process_event(self, event):
        method = self.method_cache.get(event.type, KeyError)
        if method is KeyError:
            method = getattr(self, 'process_%s' % (pygame.event.event_name(event.type),), None)
            self.method_cache[method] = method
        if method is not None:
            method(event)
        
    def process_MouseMotion(self, event):
        if self.peek(MOUSEMOTION):
            return
        if self.dragging:
            if (abs(event.pos[0] - self.click_origin[0]) +
                abs(event.pos[1] - self.click_origin[1])) > 12:
                self.click_time = None
            dx = event.pos[0] - self.dragging[0]
            dy = event.pos[1] - self.dragging[1]
            if event.buttons[0]:   # left mouse button
                self.viewer.shiftscale(1.003 ** (dx+dy))
            else:
                self.viewer.shiftoffset(-2*dx, -2*dy)
            self.dragging = event.pos
            self.must_redraw = True
        else:
            self.notifymousepos(event.pos)

    def process_MouseButtonDown(self, event):
        self.dragging = self.click_origin = event.pos
        self.click_time = time.time()
        pygame.event.set_grab(True)

    def process_MouseButtonUp(self, event):
        self.dragging = None
        pygame.event.set_grab(False)
        if self.click_time is not None and abs(time.time() - self.click_time) < 1:
            # click (no significant dragging)
            self.notifyclick(self.click_origin)
        self.click_time = None
        self.notifymousepos(event.pos)

    def process_KeyDown(self, event):
        method, args = self.key_cache.get((event.key, event.mod), (None, None))
        if method is not None:
            method(*args)

    def process_VideoResize(self, event):
        # short-circuit if there are more resize events pending
        if self.peek(VIDEORESIZE):
            return
        self.resize(event.size)
        self.must_redraw = True

    def process_Quit(self, event):
        self.quit()
     
    def quit(self):
        raise StopIteration
    
    def run(self):
        self.dragging = self.click_origin = self.click_time = None
        events = self.events = []
        try:

            while True:

                if self.must_redraw and not events:
                    self.viewer.render()
                    if self.statusbarinfo:
                        self.drawstatusbar()
                    else:
                        self.status_bar_height = 0
                    pygame.display.flip()
                    self.must_redraw = False

                if not events:
                    events.append(pygame.event.wait())
                    events.extend(pygame.event.get())

                self.process_event(events.pop(0))

        except StopIteration:
            pass

        # cannot safely close and re-open the display, depending on
        # Pygame version and platform.
        pygame.display.set_mode((self.width,1))
