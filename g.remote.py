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
#% required: no
#% multiple: no
#% description: Path to the input GRASS script
#%end
#%option
#% key: exec
#% type: string
#% required: no
#% key_desc: command
#% description: Module or command to execute
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
#% options: simple,pexpect,paramiko,local
#% descriptions: simple;Simple backend requires ssh and scp command line tools to be installed and available on PATH;pexpect;Pexpect backend requires the same as simple backend and Pexpect Python package;paramiko;Paramiko backend requires Paramiko Python package;local;Backend which works on local machine
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
#% answer: grass7
#% description: Name or path of a command to run GRASS GIS
#%end
#%option
#% key: grass_version
#% type: string
#% required: no
#% key_desc: name
#% description: Version of GRASS GIS used remotely
#%end
#%flag
#% key: k
#% label: Keep temporary files
#% description: This is useful for debugging [Not implemented, all files are left behind]
#%end
#%flag
#% key: l
#% label: Create the remote Location
#% description: Copy the location to the remote server
#%end
#%rules
#% required: grass_script,exec
#%end


import os
import sys
import io
import stat
from collections import Iterable

import grass.script as gscript


def ensure_nones(dictionary, keys):
    """Ensure that the specified values are ``None`` if they are not true"""
    for key in keys:
        if not dictionary[key]:
            dictionary[key] = None


def to_ints(dictionary, keys):
    """Convert specified values to ``int``"""
    for key in keys:
        if dictionary[key]:
            dictionary[key] = int(dictionary[key])


def as_list(option):
    """Convert "option multiple" to a list"""
    if option:
        return option.split(",")
    else:
        return []


def check_config_file(filename):
    """Check if config file exists and has expected permissions"""
    if not os.path.exists(filename):
        gscript.fatal(_("The file <%s> doesn't exist") % filename)
    if stat.S_IMODE(os.stat(filename).st_mode) != int("0600", 8):
        gscript.fatal(
            _(
                "The file permissions of <{config}> are considered"
                " insecure.\nPlease correct permissions to read and"
                " write only for the current user (mode 600).\n"
                " In Linux (unix) command line:\n"
                " chmod 600 {config}\n"
                " In Python:\n"
                " os.chmod('{config}', stat.S_IWRITE | stat.S_IREAD)".format(
                    config=filename
                )
            )
        )


# options could be replaced by individual parameters
def get_session(options):
    """Based on a dictionary and available backends create a remote session"""
    requested_backend = options["backend"]
    if requested_backend:
        backends = [requested_backend]
    else:
        # on win there is minimal chance of ssh but try anyway
        # pexpect only upon request, it is specific and insufficiently tested
        backends = ["paramiko", "simple"]
    session = None
    ensure_nones(options, ["port", "password"])
    to_ints(options, ["port"])

    # TODO: provide a flag (or default) for reading the file or params
    # from some standardized location or variable (so we have shorter
    # command lines)
    config_name = options["config"]
    if config_name:
        gscript.debug("Config file supplied for login")
        check_config_file(config_name)
        with open(config_name, "r") as config_file:
            config = config_file.read()
            # split using whitespace
            # (supposing no spaces in user name and password)
            values = config.split()
            if len(values) == 2:
                gscript.verbose(_("Using values for login from config file"))
                options["user"] = values[0]
                options["password"] = values[1]
            else:
                gscript.fatal(
                    _(
                        "The config file <%s> is not well-formed."
                        " It should contain user name and password"
                        " separated by whitespace"
                        " (newlines, spaces or tabs)" % config_name
                    )
                )

    # get access to wrappers
    from grass.pygrass.utils import set_path

    set_path("g.remote")

    for backend in backends:
        if backend == "paramiko":
            try:
                from friendlyssh import Connection

                session = Connection(
                    username=options["user"],
                    host=options["server"],
                    password=options["password"],
                    port=options["port"],
                )
                gscript.verbose(_("Using Paramiko backend"))
                break
            except ImportError as error:
                gscript.verbose(
                    _("Tried Paramiko backend but" " it is not available (%s)" % error)
                )
                continue
        elif backend == "simple":
            try:
                from simplessh import SshConnection as Connection

                # TODO: support password and port (or warn they are missing)
                session = Connection(user=options["user"], host=options["server"])
                gscript.verbose(_("Using simple (ssh and scp) backend"))
                break
            except ImportError as error:
                gscript.verbose(
                    _(
                        "Tried simple (ssh and scp) backend but"
                        " it is not available (%s)" % error
                    )
                )
                continue
        elif backend == "pexpect":
            try:
                from pexpectssh import SshSession as Connection

                # TODO: support port (or warn it's missing)
                session = Connection(
                    user=options["user"],
                    host=options["server"],
                    logfile="gcloudsshiface.log",
                    verbose=1,
                    password=options["password"],
                )
                gscript.verbose(_("Using Pexpect (with ssh and scp) backend"))
                break
            except ImportError as error:
                gscript.verbose(
                    _(
                        "Tried Pexpect (ssh, scp and pexpect)"
                        " backend but it is not available"
                        " (%s)" % error
                    )
                )
                continue
        elif backend == "local":
            try:
                from localsession import LocalConnection as Connection

                session = Connection()
                gscript.verbose(_("Using local host backend"))
                break
            except ImportError as error:
                gscript.verbose(
                    _(
                        "Tried local host"
                        " backend but it is not available"
                        " (%s)" % error
                    )
                )
                continue
    if session is None:
        hint = _("Please install Paramiko Python package" " or ssh and scp tools.")
        verbose_message = _("Use --verbose flag to get more information.")
        if sys.platform.startswith("win"):
            platform_hint = _(
                "Note that the ssh is generally not available"
                " for MS Windows. Paramiko should be accessible"
                " through python pip but you have to make it"
                " available to GRASS GIS (or OSGeo4W) Python."
            )
        else:
            platform_hint = _(
                "All should be in the software repositories."
                " If Paramiko is not in the repository use pip."
            )
        gscript.fatal(
            _(
                "No backend available. {general_hint} {platform_hint}" " {verbose}"
            ).format(
                general_hint=hint, platform_hint=platform_hint, verbose=verbose_message
            )
        )
    return session


def preparse_exec():
    """Extract exec part of the command if present and fix ``sys.argv``

    Returns the command to execute as a list or None.
    Modifies ``sys.argv`` for GRASS parser if needed.
    """
    split_parser = "exec="  # magic parameter to split for parser syntax
    split_parameter = "--exec"  # magic parameter to split for grass72 syntax
    single_command = None
    use_parser = False

    for i, arg in enumerate(sys.argv):
        if arg.startswith(split_parser):
            use_parser = True
            split_at = i
            break
    if use_parser:
        # ...exec="g.region -p"... or ...exec=g.region -p
        exec_value = sys.argv[split_at].split("=")[1]
        if " " in exec_value:  # is not module name
            # exec is a whole command, this code could be also somewhere
            # later on but we need the other tests anyway, after this
            # we just use normal parser
            import shlex

            single_command = shlex.split(exec_value)
        else:
            # exec is just the module name
            single_command = sys.argv[split_at + 1 :]
            single_command.insert(0, exec_value)
            # remove additional parameters
            # but leave the required there
            sys.argv = sys.argv[: split_at + 1]
    elif split_parameter in sys.argv:
        # ...--exec g.region -p
        split_at = sys.argv.index(split_parameter)
        single_command = sys.argv[split_at + 1 :]
        sys.argv = sys.argv[:split_at]
        # remove additional parameters
        # and pretend user provided the required parameters
        sys.argv.append(split_parser + single_command[0])
    return single_command


# TODO: more robust handling, now format ###, e.g. 700, required
# TODO: acquire automatically when not provided
def version_to_number(string):
    if string:
        return int(string)
    else:
        return None


# TODO: what happens to the processes when we interrupt the module
# or the connection is broken? Seems that they are running, that might
# be advantageous but not always desired. (controlled processing
# without connection as in g.cloud would be another level)
def main():
    single_command = preparse_exec()
    options, flags = gscript.parser()

    script_path = options["grass_script"]
    # TODO: read script from stdin

    # TODO: support creating grassdata in a tmp place
    remote_grassdata = options["grassdata"]
    remote_location = options["location"]
    remote_mapset = options["mapset"]

    raster_inputs = as_list(options["raster_input"])
    raster_outputs = as_list(options["raster_output"])
    vector_inputs = as_list(options["vector_input"])
    vector_outputs = as_list(options["vector_output"])

    grass_version = version_to_number(options["grass_version"])

    session = get_session(options)

    # TODO: use variable, e.g. for packing
    if options["local_workdir"]:
        local_workdir = options["local_workdir"]
    else:
        # TODO: this should be tmp
        local_workdir = "."

    from grasssession import GrassSession

    # TODO: default grass binary should be derived from the version we are running
    gsession = GrassSession(
        connection=session,
        grassdata=remote_grassdata,
        location=remote_location,
        mapset=remote_mapset,
        grass_command=options["grass_command"],
        grass_version=grass_version,
        directory=options["remote_workdir"],
    )
    if flags["l"]:
        gsession.create_location()
    gsession.put_region()
    gsession.put_rasters(raster_inputs)
    gsession.put_vectors(vector_inputs)
    if script_path:
        gsession.run_script(script_path)
    elif single_command:
        gsession.run_bash_command(single_command)
    # TODO: add also Python code as an input
    gsession.get_rasters(raster_outputs)
    gsession.get_vectors(vector_outputs)
    gsession.close()


if __name__ == "__main__":
    main()
