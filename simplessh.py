#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
############################################################################
#
# MODULE:       simplessh.py (not an actual GRASS module)
# AUTHOR(S):    Vaclav Petras
#
# PURPOSE:      Communicate with a remote host using ssh and scp
#
# COPYRIGHT:    (C) 2015 by Vaclav Petras and GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
############################################################################


"""A simple implementation of a remote connection using ssh command et al."""

import subprocess


class SshConnection:
    """Connection to run commands on a remote server and copy files

    This class uses ``ssh`` and ``scp`` to perform the operations.

    This class currenly does authentication using keys only.
    """

    def __init__(self, user, host):
        """
        :param user: user name on a remote machine
        :param host: name or IP address of a remote machine
        """
        self.user = user
        self.host = host
        self.openssh = True  # currently equivalent with theoretical batch=True

    def _exec(self, command, check=True):
        """Execute command localy"""
        # subprocess needs a list if it should work on all platforms
        # without shell=True
        if self.openssh:
            # works for OpenSSH client and related scp
            # will not prompt for password if keys are not available
            command.insert(1, "-oBatchMode=yes")
        result = subprocess.run(command, shell=False, check=check, capture_output=True)
        result.stdout = result.stdout.decode()
        result.stderr = result.stderr.decode()
        return result

    def run(self, command):
        """Exectute command on a remote machine"""
        # here we pass command as one string
        return self._exec(["ssh", "-l", self.user, self.host, command])

    def put(self, localpath, remotepath):
        """Copy file from local machine to remote machine"""
        return self._exec(
            ["scp", localpath, "%s@%s:%s" % (self.user, self.host, remotepath)]
        )

    def get(self, remotepath, localpath):
        """Copy file from remote machine to local machine"""
        return self._exec(
            ["scp", "%s@%s:%s" % (self.user, self.host, remotepath), localpath]
        )

    def chmod(self, path, mode):
        """Change permission (mode) of a remote file or directory

        For files executable by user use ``mode=stat.S_IRWXU``.

        :param mode: permissions defined in stat package
        """
        return self.run(f"chmod {mode:o} {path}")
