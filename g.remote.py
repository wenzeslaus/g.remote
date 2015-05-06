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
#% key: password
#% type: string
#% required: no
#% multiple: no
#% key_desc: secret
#% description: User password
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
#% key: port
#% type: integer
#% required: no
#% multiple: no
#% answer: 22
#% key_desc: portnum
#% label: Port on the server used for the connection
#% description: If you don't know it, then the default value is probably fine.
#%end
#%option G_OPT_F_INPUT
#% key: grass_script
#% required: no
#% multiple: no
#% description: Path to the input GRASS script
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
#% key: grass_command
#% type: string
#% required: yes
#% key_desc: name
#% answer: grass70
#% description: Name or path of a command to run GRASS GIS
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
import io
import stat
from collections import Iterable

import grass.script as gscript


def ensure_nones(dictionary, keys):
    for key in keys:
        if not dictionary[key]:
            dictionary[key] = None


def to_ints(dictionary, keys):
    for key in keys:
        if dictionary[key]:
            dictionary[key] = int(dictionary[key])


# options could be replaced by individual parameters
def get_session(options):
    requested_backend = options['backend']
    if requested_backend:
        backends = [requested_backend]
    else:
        # on win there is minimal chance of ssh but try anyway
        # pexpect only upon request, it is specific and insufficiently tested
        backends = ['paramiko', 'simple']
    session = None
    ensure_nones(options, ['port', 'password'])
    to_ints(options, ['port'])
    for backend in backends:
        if backend == 'paramiko':
            try:
                from friendlyssh import Connection
                session = Connection(
                    username=options['user'], host=options['server'],
                    password=options['password'], port=options['port'])
                gscript.verbose(_("Using Paramiko backend"))
                break
            except ImportError as error:
                gscript.verbose(_("Tried Paramiko backend but"
                                  " it is not available (%s)" % error))
                continue
        elif backend == 'simple':
            try:
                from simplessh import SshConnection as Connection
                session = Connection(
                    user=options['user'], host=options['server'],
                    password=options['password'], port=options['port'])
                gscript.verbose(_("Using simple (ssh and scp) backend"))
                break
            except ImportError as error:
                gscript.verbose(_("Tried simple (ssh and scp) backend but"
                                  " it is not available (%s)" % error))
                continue
        elif backend == 'pexpect':
            try:
                from pexpectssh import SshSession as Connection
                session = Connection(
                    user=options['user'], host=options['server'],
                    logfile='gcloudsshiface.log', verbose=1,
                    password=options['password'], port=options['port'])
                gscript.verbose(_("Using Pexpect (with ssh and scp) backend"))
                break
            except ImportError as error:
                gscript.verbose(_("Tried Pexpect (ssh, scp and pexpect)"
                                  " backend but it is not available"
                                  " (%s)" % error))
                continue
    if session is None:
        hint = _("Please install Paramiko Python package"
                 " or ssh and scp tools.")
        verbose_message = _("Use --verbose flag to get more information.")
        if sys.platform.startswith('win'):
            platform_hint = _("Note that the ssh is generally not available"
                              " for MS Windows. Paramiko should be accessible"
                              " through python pip but you have to make it"
                              " available to GRASS GIS (or OSGeo4W) Python.")
        else:
            platform_hint = _("All should be in the software repositories."
                              " If Paramiko is not in the repository use pip.")
        gscript.fatal(_(
            "No backend available. {general_hint} {platform_hint}"
            " {verbose}").format(
                general_hint=hint, platform_hint=platform_hint,
                verbose=verbose_message))
    return session


class GrassSession(object):
    def __init__(self, connection, grassdata, location, mapset, grass_command):
        self.connection = connection
        self.grass_command = grass_command
        remote_sep = '/'  # path separator on remote host
        self.full_mapset = remote_sep.join(
            [grassdata, location, mapset])
        unique = "random"
        self.directory = "/tmp/{dir}".format(dir=unique)
        directory = "random"
        directory_path = "/tmp/{dir}".format(dir=directory)
        self.connection.run('mkdir {dir}'.format(dir=directory_path))

    def put_region(self):
        region_name = 'g_remote_current_region'
        gscript.run_command('g.region', save=region_name, overwrite=True)
        region_file = gscript.find_file(region_name, element='windows')['file']
        self.connection.put(region_file, '/'.join([self.full_mapset, 'windows', region_name]))
        self.run_command('g.region', region=region_name)

    def put_rasters(self, rasters):
        for raster in rasters:
            filename = raster + '.rpack'
            gscript.run_command(
                'r.pack', input=raster, output=filename, overwrite=True)
            remote_filename = "{dir}/{file}".format(
                dir=self.directory, file=filename)
            self.connection.put(filename, remote_filename)
            self.run_command('r.unpack', input=remote_filename, overwrite=True)

    def get_rasters(self, raster_outputs):
        for raster in raster_outputs:
            filename = raster + '.rpack'
            remote_filename = "{dir}/{file}".format(
                dir=self.directory, file=filename)
            self.run_command('r.pack', input=raster, output=remote_filename,
                             overwrite=True)
            self.connection.get(remote_filename, filename)
            gscript.run_command('r.unpack', input=filename, overwrite=True)

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
            'GRASS_BATCH_JOB={script} {grass} -text {mapset}'.format(
                script=remote_script_path, mapset=self.full_mapset,
                grass=self.grass_command))
        if remove:
            self.connection.run('rm {file}'.format(file=remote_script_path))

    def run_code(self, code):
        # TODO: io requires unicode but we should be able to accept str and unicode
        script_name = 'pack_script.py'
        script = io.open(script_name, 'w', newline='')

        script.write(u"#!/usr/bin/env python\n")
        script.write(u"import grass.script as gscript\n")

        if (not isinstance(code, str) and not isinstance(code, str)
           and isinstance(code, Iterable)):
            for line in code:
                script.write(unicode(line + '\n'))
        else:
            script.write(unicode(code))
        script.close()
        self.run_script(script_name, remove=True)
        os.remove(script_name)

    def run_command(self, *args, **kwargs):
        # TODO: perhaps PyGRASS would be appropriate here
        parameters = ["'%s'" % str(arg) for arg in args]
        for opt, val in kwargs.iteritems():
            if "'" in str(val):
                quote = '"'
            else:
                quote = "'"
            parameters.append('{opt}={q}{val}{q}'.format(
                opt=opt, val=str(val), q=quote))
        code = "gscript.run_command(%s)\n" % ', '.join(parameters)
        self.run_code(code)

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
                            location=remote_location, mapset=remote_mapset,
                            grass_command=options['grass_command'])
    gsession.put_region()
    gsession.put_rasters(rasters)
    gsession.run_script(script_path)
    gsession.get_rasters(raster_outputs)
    gsession.close()


if __name__ == "__main__":
    main()
