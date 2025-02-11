import os

from setuptools import setup, find_packages


VERSION = '2.1.0'

# Available classifiers: https://pypi.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Topic :: Office/Business :: Office Suites',
    'Topic :: Software Development :: Libraries',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3 :: Only',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13',
    'Operating System :: OS Independent',
]


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname), 'r') as file:
        return file.read()


requires = [
    'requests>=2.32.0',
    'msal>=1.31.1',
    'python-dateutil>=2.7',
    'tzlocal>=5.0',
    'beautifulsoup4>=4.0.0',
    'tzdata>=2023.4'
]

setup(
    name='o365',
    version=VERSION,
    packages=find_packages(),
    url='https://github.com/O365/python-o365',
    license='Apache License 2.0',
    author='Alejcas, Roycem90, Narcolapser',
    author_email='alejcas@users.noreply.github.com',
    maintainer='alejcas',
    maintainer_email='alejcas@users.noreply.github.com',
    description='Microsoft Graph and Office 365 API made easy',
    long_description=read('README.md'),
    long_description_content_type="text/markdown",
    classifiers=CLASSIFIERS,
    python_requires=">=3.9",
    install_requires=requires,
    setup_requires=["wheel"],
)
