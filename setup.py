#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" distribute- and pip-enabled setup.py for simple_eyetracker """

from distribute_setup import use_setuptools
use_setuptools()
from setuptools import setup, Extension, find_packages
import os
import sys


if sys.platform == 'darwin':
    extra_link_args = ['-framework', 'CoreFoundation']
else:
    extra_link_args = []


setup(
    name='simple_eyetracker',
    version='dev',
    scripts=['scripts/simple_eyetracker'],
    include_package_data=True,
    packages=find_packages(exclude=['tests', 'scripts']),
    data_files=[(os.path.expanduser('~/.simple_eyetracker'),
                ['config/config.ini'])]
    )
