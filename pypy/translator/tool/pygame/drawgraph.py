"""
A custom graphic renderer for the '.plain' files produced by dot.

"""

from __future__ import generators
import autopath
import re, os, math
import pygame
from pygame.locals import *


FONT = os.path.join(autopath.this_dir, 'cyrvetic.ttf')
COLOR = {
    'black': (0,0,0),
    'white': (255,255,255),
    'red': (255,0,0),
    'green': (0,255,0),
    }
re_nonword=re.compile(r'(\W+)')


class GraphLayout:

    def __init__(self, filename):
        # parse the layout file (.plain format)
        lines = open(filename, 'r').readlines()
        for i in range(len(lines)-2, -1, -1):
            if lines[i].endswith('\\\n'):   # line ending in '\'
                lines[i] = lines[i][:-2] + lines[i+1]
                del lines[i+1]
        header = splitline(lines.pop(0))
        assert header[0] == 'graph'
        self.scale = float(header[1])
        self.boundingbox = float(header[2]), float(header[3])
        self.nodes = {}
        self.edges = []
        for line in lines:
            line = splitline(line)
            if line[0] == 'node':
                n = Node(*line[1:])
                self.nodes[n.name] = n
            if line[0] == 'edge':
                self.edges.append(Edge(self.nodes, *line[1:]))
            if line[0] == 'stop':
                break

class Node:
    def __init__(self, name, x, y, w, h, label, style, shape, color, fillcolor):
        self.name = name
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        self.label = label
        self.style = style
        self.shape = shape
        self.color = color
        self.fillcolor = fillcolor

class Edge:
    label = None
    
    def __init__(self, nodes, tail, head, cnt, *rest):
        self.tail = nodes[tail]
        self.head = nodes[head]
        cnt = int(cnt)
        self.points = [(float(rest[i]), float(rest[i+1]))
                       for i in range(0, cnt*2, 2)]
        rest = rest[cnt*2:]
        if len(rest) > 2:
            self.label, xl, yl = rest[:3]
            self.xl = float(xl)
            self.yl = float(yl)
            rest = rest[3:]
        self.style, self.color = rest

    def bezierpoints(self, resolution=8):
        result = []
        pts = self.points
        for i in range(0, len(pts)-3, 3):
            result += beziercurve(pts[i], pts[i+1],
                                  pts[i+2], pts[i+3], resolution)
        return result

    def arrowhead(self):
        bottom_up = self.points[0][1] > self.points[-1][1]
        if (self.tail.y > self.head.y) != bottom_up:   # reversed edge
            x0, y0 = self.points[0]
            x1, y1 = self.points[1]
        else:
            x0, y0 = self.points[-1]
            x1, y1 = self.points[-2]
        vx = x0-x1
        vy = y0-y1
        f = 0.12 / math.sqrt(vx*vx + vy*vy)
        vx *= f
        vy *= f
        return [(x0 + 0.9*vx, y0 + 0.9*vy),
                (x0 + 0.4*vy, y0 - 0.4*vx),
                (x0 - 0.4*vy, y0 + 0.4*vx)]

def beziercurve((x0,y0), (x1,y1), (x2,y2), (x3,y3), resolution=8):
    result = []
    f = 1.0/(resolution-1)
    for i in range(resolution):
        t = f*i
        t0 = (1-t)*(1-t)*(1-t)
        t1 =   t  *(1-t)*(1-t) * 3.0
        t2 =   t  *  t  *(1-t) * 3.0
        t3 =   t  *  t  *  t
        result.append((x0*t0 + x1*t1 + x2*t2 + x3*t3,
                       y0*t0 + y1*t1 + y2*t2 + y3*t3))
    return result

def splitline(line, re_word = re.compile(r'[^\s"]\S*|["]["]|["].*?[^\\]["]')):
    result = []
    for word in re_word.findall(line):
        if word.startswith('"'):
            word = eval(word)
        result.append(word)
    return result


class GraphRenderer:
    MARGIN = 0.2
    SCALEMIN = 30
    SCALEMAX = 100
    FONTCACHE = {}
    
    def __init__(self, screen, graphlayout, scale=75):
        self.graphlayout = graphlayout
        self.setscale(scale)
        self.setoffset(0, 0)
        self.screen = screen
        self.textzones = []
        self.highlightwords = {}

    def setscale(self, scale):
        scale = max(min(scale, self.SCALEMAX), self.SCALEMIN)
        self.scale = float(scale)
        w, h = self.graphlayout.boundingbox
        self.margin = int(self.MARGIN*scale)
        self.width = int((w + 2*self.MARGIN)*scale)
        self.height = int((h + 2*self.MARGIN)*scale)
        self.bboxh = h
        size = max(4, int(15 * (scale-10) / 75))
        if size in self.FONTCACHE:
            self.font = self.FONTCACHE[size]
        else:
            self.font = self.FONTCACHE[size] = pygame.font.Font(FONT, size)

    def setoffset(self, offsetx, offsety):
        "Set the (x,y) origin of the rectangle where the graph will be rendered."
        self.ofsx = offsetx - self.margin
        self.ofsy = offsety - self.margin

    def shiftoffset(self, dx, dy):
        self.ofsx += dx
        self.ofsy += dy

    def shiftscale(self, factor, fix=None):
        if fix is None:
            fixx, fixy = self.screen.get_size()
            fixx //= 2
            fixy //= 2
        else:
            fixx, fixy = fix
        x, y = self.revmap(fixx, fixy)
        self.setscale(self.scale * factor)
        newx, newy = self.map(x, y)
        self.shiftoffset(newx - fixx, newy - fixy)

    def getboundingbox(self):
        "Get the rectangle where the graph will be rendered."
        offsetx = - self.margin - self.ofsx
        offsety = - self.margin - self.ofsy
        return (offsetx, offsety, self.width, self.height)

    def map(self, x, y):
        return (int(x*self.scale) - self.ofsx,
                int((self.bboxh-y)*self.scale) - self.ofsy)

    def revmap(self, px, py):
        return ((px + self.ofsx) / self.scale,
                self.bboxh - (py + self.ofsy) / self.scale)

    def draw_node_commands(self, node):
        xcenter, ycenter = self.map(node.x, node.y)
        boxwidth = int(node.w * self.scale)
        boxheight = int(node.h * self.scale)
        fgcolor = COLOR.get(node.color, (0,0,0))
        bgcolor = COLOR.get(node.fillcolor, (255,255,255))

        text = node.label
        lines = text.replace('\l','\l\n').replace('\r','\r\n').split('\n')
        # ignore a final newline
        if not lines[-1]:
            del lines[-1]
        wmax = 0
        hmax = 0
        commands = []
        bkgndcommands = []

        for line in lines:
            raw_line = line.replace('\l','').replace('\r','') or ' '
            img = TextSnippet(self, raw_line, (0, 0, 0), bgcolor)
            w, h = img.get_size()
            if w>wmax: wmax = w
            if raw_line.strip():
                if line.endswith('\l'):
                    def cmd(img=img, y=hmax):
                        img.draw(xleft, ytop+y)
                elif line.endswith('\r'):
                    def cmd(img=img, y=hmax, w=w):
                        img.draw(xright-w, ytop+y)
                else:
                    def cmd(img=img, y=hmax, w=w):
                        img.draw(xcenter-w//2, ytop+y)
                commands.append(cmd)
            hmax += h
            #hmax += 8

        # we know the bounding box only now; setting these variables will
        # have an effect on the values seen inside the cmd() functions above
        xleft = xcenter - wmax//2
        xright = xcenter + wmax//2
        ytop = ycenter - hmax//2
        x = xcenter-boxwidth//2
        y = ycenter-boxheight//2

        if node.shape == 'box':
            rect = (x-1, y-1, boxwidth+2, boxheight+2)
            def cmd():
                self.screen.fill(bgcolor, rect)
            bkgndcommands.append(cmd)
            def cmd():
                pygame.draw.rect(self.screen, fgcolor, rect, 1)
            commands.append(cmd)
        elif node.shape == 'octagon':
            step = 1-math.sqrt(2)/2
            points = [(int(x+boxwidth*fx), int(y+boxheight*fy))
                      for fx, fy in [(step,0), (1-step,0),
                                     (1,step), (1,1-step),
                                     (1-step,1), (step,1),
                                     (0,1-step), (0,step)]]
            def cmd():
                pygame.draw.polygon(self.screen, bgcolor, points, 0)
            bkgndcommands.append(cmd)
            def cmd():
                pygame.draw.polygon(self.screen, fgcolor, points, 1)
            commands.append(cmd)
        return bkgndcommands, commands

    def draw_commands(self):
        nodebkgndcmd = []
        nodecmd = []
        for node in self.graphlayout.nodes.values():
            cmd1, cmd2 = self.draw_node_commands(node)
            nodebkgndcmd += cmd1
            nodecmd += cmd2

        edgebodycmd = []
        edgeheadcmd = []
        for edge in self.graphlayout.edges:
            fgcolor = COLOR.get(edge.color, (0,0,0))
            points = [self.map(*xy) for xy in edge.bezierpoints()]
            
            def drawedgebody(points=points, fgcolor=fgcolor):
                pygame.draw.lines(self.screen, fgcolor, False, points)
            edgebodycmd.append(drawedgebody)

            points = [self.map(*xy) for xy in edge.arrowhead()]
            def drawedgehead(points=points, fgcolor=fgcolor):
                pygame.draw.polygon(self.screen, fgcolor, points, 0)
            edgeheadcmd.append(drawedgehead)
            
            if edge.label:
                x, y = self.map(edge.xl, edge.yl)
                img = TextSnippet(self, edge.label, (0, 0, 0))
                w, h = img.get_size()
                def drawedgelabel(img=img, x1=x-w//2, y1=y-h//2):
                    img.draw(x1, y1)
                edgeheadcmd.append(drawedgelabel)

        return edgebodycmd + nodebkgndcmd + edgeheadcmd + nodecmd

    def render(self):
        bbox = self.getboundingbox()
        self.screen.fill((224, 255, 224), bbox)

        # gray off-bkgnd areas
        ox, oy, width, height = bbox
        dpy_width, dpy_height = self.screen.get_size()
        gray = (128, 128, 128)
        if ox > 0:
            self.screen.fill(gray, (0, 0, ox, dpy_height))
        if oy > 0:
            self.screen.fill(gray, (0, 0, dpy_width, oy))
        w = dpy_width - (ox + width)
        if w > 0:
            self.screen.fill(gray, (dpy_width-w, 0, w, dpy_height))
        h = dpy_height - (oy + height)
        if h > 0:
            self.screen.fill(gray, (0, dpy_height-h, dpy_width, h))

        # draw the graph and record the position of texts
        del self.textzones[:]
        for cmd in self.draw_commands():
            cmd()

    def at_position(self, (x, y)):
        """Figure out the word under the cursor."""
        for rx, ry, rw, rh, word in self.textzones:
            if rx <= x < rx+rw and ry <= y < ry+rh:
                return word
        return None

class TextSnippet:
    
    def __init__(self, renderer, text, fgcolor, bgcolor=None):
        self.renderer = renderer
        parts = []
        for word in re_nonword.split(text):
            if not word:
                continue
            if word in renderer.highlightwords:
                fg, bg = renderer.highlightwords[word]
                bg = bg or bgcolor
            else:
                fg, bg = fgcolor, bgcolor
            parts.append((word, fg, bg))
        # consolidate sequences of words with the same color
        for i in range(len(parts)-2, -1, -1):
            if parts[i][1:] == parts[i+1][1:]:
                word, fg, bg = parts[i]
                parts[i] = word + parts[i+1][0], fg, bg
                del parts[i+1]
        # delete None backgrounds
        for i in range(len(parts)):
            if parts[i][2] is None:
                parts[i] = parts[i][:2]
        # render parts
        self.imgs = []
        i = 0
        while i < len(parts):
            part = parts[i]
            word = part[0]
            antialias = not re_nonword.match(word)  # SDL bug with anti-aliasing
            try:
                img = renderer.font.render(word, antialias, *part[1:])
            except pygame.error:
                del parts[i]   # Text has zero width
            else:
                self.imgs.append(img)
                i += 1
        self.parts = parts

    def get_size(self):
        if self.imgs:
            sizes = [img.get_size() for img in self.imgs]
            return sum([w for w,h in sizes]), max([h for w,h in sizes])
        else:
            return 0, 0

    def draw(self, x, y):
        for part, img in zip(self.parts, self.imgs):
            word = part[0]
            self.renderer.screen.blit(img, (x, y))
            w, h = img.get_size()
            self.renderer.textzones.append((x, y, w, h, word))
            x += w


try:
    sum   # 2.3 only
except NameError:
    def sum(lst):
        total = 0
        for item in lst:
            total += lst
        return total


def build_layout(graphs, name=None):
    """ Build a GraphLayout from a list of control flow graphs.
    """
    from pypy.translator.tool.make_dot import make_dot_graphs
    name = name or graphs[0].name
    gs = [(graph.name, graph) for graph in graphs]
    fn = make_dot_graphs(name, gs, target='plain')
    return GraphLayout(str(fn))
