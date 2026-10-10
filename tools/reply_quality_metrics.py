"""Diagnóstico de calidad de la caché de replies; SOLO LECTURA.

No es el embudo histórico de #117: answers.json caduca y no enlaza
publicaciones ni réplicas. No infiere ACK ni recepción de terceros.
"""
from __future__ import annotations

import datetime
import json
from collections import Counter


def summarize(pending, answers, *, fresh, prefix, supported, answers_missing=False,
              pending_missing=False):
    """Agrega estados ya observados; nunca devuelve texto, handles o IDs.

    `fresh` y `prefix` vienen de reply_queue y reply_writer para no crear
    políticas paralelas de caducidad ni de normalización.
    """
    nets = sorted(set(supported))
    totals = {net: Counter() for net in nets}
    starts = {net: set() for net in nets}
    outside = Counter()
    for key, entry in pending.items():
        net = entry.get("network", "")
        counts = totals.get(net) if isinstance(net, str) else None
        if counts is None:
            outside["pendientes_sin_red_soportada"] += 1
        elif fresh(entry):
            counts["pendientes"] += 1
            if key in answers:
                counts["solapan_respuesta"] += 1
        else:
            counts["pendientes_caducados"] += 1

    for entry in answers.values():
        net = entry.get("network", "")
        counts = totals.get(net) if isinstance(net, str) else None
        if counts is None:
            outside["respuestas_sin_red_soportada"] += 1
            continue
        if not fresh(entry):
            counts["respuestas_caducadas"] += 1
            continue
        state = entry.get("state")
        if state == "written" and isinstance(entry.get("reply"), str) and entry["reply"].strip():
            counts["escritas"] += 1
            if entry.get("source_hash"):
                counts["con_huella_contextual"] += 1
            start = prefix(entry["reply"])
            if start:
                starts[net].add(start)
        elif state == "null" and entry.get("reply") is None:
            counts["abstenciones_explicitas"] += 1
        elif state == "rejected" and entry.get("reply") is None:
            counts["rechazos_formales"] += 1
        else:
            # El legacy sin state NO equivale a rechazo ni abstención.
            counts["estados_legacy_indeterminados"] += 1

    # Una respuesta v1 sin red conocida NO demuestra que las otras redes
    # tengan cero interacciones: tasas desconocidas hasta poder atribuirla.
    incomplete_attribution = sum(outside.values()) > 0
    incomplete_data = bool(answers_missing or pending_missing or incomplete_attribution)
    rows = {}
    fields = ("pendientes", "solapan_respuesta", "pendientes_caducados",
              "respuestas_caducadas", "escritas", "con_huella_contextual",
              "abstenciones_explicitas", "rechazos_formales",
              "estados_legacy_indeterminados")
    for net, counts in totals.items():
        complete = counts["escritas"] + counts["abstenciones_explicitas"] + counts["rechazos_formales"]
        written = counts["escritas"]
        rows[net] = {field: counts[field] for field in fields}
        rows[net].update({
            "resueltas_observadas": complete,
            "tasa_escritura_resueltas": round(written / complete, 4)
            if complete and not (answers_missing or incomplete_attribution) else None,
            "arranques_distintos": len(starts[net]),
            "tasa_variedad_arranques": round(len(starts[net]) / written, 4)
            if written >= 10 and not (answers_missing or incomplete_attribution) else None,
            "atribuible_completo": not incomplete_attribution,
            "publicadas_atribuidas": None,
            "replicas_atribuidas": None,
        })
    return {
        "fuente": "snapshot_cola_no_historico",
        "pendientes_no_disponibles": bool(pending_missing),
        "respuestas_no_disponibles": bool(answers_missing),
        "datos_parciales": incomplete_data,
        "atribucion_incompleta": incomplete_attribution,
        "otros": dict(outside),
        "redes": rows,
        "limitaciones": [
            "No es cohorte diaria ni embudo: las respuestas caducan y se purgan.",
            "No hay enlace fiable respuesta-publicacion-replica; null no significa cero.",
            "La variedad mide los dos primeros vocablos, no calidad semantica.",
            "Datos antiguos sin network impiden atribuirlos a una red.",
            "Instagram carece de adaptador en reply_writer.MAX_CHARS.",
        ],
    }


def _read_only_json(path, kind):
    """Lee snapshots v1/v3 sin _load: una lectura NUNCA sanea estado vivo."""
    if kind not in ("pending", "answers"):
        raise ValueError("tipo_snapshot_no_admitido")
    # json.load estándar acepta claves duplicadas o NaN; ambas situaciones
    # ocultarían filas o alterarían las métricas. Rechazar sin reparar archivos.
    def strict_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("clave_json_duplicada")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("numero_json_no_finito")

    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream, object_pairs_hook=strict_pairs,
                             parse_constant=reject_constant)
    except FileNotFoundError:
        return {}, True
    if not isinstance(data, dict):
        raise ValueError("snapshot_no_objeto")
    for key, entry in data.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise ValueError("entrada_invalida")
        stamp = entry.get("ts")
        if not isinstance(stamp, str):
            raise ValueError("fecha_invalida")
        try:
            dt = datetime.datetime.fromisoformat(stamp)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("fecha_invalida") from exc
        if dt.tzinfo is not None:
            raise ValueError("fecha_con_zona")
        if kind == "pending":
            if not (isinstance(entry.get("network"), str) and entry["network"].strip()
                    and isinstance(entry.get("text"), str) and entry["text"].strip()):
                raise ValueError("pendiente_invalido")
            if "incomplete_attempts" in entry:
                n = entry["incomplete_attempts"]
                if type(n) is not int or n < 0 or n > 4:
                    raise ValueError("reintentos_invalidos")
            if "retry_after" in entry:
                later = entry["retry_after"]
                if not isinstance(later, str):
                    raise ValueError("reintento_fecha_invalida")
                try:
                    parsed = datetime.datetime.fromisoformat(later)
                except (ValueError, OverflowError) as exc:
                    raise ValueError("reintento_fecha_invalida") from exc
                if parsed.tzinfo is not None:
                    raise ValueError("reintento_fecha_invalida")
        elif kind == "answers":
            if "network" in entry and not isinstance(entry["network"], str):
                raise ValueError("red_invalida")
            reply = entry.get("reply")
            state = entry.get("state")
            if "reply" not in entry or not (reply is None or isinstance(reply, str)):
                raise ValueError("respuesta_invalida")
            if "state" in entry and state not in ("written", "null", "rejected"):
                raise ValueError("estado_invalido")
            if state == "written" and (not isinstance(reply, str) or not reply.strip()):
                raise ValueError("respuesta_vacia")
            if state in ("null", "rejected") and reply is not None:
                raise ValueError("estado_con_texto")
            if "source_hash" in entry:
                h = entry["source_hash"]
                if not (isinstance(h, str) and len(h) == 64
                        and all(c in "0123456789abcdef" for c in h)):
                    raise ValueError("huella_contextual_invalida")
    return data, False


def snapshot(now=None):
    """Dos lecturas JSON no atómicas; compatible con cola antigua y vigente."""
    import reply_queue as rq
    import reply_writer as rw
    # Un único reloj para dos ficheros; evita mezclar instantes dentro de
    # una misma muestra. Se conserva TTL declarado por la cola operativa.
    now = datetime.datetime.now() if now is None else now
    if not isinstance(now, datetime.datetime) or now.tzinfo is not None:
        raise ValueError("reloj_invalido")
    ttl = rq.TTL_HOURS
    if type(ttl) not in (int, float) or not 0 < ttl <= 24 * 365:
        raise ValueError("ttl_invalido")
    pending, missing_p = _read_only_json(rq.PENDING, "pending")
    answers, missing_a = _read_only_json(rq.ANSWERS, "answers")

    def fresh(entry):
        try:
            stamp = datetime.datetime.fromisoformat(entry["ts"])
            if stamp.tzinfo is not None:
                return False
            age = (now - stamp).total_seconds()
            return -300 <= age < ttl * 3600
        except (TypeError, KeyError, ValueError, OverflowError):
            return False

    return summarize(pending, answers, fresh=fresh, prefix=rw._start,
                     supported=rw.MAX_CHARS, answers_missing=missing_a,
                     pending_missing=missing_p)


def main():
    import sys
    try:
        print(json.dumps(snapshot(), ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as exc:
        # No publicar textos, rutas privadas o cuerpos de errores de I/O.
        print(f"[reply_quality_metrics] lectura no verificable: {type(exc).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
