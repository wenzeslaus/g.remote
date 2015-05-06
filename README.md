# g.remote

GRASS GIS module for executing scripts on a remote server


## Example

### Preparation

Run the following locally:

    r.surf.fractal fractal_surface

### Test script

    #!/usr/bin/env python

    import grass.script as gscript

    gscript.run_command('r.univar', map='fractal_surface')

### Running g.remote

    g.remote user=john password=Ajf_de8sd server=example.com grass_script=/path/to/test_script.py grassdata=/grassdata location=nc_spm mapset=practice1 raster=fractal_surface raster_output=elevation


## Copyright and License

See the individual files for their authors. The code is licensed to
GNU GPL, see the individual files and LICENSE file for details.
