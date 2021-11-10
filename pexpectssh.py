#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
############################################################################
#
# MODULE:       pexpect.py (not an actual GRASS module)
# AUTHOR(S):    Eric S. Raymond
#               Greatly modified by Nigel W. Moriarty, April 2003
#               Modified by Luca Delucchi 2011
#
# PURPOSE:      establish a SSH session to a remote system
#
# COPYRIGHT:    (C) 2011 by Eric S. Raymond, Nigel W. Moriarty, Luca Delucchi
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
############################################################################

# Original ssh_session.py
#
# The SSH wrapper was derived from ssh_session.py
# example which is or was part of Pexpect (https://github.com/pexpect/pexpect).
#
# The original file can be found in this repository (under the MIT license):
# http://opensource.apple.com/source/lldb/lldb-112/test/pexpect-2.4/
# Note that the code is now relicensed under GNU GPL as the MIT license allows.

"""SSH interface which uses Pexpect"""

import getpass
import subprocess
import sys
import time

import pexpect


class SshSession:
    # We allow for a higher number of attributes, although some could be grouped.
    # pylint: disable=too-many-instance-attributes
    """Connection to run commands on a remote server and copy files

    This class uses ``ssh`` and ``scp`` to perform the operations
    and allows fine control over special states thanks to pexpect.
    """

    def __init__(self, user, host, logfile, password=None, verbose=False):
        """
        :param user: user name on a remote machine
        :param host: name or IP address of a remote machine
        :param logfile: file used to log the information about the processes
        :param password: user password for a remote machine
        :param verbose: whether the execution should be verbose
        """
        # Allow many arguments to create an object.
        # pylint: disable=too-many-arguments
        self.user = user
        self.host = host
        self.verbose = verbose
        self.password = password
        self.logfile_name = logfile
        self.openagent = False
        # keys for pexpect to expect when commands are executed
        self.keys = [
            "authenticity",
            "password:",
            "Enter passphrase",
            "@@@@@@@@@@@@",
            "Command not found.",
            pexpect.EOF,
        ]
        self.logfile = open(self.logfile_name, "w")

    def __repr__(self):
        outl = "class :" + self.__class__.__name__
        for attr in self.__dict__:
            if attr == "password":
                outl += "\n\t" + attr + " : " + "*" * len(self.password)
            else:
                outl += "\n\t" + attr + " : " + str(getattr(self, attr))
        return outl

    def _exec(self, command):
        """Execute a command on the remote host. Return the output."""
        child = pexpect.spawn(command)  # , timeout=10
        if self.verbose:
            sys.stderr.write("-> " + command + "\n")
        seen = child.expect(self.keys)
        self.logfile.write(str(child.before) + str(child.after) + "\n")
        if seen == 0:
            child.sendline("yes")
            seen = child.expect(self.keys)
        if seen in [1, 2]:
            if not self.password:
                self.password = getpass.getpass("Remote password: ")
            child.sendline(self.password)
            child.readline()
            time.sleep(5)
            # Added to allow the background running of remote process
            if not child.isalive():
                seen = child.expect(self.keys)
        if seen == 3:
            lines = child.readlines()
            self.logfile.write(lines)
        if self.verbose:
            sys.stderr.write("<- " + child.before + "|\n")
        try:
            self.logfile.write(str(child.before) + str(child.after) + "\n")
        except Exception:  # pylint: disable=broad-except
            # Ignoring logging errors and access errors during logging.
            pass
        # self.logfile.close()
        return child.before

    def run(self, command):
        """Exectute command on a remote machine"""
        return self._exec('ssh -l %s %s "%s"' % (self.user, self.host, command))

    def put(self, localpath, remotepath):
        """Copy file from local machine to remote machine"""
        return self._exec(
            "scp %s %s@%s:%s" % (localpath, self.user, self.host, remotepath)
        )

    def get(self, remotepath, localpath):
        """Function to move data from server to client"""
        return self._exec(
            "scp %s@%s:%s %s" % (self.user, self.host, remotepath, localpath)
        )

    def chmod(self, path, mode):
        """Change permission (mode) of a remote file or directory

        For files executable by user use ``mode=stat.S_IRWXU``.

        :param mode: permissions defined in stat package
        """
        return self.run(f"chmod {mode:o} {path}")

    def close(self):
        """Close connection"""
        if self.openagent:
            subprocess.Popen(["ssh-agent", "-k"], stdout=subprocess.PIPE)
        return self.logfile.close()
