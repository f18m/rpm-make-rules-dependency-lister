#!/usr/bin/python
# see https://pypi.org/project/rpm-make-rules-dependency-lister/

"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='rpm-make-rules-dependency-lister',
    packages=['rpm_frontend'],
    python_requires='>=3',
    version='0.3',
    description='Module for analyzing RPM dependencies and speedup RPM building process.',
    long_description=long_description,  # Optional
    long_description_content_type='text/markdown',  # Optional (see note above)
    author='Francesco Montorsi',
    author_email='francesco.montorsi@gmail.com',
    url='https://github.com/f18m/rpm-make-rules-dependency-lister',
    download_url='https://github.com/f18m/rpm-make-rules-dependency-lister/archive/v1.0.tar.gz',
    keywords=['RPM', 'GNU make', 'dependency'],
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    entry_points={
        'console_scripts': [
            'rpm_make_rules_dependency_lister = rpm_frontend.rpm_frontend:main',
        ]
    }
)
