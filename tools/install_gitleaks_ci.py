"""Install the pinned, MIT-licensed Gitleaks CLI for read-only CI scanning.

Only verified release archives are accepted; no GitHub Action token is required.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import os
from pathlib import Path
import platform
import tarfile
import tempfile
import urllib.request
import zipfile

VERSION = "8.30.1"
MAX_ARCHIVE_SIZE = 32 * 1024 * 1024
# Digests supplied by GitHub release asset metadata for v8.30.1 (2026-03-21).
ASSETS = {
    "Linux": ("linux_x64.tar.gz", "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"),
    "Windows": ("windows_x64.zip", "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"),
}


def executable_path(*, system: str | None = None, temp_dir: Path | None = None) -> Path:
    system = system or platform.system()
    if system not in ASSETS or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("Solo se admiten runners Linux/Windows x64")
    base = Path(temp_dir or os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
    return base / f"ci-gitleaks-{VERSION}" / ("gitleaks.exe" if system == "Windows" else "gitleaks")


def verified_executable(data: bytes, *, system: str) -> bytes:
    suffix, expected_sha = ASSETS[system]
    if len(data) > MAX_ARCHIVE_SIZE or not hmac.compare_digest(hashlib.sha256(data).hexdigest(), expected_sha):
        raise ValueError("Archivo Gitleaks demasiado grande o digest SHA-256 incorrecto")
    binary_name = "gitleaks.exe" if system == "Windows" else "gitleaks"
    with io.BytesIO(data) as stream:
        if suffix.endswith(".zip"):
            with zipfile.ZipFile(stream) as archive:
                if binary_name not in archive.namelist():
                    raise ValueError("No aparece el ejecutable esperado")
                binary = archive.read(binary_name)
        else:
            with tarfile.open(fileobj=stream, mode="r:gz") as archive:
                member = archive.getmember(binary_name)
                if not member.isfile():
                    raise ValueError("La entrada esperada no es un fichero regular")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError("No se puede extraer el ejecutable")
                binary = extracted.read()
    if not binary or len(binary) > MAX_ARCHIVE_SIZE:
        raise ValueError("Ejecutable vacío o demasiado grande")
    return binary


def install() -> Path:
    system = platform.system()
    target = executable_path(system=system)
    suffix, _ = ASSETS[system]
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/gitleaks_{VERSION}_{suffix}"
    request = urllib.request.Request(url, headers={"User-Agent": "ci-mirror-gitleaks-installer"})
    with urllib.request.urlopen(request, timeout=45) as response:
        archive = response.read(MAX_ARCHIVE_SIZE + 1)
    binary = verified_executable(archive, system=system)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    try:
        partial.write_bytes(binary)
        partial.chmod(0o700)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def main() -> int:
    try:
        path = install()
    except (OSError, ValueError, RuntimeError, tarfile.TarError, zipfile.BadZipFile, KeyError) as exc:
        print(f"Error al instalar Gitleaks fijado: {type(exc).__name__}")
        return 2
    print(f"Gitleaks {VERSION} verificado: {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
