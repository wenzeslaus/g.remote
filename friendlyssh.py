#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
############################################################################
#
# MODULE:       friendlyssh.py (not an actual GRASS module)
# AUTHOR(S):    Original author unknown
#               Modified by Vaclav Petras, 2015
#
# PURPOSE:      establish a SSH session to a remote system
#
# COPYRIGHT:    (C) 2015 by Vaclav Petras and GRASS Development Team
#
#               This program is free software under the GNU General Public
#               License (>=v2). Read the file COPYING that comes with GRASS
#               for details.
#
############################################################################

# Original Friendly Python SSH2 interface file
#
# The original file can be found in this repository (under LGPL license,
# original author probably unknown, original probabaly Public Domain or
# something permisive, zoink-sftp maintainer Oisin Mulvihill):
# http://bazaar.launchpad.net/~oisin-mulvihill/zoink-sftp/trunk/view/head:/lib/zoinksftp/ssh.py
# There are different versions of this file online with slight differences:
# http://cloudwizard.googlecode.com/svn-history/r36/trunk/cloudwizard/ssh.py
# http://media.commandline.org.uk/code/ssh.txt
# Note that this code is now relicensed and is under GNU GPL.


import os
import sys
import logging
import tempfile
import paramiko


class Connection(object):

    """Connects and logs into the specified hostname.
    Arguments that are not given are guessed from the environment."""

    def __init__(self,
                 host,
                 username=None,
                 private_key=None,
                 password=None,
                 port=22,
                 ):

        self.log = logging.getLogger("zoinksftp.ssh.Connection")

        self._sftp_live = False
        self._sftp = None
        if not username:
            username = os.environ['LOGNAME']

        # Log to a temporary file.
        # TODO: check if we need this
        templog = tempfile.mkstemp('.txt', 'ssh-')[1]
        paramiko.util.log_to_file(templog)

        # Begin the SSH transport.
        self._transport = paramiko.Transport((host, port))
        self._tranport_live = True
        # Authenticate the transport.
        if password:
            # Using Password.
            self._transport.connect(username=username, password=password)
        else:
            # Use Private Key.
            if not private_key:
                # Try to use default key.
                if os.path.exists(os.path.expanduser('~/.ssh/id_rsa')):
                    private_key = '~/.ssh/id_rsa'
                elif os.path.exists(os.path.expanduser('~/.ssh/id_dsa')):
                    private_key = '~/.ssh/id_dsa'
                else:
                    raise TypeError("You have not specified a password or key.")

            private_key_file = os.path.expanduser(private_key)
            rsa_key = paramiko.RSAKey.from_private_key_file(private_key_file)
            self._transport.connect(username=username, pkey=rsa_key)

    def _sftp_connect(self):
        """Establish the SFTP connection."""
        if not self._sftp_live:
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            self._sftp_live = True

    def get(self, remotepath, localpath=None):
        """Copies a file between the remote host and the local host."""
        if not localpath:
            localpath = os.path.split(remotepath)[1]
        self._sftp_connect()
        self._sftp.get(remotepath, localpath)

    def getdir(self, remotepath, localpath=None):
        """Copies and entire directory from remote to local.

        Based on what is seen by listdir.

        This does not recurse through a directory tree currently. If
        a directory is encountered then you'll see and unable to recover
        error message.
        """
        if not localpath:
            localpath = os.path.abspath(os.curdir)

        self._sftp_connect()
        for i in self._sftp.listdir(remotepath):
            try:
                self._sftp.get("%s/%s" % (remotepath, i),
                               "%s/%s" % (localpath, i))
            except IOError as error:
                self.log.warn("unable to recover item '%s'" % i)

    def put(self, localpath, remotepath=None):
        """Copies a file between the local host and the remote host."""
        if not remotepath:
            remotepath = os.path.split(localpath)[1]
            # TODO: support directory as remotepath as scp does
        self._sftp_connect()
        self._sftp.put(localpath, remotepath)

    def chmod(self, path, mode):
        """Change permission (mode) of a remote file or directory"""
        self._sftp.chmod(path, mode)

    def run(self, command):
        """Execute the given commands on a remote machine."""
        channel = self._transport.open_session()
        channel.exec_command(command)
        stdout = channel.makefile('rb', -1)
        stderr = channel.makefile_stderr('rb', -1)
        if stderr:
            # shutil.copyfileobj
            sys.stdout.write(stdout.read())
        if stderr:
            sys.stderr.write(stderr.read())

    def close(self):
        """Closes the connection and cleans up."""
        # Close SFTP Connection.
        if self._sftp_live:
            self._sftp.close()
            self._sftp_live = False
        # Close the SSH Transport.
        if self._tranport_live:
            self._transport.close()
            self._tranport_live = False

    def __del__(self):
        """Attempt to clean up if not explicitly closed."""
        try:
            self.close()

        except AttributeError as error:
            # Usually raised if close was called before this was
            # garbage collected.
            pass
