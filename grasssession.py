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


import os
import io
import stat
from collections import Iterable

import grass.script as gscript


class GrassSession(object):
    """Connection to a remote GRASS GIS session"""

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
        self.connection = connection
        self.grass_command = grass_command
        self.grass_version = grass_version
        # TODO: path.join method as part of connection
        self.remote_sep = "/"  # path separator on remote host
        self.full_location = self.remote_sep.join([grassdata, location])
        self.full_mapset = self.remote_sep.join([grassdata, location, mapset])
        self.full_permanent = self.remote_sep.join([grassdata, location, "PERMANENT"])
        if directory:
            self.directory = directory
        else:
            directory = "/tmp/gremote"
            self.directory = directory
            # TODO: implement connection.mkdir (duplicate os or shutils names)
            self.connection.run("mkdir {dir}".format(dir=directory))

    def create_location(self):
        """Create a Location on a remote server"""
        # TODO: remove location
        # create remote directories
        self.connection.run("mkdir {dir}".format(dir=self.full_location))
        self.connection.run("mkdir {dir}".format(dir=self.full_permanent))
        # copy the files
        path = gscript.read_command(
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
        region_name = "g_remote_current_region"
        # TODO: remove the region
        gscript.run_command("g.region", save=region_name, overwrite=True)
        region_file = gscript.find_file(region_name, element="windows")["file"]
        remote_dir = "/".join([self.full_mapset, "windows"])
        remote_file = "/".join([remote_dir, region_name])
        self.connection.run("mkdir {dir}".format(dir=remote_dir))
        self.connection.put(region_file, remote_file)
        self.run_command("g.region", region=region_name)

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
            gscript.run_command(pack, input=name, output=filename, overwrite=True)
            remote_filename = "{dir}/{file}".format(dir=self.directory, file=filename)
            self.connection.put(filename, remote_filename)
            self.run_command(unpack, input=remote_filename, overwrite=True)

    def get_elements(self, elements, pack, unpack, suffix):
        """Copy each element from the server

        Complementary with put_elements().
        """
        for name in elements:
            filename = name + suffix
            remote_filename = "{dir}/{file}".format(dir=self.directory, file=filename)
            self.run_command(pack, input=name, output=remote_filename, overwrite=True)
            self.connection.get(remote_filename, filename)
            gscript.run_command(unpack, input=filename, overwrite=True)

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
        if not self.grass_version or self.grass_version < 720:
            self.connection.run(
                "GRASS_BATCH_JOB={script} {grass} -text {mapset}".format(
                    script=remote_script_path,
                    mapset=self.full_mapset,
                    grass=self.grass_command,
                )
            )
        else:
            self.connection.run(
                "{grass} -text {mapset} --exec {script}".format(
                    script=remote_script_path,
                    mapset=self.full_mapset,
                    grass=self.grass_command,
                )
            )
        if remove:
            self.connection.run("rm {file}".format(file=remote_script_path))

    def run_code(self, code):
        """Run piece of Python code on the server

        Some imports are provided.
        """
        # TODO: io requires unicode but we should be able to accept str and unicode
        # TODO randomize the name but keep it informative (add start of code)
        script_name = "pack_script.py"
        script = io.open(script_name, "w", newline="")

        script.write(u"#!/usr/bin/env python\n")
        script.write(u"import grass.script as gscript\n")

        if (
            not isinstance(code, str)
            and not isinstance(code, str)
            and isinstance(code, Iterable)
        ):
            for line in code:
                script.write(unicode(line + "\n"))
        else:
            script.write(unicode(code))
        script.close()
        self.run_script(script_name, remove=True)
        os.remove(script_name)

    def run_command(self, *args, **kwargs):
        """Run a module with given parameters on the server"""
        # TODO: perhaps PyGRASS would be appropriate here
        # TODO: for 7.2 and higher, it could use --exec and skip Python
        # TODO: parameters for accumulating commands and executing all at once
        parameters = ["'%s'" % str(arg) for arg in args]
        for opt, val in kwargs.iteritems():
            if "'" in str(val):
                quote = '"'
            else:
                quote = "'"
            parameters.append(
                "{opt}={q}{val}{q}".format(opt=opt, val=str(val), q=quote)
            )
        code = "gscript.run_command(%s)\n" % ", ".join(parameters)
        self.run_code(code)

    def run_bash_code(self, code):
        """Run piece of Bash code on the server"""
        # TODO: io requires unicode but we should be able to accept str and unicode
        # TODO randomize the name but keep it informative (add start of code)
        script_name = "pack_script.sh"
        script = io.open(script_name, "w", newline="")

        script.write(u"#!/usr/bin/env bash\n")

        # TODO: share some code with Python function
        if (
            not isinstance(code, str)
            and not isinstance(code, str)
            and isinstance(code, Iterable)
        ):
            for line in code:
                script.write(unicode(line + "\n"))
        else:
            script.write(unicode(code))
        script.close()
        self.run_script(script_name, remove=True)
        os.remove(script_name)

    def run_bash_command(self, command):
        """Run a bash command provided as list"""
        # TODO: perhaps PyGRASS would be appropriate here
        # TODO: for 7.2 and higher, it could use --exec and skip script
        # TODO: parameters for accumulating commands and executing all at once
        code = ["'%s'" % str(arg) for arg in command]
        self.run_bash_code(" ".join(code))

    def close(self):
        """Finish the connection"""
        self.connection.run("rm -r {dir}".format(dir=self.directory))
