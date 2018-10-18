#!/usr/bin/env python

from setuptools import setup

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Topic :: Office/Business :: Office Suites',
    'Topic :: Software Development :: Libraries'
]

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(name='O365',
      version='0.9.17',
      description='Python library for working with Microsoft Office 365',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='Toben Archer',
      author_email='sandslash+O365@gmail.com',
      url='https://github.com/Narcolapser/python-o365',
      packages=['O365'],
      install_requires=['requests', 'oauthlib', 'requests_oauthlib', 'future'],
      license='Apache 2.0',
      classifiers=CLASSIFIERS
      )

"""
Quick reference:

Generate dist:
python setup.py sdist bdist_wheel

Upload to TestPyPI
twine upload --repository-url https://test.pypi.org/legacy/ dist/*

Upload to PyPI
twine upload dist/*
"""
