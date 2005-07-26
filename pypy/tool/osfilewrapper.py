import os

class OsFileWrapper(object):
    """ Very simple os file wrapper.
    Note user is responsible for closing.
    XXX Could add a simple buffer mechanism. """
    
    def __init__(self, fd):
        self.fd = fd
        
    def read(self, expected):
        readcount = 0
        bufs = []
        while readcount < expected:
            # os.read will raise an error itself
            buf = os.read(self.fd, expected)
            readcount += len(buf)
            bufs.append(buf)
        return "".join(bufs)

    def write(self, buf):
        writecount = 0
        towrite = len(buf)
        while writecount < towrite:
            # os.write will raise an error itself
            writecount += os.write(self.fd, buf)
            buf = buf[writecount:]

    def close(self):
        os.close(self.fd)

    
def create_wrapper(filename, flag, mode=0777):
    fd = os.open(filename, flag, mode)
    return OsFileWrapper(fd)
