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
#%option G_OPT_R_INPUTS
#% key: raster
#% required: no
#% description: Name of input vector map(s) used by GRASS script
#%end
#%option G_OPT_V_INPUTS
#% key: vector
#% required: no
#% description: Name of input vector map(s) used by GRASS script
#%end
#%option G_OPT_R_OUTPUTS
#% key: raster_output
#% required: no
#% description: Name of output raster map(s) used by GRASS script
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


# options could be replaced by individual parameters
def get_session(options):
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
    return session


class GrassSession(object):
    def __init__(self, connection, grassdata, location, mapset):
        self.connection = connection
        remote_sep = '/'  # path separator on remote host
        self.full_mapset = remote_sep.join(
            [grassdata, location, mapset])
        unique = "random"
        self.directory = "/tmp/{dir}".format(dir=unique)
        directory = "random"
        directory_path = "/tmp/{dir}".format(dir=directory)
        self.connection.run('mkdir {dir}'.format(dir=directory_path))

    def put_rasters(self, rasters):
        unpack_script = 'unpack_script.py'
        unpack = open(unpack_script, 'w')
        unpack.write("#!/usr/bin/env python\n")
        unpack.write("import grass.script as gscript\n")

        region_name = 'g_remote_current_region'
        gscript.run_command('g.region', save=region_name, overwrite=True)
        region_file = gscript.find_file(region_name, element='windows')['file']
        self.connection.put(region_file, '/'.join([self.full_mapset, 'windows', region_name]))
        unpack.write("gscript.run_command('g.region', region='{region}')\n".format(region=region_name))

        files_to_transfer = []
        for raster in rasters:
            filename = raster + '.rpack'
            gscript.run_command(
                'r.pack', input=raster, output=filename, overwrite=True)
            remote_filename = "{dir}/{file}".format(
                dir=self.directory, file=filename)
            files_to_transfer.append((filename, remote_filename))
            unpack.write("gscript.run_command('r.unpack', input='{file}', overwrite=True)\n".format(file=remote_filename))

        for filenames in files_to_transfer:
            self.connection.put(filenames[0], filenames[1])

        unpack.close()
        # run the unpack script
        remote_unpack_script_path = "{dir}/{file}".format(
            dir=self.directory, file=unpack_script)
        self.connection.put(unpack_script, remote_unpack_script_path)
        self.connection.chmod(remote_unpack_script_path, stat.S_IRWXU)
        self.connection.run(
            'GRASS_BATCH_JOB={script} grass-trunk -text {mapset}'.format(
                script=remote_unpack_script_path, mapset=self.full_mapset))

    def get_rasters(self, raster_outputs):
        pack_script = 'pack_script.py'
        pack = open(pack_script, 'w')
        pack.write("#!/usr/bin/env python\n")
        pack.write("import grass.script as gscript\n")

        files_to_transfer_back = []
        for raster in raster_outputs:
            filename = raster + '.rpack'
            remote_filename = "{dir}/{file}".format(
                dir=self.directory, file=filename)
            files_to_transfer_back.append((remote_filename, filename))
            pack.write("gscript.run_command('r.pack', input='{map}', output='{file}', overwrite=True)\n".format(map=raster, file=remote_filename))

        pack.close()
        # run the pack script
        remote_pack_script_path = "{dir}/{file}".format(
            dir=self.directory, file=pack_script)
        self.connection.put(pack_script, remote_pack_script_path)
        self.connection.chmod(remote_pack_script_path, stat.S_IRWXU)
        self.connection.run(
            'GRASS_BATCH_JOB={script} grass-trunk -text {mapset}'.format(
                script=remote_pack_script_path, mapset=self.full_mapset))

        for filenames in files_to_transfer_back:
            self.connection.get(filenames[0], filenames[1])
            gscript.run_command('r.unpack', input=filenames[1], overwrite=True)

    # TODO: perhaps we can remove by default? but not removing is faster
    def run_script(self, script, remove=False):
        """
        :param remove: remove file on a remote after execution
        """
        script_path = script
        script_name = os.path.basename(script_path)
        remote_script_path = "{dir}/{script}".format(
            dir=self.directory, script=script_name)
        self.connection.put(script_path, remote_script_path)
        self.connection.chmod(remote_script_path, stat.S_IRWXU)
        self.connection.run(
            'GRASS_BATCH_JOB={script} grass-trunk -text {mapset}'.format(
                script=remote_script_path, mapset=self.full_mapset))
        if remove:
            self.connection.run('rm {file}'.format(file=remote_script_path))

    def close(self):
        self.connection.run('rm -r {dir}'.format(dir=self.directory))


def as_list(option):
    if option:
        return option.split(',')
    else:
        return []


def main():
    options, flags = gscript.parser()
    script_path = options['grass_script']

    remote_grassdata = options['grassdata']
    remote_location = options['location']
    remote_mapset = options['mapset']

    rasters = as_list(options['raster'])
    raster_outputs = as_list(options['raster_output'])

    session = get_session(options)
    gsession = GrassSession(connection=session, grassdata=remote_grassdata,
                            location=remote_location, mapset=remote_mapset)
    gsession.put_rasters(rasters)
    gsession.run_script(script_path)
    gsession.get_rasters(raster_outputs)
    gsession.close()


if __name__ == "__main__":
    main()
