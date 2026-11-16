import shutil
import subprocess
from pathlib import Path

import click


def run(*args: str) -> None:
    """Run a command and stop if it fails."""
    subprocess.run(args, check=True)


@click.command()
def main() -> None:
    """Build and publish the Python package."""

    # 1. Version bump
    bump = click.prompt(
        "Do you want to bump the version?",
        type=click.Choice(
            ["No", "Major", "Minor", "Patch"],
            case_sensitive=False,
        ),
        default="Patch",
        show_choices=True,
    )

    if bump.lower() != "no":
        run("uv", "version", "--bump", bump.lower())

    # 2. Build
    if click.confirm("Do you want to build the package?", default=True):
        dist = Path("dist")

        if dist.exists():
            click.echo("Removing previous builds...")
            shutil.rmtree(dist)

        click.echo("Building package...")
        run("uv", "build", "--no-sources")

    # 3. Publish
    if click.confirm("Do you want to publish the package?", default=False):
        click.echo("Publishing package...")
        run("uv", "publish")

    click.echo("Done.")


if __name__ == "__main__":
    main()
