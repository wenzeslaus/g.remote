#!/usr/bin/env python

# -*- coding: utf-8 -*-
"""
Created on Mon Apr  6 12:52:28 2015

@author: vpetras
"""

import grass.script as gscript

gscript.run_command("g.list", type="raster,vector", flags="p")
