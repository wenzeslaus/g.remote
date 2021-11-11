# MODULE:    g.remote
#
# AUTHOR(S): Vaclav Petras <wenzeslaus gmail com>
#
# PURPOSE:   Execute GRASS GIS scripts on a remote machine
#
# COPYRIGHT: (C) 2021 Vaclav Petras, and by the GRASS Development Team
#
#           This program is free software under the GNU General Public
#           License (>=v2). Read the file COPYING that comes with GRASS
#           for details.

"""A connection class wrapper for a Fabric connection class"""

from fabric import Connection


class FabricConnection(Connection):
    """Connects into the specified hostname and runs commands there.

    Connection arguments that are not given are determined automatically if possible.
    """

    def run(self, command, **kwargs):
        result = super().run(command, hide=True, **kwargs)
        result.returncode = result.return_code
        return result

    def chmod(self, path, mode):
        """Change permission (mode) of a remote file or directory

        For files executable by user use ``mode=stat.S_IRWXU``.

        :param mode: permissions defined in stat package
        """
        return self.run(f"chmod {mode:o} {path}")
