# encoding: utf-8

from __future__ import absolute_import

import os
import sys

__all__ = ['daemonize']

def __close_ttys():
    """Helper function that closes all open descriptors for tty"""
    import resource
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if maxfd == resource.RLIM_INFINITY:
        maxfd = 1024

    for fd in range(0, maxfd):
        try:
            os.ttyname(fd)
        except:
            continue

        try:
            os.close(fd)
        except:
            pass

    devnull = getattr(os, 'devnull', '/dev/null')
    os.open(devnull, os.O_RDWR)
    # Open returns lowest-available descriptor number
    # We have either /dev/null, or stdin
    os.dup2(0, 1)
    os.dup2(0, 2)


def daemonize():
    """Converts running process into daemon

    It is using standard Unix technique with double-fork and therefore it can
    be only run on Posix systems. For other systems it silently returns.
    """
    if os.name != 'posix':
        return

    if os.fork() != 0:
        sys.exit(0)

    os.setsid()

    if os.fork() != 0:
        sys.exit(0)

    __close_ttys()
