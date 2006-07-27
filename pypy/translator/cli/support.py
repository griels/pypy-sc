# some code has been stolen from genc
def string_literal(s):
    def char_repr(c):
        if c in '\\"': return '\\' + c
        if ' ' <= c < '\x7F': return c
        if c == '\n': return '\\n'
        if c == '\t': return '\\t'
        raise ValueError
    def line_repr(s):
        return ''.join([char_repr(c) for c in s])
    def array_repr(s):
        return ' '.join(['%x 00' % ord(c) for c in s+'\001'])

    try:
        return '"%s"' % line_repr(s)
    except ValueError:
        return "bytearray ( %s )" % array_repr(s)


class Tee(object):
    def __init__(self, *args):
        self.outfiles = args

    def write(self, s):
        for outfile in self.outfiles:
            outfile.write(s)

    def close(self):
        for outfile in self.outfiles:
            if outfile is not sys.stdout:
                outfile.close()
