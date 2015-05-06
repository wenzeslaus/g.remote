# g.remote

GRASS GIS module for executing scripts on a remote server.
If it will prove useful, it will be moved to official GRASS GIS Addons
repository.

The focus is on running a script on a remote machine in synchronous mode
(you wait for the result) and getting the new data back to the local
machine.

It is expected that the server has GRASS GIS, SSH server and
GRASS GIS Location which matches the projection of the Location
on the local machine.


## Installation

### Linux

You need something which provides `ssh` and `scp` commands or
you need to have Paramico Python package.

To install SSH on Ubuntu use:

    sudo apt-get install openssh-client

This package provided `ssh` and other tools required used by
the `simple` backend.

You can also use Python SSH implementation Paramiko:

To install Paramiko on Ubuntu use:

    sudo apt-get install python-paramiko

Use Git to get the latest source code from this repository,
then in GRASS session, use:

    python /path/to/g.remote.py ...

to run the command. This will give you the CLI access. If you want to
get GUI dialog, follow the steps provided for MS Windows.


### MS Windows

On MS Windows you have to use Paramiko which depends on PyCrypto
and ECDSA Python packages.
Paramiko can be installed through `pip` and in theory including
the dependencies. Unfortunately, PyCrypto is for different reasons
difficult to install and must be installed manually.

Install PyCrypto using installer from *Voidspace*:

* http://www.voidspace.org.uk/python/modules.shtml#pycrypto

Start the installer (the `.exe` file). At one point you will be offered
to which Python you want to install it. If you are lucky, you will be
able to select the Python which is associated with your GRASS GIS
installation (or OSGeo4W installation if you are using GRASS GIS from
OSGeo4W). However, likely there will be only one Python which is
in the Windows Registry and is not the one you want. Install PyCrypto
to the Python installation available and remember the path shown for
this Python installation. Finish the installation.

After installation, browse in file manager to the `site-packages`
directory of the Python installation you selected (this is the directory
you should have remembered). Find `Crypto` directory there.
Copy this directory to the `site-packages` directory of you GRASS GIS
installation (or OSGeo4W installation). For standalone GRASS GIS
(WinGRASS), the directory is something like:

    C:\Program File (x86)\GRASS GIS 7.0.0\Python27\lib\site-packages

Note that you will have to copy the file as an administrator (you should
get a dialog for that).

Run GRASS GIS as an administrator. It is enough to start only
the command line, we won't use GUI, but it is still necessary to
select some Location and Mapset.

In the GRASS GIS session, in the system ("black") command line,
install ECDSA using `pip`:

    python -m pip install ecdsa

Then install Paramiko but without its dependencies:

    python -m pip install --no-deps paramiko

We need to use `--no-deps` (or --no-dependencies) to skip installation
of PyCrypto (which in ideal world would be compiled on the fly).

To gain general understanding of installing packages to Python
associated with GRASS GIS or OSGeo4W read:

* https://trac.osgeo.org/osgeo4w/wiki/ExternalPythonPackages
* http://www.region3dfg.org/comp/python_widows/activestate_python/osgeoactivestate

Now you can proceed with getting *g.remote*.
Unless you want to use Git, download the ZIP file with latest source
code. Uncompress the ZIP file. Put the content somewhere in your home
directory. Then in GRASS GIS in the main GUI menu use:

    File > Launch script

Browse to the `g.remote.py` file and select it.
You will be asked if you want to add the directory with `g.remote.py`
file to GRASS GIS Addons paths. For best results answer yes (OK).


## Notes for MS Windows users

It is expected that all servers are using unix-style newlines
(LF, line feet, `\n`), so your script file you have to use these
and not the MS Windows line endings. For example in Spyder editor,
you find the settings in the menu here:

    Source > Convert end-of-line characters

in the code itself, just use `\n` as usually and let Python solve it
for you. Similarly, for paths in you script, you use `os.linesep` to
get the proper file path delimiter (again, this you should do always).


## Example of connection

### Preparation

Run the following locally:

    r.surf.fractal fractal_surface

### Test script

    #!/usr/bin/env python

    import grass.script as gscript

    gscript.run_command('r.univar', map='fractal_surface')

### Running g.remote

    g.remote user=john server=example.com grass_script=/path/to/test.py grassdata=/grassdata location=nc_spm mapset=practice1 raster=fractal_surface raster_output=elevation

In case you have access using password, add also `password` parameter.


## Example of server setup

A user using GRASS GIS through SSH must have full (non-root) access to
the operating system, so high security measures should be applied.
One possible solution is using Docker.

Build an image from repository:

    docker build -t john/grass git://github.com/wenzeslaus/grass-gis-docker.git

Run a new container:

    docker run -d -P --name grass1 -v /some/host/grassdata/:/grassdata john/grass

This adds `/some/host/grassdata/` directory on host machine
as `/grassdata` directory in the container. You will need to solve
permissions and ownership on the host machine using something like:

    chown john:grassusers
    sefacl -Rdm g:grassusers:rwX

See some more details at:

* https://github.com/wenzeslaus/grass-gis-docker

Each running container will have its port and password. You should
give the access only to people you trust. The containers should
be recreated periodically.

Possible improvements include using docker with `--volumes-from``
parameter and scripts (or some actual tool) to manage the containers.
Management of the data should be improved overall to set right
permissions on the mounted volume and manage the rights in a fine way
to protect data shared between users.

In comparison to passwords, SSH keys can be much more easier
and secure but are harder to setup with Docker. They should be
used in cases where users already have SSH access with keys
to the remote machine.


## Copyright and License

See the individual files for their authors. The code is licensed to
GNU GPL, see the individual files and LICENSE file for details.
