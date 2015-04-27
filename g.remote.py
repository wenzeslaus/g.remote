#!/usr/bin/env python
############################################################################
#
# MODULE:       g.remote
# AUTHOR(S):    Vaclav Petras
# PURPOSE:      Execute GRASS GIS scripts on a remote machine
# COPYRIGHT:    (C) 2015 by Vaclav Petras, and the GRASS Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
############################################################################

#%module
#% description: Connects GRASS session with another one in a cluster system.
#% keyword: general
#% keyword: cloud computing
#%end
#%flag
#% key: k
#% description: Keep temporal files and mapsets
#%end
#%option
#% key: config
#% type: string
#% required: no
#% multiple: no
#% label: Path to ASCII file containing authentication parameters
#% description: "-" to pass the parameters interactively
#% gisprompt: old,file,input
#% guisection: Define
#%end
#%option
#% key: user
#% type: string
#% required: no
#% multiple: no
#% key_desc: name
#% description: User name
#%end
#%option
#% key: server
#% type: string
#% required: yes
#% multiple: no
#% key_desc: name
#% description: Name or IP of server (remote host) to be connected
#%end
#%option
#% key: grass_script
#% type: string
#% required: no
#% multiple: no
#% key_desc: name
#% description: Path to the input GRASS script
#% gisprompt: old,file,input
#%end
#%option
#% key: grassdata
#% type: string
#% required: yes
#% key_desc: directory
#% description: Path to GRASS Database directory on a remote host
#%end
#%option
#% key: location
#% type: string
#% required: yes
#% key_desc: directory
#% description: GRASS Location on a remote host
#%end
#%option
#% key: mapset
#% type: string
#% required: yes
#% key_desc: directory
#% description: GRASS Mapset on a remote host
#%end
#%option
#% key: vector
#% type: string
#% required: no
#% multiple: yes
#% key_desc: name
#% description: Name of input vector map(s) used by GRASS script
#% gisprompt: old,vector,vector
#%end
#%option
#% key: backend
#% type: string
#% required: no
#% multiple: no
#% key_desc: name
#% label: Backend to be used for connection to the remote machine (server)
#% description: The main difference between various backends are their dependencies. By default an appropriate backend is selected automatically.
#% options: simple,pexpect,paramiko
#% descriptions: simple;Simple backend requires ssh and scp command line tools to be installed and available on PATH;pexpect;Pexpect backend requires the same as simple backend and Pexpect Python package;paramiko;Paramiko backend requires Paramiko Python package
#%end
#%option
#% key: workdir
#% type: string
#% required: no
#% multiple: no
#% key_desc: path
#% description: Working directory (path) for the script execution
#% answer: ~
#%end


import os
import sys
import stat
import grass.script as gscript


def main():
    options, flags = gscript.parser()
    script_path = options['grass_script']
    script_name = os.path.basename(script_path)

    remote_grassdata = options['grassdata']
    remote_location = options['location']
    remote_mapset = options['mapset']

    remote_sep = '/'  # path separator on remote host

    requested_backend = options['backend']
    if requested_backend:
        backends = [requested_backend]
    else:
        if sys.platform.startswith('win'):
            backends = ['paramiko', 'simple']
        else:
            backends = ['paramiko', 'pexpect', 'simple']

    session = None

    for backend in backends:
        if backend == 'paramiko':
            try:
                from friendlyssh import Connection
                session = Connection(
                    username=options['user'], host=options['server'])
                gscript.verbose(_("Using Paramiko backend"))
                break
            except ImportError:
                gscript.verbose(_("Tried Paramiko backend but"
                                  " it is not available"))
                continue
        elif backend == 'simple':
            try:
                from friendlyssh import Connection as Connection
                session = Connection(
                    user=options['user'], host=options['server'])
                gscript.verbose(_("Using simple (ssh and scp) backend"))
                break
            except ImportError:
                gscript.verbose(_("Tried simple (ssh and scp) backend but"
                                  " it is not available"))
                continue
        elif backend == 'pexpect':
            try:
                from pexpectssh import SshSession as Connection
                session = Connection(
                    user=options['user'], host=options['server'],
                    logfile='gcloudsshiface.log', verbose=1)
                gscript.verbose(_("Using Pexpect (with ssh and scp) backend"))
                break
            except ImportError:
                gscript.verbose(_("Tried Pexpect (ssh, scp and pexpect)"
                                  " backend but it is not available"))
                continue

    if session is None:
        hint = _("Please install Paramiko Python package"
                 " or ssh and scp tools.")
        if sys.platform.startswith('win'):
            platform_hint = _("Note that the ssh is generally not available"
                              " for MS Windows. Paramiko should be accessible"
                              " through python pip but you have to make it"
                              " available to GRASS GIS (or OSGeo4W) Python.")
        else:
            platform_hint = _("All should be in the software repositories."
                              " If Paramiko is not in the repository use pip.")
        gscript.fatal(_(
            "No backend available. {general_hint} {platfrom_hint}").format(
                general_hint=hint, platform_hint=platform_hint))

    full_mapset = remote_sep.join(
        [remote_grassdata, remote_location, remote_mapset])

    directory = "random"
    directory_path = "/tmp/{dir}".format(dir=directory)
    remote_script_path = "{dir}/{script}".format(dir=directory_path, script=script_name)
    session.run('mkdir {dir}'.format(dir=directory_path))
    session.put(script_path, remote_script_path)
    session.chmod(remote_script_path, stat.S_IRWXU)
    #session.ssh('{dir}/{script}'.format(dir=directory_path, script=script_name))
    #session.ssh('TEST=ABCabc; echo $TEST'.format(dir=directory_path, script=script_name))
    session.run('GRASS_BATCH_JOB={script} grass-trunk -text {mapset}'.format(
        script=remote_script_path, mapset=full_mapset))
    session.run('rm -r {dir}'.format(dir=directory_path))


if __name__ == "__main__":
    main()
