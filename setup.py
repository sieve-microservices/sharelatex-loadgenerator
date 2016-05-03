"""stressing sharelatex
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

from pip.req import parse_requirements

here = path.abspath(path.dirname(__file__))

requirements = parse_requirements(path.join(here, "requirements.txt"), session=False)
install_requires = [str(ir.req) for ir in requirements]

setup(
    name='loadgenerator',
    version='0.0.1',

    description='stressing sharelatex',
    packages=find_packages(exclude=[]),
    install_requires=install_requires,
    extras_require={
        'dev': ['pip'],
        'test': [],
    },
)
