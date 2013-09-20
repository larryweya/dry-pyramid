import os

from setuptools import setup


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'pyramid',
    'SQLAlchemy',
    'transaction',
    'pyramid_tm',
    'pyramid_debugtoolbar',
    'zope.sqlalchemy',
    'MySQL-python',
    'webtest',
    'python-slugify',
    'colander',
    'deform',
    'passlib'
]

setup(
    name='drypyramid',
    version='0.2.3',
    description='Package that sits atop pyramid and trys to be dry',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: CRUD :: DRY",
    ],
    author='Larry Weya',
    author_email='larryweya@gmail.com',
    url='',
    packages=['drypyramid'],
    include_package_data=True,
    zip_safe=False,
    test_suite='drypyramid',
    install_requires=requires,
    license='See LICENSE.txt',
)
