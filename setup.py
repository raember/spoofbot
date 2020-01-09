#!/usr/bin/env python3
import setuptools

import spoofbot

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="spoofbot",
    version=spoofbot.__version__,
    author="raember",
    author_email="",
    description="A python requests wrapper for spoofing common browser behaviour",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/raember/spoofbot",
    packages=setuptools.find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
