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

"""Remote GRASS session handling"""

import io
import os
import stat
import sys
from collections.abc import Iterable

import grass.script as gs


def unique_script_name(code, extension):
    """Return unique name for a script

    Randomizes the name but keeps it informative by adding start of code.
    """
    unique = gs.legalize_vector_name(code[: min(len(code), 20)], fallback_prefix="x")
    unique = gs.append_uuid(unique)
    return f"g_remote_script_{unique}.{extension}"


class GrassSession:
    """Connection to a remote GRASS GIS session"""

    # Especially, mapset-related attributes could be managed by a new v8 MapsetPath
    # object, but in general, we consider this a massive class.
    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        connection,
        grassdata,
        location,
        mapset,
        directory,
        grass_command,
        grass_version,
    ):
        # Allow many arguments to create an object.
        # pylint: disable=too-many-arguments

        self.connection = connection
        self.grass_command = grass_command
        self.grass_version = grass_version
        # TODO: path.join method as part of connection
        self.remote_sep = "/"  # path separator on remote host
        self.full_location = self.remote_sep.join([grassdata, location])
        self.full_mapset = self.remote_sep.join([grassdata, location, mapset])
        self.full_permanent = self.remote_sep.join([grassdata, location, "PERMANENT"])
        if directory:
            # Parent directory must exist (we don't want to create whole hierarchy).
            result = self.connection.run("ls {directory}/..")
            # Create the directory if it does not exist.
            self.connection.run("mkdir -p {directory}")
            self.directory = directory
            self._delete_directory = False
        else:
            # Create temporary directory on the remote machine and mark delete it later.
            result = self.connection.run("mktemp -d")
            self.directory = result.stdout.strip()
            self._delete_directory = True
            # TODO: implement connection.mkdir (and duplicate os or shutils names?)

    def create_location(self):
        """Create a Location on a remote server"""
        # TODO: remove location
        # create remote directories
        self.connection.run("mkdir {dir}".format(dir=self.full_location))
        self.connection.run("mkdir {dir}".format(dir=self.full_permanent))
        # copy the files
        path = gs.read_command(
            "g.gisenv", get="GISDBASE,LOCATION_NAME", separator="/"
        ).strip()
        path = os.path.join(path, "PERMANENT")
        for file in ["DEFAULT_WIND", "MYNAME", "PROJ_EPSG", "PROJ_INFO", "PROJ_UNITS"]:
            local = os.path.join(path, file)
            remote = self.remote_sep.join([self.full_location, "PERMANENT", file])
            self.connection.put(local, remote)
        # if location is new, then mapset does not exist
        self.connection.run(
            "{grass} -text {mapset} -c -e".format(
                mapset=self.full_mapset, grass=self.grass_command
            )
        )
        # TODO: implement self.run_grass

    def put_region(self):
        """Set the remote region to the current region"""
        region_name = gs.append_node_pid("g_remote_current")
        # TODO: remove the region
        gs.run_command("g.region", save=region_name, overwrite=True)
        region_file = gs.find_file(region_name, element="windows")["file"]
        remote_dir = "/".join([self.full_mapset, "windows"])
        remote_file = "/".join([remote_dir, region_name])
        self.connection.run("mkdir -p {dir}".format(dir=remote_dir))
        self.connection.put(region_file, remote_file)
        result = self.run_command("g.region", region=region_name)
        if result.returncode:
            print(result.stderr, file=sys.stderr)

    def put_elements(self, elements, pack, unpack, suffix):
        """Copy each element to the server

        The pack module needs to accept input.
        The unpack module needs to accept input and output.

        :param elements: list of element names
        :param pack: module to pack the element
        :param unpack: module to unpack the element
        :param suffix: file suffix to use
        """
        for name in elements:
            filename = name + suffix
            gs.run_command(pack, input=name, output=filename, overwrite=True)
            remote_filename = "{dir}/{file}".format(dir=self.directory, file=filename)
            self.connection.put(filename, remote_filename)
            result = self.run_command(unpack, input=remote_filename, overwrite=True)
            if result.returncode:
                print(result.stderr, file=sys.stderr)

    def get_elements(self, elements, pack, unpack, suffix):
        """Copy each element from the server

        Complementary with put_elements().
        """
        for name in elements:
            filename = name + suffix
            remote_filename = "{dir}/{file}".format(dir=self.directory, file=filename)
            self.run_command(pack, input=name, output=remote_filename, overwrite=True)
            self.connection.get(remote_filename, filename)
            gs.run_command(unpack, input=filename, overwrite=True)

    def put_rasters(self, maps):
        """Copy raster maps to server"""
        self.put_elements(maps, "r.pack", "r.unpack", ".rpack")

    def get_rasters(self, maps):
        """Copy raster maps from server"""
        self.get_elements(maps, "r.pack", "r.unpack", ".rpack")

    def put_vectors(self, maps):
        """Copy vector maps to server"""
        self.put_elements(maps, "v.pack", "v.unpack", ".vpack")

    def get_vectors(self, maps):
        """Copy vector maps from server"""
        self.get_elements(maps, "v.pack", "v.unpack", ".vpack")

    # TODO: perhaps we can remove by default? but not removing is faster
    def run_script(self, script, remove=False):
        """Run script on the server

        :param script: path to a local file
        :param remove: remove file on a remote after execution
        """
        # TODO: make script results visible or hidden
        script_path = script
        script_name = os.path.basename(script_path)
        remote_script_path = "{dir}/{script}".format(
            dir=self.directory, script=script_name
        )
        self.connection.put(script_path, remote_script_path)
        self.connection.chmod(remote_script_path, stat.S_IRWXU)
        result = self.connection.run(
            "{grass} {mapset} --exec {script}".format(
                script=remote_script_path,
                mapset=self.full_mapset,
                grass=self.grass_command,
            )
        )
        if remove:
            self.connection.run("rm {file}".format(file=remote_script_path))
        return result

    def run_code(self, code):
        """Run piece of Python code on the server

        Some imports are provided.
        """
        script_name = unique_script_name(code, "py")
        script = io.open(script_name, "w", newline="")

        script.write("#!/usr/bin/env python\n")
        script.write("import grass.script as gs\n")

        if (
            not isinstance(code, str)
            and not isinstance(code, str)
            and isinstance(code, Iterable)
        ):
            for line in code:
                script.write(line + "\n")
        else:
            script.write(code)
        script.close()
        result = self.run_script(script_name, remove=True)
        os.remove(script_name)
        return result

    def run_command(self, *args, **kwargs):
        """Run a module with given parameters on the server"""
        # TODO: perhaps PyGRASS would be appropriate here
        # TODO: for 7.2 and higher, it could use --exec and skip Python
        # TODO: parameters for accumulating commands and executing all at once
        parameters = ["'%s'" % str(arg) for arg in args]
        for opt, val in kwargs.items():
            if "'" in str(val):
                quote = '"'
            else:
                quote = "'"
            parameters.append(
                "{opt}={q}{val}{q}".format(opt=opt, val=str(val), q=quote)
            )
        code = "gs.run_command({})\n".format(", ".join(parameters))
        return self.run_code(code)

    def run_bash_code(self, code):
        """Run piece of Bash code on the server"""
        script_name = unique_script_name(code, "sh")
        script = io.open(script_name, "w", newline="")

        script.write("#!/usr/bin/env bash\n")

        # TODO: share some code with Python function
        if (
            not isinstance(code, str)
            and not isinstance(code, str)
            and isinstance(code, Iterable)
        ):
            for line in code:
                script.write(line + "\n")
        else:
            script.write(code)
        script.close()
        result = self.run_script(script_name, remove=True)
        os.remove(script_name)
        return result

    def run_bash_command(self, command):
        """Run a bash command provided as list"""
        # TODO: perhaps PyGRASS would be appropriate here
        # TODO: for 7.2 and higher, it could use --exec and skip script
        # TODO: parameters for accumulating commands and executing all at once
        code = ["'%s'" % str(arg) for arg in command]
        return self.run_bash_code(" ".join(code))

    def close(self):
        """Finish the connection"""
        if self._delete_directory:
            self.connection.run(f"rm -r {self.directory}")
