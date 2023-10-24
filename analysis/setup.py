from setuptools import setup, Extension
import pybind11

setup(
    name='graph_module',
    ext_modules=[
        Extension(
            'graph_module',
            ['graph_helper.cpp'],
            include_dirs=[pybind11.get_include()],
            language='c++',
            extra_compile_args=['-std=c++11']
        ),
    ],
    setup_requires=['pybind11'],
)
