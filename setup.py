#!/usr/bin/env python
# encoding: utf-8

from setuptools import setup, find_packages
setup(
    name = "TwillManager",
    version = "0.1-rc2",
    packages = find_packages(),
    install_requires=["Cherrypy>=3.1.2", "Mako", "multiprocessing", "twill"],
    tests_require=["nose", "mock"],
    zip_safe = False,
    include_package_data = True,
    entry_points = {
        'console_scripts': [
            'twillmanager-run = twillmanager:start',
        ],
    }
)
