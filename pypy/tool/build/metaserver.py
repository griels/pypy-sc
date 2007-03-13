import random
import time
import thread
import smtplib
import py
from pypy.tool.build.build import BuildPath

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

def make_id(build):
    """ generate a unique, but predictable id for a build """

class MetaServer(object):
    """ the build meta-server

        this delegates or queues build requests, and stores results and sends
        out emails when they're done
    """
    retry_interval = 10
    
    def __init__(self, config, channel):
        self.config = config
        self._channel = channel
        self._buildroot = buildpath = py.path.local(config.buildpath)
        
        self._builders = []

        done = []
        for bp in self._get_buildpaths(buildpath):
            if bp.done:
                done.append(bp)
            else:
                # throw away half-done builds...
                bp.remove()

        self._done = done

        self._queued = [] # no builders available
        self._waiting = [] # compilation already in progress for someone else

        self._queuelock = thread.allocate_lock()
        self._namelock = thread.allocate_lock()
        
    def register(self, builder):
        """ register a builder (instance) """
        self._builders.append(builder)
        self._channel.send('registered %s with info %r' % (
                            builder, builder.sysinfo))

    def compile(self, request):
        """start a compilation

            requester_email is an email address of the person requesting the
            build, info is a tuple (sysinfo, compileinfo) where both infos
            are configs converted (or serialized, basically) to dict

            returns a tuple (ispath, data)

            if there's already a build available for info, this will return
            a tuple (True, path), if not, this will return (False, message),
            where message describes what is happening with the request (is
            a build made rightaway, or is there no builder available?)

            in any case, if the first item of the tuple returned is False,
            an email will be sent once the build is available
        """
        # store the request, if there's already a build available the
        # storage will return that path
        requestid = request.id()
        for bp in self._done:
            if request.has_satisfying_data(bp.request):
                path = str(bp)
                self._channel.send('already a build for this info available')
                return {'path': path, 'id': requestid, 'isbuilding': True,
                        'message': 'build is already available'}
        for builder in self._builders:
            if builder.busy_on and request.has_satisfying_data(builder.busy_on):
                self._channel.send(
                    "build for %s currently in progress on '%s'" % (
                        request, builder.hostname))
                self._waiting.append(request)
                return {'path': None, 'id': requestid, 'isbuilding': True,
                        'message': "this build is already in progress "
                                   "on '%s'" % (builder.hostname,)}
        # we don't have a build for this yet, find a builder to compile it
        hostname = self.run(request)
        if hostname is not None:
            return {'path': None, 'id': requestid, 'isbuilding': True,
                    'message': "found a suitable server, going to build "
                               "on '%s'" % (hostname, )}
        self._queuelock.acquire()
        try:
            self._queued.append(request)
        finally:
            self._queuelock.release()
        return {'path': None, 'id': requestid, 'isbuilding': False,
                'message': 'no suitable build server found; your request '
                           'is queued'}
    
    def run(self, request):
        """find a suitable build server and run the job if possible"""
        builders = self._builders[:]
        # XXX shuffle should be replaced by something smarter obviously ;)
        random.shuffle(builders)
        for builder in builders:
            # if builder is busy, or sysinfos don't match, refuse rightaway,
            # else ask builder to build it
            if (builder.busy_on or
                    not issubdict(request.sysinfo, builder.sysinfo) or
                    request in builder.refused):
                continue
            else:
                self._channel.send(
                    'going to send compile job for request %s to %s' % (
                        request, builder.hostname
                    )
                )
                accepted = builder.compile(request)
                if accepted:
                    self._channel.send('compile job accepted')
                    return builder.hostname
                else:
                    self._channel.send('compile job denied')
        self._channel.send(
            'no suitable build server available for compilation of %s' % (
                request,
            )
        )

    def serve_forever(self):
        """this keeps the script from dying, and re-tries jobs"""
        self._channel.send('going to serve')
        while 1:
            time.sleep(self.retry_interval)
            self._cleanup_builders()
            self._test_waiting()
            self._try_queued()

    def get_new_buildpath(self, request):
        path = BuildPath(str(self._buildroot / self._create_filename()))
        path.request = request
        return path

    def compilation_done(self, buildpath):
        """builder is done with compiling and sends data"""
        self._queuelock.acquire()
        try:
            self._channel.send('compilation done for %s, written to %s' % (
                                                buildpath.request, buildpath))
            emails = [buildpath.request.email]
            self._done.append(buildpath)
            waiting = self._waiting[:]
            for req in waiting:
                if req.has_satisfying_data(buildpath.request):
                    self._waiting.remove(req)
                    emails.append(req.email)
            for emailaddr in emails:
                print 'sending mail to %s' % (emailaddr,)
                self._send_email(emailaddr, buildpath)
        finally:
            self._queuelock.release()

    def _cleanup_builders(self):
        self._queuelock.acquire()
        try:
            builders = self._builders[:]
            for builder in builders:
                if builder.channel.isclosed():
                    self._channel.send('build server %s disconnected' % (
                        builder,))
                    if builder.busy_on:
                        self._queued.append(builder.busy_on)
                    self._builders.remove(builder)
        finally:
            self._queuelock.release()

    def _test_waiting(self):
        """ for each waiting request, see if the compilation is still alive

            if the compilation is dead, the request is moved to self._queued
        """
        self._queuelock.acquire()
        try:
            waiting = self._waiting[:]
            for request in waiting:
                for builder in self._builders:
                    if request.has_satisfying_data(builder.busy_on):
                        break
                else:
                    # move request from 'waiting' (waiting for a compilation
                    # that is currently in progress) to 'queued' (waiting for
                    # a suitable build builder to connect)
                    self._waiting.remove(request)
                    self._queued.append(request)
                    continue
        finally:
            self._queuelock.release()

    def _try_queued(self):
        self._queuelock.acquire()
        try:
            toremove = []
            for request in self._queued:
                if self.run(request):
                    toremove.append(request)
            for request in toremove:
                self._queued.remove(request)
        finally:
            self._queuelock.release()

    def _get_buildpaths(self, dirpath):
        for p in dirpath.listdir():
            yield BuildPath(str(p))

    _i = 0
    def _create_filename(self):
        self._namelock.acquire()
        try:
            today = time.strftime('%Y%m%d')
            buildnames = [p.basename for p in 
                            py.path.local(self._buildroot).listdir()]
            while True:
                name = '%s-%s-%s' % (self.config.projectname, today, self._i)
                self._i += 1
                if name not in buildnames:
                    return name
        finally:
            self._namelock.release()

    def _send_email(self, addr, buildpath):
        self._channel.send('going to send email to %s' % (addr,))
        if self.config.mailhost is not None:
            try:
                if buildpath.error:
                    subject = '%s - %s during compilation' % (
                                self.config.projectname,
                                buildpath.error.__class__.__name__)
                    body = ('There was an error during the compilation you '
                            'requested. The log can be found below.'
                            '\n\n%s' % (buildpath.log,))
                else:
                    subject = '%s - compilation done' % (
                               self.config.projectname,)
                    body = ('The compilation you requested is done. You can '
                            'find it at:\n%s\n' % (
                             self.config.path_to_url(buildpath,)))
                msg = '\r\n'.join([
                    'From: %s' % (self.config.mailfrom,),
                    'To: %s' % (addr,),
                    'Subject: %s' % (subject,),
                    '',
                    body,
                ])
                server = smtplib.SMTP(self.config.mailhost,
                                      self.config.mailport)
                server.set_debuglevel(0)
                server.sendmail(self.config.mailfrom, addr, msg)
                server.quit()
            except:
                exc, e, tb = py.std.sys.exc_info()
                self._channel.send(
                    'exception sending mail: %s - %s' % (exc, e))
                del tb

initcode = """
    import sys
    sys.path += %r

    try:
        try:
            from pypy.tool.build.metaserver import MetaServer
            from pypy.tool.build import config
            server = MetaServer(config, channel)

            # make the metaserver available to build servers as
            # pypy.tool.build.metaserver_instance
            from pypy.tool import build
            build.metaserver_instance = server

            server.serve_forever()
        except:
            try:
                import sys, traceback
                exc, e, tb = sys.exc_info()
                channel.send(str(exc) + ' - ' + str(e))
                for line in traceback.format_tb(tb):
                    channel.send(line[:1])
                del tb
            except:
                try:
                    channel.close()
                except:
                    pass
    finally:
        channel.close()
"""
def init(gw, config):
    from pypy.tool.build import execnetconference
    
    conference = execnetconference.conference(gw, config.port, True)
    channel = conference.remote_exec(initcode % (config.path,))
    return channel

