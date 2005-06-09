#! /usr/bin/env python
"""
Client for a graph server (either in-process or over a socket).
"""

import autopath
from pypy.translator.tool.pygame.drawgraph import GraphLayout
from pypy.translator.tool.graphserver import send_msg, recv_msg, MissingPage
from pypy.tool.udir import udir
from py.process import cmdexec


DOT_FILE   = udir.join('graph.dot')
PLAIN_FILE = udir.join('graph.plain')


class ClientGraphLayout(GraphLayout):

    def __init__(self, connexion, key, dot, links, **ignored):
        # generate a temporary .dot file and call dot on it
        DOT_FILE.write(dot)
        cmdexec('dot -Tplain %s>%s' % (str(DOT_FILE),str(PLAIN_FILE)))
        GraphLayout.__init__(self, PLAIN_FILE)
        self.connexion = connexion
        self.key = key
        self.links.update(links)

    def followlink(self, name):
        return self.connexion.download(self.key, name)

    def reload(self):
        return self.connexion.download(self.key)


class InProcessConnexion:

    def download(self, page, link=None):
        if link is not None:
            try:
                page = page.content().followlink(link)
            except KeyError:
                page = MissingPage()
        key = page
        page = page.content()
        return ClientGraphLayout(self, key, page.source, page.links)


class SocketConnexion:

    def __init__(self, s):
        self.s = s

    def download(self, key, link=None):
        send_msg(self.s, (key, link))
        data = recv_msg(self.s)
        return ClientGraphLayout(self, **data)


def get_layout(homepage):
    return InProcessConnexion().download(homepage)

def get_remote_layout(hostname, port=8888):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((hostname, port))
    return SocketConnexion(s).download(0)


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2 or sys.argv[1].count(':') != 1:
        print >> sys.stderr, 'Connects to a graph server like goal/translate_pypy.'
        print >> sys.stderr, 'Usage:  %s hostname:port' % (sys.argv[0],)
        print >> sys.stderr, '   or   %s :port' % (sys.argv[0],)
        sys.exit(2)
    hostname, port = sys.argv[1].split(':')
    port = int(port)
    layout = get_remote_layout(hostname, port)
    layout.display()
