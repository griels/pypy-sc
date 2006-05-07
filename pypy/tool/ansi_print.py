"""
A color print.
"""

import sys

def ansi_print(text, esc, file=None, newline=True, flush=False):
    if file is None: file = sys.stderr
    text = text.rstrip()
    if esc and sys.platform != "win32" and file.isatty():
        if not isinstance(esc, tuple):
            esc = (esc,)
        text = (''.join(['\x1b[%sm' % cod for cod in esc])  +  
                text +
                '\x1b[0m')     # ANSI color code "reset"
    if newline:
        text += '\n'
    file.write(text)
    if flush:
        file.flush()


class AnsiLog:

    KW_TO_COLOR = {
        # color supress
        'red': ((31,), True),
        'bold': ((1,), True),
        'WARNING': ((31,), False),
        'event': ((1,), True),
        'ERROR': ((1, 31), False),
        'info': ((35,), False),
    }

    def __init__(self, kw_to_color={}, file=None):
        self.kw_to_color = self.KW_TO_COLOR.copy()
        self.kw_to_color.update(kw_to_color)
        self.file = file

    def __call__(self, msg):
        tty = getattr(sys.stderr, 'isatty', lambda: False)()
        flush = False
        newline = True
        keywords = []
        esc = []
        for kw in msg.keywords:
            color, supress = self.kw_to_color.get(kw, (None, False))
            if color:
                esc.extend(color)
            if not supress:
                keywords.append(kw)
        if 'start' in keywords:
            if tty:
                newline = False
                flush = True
                keywords.remove('start')
        elif 'done' in keywords:
            if tty:
                print >> sys.stderr
                return
        esc = tuple(esc)
        for line in msg.content().splitlines():
            ansi_print("[%s] %s" %(":".join(keywords), line), esc, 
                       file=self.file, newline=newline, flush=flush)
 
ansi_log = AnsiLog()

# ____________________________________________________________
# Nice helper

def raise_nicer_exception(*extraargs):
    cls, e, tb = sys.exc_info()
    str_e = str(e)
    class ExcSubclass(cls):
        def __str__(self):
            lines = [str_e]
            for extra in extraargs:
                lines.append('\t.. %r' % (extra,))
            return '\n'.join(lines)
    ExcSubclass.__name__ = cls.__name__ + "'"
    ExcSubclass.__module__ = cls.__module__
    e.__class__ = ExcSubclass
    raise ExcSubclass, e, tb
