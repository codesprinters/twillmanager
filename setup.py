#!/usr/bin/env python

from setuptools import setup, find_packages
setup(
    name = "TwillManager",
    version = "0.1",
    packages = find_packages(),
    install_requires=["Cherrypy>=3.1.2", "Mako", "nose"],
)
