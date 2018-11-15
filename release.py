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
DIST_PATH_DELETE = 'dist_delete'
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    pass


@cli.command()
@click.option('--force/--no-force', default=False)
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
    subprocess.check_call(['python', 'setup.py', 'sdist',
                           '--formats=gztar'])


@cli.command()
@click.option('--release/--no-release', default=False)
@click.option('--rebuild/--no-rebuild', default=True)
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
@click.option('--annotate/--no-annotate',default=False)
@click.option('--coverage/--no-coverage',default=False)
@click.option('-v/-nv',default=False)
@click.option('-vv/-nvv',default=False)
def test(annotate,coverage,v,vv):
    """ runs tests and optionally creates annotated files of coverage. """
    args = ["python3","-m","pytest","tests/"]
    if coverage:
        args.append("--cov=O365")
        if annotate:
            args.append("--cov-report")
            args.append("annotate")
        if v:#Verbose
            args.append("-v")
        if vv and not v:#Very verbose
            args.append("-vv")
    
    env = os.environ.copy()
    
    p = subprocess.Popen(args,env=env)
    
    p.wait()


if __name__ == "__main__":
    cli()
