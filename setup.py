#!/usr/bin/env python3
"""
Archive Arbitrage - Package Setup

Install in development mode:
    pip install -e .

Install with all dependencies:
    pip install -e ".[dev]"
"""

from setuptools import setup, find_packages
import os

# Read requirements from files
def read_requirements(filename):
    """Read requirements from a file, skipping comments and empty lines."""
    with open(filename, 'r') as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith('#')
        ]

# Get current directory
here = os.path.abspath(os.path.dirname(__file__))

# Read long description from README
long_description = ""
readme_path = os.path.join(here, 'README.md')
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()

# Core requirements
install_requires = read_requirements('requirements.txt')

# Development requirements
dev_requires = read_requirements('requirements-dev.txt')

setup(
    name='archive-arbitrage',
    version='1.0.0',
    description='Fashion resale arbitrage tool for finding underpriced archive items',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Alex Marianetti',
    python_requires='>=3.11',
    packages=find_packages(exclude=['tests', 'tests.*', 'venv', 'venv.*']),
    include_package_data=True,
    install_requires=install_requires,
    extras_require={
        'dev': dev_requires,
    },
    entry_points={
        'console_scripts': [
            'archive-arbitrage=gap_hunter:main',
            'aa-validate=core.dependencies:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)
