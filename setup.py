import os
from setuptools import setup, find_packages

long_desc = """
This project aims is to make it easy to interact with Microsoft Graph and Office 365 Email, Contacts, Calendar, OneDrive, etc.

This project is inspired on the super work done by [Toben Archer](https://github.com/Narcolapser) [Python-O365](https://github.com/Narcolapser/python-o365).
The oauth part is based on the work done by [Royce Melborn](https://github.com/roycem90) which is now integrated with the original project.

I just want to make this project different in almost every sense, and make it also more pythonic.
So I ended up rewriting the hole project from scratch.

The result is a package that provides a lot of the Microsoft Graph and Office 365 API capabilities.

This is for example how you send a message:

from pyo365 import Account

credentials = ('client_id', 'client_secret')

account = Account(credentials, auth_method='oauth')
m = account.new_message()
m.to.add('to_example@example.com')
m.subject = 'Testing!'
m.body = "George Best quote: I've stopped drinking, but only while I'm asleep."
m.send()
"""

# Available classifiers: https://pypi.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: Apache Software License',
    'Topic :: Office/Business :: Office Suites',
    'Topic :: Software Development :: Libraries',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3 :: Only',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Operating System :: OS Independent',
]


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname), 'r') as file:
        return file.read()


requires = [
    'requests>=2.0.0',
    'requests_oauthlib>=1.0.0',
    'python-dateutil>=2.7',
    'pytz>=2018.5',
    'tzlocal>=1.5.0',
    'beautifulsoup4>=4.0.0',
    'stringcase>=1.2.0'
]

setup(
    name='pyo365',
    version='0.1.0',
    # packages=['pyo365', 'pyo365.utils'],
    packages=find_packages(),
    url=' https://github.com/janscas/pyo365',
    license='Apache License 2.0',
    author='Janscas',
    author_email='janscas@users.noreply.github.com',
    maintainer='Janscas',
    maintainer_email='janscas@users.noreply.github.com',
    description='Microsoft Graph and Office 365 API made easy',
    long_description=read('README.md'),
    long_description_content_type="text/markdown",
    classifiers=CLASSIFIERS,
    python_requires=">=3.4",
    install_requires=requires,
)
