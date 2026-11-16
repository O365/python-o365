import shutil
import subprocess
from pathlib import Path


def run(*args: str) -> None:
    subprocess.run(args, check=True)


# 1. Incrementar versión: 2.1.10 -> 2.1.11
run("uv", "version", "--bump", "patch")

# 2. Eliminar builds anteriores
dist = Path("dist")
if dist.exists():
    shutil.rmtree(dist)

# 3. Generar los nuevos paquetes: wheel + sdist
run("uv", "build")

# 4. Publicarlos en PyPI
run("uv", "publish")
