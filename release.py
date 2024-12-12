"""
Release script
"""

import os
import shutil
import subprocess
import sys
import requests
from pathlib import Path
from math import floor

import click

PYPI_PACKAGE_NAME = 'O365'
PYPI_URL = 'https://pypi.org/pypi/{package}/json'
DIST_PATH = 'dist'
DIST_PATH_DELETE = 'dist_delete'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    pass


@cli.command()
@click.option('--force/--no-force', default=False, help='Will force a new build removing the previous ones')
def build(force):
    """ Builds the distribution files: wheels and source. """
    dist_path = Path(DIST_PATH)
    if dist_path.exists() and list(dist_path.glob('*')):
        if force or click.confirm('{} is not empty - delete contents?'.format(dist_path)):
            dist_path.rename(DIST_PATH_DELETE)
            shutil.rmtree(Path(DIST_PATH_DELETE))
            dist_path.mkdir()
        else:
            click.echo('Aborting')
            sys.exit(1)

    subprocess.check_call(['python', 'setup.py', 'bdist_wheel'])
    subprocess.check_call(['python', 'setup.py', 'sdist', '--formats=gztar'])


@cli.command()
@click.option('--release/--no-release', default=False, help='--release to upload to pypi otherwise upload to test.pypi')
@click.option('--rebuild/--no-rebuild', default=True, help='Will force a rebuild of the build files (src and wheels)')
@click.pass_context
def upload(ctx, release, rebuild):
    """ Uploads distribuition files to pypi or pypitest. """
    dist_path = Path(DIST_PATH)
    if rebuild is False:
        if not dist_path.exists() or not list(dist_path.glob('*')):
            print("No distribution files found. Please run 'build' command first")
            return
    else:
        ctx.invoke(build, force=True)

    if release:
        args = ['twine', 'upload', 'dist/*']
    else:
        repository = 'https://test.pypi.org/legacy/'
        args = ['twine', 'upload', '--repository-url', repository, 'dist/*']

    env = os.environ.copy()

    p = subprocess.Popen(args, env=env)
    p.wait()


@cli.command()
def check():
    """ Checks the long description. """
    dist_path = Path(DIST_PATH)
    if not dist_path.exists() or not list(dist_path.glob('*')):
        print("No distribution files found. Please run 'build' command first")
        return

    subprocess.check_call(['twine', 'check', 'dist/*'])


@cli.command()
@click.option('--annotate/--no-annotate', default=False, help='Annotate coverage on files')
@click.option('--coverage/--no-coverage', default=False, help='Run coverage')
@click.option('-v/-nv', default=False, help='Verbose')
@click.option('-vv/-nvv', default=False, help='Very verbose')
def test(annotate, coverage, v, vv):
    """ Runs tests and optionally creates annotated files of coverage. """
    args = ['python3', '-m', 'pytest', 'tests/']
    if coverage:
        args.append('--cov=O365')
        if annotate:
            args.append('--cov-report')
            args.append('annotate')
        if v:  # Verbose
            args.append('-v')
        if vv and not v:  # Very verbose
            args.append('-vv')

    env = os.environ.copy()

    p = subprocess.Popen(args, env=env)
    p.wait()


def _get_releases():
    """ Retrieves all releases on pypi """
    releases = None

    response = requests.get(PYPI_URL.format(package=PYPI_PACKAGE_NAME))
    if response:
        data = response.json()

        releases = []
        releases_dict = data.get('releases', {})

        if releases_dict:
            for version, release in releases_dict.items():
                release_formats = []
                published_on_date = None
                for fmt in release:
                    release_formats.append(fmt.get('packagetype'))
                    published_on_date = fmt.get('upload_time')

                release_formats = ' | '.join(release_formats)
                releases.append((version, published_on_date, release_formats))

    releases.sort(key=lambda x: x[1])

    return releases


# noinspection PyShadowingBuiltins
@cli.command(name='list')
def list_releases():
    """ Lists all releases published on pypi. """

    releases = _get_releases()

    if releases is None:
        print('Package "{}" not found on Pypi.org'.format(PYPI_PACKAGE_NAME))
    elif not releases:
        print('No releases found for {}'.format(PYPI_PACKAGE_NAME))
    else:
        for version, published_on_date, release_formats in releases:
            print('{:<10}{:>15}{:>25}'.format(version, published_on_date, release_formats))


# Mostly just for fun. I was curious to see what the shape of contributions was.
@cli.command(name='contributors')
def contribution_breakdown():
    """ Displays a table of the contributors and to what extent we have them to thank."""
    args = ['git', 'blame']
    counts = {}
    line_format = '{0:30}\t{1:>10}\t{2:>10}%'
    files = subprocess.check_output(['git', 'ls-files']).decode("utf-8").split('\n')

    for f in files[:-1]:
        if 'docs/latest' in f or '_themes' in f:
            continue  # skip generated stuff
        lines = subprocess.check_output(args + [f]).decode('utf-8')
        blames = [get_line_blame(line) for line in lines.split('\n')]
        for blame in blames:
            counts[blame] = counts.get(blame, 0) + 1

    total = sum([counts[count] for count in counts])
    contribs = [(user, counts[user]) for user in counts]
    contribs.sort(key=lambda x: x[1], reverse=True)

    print(line_format.format('User', 'Lines', 'Line '))

    for user in contribs:
        percent = floor(100.0 * user[1] / total)
        if percent == 0: percent = '>1'
        print(line_format.format(user[0], user[1], percent))

    print(line_format.format('Total', total, 100))


def get_line_blame(line):
    line = line
    start = line.find('(') + 1
    end = line.find(' 2', start)  # should be good for the next ~900 years
    name = line[start:end]
    return name.rstrip(' ').title() if name != '' else 'Unknown'


if __name__ == "__main__":
    cli()
