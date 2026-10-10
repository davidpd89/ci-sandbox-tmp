"""Run upstream Gitleaks on the first-parent patch of a synthetic PR merge.

GitHub's pull_request checkout is HEAD (synthetic merge), HEAD^1 (base),
HEAD^2 (proposed tip). Never scan history outside HEAD^1..HEAD.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from install_gitleaks_ci import executable_path

# Git log's first-parent merge diff is crucial: ordinary git log -p skips merges.
# --no-renames makes new destinations of renames visible as added file content.
# --text defeats PR-controlled .gitattributes (e.g. '*.py -diff').
LOG_OPTS = "--text --first-parent --diff-merges=first-parent --no-renames --diff-filter=AMT --no-ext-diff --no-textconv --unified=0 HEAD^1..HEAD"


def assert_pr_merge(repo: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--parents", "-n", "1", "HEAD"],
        capture_output=True, check=False, text=True, encoding="utf-8", errors="replace",
    )
    # No fallback to all-history scans or to a push commit: fail closed.
    if result.returncode != 0 or len(result.stdout.strip().split()) != 3:
        raise ValueError("Se requiere el checkout del merge sintético de una PR (dos padres)")


def scan(repo: Path, *, executable: Path, config: Path | None = None) -> int:
    assert_pr_merge(repo)
    # Gitleaks auto-loads both files from the scanned source. A PR must not
    # replace detection rules or silence findings through its own ignore list.
    if config is None:
        for name in (".gitleaks.toml", ".gitleaksignore"):
            candidate = repo / name
            if candidate.exists() or candidate.is_symlink():
                raise ValueError("Configuración/ignorados de Gitleaks desde el repositorio no permitidos en CI")
    if not executable.is_file():
        raise FileNotFoundError("No está instalado el Gitleaks fijado y verificado")
    command = [str(executable), "git", "--no-banner", "--redact=100", "--log-level=error",
               "--ignore-gitleaks-allow", "--log-opts=" + LOG_OPTS]
    if config is not None:  # Solo para test de integración con regla 100 % sintética.
        command += ["--config", str(config.resolve())]
    command.append(str(repo))
    # Gitleaks otherwise accepts arbitrary rules from these env variables.
    clean_env = os.environ.copy()
    clean_env.pop("GITLEAKS_CONFIG", None)
    clean_env.pop("GITLEAKS_CONFIG_TOML", None)
    result = subprocess.run(command, cwd=repo, env=clean_env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, check=False)
    if result.returncode == 0:
        print("SECRET CONTENT OK: diff del merge de PR sin hallazgos.")
    elif result.returncode == 1:
        print("SECRET CONTENT FAILED: hallazgo o error interno de Gitleaks; revisar localmente con salida redactada.", file=sys.stderr)
    else:
        print("SECRET CONTENT ERROR: escaneo no completado; no se considera aprobado.", file=sys.stderr)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detecta secretos añadidos en el diff de una PR")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        return scan(args.repo.resolve(), executable=executable_path())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"SECRET CONTENT ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
