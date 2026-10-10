"""
Módulo común de utilidades temporales y desambiguación DST (Daylight Saving Time).
Centraliza la conversión a instantes UTC aware y la clasificación/resolución
de horas locales en transiciones de cambio de hora.
"""
import datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def classify_local_datetime(dt_naive, tz_name="Europe/Madrid"):
    """Clasifica una fecha/hora local naive en su zona horaria:
    - 'missing': dt_naive es None.
    - 'unambiguous': hora normal sin salto ni solapamiento.
    - 'non_existent': salto de primavera (spring-forward gap), hora imposible.
    - 'ambiguous': solapamiento de otoño (fall-back overlap), dos instantes UTC.
    """
    if dt_naive is None:
        return "missing"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return "invalid_timezone"

    dt0 = dt_naive.replace(tzinfo=tz, fold=0)
    dt1 = dt_naive.replace(tzinfo=tz, fold=1)

    utc0 = dt0.astimezone(datetime.timezone.utc)
    back0 = utc0.astimezone(tz)
    if (back0.hour, back0.minute, back0.second) != (dt_naive.hour, dt_naive.minute, dt_naive.second):
        return "non_existent"

    if dt0.utcoffset() != dt1.utcoffset():
        return "ambiguous"

    return "unambiguous"


def to_utc_instant(dt_or_now, tz_name="Europe/Madrid"):
    """Normaliza un datetime (naive o aware) a un datetime aware en UTC."""
    if dt_or_now is None:
        return None
    if not isinstance(dt_or_now, datetime.datetime):
        return None
    if dt_or_now.tzinfo is None:
        try:
            tz = ZoneInfo(tz_name)
            return dt_or_now.replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            return dt_or_now.replace(tzinfo=datetime.timezone.utc)
    return dt_or_now.astimezone(datetime.timezone.utc)


def resolve_dst_datetime(dt_naive_or_aware, meta=None, tz_name="Europe/Madrid"):
    """Resuelve el instante UTC exacto para una fecha/hora local (o ya aware), aplicando
    desambiguación explícita (fold, offset o instante UTC) si la hora es ambigua.
    Devuelve (classification, dt_utc, error_msg).
    """
    if dt_naive_or_aware is None:
        return ("missing", None, None)

    # Idempotencia si la entrada ya es aware
    if isinstance(dt_naive_or_aware, datetime.datetime) and dt_naive_or_aware.tzinfo is not None:
        return ("unambiguous", dt_naive_or_aware.astimezone(datetime.timezone.utc), None)

    status = classify_local_datetime(dt_naive_or_aware, tz_name=tz_name)
    if status == "invalid_timezone":
        return ("invalid_timezone", None, f"zona horaria desconocida o no encontrada: {tz_name}")
    if status == "non_existent":
        return ("non_existent", None, "fecha/hora imposible (salto DST / spring-forward gap)")

    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return ("invalid_timezone", None, f"zona horaria desconocida o no encontrada: {tz_name}")

    if status == "unambiguous":
        dt_tz = dt_naive_or_aware.replace(tzinfo=tz)
        return ("unambiguous", dt_tz.astimezone(datetime.timezone.utc), None)

    meta = meta or {}
    fold_str = meta.get("fold")
    offset_str = meta.get("offset") or meta.get("offset utc") or meta.get("utc offset")
    utc_str = meta.get("utc") or meta.get("instante utc") or meta.get("utc instant")

    parsed_utc = None
    if utc_str:
        try:
            raw_iso = str(utc_str).strip()
            # Validación estricta de string ISO UTC sin fragmentos arbitrarios
            iso_clean = raw_iso.rstrip("Z").rstrip(".")
            if "T" not in iso_clean and " " in iso_clean:
                iso_clean = iso_clean.replace(" ", "T")
            dt_utc = datetime.datetime.fromisoformat(iso_clean)
            if dt_utc.tzinfo is None:
                if not raw_iso.endswith("Z") and "+00:00" not in raw_iso and "-00:00" not in raw_iso:
                    # Exigir indicación explícita de Z o offset para la clave UTC si se proporciona
                    pass
                parsed_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
            else:
                parsed_utc = dt_utc.astimezone(datetime.timezone.utc)
        except (ValueError, TypeError):
            parsed_utc = None

    parsed_fold = None
    if fold_str in ("0", "1"):
        parsed_fold = int(fold_str)

    parsed_offset_utc = None
    if offset_str:
        # Validación anclada de offset (+HH:MM o -HH:MM)
        m = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})?", str(offset_str).strip())
        if m:
            sign = -1 if m.group(1) == "-" else 1
            hrs = int(m.group(2))
            mins = int(m.group(3) or 0)
            if 0 <= hrs <= 14 and 0 <= mins < 60:
                target_seconds = sign * (hrs * 3600 + mins * 60)
                dt0 = dt_naive_or_aware.replace(tzinfo=tz, fold=0)
                dt1 = dt_naive_or_aware.replace(tzinfo=tz, fold=1)
                match0 = (int(dt0.utcoffset().total_seconds()) == target_seconds)
                match1 = (int(dt1.utcoffset().total_seconds()) == target_seconds)
                if match0 and not match1:
                    parsed_offset_utc = dt0.astimezone(datetime.timezone.utc)
                elif match1 and not match0:
                    parsed_offset_utc = dt1.astimezone(datetime.timezone.utc)
                elif match0 and match1:
                    parsed_offset_utc = dt0.astimezone(datetime.timezone.utc)

    # Detección de conflicto entre metadatos proporcionados
    candidates = []
    if parsed_utc:
        candidates.append(("utc", parsed_utc))
    if parsed_fold is not None:
        dt_tz = dt_naive_or_aware.replace(tzinfo=tz, fold=parsed_fold)
        candidates.append(("fold", dt_tz.astimezone(datetime.timezone.utc)))
    if parsed_offset_utc:
        candidates.append(("offset", parsed_offset_utc))

    if candidates:
        first_source, first_val = candidates[0]
        for src, val in candidates[1:]:
            if val != first_val:
                return ("ambiguous", None, f"metadatos de desambiguación contradictorios ({first_source} vs {src})")
        return ("ambiguous", first_val, None)

    return ("ambiguous", None, "fecha/hora ambigua en cambio de hora (fall-back overlap); se requiere offset o fold explícito")
