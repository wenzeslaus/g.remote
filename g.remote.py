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
#% description: Exectues processes in GRASS GIS session on a server
#% keyword: general
#% keyword: cloud computing
#% keyword: server
#% keyword: HPC
#%end
#%option
#% key: server
#% type: string
#% required: yes
#% key_desc: name
#% description: Name or IP of server (remote host) to be connected
#%end
#%option
#% key: port
#% type: integer
#% required: no
#% answer: 22
#% key_desc: portnum
#% label: Port on the server used for the connection
#% description: If you don't know it, then the default value is probably fine.
#%end
#%option
#% key: user
#% type: string
#% required: no
#% key_desc: name
#% description: User name
#% guisection: Authentication
#%end
#%option
#% key: password
#% type: string
#% required: no
#% key_desc: secret
#% description: User password
#% guisection: Authentication
#%end
#%option G_OPT_F_INPUT
#% key: config
#% required: no
#% label: Path to text (ASCII) file containing authentication parameters
#% description: User name and password separated by whitespace
#% guisection: Authentication
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
#%option G_OPT_F_INPUT
#% key: grass_script
#% required: yes
#% multiple: no
#% description: Path to the input GRASS script
#%end
#%option G_OPT_R_INPUTS
#% key: raster_input
#% required: no
#% description: Name of input vector map(s) used by GRASS script
#% guisection: Data
#%end
#%option G_OPT_V_INPUTS
#% key: vector_input
#% required: no
#% description: Name of input vector map(s) used by GRASS script
#% guisection: Data
#%end
#%option G_OPT_R_OUTPUTS
#% key: raster_output
#% required: no
#% description: Name of output raster map(s) used by GRASS script
#% guisection: Data
#%end
# TODO: G_OPT_V_OUTPUTS does not exist, add it to lib
#%option G_OPT_V_OUTPUTS
#% key: vector_output
#% required: no
#% description: Name of output vector map(s) used by GRASS script
#% guisection: Data
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
#% key: local_workdir
#% type: string
#% required: no
#% key_desc: path
#% label: Working directory used to manage temporary files on the local machine
#% description: Default: current directory [Not implemented, only current directory is supported]
#%end
#%option
#% key: remote_workdir
#% type: string
#% required: no
#% key_desc: path
#% label: Working directory (path) for the script execution on the remote server
#% description: Used also to manage temporary files (Default: system temporary directory) [Not implemented, directoryin /tmp with a fixed name is used]
#%end
#%option
#% key: grass_command
#% type: string
#% required: no
#% key_desc: name
#% answer: grass70
#% description: Name or path of a command to run GRASS GIS
#%end
#%flag
#% key: k
#% label: Keep temporary files
#% description: This is useful for debugging [Not implemented, all files are left behind]
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


def check_config_file(filename):
    if not os.path.exists(filename):
        gscript.fatal(_("The file <%s> doesn\'t exist") % filename)
    if stat.S_IMODE(os.stat(filename).st_mode) != int('0600', 8):
        gscript.fatal(_("The file permissions of <{config}> are considered"
                        " insecure.\nPlease correct permissions to read and"
                        " write only for the current user (mode 600).\n"
                        " In Linux (unix) command line:\n"
                        " chmod 600 {config}\n"
                        " In Python:\n"
                        " os.chmod('{config}', stat.S_IWRITE | stat.S_IREAD)"
                        .format(config=filename)))


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

    config_name = options['config']
    if config_name:
        gscript.debug("Config file supplied for login")
        check_config_file(config_name)
        with open(config_name, 'r') as config_file:
            config = config_file.read()
            # split using whitespace
            # (supposing no spaces in user name and password)
            values = config.split()
            if len(values) == 2:
                gscript.verbose(_("Using values for login from config file"))
                options['user'] = values[0]
                options['password'] = values[1]
            else:
                gscript.fatal(_("The config file <%s> is not well-formed."
                                " It should contain user name and password"
                                " separated by whitespace"
                                " (newlines, spaces or tabs)" % config_name))

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
    def __init__(self, connection, grassdata, location, mapset,
                 directory, grass_command):
        self.connection = connection
        self.grass_command = grass_command
        remote_sep = '/'  # path separator on remote host
        self.full_mapset = remote_sep.join(
            [grassdata, location, mapset])
        if directory:
            self.directory = directory
        else:
            directory = "/tmp/gremote"
            self.directory = directory
            self.connection.run('mkdir {dir}'.format(dir=directory))

    def put_region(self):
        region_name = 'g_remote_current_region'
        gscript.run_command('g.region', save=region_name, overwrite=True)
        region_file = gscript.find_file(region_name, element='windows')['file']
        self.connection.put(region_file, '/'.join([self.full_mapset, 'windows', region_name]))
        self.run_command('g.region', region=region_name)

    def put_elements(self, elements, pack, unpack, suffix):
        for name in elements:
            filename = name + suffix
            gscript.run_command(
                pack, input=name, output=filename, overwrite=True)
            remote_filename = "{dir}/{file}".format(
                dir=self.directory, file=filename)
            self.connection.put(filename, remote_filename)
            self.run_command(unpack, input=remote_filename, overwrite=True)

    def get_elements(self, elements, pack, unpack, suffix):
        for name in elements:
            filename = name + suffix
            remote_filename = "{dir}/{file}".format(
                dir=self.directory, file=filename)
            self.run_command(pack, input=name, output=remote_filename,
                             overwrite=True)
            self.connection.get(remote_filename, filename)
            gscript.run_command(unpack, input=filename, overwrite=True)

    def put_rasters(self, maps):
        self.put_elements(maps, 'r.pack', 'r.unpack', '.rpack')

    def get_rasters(self, maps):
        self.get_elements(maps, 'r.pack', 'r.unpack', '.rpack')

    def put_vectors(self, maps):
        self.put_elements(maps, 'v.pack', 'v.unpack', '.vpack')

    def get_vectors(self, maps):
        self.get_elements(maps, 'v.pack', 'v.unpack', '.vpack')

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

    raster_inputs = as_list(options['raster_input'])
    raster_outputs = as_list(options['raster_output'])
    vector_inputs = as_list(options['vector_input'])
    vector_outputs = as_list(options['vector_output'])

    session = get_session(options)

    if options['local_workdir']:
        local_workdir = options['local_workdir']
    else:
        local_workdir = '.'

    gsession = GrassSession(connection=session, grassdata=remote_grassdata,
                            location=remote_location, mapset=remote_mapset,
                            grass_command=options['grass_command'],
                            directory=options['remote_workdir'])
    gsession.put_region()
    gsession.put_rasters(raster_inputs)
    gsession.put_vectors(vector_inputs)
    gsession.run_script(script_path)
    gsession.get_rasters(raster_outputs)
    gsession.get_vectors(vector_outputs)
    gsession.close()


if __name__ == "__main__":
    main()
