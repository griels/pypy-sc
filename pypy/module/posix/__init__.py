# Package initialisation
from pypy.interpreter.mixedmodule import MixedModule

import os
exec 'import %s as posix' % os.name

class Module(MixedModule):
    """This module provides access to operating system functionality that is
standardized by the C Standard and the POSIX standard (a thinly
disguised Unix interface).  Refer to the library manual and
corresponding Unix manual entries for more information on calls."""

    applevel_name = os.name

    appleveldefs = {
    'error'      : 'app_posix.error',
    'stat_result': 'app_posix.stat_result',
    'fdopen'     : 'app_posix.fdopen',
    }
    
    interpleveldefs = {
    'open'      : 'interp_posix.open',
    'lseek'     : 'interp_posix.lseek',
    'write'     : 'interp_posix.write',
    'isatty'    : 'interp_posix.isatty',
    'read'      : 'interp_posix.read',
    'close'     : 'interp_posix.close',
    'fstat'     : 'interp_posix.fstat',
    'stat'      : 'interp_posix.stat',
    'lstat'     : 'interp_posix.lstat',
    'dup'       : 'interp_posix.dup',
    'dup2'      : 'interp_posix.dup2',
    'system'    : 'interp_posix.system',
    'unlink'    : 'interp_posix.unlink',
    'remove'    : 'interp_posix.remove',
    'getcwd'    : 'interp_posix.getcwd',
    'getcwdu'    : 'interp_posix.getcwdu',
    'chdir'     : 'interp_posix.chdir',
    'mkdir'     : 'interp_posix.mkdir',
    'rmdir'     : 'interp_posix.rmdir',
    'environ'   : 'interp_posix.get(space).w_environ',
    'listdir'   : 'interp_posix.listdir',
    'strerror'  : 'interp_posix.strerror',
    'pipe'      : 'interp_posix.pipe',
    'chmod'     : 'interp_posix.chmod',
    'rename'    : 'interp_posix.rename',
    '_exit'     : 'interp_posix._exit',
    'abort'     : 'interp_posix.abort',
    'access'    : 'interp_posix.access',
    'major'     : 'interp_posix.major',
    'minor'     : 'interp_posix.minor',
    }
    
    for func_name in ['ftruncate', 'putenv', 'unsetenv', 'getpid', 'link',
        'symlink', 'readlink', 'fork', 'waitpid', 'chown', 'chroot',
        'confstr', 'ctermid', 'fchdir', 'fpathconf', 'getegid', 'geteuid',
        'getgid', 'getuid', 'getpgid', 'getpid', 'getppid', 'getpgrp',
        'getsid', 'getlogin', 'getgroups', 'getloadavg', 'lchown', 'pathconf']:
        if hasattr(os, func_name):
            interpleveldefs[func_name] = 'interp_posix.%s' % func_name
    
for constant in dir(os):
    value = getattr(os, constant)
    if constant.isupper() and type(value) is int:
        Module.interpleveldefs[constant] = "space.wrap(%s)" % value
for const in ['confstr_names', 'pathconf_names']:
    if hasattr(os, const):
        Module.interpleveldefs[const] = "space.wrap(%s)" % getattr(os, const)
