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
#############################################################################

# Original ssh_session.py
#
# The SSH wrapper, namelly the pexpect part was derived from ssh_session.py
# example which is or was part of Pexpect (https://github.com/pexpect/pexpect).
#
# The original file can be found in this repository (under MIT license):
# http://opensource.apple.com/source/lldb/lldb-112/test/pexpect-2.4/
# Note that the code is now relicensed under GNU GPL as MIT license allows.


import pexpect
import os
import sys
import subprocess
import getpass
import time


class SshSession(object):
    """Connection to run commands on a remote server and copy files

    This class uses ``ssh`` and ``scp`` to perform the operations
    and allows fine control over special states thanks to pexpect.
    """

    def __init__(self, user, host, logfile,
                 password=None, verbose=False):
        """
        :param user: user name on a remote machine
        :param host: name or IP address of a remote machine
        :param logfile: file used to log the information about the processes
        :param password: user password for a remote machine
        :param verbose: whether the execution should be verbose
        """
        self.user = user
        self.host = host
        self.verbose = verbose
        self.password = password
        self.logfile_name = logfile
        self.openagent = False
        # keys for pexpect to expect when commands are exectued
        self.keys = [
            'authenticity',
            'password:',
            'Enter passphrase',
            '@@@@@@@@@@@@',
            'Command not found.',
            pexpect.EOF,
        ]
        self.logfile = open(self.logfile_name, 'w')

    def __repr__(self):
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            if attr == 'password':
                outl += '\n\t' + attr + ' : ' + '*' * len(self.password)
            else:
                outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
        return outl

    def _exec(self, command):
        """Execute a command on the remote host. Return the output."""
        child = pexpect.spawn(command)  # , timeout=10
        if self.verbose:
            sys.stderr.write("-> " + command + "\n")
        seen = child.expect(self.keys)
        self.logfile.write(str(child.before) + str(child.after) + '\n')
        if seen == 0:
            child.sendline('yes')
            seen = child.expect(self.keys)
        if seen == 1 or seen == 2:
            if not self.password:
                self.password = getpass.getpass('Remote password: ')
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
            self.logfile.write(str(child.before) + str(child.after) + '\n')
        except:
            pass
        # self.logfile.close()
        return child.before

    def run(self, command):
        """Exectute command on a remote machine"""
        return self._exec(
            "ssh -l %s %s \"%s\"" % (self.user, self.host, command))

    def put(self, localpath, remotepath):
        """Copy file from local machine to remote machine"""
        return self._exec(
            "scp %s %s@%s:%s" % (localpath, self.user, self.host, remotepath))

    def get(self, remotepath, localpath):
        """Function to move data from server to client"""
        return self._exec(
            "scp %s@%s:%s %s" % (self.user, self.host, remotepath, localpath))

    def add(self):
        """Function to launch ssh-add"""
        sess = self._exec("ssh-add")
        if sess.find('Could not open') == -1:
            return 0
        else:
            self.openagent = True
            proc = subprocess.Popen(
                ['ssh-agent', '-s'], stdout=subprocess.PIPE)
            output = proc.stdout.read()
            vari = output.split('\n')
            sshauth = vari[0].split(';')[0].split('=')
            sshpid = vari[1].split(';')[0].split('=')
            os.putenv(sshauth[0], sshauth[1])
            os.putenv(sshpid[0], sshpid[1])
            self.add()

    def close(self):
        """Close connection"""
        if self.openagent:
            subprocess.Popen(['ssh-agent', '-k'], stdout=subprocess.PIPE)
        return self.logfile.close()
