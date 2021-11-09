#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
############################################################################
#
# MODULE:       localsession.py (not an actual GRASS module)
# AUTHOR(S):    Vaclav Petras
#
# PURPOSE:      Work on a local machine with interface of a remote one
#
# COPYRIGHT:    (C) 2016 by Vaclav Petras and GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
############################################################################


"""Control local machine as if it would be a remote machine"""


import shlex
import subprocess


class LocalConnection:
    """Connection to run commands and copy files on a local machine

    This operates on the localhost but provides unified interface with
    the remote connection classes.
    """

    def __init__(self):
        """ """
        pass

    def _exec(self, command):
        """Execute command locally"""
        # subprocess needs a list if it should work on all platforms
        subprocess.call(command)

    def run(self, command):
        """Execute command on a remote machine"""
        # TODO: list versus string in this context and as a parameter
        # currently, unlike the simplessh, we don't support variable
        # before command which is needed for 7.0 batch processing
        return self._exec(shlex.split(command))

    def put(self, localpath, remotepath):
        """Copy file from local machine to remote machine"""
        return self._exec(["cp", localpath, remotepath])

    def get(self, remotepath, localpath):
        """Copy file from remote machine to local machine"""
        return self._exec(["cp", remotepath, localpath])

    def chmod(self, path, mode):
        """Change permission (mode) of a remote file or directory

        For files executable by user use ``mode=stat.S_IRWXU``.

        :param mode: permissions defined in stat package
        """
        return self.run(f"chmod {mode:o} {path}")
