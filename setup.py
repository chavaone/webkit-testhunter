#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright 2014,2015 Igalia S.L.
#  Carlos Alberto Lopez Perez <clopez@igalia.com>
#  Marcos Chavarría Teiejeiro <chavarria1991@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os

try:
    from setuptools import setup
except ImportError:
    print ("You must have setuptools package installed. Try \"sudo apt-get" + \
          " install python-setuptools\"")
    quit()

install_requires = ["requests"]

datafiles = []#[(os.path.expanduser(root.replace("jsonresults",'~/.wkth_json_results')) ,
            # [os.path.join(root, f) for f in files]) for root, dirs, files in os.walk("jsonresults")]

setup(
    name="WKTH",
    version="0.8Beta",
    scripts=["wktesthunter"],
    packages=["wkth"],
    install_requires=install_requires,
    data_files=datafiles
)
