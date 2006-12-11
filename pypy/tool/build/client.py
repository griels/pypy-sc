import thread
import py
from zipfile import ZipFile


class PPBClient(object):
    def __init__(self, channel, sysinfo, testing=False):
        self.channel = channel
        self.sysinfo = sysinfo
        self.busy_on = None
        self.testing = testing

        from pypy.tool.build import ppbserver
        self.server = ppbserver
        self.server.register(self)
        
    def sit_and_wait(self):
        """connect to the host and wait for commands"""
        self.channel.waitclose()
        self.channel.close()

    def compile(self, info):
        """send a compile job to the client side"""
        self.busy_on = info
        self.channel.send(info)
        accepted = self.channel.receive()
        if accepted:
            thread.start_new_thread(self.wait_until_done, (info,))
        return accepted

    def wait_until_done(self, info):
        buildpath = self.server.get_new_buildpath(info)
        
        if not self.testing:
            fp = buildpath.zipfile.open('w')
            try:
                while True:
                    # read data in chunks
                    try:
                        chunk = self.channel.receive()
                    except EOFError:
                        # stop compilation, client has disconnected
                        return 
                    if chunk is None:
                        break
                    fp.write(chunk)
            finally:
                fp.close()
        
        self.server.compilation_done(info, buildpath)
        self.busy_on = None

initcode = """
    import sys
    sys.path += %r
    
    from pypy.tool.build.client import PPBClient

    try:
        try:
            client = PPBClient(channel, %r, %r)
            client.sit_and_wait()
        except:
            try:
                import sys, traceback
                exc, e, tb = sys.exc_info()
                channel.send(str(exc) + ' - ' + str(e))
                for line in traceback.format_tb(tb):
                    channel.send(line[:-1])
                del tb
            except:
                pass
    finally:
        channel.close()
"""
def init(gw, sysconfig, path=None, port=12321, testing=False):
    from pypy.tool.build import execnetconference
    from pypy.config.config import make_dict
    
    if path is None:
        path = []

    sysinfo = make_dict(sysconfig)
    conference = execnetconference.conference(gw, port, False)
    channel = conference.remote_exec(initcode % (path, sysinfo, testing))
    return channel

class ChannelWrapper(object):
    """ wrapper around a channel

        implements (a small part of) the file interface, sends the data
        over the wire in chunks, ending with a None
    """
    def __init__(self, channel):
        self.channel = channel
        self.loc = 0

    def write(self, data):
        self.loc += len(data)
        self.channel.send(data)

    def close(self):
        self.channel.send(None)

    def tell(self):
        return self.loc

    def flush(self):
        pass

def zip_result(res_dir, channel):
    channelwrapper = ChannelWrapper(channel)
    zip = ZipFile(channelwrapper, 'w')
    # might not be C pypy...
    # zip.writestr('pypy-c', res_dir.join('testing_1/testing_1').read())
    for fpath in res_dir.visit():
        try:
            zip.writestr(fpath.relto(res_dir), fpath.read())
        except (py.error.ENOENT, py.error.EISDIR), exc:
            print exc
            continue
    zip.close()
