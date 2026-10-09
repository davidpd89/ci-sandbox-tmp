"""Valida las publicaciones fechadas preparadas por red social."""
import csv
import re
import sys
from datetime import date
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
NETWORKS = {
    "X": (280, ("Texto final propuesto",)),
    "Threads": (500, ("Texto final propuesto",)),
    "Instagram": (2200, ("Caption final",)),
    "Facebook": (8000, ("Texto final",)),
    "TikTok": (2200, ("Caption final",)),
    "Bluesky": (300, ("Texto final",)),
    "Mastodon": (500, ("Texto final",)),
    "LinkedIn": (3000, ("Texto final",)),
}
MEDIA_RE = re.compile(r"`([^`]+\.(?:png|jpe?g|webp|mp4))`", re.I)
HASHTAG_RE = re.compile(r"(?<!\w)#[\wÁÉÍÓÚÜÑáéíóúüñ]+", re.UNICODE)


def section(markdown, headings):
    choices = "|".join(re.escape(h) for h in headings)
    match = re.search(rf"^## (?:{choices})\s*$\n(.*?)(?=^## |\Z)", markdown, re.M | re.S)
    if not match:
        return None
    text = match.group(1).strip()
    text = re.sub(r"^```[^\n]*\n|\n```$", "", text).strip()
    return text


def platform_length(network, text):
    if network == "X":
        # X transforma cualquier URL en un enlace t.co de 23 caracteres.
        return len(re.sub(r"https?://\S+", "x" * 23, text))
    return len(text)


def validate_csv(folder, errors):
    path = folder / "REGISTRO_CONTENIDO_USADO.csv"
    if not path.exists():
        errors.append(f"Falta {path.relative_to(ROOT)}")
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 2:
        errors.append(f"{path.relative_to(ROOT)}: se esperaban al menos 2 filas, hay {len(rows)}")
    for row in rows:
        if not row.get("id") or not row.get("estado"):
            errors.append(f"{path.relative_to(ROOT)}: fila sin id/estado")


def main():
    errors = []
    checked_docs = 0
    checked_media = set()
    lengths = []

    rotation = ROOT / "publicaciones GPT/ROTACION_MULTIRRED_2026-09-28_10-04.csv"
    if rotation.exists():
        with rotation.open(encoding="utf-8-sig", newline="") as handle:
            rotation_rows = list(csv.DictReader(handle))
        if len(rotation_rows) != 27:
            errors.append(f"{rotation.relative_to(ROOT)}: se esperaban 27 filas, hay {len(rotation_rows)}")
        bases = [row["base_id"] for row in rotation_rows]
        if len(set(bases)) != len(bases):
            errors.append(f"{rotation.relative_to(ROOT)}: hay BASE repetidas en la rotación")
        ids = [row["id"] for row in rotation_rows]
        if len(set(ids)) != len(ids):
            errors.append(f"{rotation.relative_to(ROOT)}: hay ID repetidos")
        counts = {}
        for row in rotation_rows:
            counts[row["red"]] = counts.get(row["red"], 0) + 1
        wrong = {network: count for network, count in counts.items() if count != 3}
        if wrong or len(counts) != 9:
            errors.append(f"{rotation.relative_to(ROOT)}: reparto por red incorrecto: {counts}")
        for row in rotation_rows:
            if row.get("tipo_base") != "rotada":
                continue
            if row.get("red") == row.get("red_origen"):
                errors.append(
                    f"{rotation.relative_to(ROOT)}: {row['base_id']} vuelve a {row['red']} en vez de cambiar de red"
                )
            try:
                target = date.fromisoformat(row["fecha"])
                origin = date.fromisoformat(row["fecha_origen_prevista"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{rotation.relative_to(ROOT)}: fechas inválidas en {row.get('base_id')}")
                continue
            if (target - origin).days < 7:
                errors.append(
                    f"{rotation.relative_to(ROOT)}: {row['base_id']} rota con menos de 7 días de separación"
                )

        reddit_live = [
            row for row in rotation_rows
            if row.get("red") == "Reddit" and not row.get("estado", "").startswith("reserva")
        ]
        if len(reddit_live) > 1:
            errors.append(
                f"{rotation.relative_to(ROOT)}: Reddit tiene {len(reddit_live)} posts propios activos; máximo 1"
            )

    queue = ROOT / "publicaciones GPT/COLA_ROTACION_BASES.csv"
    master = ROOT / "publicaciones GPT/REGISTRO_MAESTRO_MULTIRRED.csv"
    master_bases = set()
    if master.exists():
        with master.open(encoding="utf-8-sig", newline="") as handle:
            master_bases = {row.get("base_id") for row in csv.DictReader(handle) if row.get("base_id")}
    else:
        errors.append(f"Falta {master.relative_to(ROOT)}")
    if not queue.exists():
        errors.append(f"Falta {queue.relative_to(ROOT)}")
    else:
        with queue.open(encoding="utf-8-sig", newline="") as handle:
            queue_rows = list(csv.DictReader(handle))
        queue_bases = [row.get("base_id") for row in queue_rows]
        if len(set(queue_bases)) != len(queue_rows):
            errors.append(
                f"{queue.relative_to(ROOT)}: hay BASE duplicadas"
            )
        missing_from_queue = master_bases - set(queue_bases)
        if missing_from_queue:
            errors.append(
                f"{queue.relative_to(ROOT)}: faltan BASE del maestro: {sorted(missing_from_queue)}"
            )

    next_rotation = ROOT / "publicaciones GPT/ROTACION_MULTIRRED_2026-10-05_10-11.csv"
    if not next_rotation.exists():
        errors.append(f"Falta {next_rotation.relative_to(ROOT)}")
    else:
        with next_rotation.open(encoding="utf-8-sig", newline="") as handle:
            next_rows = list(csv.DictReader(handle))
        if len(next_rows) != 27:
            errors.append(f"{next_rotation.relative_to(ROOT)}: se esperaban 27 filas, hay {len(next_rows)}")
        next_bases = [row.get("base_id") for row in next_rows]
        if len(set(next_bases)) != len(next_bases):
            errors.append(f"{next_rotation.relative_to(ROOT)}: hay BASE repetidas")
        next_counts = {}
        for row in next_rows:
            next_counts[row.get("red")] = next_counts.get(row.get("red"), 0) + 1
            if row.get("tipo_base") == "rotada":
                try:
                    target = date.fromisoformat(row["fecha"])
                    origin = date.fromisoformat(row["fecha_origen_prevista"])
                except (KeyError, TypeError, ValueError):
                    errors.append(f"{next_rotation.relative_to(ROOT)}: fechas inválidas en {row.get('base_id')}")
                    continue
                if (target - origin).days < 7:
                    errors.append(
                        f"{next_rotation.relative_to(ROOT)}: {row['base_id']} rota con menos de 7 días"
                    )
                if row.get("red") == row.get("red_origen"):
                    errors.append(f"{next_rotation.relative_to(ROOT)}: {row['base_id']} repite red")
        expected_counts = {network: 3 for network in (*[n for n in NETWORKS if n != "LinkedIn"], "Pinterest", "Reddit")}
        if next_counts != expected_counts:
            errors.append(f"{next_rotation.relative_to(ROOT)}: reparto incorrecto: {next_counts}")
        if any(row.get("red") == "Reddit" and row.get("estado") != "reserva_regla_semanal" for row in next_rows):
            errors.append(f"{next_rotation.relative_to(ROOT)}: la semana ya tiene RDGPT-P003; las nuevas de Reddit deben ser reservas")

    for network, (limit, headings) in NETWORKS.items():
        folder = ROOT / f"publicaciones {network} GPT"
        validate_csv(folder, errors)
        for doc in sorted(folder.glob("20*/publicacion.md")):
            checked_docs += 1
            markdown = doc.read_text(encoding="utf-8")
            body = section(markdown, headings)
            if body is None:
                errors.append(f"{doc.relative_to(ROOT)}: no se encontró el texto final")
            else:
                count = platform_length(network, body)
                lengths.append((network, doc.parent.name, count, limit))
                if count > limit:
                    errors.append(f"{doc.relative_to(ROOT)}: {count}>{limit} caracteres")
                hashtag_count = len(HASHTAG_RE.findall(body))
                hashtag_limits = {"X": (1, 2), "Instagram": (1, 5), "TikTok": (1, 5)}
                if network in hashtag_limits:
                    minimum, maximum = hashtag_limits[network]
                    if not minimum <= hashtag_count <= maximum:
                        errors.append(
                            f"{doc.relative_to(ROOT)}: {hashtag_count} hashtags; "
                            f"se esperaban {minimum}-{maximum}"
                        )
            if network in {"Instagram", "TikTok"}:
                if "- **Destino web:** https://" not in markdown:
                    errors.append(f"{doc.relative_to(ROOT)}: falta Destino web operativo")
            if network == "Instagram":
                if "- **Etiqueta del enlace de perfil:**" not in markdown:
                    errors.append(f"{doc.relative_to(ROOT)}: falta etiqueta del enlace de perfil")
            if network == "TikTok" and body and re.search(r"enlace (?:de la bio|del? perfil)", body, re.I):
                errors.append(f"{doc.relative_to(ROOT)}: promete un enlace de perfil variable")
            if network == "Threads" and not any(
                marker in markdown
                for marker in ("- **Tema nativo candidato:**", "- **Topic nativo:**")
            ):
                errors.append(f"{doc.relative_to(ROOT)}: falta tema nativo candidato")
            for name in MEDIA_RE.findall(markdown):
                path = doc.parent / name
                if not path.exists():
                    errors.append(f"{doc.relative_to(ROOT)}: falta {name}")
                else:
                    checked_media.add(path)

    for network in ("Pinterest", "Reddit"):
        folder = ROOT / f"publicaciones {network} GPT"
        validate_csv(folder, errors)
        for doc in sorted(folder.glob("20*/publicacion.md")):
            checked_docs += 1
            markdown = doc.read_text(encoding="utf-8")
            for name in MEDIA_RE.findall(markdown):
                path = doc.parent / name
                if not path.exists():
                    errors.append(f"{doc.relative_to(ROOT)}: falta {name}")
                else:
                    checked_media.add(path)

    for path in checked_media:
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        with Image.open(path) as image:
            width, height = image.size
        rel = str(path.relative_to(ROOT))
        if "publicaciones Pinterest GPT" in rel and width * 3 != height * 2:
            errors.append(f"{rel}: Pinterest exige 2:3, tiene {width}x{height}")
        if any(f"publicaciones {n} GPT" in rel for n in ("Instagram", "TikTok")) and width > height:
            errors.append(f"{rel}: medio horizontal inesperado ({width}x{height})")

    for network, publication_date, count, limit in lengths:
        print(f"OK texto {network:10s} {publication_date}: {count}/{limit}")
    print(f"Fichas: {checked_docs} | medios referenciados: {len(checked_media)}")
    if rotation.exists():
        print("Rotaciones: tanda 28/09 y tanda 05/10 comprobadas; cola maestra sincronizada.")
    if errors:
        print("\nERRORES:")
        for error in errors:
            print("-", error)
        return 1
    print("OK: validación completa sin errores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
