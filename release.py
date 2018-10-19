"""
Release script
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click


DIST_PATH = 'dist'


@click.group()
def cli():
    pass


@cli.command()
def build():
    dist_path = Path(DIST_PATH)
    if dist_path.exists() and list(dist_path.glob('*')):
        if click.confirm('{} is not empty - delete contents?'.format(dist_path)):
            shutil.rmtree(dist_path)
            dist_path.mkdir()
        else:
            click.echo('Aborting')
            sys.exit(1)

    subprocess.check_call(['python', 'setup.py', 'bdist_wheel'])
    subprocess.check_call(['python', 'setup.py', 'sdist',
                           '--formats=gztar'])


@cli.command()
@click.option('--release/--no-release', default=False)
def upload(release):
    if release:
        repository = 'pypi'
    else:
        repository = 'pypitest'

    env = os.environ.copy()

    args = ['twine', 'upload', '-r', repository, 'dist/*']

    p = subprocess.Popen(args, env=env)
    p.wait()


@cli.command()
def check():
    """ Checks the long description """
    subprocess.check_call(['twine', 'check', 'dist/*'])


if __name__ == "__main__":
    cli()
