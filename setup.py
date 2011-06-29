from setuptools import setup, find_packages

setup(
    name="coal",
    version="0.1.1",
    test_suite="unittest2.collector",
    tests_require=["unittest2"],
    install_requires=["Mako"],
    packages=find_packages(exclude=[])
)

