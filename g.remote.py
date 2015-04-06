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
#% key: workdir
#% type: string
#% required: no
#% multiple: no
#% key_desc: path
#% description: Working directory (path) for the script execution
#% answer: ~
#%end

import os
import grass.script as gscript
import gcloudsshiface


def main():
    options, flags = gscript.parser()
    script_path = options['grass_script']
    script_name = os.path.basename(script_path)

    remote_grassdata = options['grassdata']
    remote_location = options['location']
    remote_mapset = options['mapset']

    session = gcloudsshiface.ssh_session(
        user=options['user'], host=options['server'],
        gsession='gcloudsshiface_session', verbose=1)

    full_mapset = '/'.join([remote_grassdata, remote_location, remote_mapset])

    directory = "random"
    directory_path = "/tmp/{dir}".format(dir=directory)
    session.ssh('mkdir {dir}'.format(dir=directory_path))
    session.scp(script_path, directory_path)
    #session.ssh('{dir}/{script}'.format(dir=directory_path, script=script_name))
    #session.ssh('TEST=ABCabc; echo $TEST'.format(dir=directory_path, script=script_name))
    session.ssh('GRASS_BATCH_JOB={dir}/{script} grass-trunk {mapset}'.format(
        dir=directory_path, script=script_name, mapset=full_mapset))
    session.ssh('rm -r {dir}'.format(dir=directory_path))


if __name__ == "__main__":
    main()
