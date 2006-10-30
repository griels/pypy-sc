import random
import time
import thread
import smtplib
import py

def issubdict(d1, d2):
    """sees whether a dict is a 'subset' of another dict
    
        dictvalues can be immutable data types and list and dicts of 
        immutable data types and lists and ... (recursive)
    """
    for k, v in d1.iteritems():
        if not k in d2:
            return False
        d2v = d2[k]
        if isinstance(v, dict) and isinstance(d2v, dict):
            if not issubdict(v, d2v):
                return False
        elif isinstance(v, list) and isinstance(d2v, list):
            if not set(v).issubset(set(d2v)):
                return False
        elif v != d2v:
            return False
    return True

class RequestStorage(object):
    """simple registry that manages information"""
    def __init__(self, info_to_path=[]):
        self._id_to_info = {} # id -> info dict
        self._id_to_emails = {} # id -> requestor email address
        self._id_to_path = {} # id -> filepath

        self._last_id = 0
        self._id_lock = thread.allocate_lock()

        self._build_initial(info_to_path)

    def request(self, email, info):
        """place a request

            this either returns a path to the binary (if it's available 
            already) or an id for the info
        """
        infoid = self.get_info_id(info)
        path = self._id_to_path.get(infoid)
        if path is not None:
            return path
        self._id_to_emails.setdefault(infoid, []).append(email)
    
    def get_info_id(self, info):
        """retrieve or create an id for an info dict"""
        self._id_lock.acquire()
        try:
            for k, v in self._id_to_info.iteritems():
                if v == info:
                    return k
            self._last_id += 1
            id = self._last_id
            self._id_to_info[id] = info
            return id
        finally:
            self._id_lock.release()

    def add_build(self, info, path):
        """store the data for a build and make it available

            returns a list of email addresses for the people that should be
            warned
        """
        infoid = self.get_info_id(info)
        emails = self._id_to_emails.pop(infoid)
        self._id_to_path[infoid] = path
        return emails

    def _build_initial(self, info_to_path):
        """fill the dicts with info about files that are already built"""
        for info, path in info_to_path:
            id = self.get_info_id(info)
            self._id_to_path[id] = path

from py.__.path.local.local import LocalPath
class BuildPath(LocalPath):
    def _info(self):
        info = getattr(self, '_info_value', [])
        if info:
            return info
        for name in ['system', 'compile']:
            currinfo = {}
            infopath = self.join('%s_info.txt' % (name,))
            if not infopath.check():
                return ({}, {})
            for line in infopath.readlines():
                line = line.strip()
                if not line:
                    continue
                chunks = line.split(':')
                key = chunks.pop(0)
                value = ':'.join(chunks)
                currinfo[key] = eval(value)
            info.append(currinfo)
        info = tuple(info)
        self._info_value = info
        return info

    def _set_info(self, info):
        self._info_value = info
        assert len(info) == 2, 'not a proper info tuple'
        for i, name in enumerate(['system', 'compile']):
            infopath = self.join('%s_info.txt' % (name,))
            infopath.ensure()
            fp = infopath.open('w')
            try:
                for key, value in info[i].iteritems():
                    fp.write('%s: %r\n' % (key, value))
            finally:
                fp.close()
    
    info = property(_info, _set_info)

    def _zipfile(self):
        return py.path.local(self / 'data.zip')

    def _set_zipfile(self, iterable):
        # XXX not in use right now...
        fp = self._zipfile().open('w')
        try:
            for chunk in iterable:
                fp.write(chunk)
        finally:
            fp.close()

    zipfile = property(_zipfile, _set_zipfile)

class PPBServer(object):
    retry_interval = 10
    
    def __init__(self, projname, channel, builddir, mailhost=None,
                    mailport=None, mailfrom=None):
        self._projname = projname
        self._channel = channel
        self._builddir = builddir
        self._mailhost = mailhost
        self._mailport = mailport
        self._mailfrom = mailfrom
        
        self._buildpath = py.path.local(builddir)
        self._clients = []
        info_to_path = [(p.info, str(p)) for p in 
                        self._get_buildpaths(builddir)]
        self._requeststorage = RequestStorage(info_to_path)
        self._queued = []

        self._queuelock = thread.allocate_lock()
        self._namelock = thread.allocate_lock()
        
    def register(self, client):
        self._clients.append(client)
        self._channel.send('registered %s with info %r' % (
                            client, client.sysinfo))
        client.channel.send('welcome')

    def compile(self, requester_email, info):
        """start a compilation

            requester_email is an email address of the person requesting the
            build, info is a tuple (sysinfo, compileinfo) where both infos
            are configs converted (or serialized, basically) to dict

            returns a tuple (ispath, data)

            if there's already a build available for info, this will return
            a tuple (True, path), if not, this will return (False, message),
            where message describes what is happening with the request (is
            a build made rightaway, or is there no client available?)

            in any case, if the first item of the tuple returned is False,
            an email will be sent once the build is available
        """
        path = self._requeststorage.request(requester_email, info)
        if path is not None:
            pathstr = str(path)
            self._channel.send('already a build for this info available')
            return (True, pathstr)
        for client in self._clients:
            if client.busy_on == info:
                self._channel.send('build for %r currently in progress' %
                                    (info,))
                return (False, 'this build is already in progress')
        # we don't have a build for this yet, find a client to compile it
        if self.run(info):
            return (False, 'found a suitable client, going to build')
        self._queuelock.acquire()
        try:
            self._queued.append(info)
        finally:
            self._queuelock.release()
        return (False, 'no suitable client found; your request is queued')
    
    def run(self, info):
        """find a suitable client and run the job if possible"""
        clients = self._clients[:]
        # XXX shuffle should be replaced by something smarter obviously ;)
        random.shuffle(clients)
        for client in clients:
            if client.busy_on or not issubdict(info[0], client.sysinfo):
                continue
            else:
                self._channel.send(
                    'going to send compile job with info %r to %s' % (
                        info, client
                    )
                )
                client.compile(info)
                return True
        self._channel.send(
            'no suitable client available for compilation with info %r' % (
                info,
            )
        )

    def serve_forever(self):
        """this keeps the script from dying, and re-tries jobs"""
        self._channel.send('going to serve')
        while 1:
            time.sleep(self.retry_interval)
            self._cleanup_clients()
            self._try_queued()

    def get_new_buildpath(self, info):
        path = BuildPath(str(self._buildpath / self._create_filename()))
        path.info = info
        return path

    def compilation_done(self, info, path):
        """client is done with compiling and sends data"""
        self._channel.send('compilation done for %r, written to %s' % (
                                                                info, path))
        emails = self._requeststorage.add_build(info, path)
        for emailaddr in emails:
            self._send_email(emailaddr, info, path)

    def _cleanup_clients(self):
        self._queuelock.acquire()
        try:
            clients = self._clients[:]
            for client in clients:
                if client.channel.isclosed():
                    if client.busy_on:
                        self._queued.append(client.busy_on)
                    self._clients.remove(client)
        finally:
            self._queuelock.release()

    def _try_queued(self):
        self._queuelock.acquire()
        try:
            toremove = []
            for info in self._queued:
                if self.run(info):
                    toremove.append(info)
            for info in toremove:
                self._queued.remove(info)
        finally:
            self._queuelock.release()

    def _get_buildpaths(self, dirpath):
        for p in py.path.local(dirpath).listdir():
            yield BuildPath(str(p))

    _i = 0
    def _create_filename(self):
        self._namelock.acquire()
        try:
            today = time.strftime('%Y%m%d')
            buildnames = [p.basename for p in 
                            py.path.local(self._buildpath).listdir()]
            while True:
                name = '%s-%s-%s' % (self._projname, today, self._i)
                self._i += 1
                if name not in buildnames:
                    return name
        finally:
            self._namelock.release()

    def _send_email(self, addr, info, path):
        self._channel.send('going to send email to %s' % (addr,))
        if self._mailhost is not None:
            msg = '\r\n'.join([
                'From: %s' % (self._mailfrom,),
                'To: %s' % (addr,),
                'Subject: %s compilation done' % (self._projname,),
                '',
                'The compilation you requested is done. You can find it at',
                str(path),
            ])
            server = smtplib.SMTP(self._mailhost, self._mailport)
            server.set_debuglevel(0)
            server.sendmail(self._mailfrom, addr, msg)
            server.quit()

initcode = """
    import sys
    sys.path += %r

    try:
        try:
            from pypy.tool.build.server import PPBServer
            server = PPBServer(%r, channel, %r, %r, %r, %r)

            # make the server available to clients as pypy.tool.build.ppbserver
            from pypy.tool import build
            build.ppbserver = server

            server.serve_forever()
        except:
            import sys, traceback
            exc, e, tb = sys.exc_info()
            channel.send(str(exc) + ' - ' + str(e))
            for line in traceback.format_tb(tb):
                channel.send(line[:1])
            del tb
    finally:
        channel.close()
"""
def init(gw, port=12321, path=[], projectname='pypy', buildpath=None,
            mailhost=None, mailport=25, mailfrom=None):
    from pypy.tool.build import execnetconference
    conference = execnetconference.conference(gw, port, True)
    channel = conference.remote_exec(initcode % (path, projectname, buildpath,
                                                    mailhost, mailport,
                                                    mailfrom))
    return channel
