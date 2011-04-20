from setuptools import setup, find_packages

setup(
    name="coal",
    version="0.1.0",
    test_suite="unittest2.collector",
    tests_require=["unittest2", "mock"],
    install_requires=[],
    packages=find_packages(exclude=[])
)

