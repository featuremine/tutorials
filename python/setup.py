"""
        COPYRIGHT (c) 2019-2023 by Featuremine Corporation.

        This Source Code Form is subject to the terms of the Mozilla Public
        License, v. 2.0. If a copy of the MPL was not distributed with this
        file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import sys
from os import path

with open(path.join(path.dirname(__file__), '..', 'VERSION')) as file:
    tutorials_version = list(file)[0].strip()

if sys.version_info < (3, 6, 0):
    print('Tried to install with an unsupported version of Python. '
          'tutorials requires Python 3.6.0 or greater')
    sys.exit(1)

import setuptools

setuptools.setup (
    name = 'tutorials',
    version = tutorials_version,
    author='Featuremine Corporation',
    author_email='support@featuremine.com',
    url='https://www.featuremine.com',
    description='Featuremine tutorials test package',
    long_description='Featuremine tutorials test package',
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
    ],
    package_data={
        'tutorials': ['*.py']
    },
    license='COPYRIGHT (c) 2019-2023 by Featuremine Corporation',
    packages=['tutorials', 'tutorials.tests'],
    scripts=['scripts/test-tutorials-python'],
    requires=['yamal']
)
