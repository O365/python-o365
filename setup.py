import os

from setuptools import setup, find_packages


VERSION = '2.0.33'

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
    'Operating System :: OS Independent',
]


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname), 'r') as file:
        return file.read()


requires = [
    'requests>=2.18.0',
    'requests_oauthlib>=1.2.0',
    'python-dateutil>=2.7',
    'tzlocal>=5.0',
    'beautifulsoup4>=4.0.0',
    'stringcase>=1.2.0',
    'tzdata>=2023.4'
]

setup(
    name='O365',
    version=VERSION,
    # packages=['O365', 'O365.utils'],
    packages=find_packages(),
    url='https://github.com/O365/python-o365',
    license='Apache License 2.0',
    author='Janscas, Roycem90, Narcolapser',
    author_email='janscas@users.noreply.github.com',
    maintainer='Janscas',
    maintainer_email='janscas@users.noreply.github.com',
    description='Microsoft Graph and Office 365 API made easy',
    long_description=read('README.md'),
    long_description_content_type="text/markdown",
    classifiers=CLASSIFIERS,
    python_requires=">=3.9",
    install_requires=requires,
    setup_requires=["wheel"],
)
