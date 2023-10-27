#!/bin/bash

# This line installs pybind11
pip install pybind11

# This line builds the extension in place
python setup.py build_ext --inplace