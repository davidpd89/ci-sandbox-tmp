"""R10 / F8: bloqueo de artefactos privados en cambios de Git, sin dependencias.

Ejemplo para el checkout de una PR que apunta al merge commit de GitHub:
    python tools/repo_hygiene.py --base HEAD^1

Usar solo sobre rutas A/M/T respecto a la base, NO sobre todos los ficheros
históricos ya presentes en el repositorio. El código no lee archivos privados.
No sustituye un escáner de secretos dentro de ficheros permitidos.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_FILES = frozenset({
    "metricas.csv", "registro_interacciones.csv", "inbound_interacciones.csv",
    "answers.json", "pending.json", "gpt_texts.json",
})
RUNTIME_DIRS = frozenset({
    "_cola_respuestas", "cache", "__pycache__", "browser_profile", "edge_profile",
    "chrome_profile", "playwright_profile", "user_data", "user-data",
    "user-data-dir", "browser_profiles", ".playwright",
})
SENSITIVE_FILES = frozenset({
    "credentials.json", "secrets.json", "secret.json", "cookies.txt",
    "id_rsa", "id_ed25519", "token.json", "tokens.json",
})
ENV_TEMPLATES = frozenset({".env.example", ".env.sample", ".env.template"})


def forbidden_path(path: str) -> bool:
    """No se basan las decisiones en Gitignore: un fichero ya stageado cuenta."""
    if not isinstance(path, str) or not path.strip():
        return True
    normalized = path.replace("\\", "/").lstrip("/")
    raw_parts = [p for p in normalized.split("/") if p != ""]
    # No permitir que espacios conviertan un nombre distinto en una plantilla autorizada.
    if any(p != p.strip() and p.strip().casefold() in ENV_TEMPLATES for p in raw_parts):
        return True
    parts = [p.strip().casefold() for p in raw_parts]
    if not parts or any(p in {"", ".", ".."} for p in parts):
        return True
    name = parts[-1]
    # Una ruta protegida usada como directorio sigue siendo protegida.
    # La llamada sobre un único componente carece de padres: no hay recursión.
    # Las plantillas .env solo se permiten como archivos independientes.
    if any(
        p in RUNTIME_DIRS or p in {"secrets", "credentials", ".ssh"}
        or p.startswith(".env") or forbidden_path(p)
        for p in parts[:-1]
    ):
        return True
    if name in RUNTIME_FILES or name.endswith("_interacciones.csv"):
        return True
    if name in SENSITIVE_FILES:
        return True
    if name.startswith(".env") and name not in ENV_TEMPLATES:
        return True
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".p8", ".sqlite", ".sqlite3")):
        return True
    if re.search(r"\.log(?:\.\d+)?$", name):
        return True
    # No bloquear por nombre los módulos Python como tools/token_resolver.py.
    # Para archivos permitidos, complementar con escaneo del contenido.
    if name.endswith((".json", ".yaml", ".yml", ".txt", ".ini", ".toml")) and re.search(
        r"(?:^|[_-])(?:secret|secrets|token|tokens|credentials)(?:[_-]|\.)", name
    ):
        return True
    return False


def violations_for_paths(paths) -> list[str]:
    """Conserva orden de Git, sin mostrar contenido privado."""
    return list(dict.fromkeys(p for p in paths if forbidden_path(p)))


def changed_paths(base: str, *, root: pathlib.Path = ROOT) -> list[str]:
    if not base or base.startswith("-"):
        raise ValueError("Se necesita un commit base comprobable")
    completed = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "-z",
         "--diff-filter=AMT", "--no-renames", base, "HEAD", "--"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise RuntimeError("No se pudo comparar la rama con la base de Git: " +
                           completed.stderr.decode("utf-8", "replace")[:300])
    try:
        return [p.decode("utf-8") for p in completed.stdout.split(b"\0") if p]
    except UnicodeDecodeError as exc:
        # git diff -z entrega nombres como bytes; no ocultar rutas con replacement.
        raise RuntimeError("Git devolvió una ruta sin codificación UTF-8 válida") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Detecta datos operativos incluidos en un diff Git")
    parser.add_argument("--base", required=True, help="Commit base, en PR: HEAD^1")
    args = parser.parse_args(argv)
    try:
        offenders = violations_for_paths(changed_paths(args.base))
    except (RuntimeError, ValueError) as exc:
        print(f"HIGIENE ERROR: {str(exc)!r}", file=sys.stderr)
        return 2
    if offenders:
        print("HIGIENE FALLIDA: no versionar artefactos de cuentas, logs, perfiles ni secretos:", file=sys.stderr)
        for path in offenders:
            print(f"  - {path!r}", file=sys.stderr)
        return 1
    print("HIGIENE OK: cambios A/M/T sin ficheros operativos prohibidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
