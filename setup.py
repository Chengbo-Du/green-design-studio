# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="gds-core",
    version="0.1.0",
    author="Chengbo Du",
    author_email="cb_du@outlook.com",
    description="Green Design Studio",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Chengbo-Du/gds",
    packages=find_packages(exclude=["tests", "docs"]),
    classifiers=[
    ],
    keywords="building simulation, energy modeling, EnergyPlus, CONTAM, Grasshopper, Honeybee",
    python_requires=">=2.7",
    install_requires=[
        # No hard dependencies - works standalone
        # honeybee-energy is optional (for HB integration)
    ],
    extras_require={
        "honeybee": ["honeybee-energy>=1.90.0"],
    },
)
