"""Cola de respuestas de ChatGPT para las redes por API y el movil (07/10/2026).

Problema: las rondas de Bluesky/Mastodon/TikTok pedian las respuestas a ChatGPT por el Edge y esperaban el turno del navegador (ocupado casi todo el dia por las rondas web): hasta 30 min de
espera por paso, y las rondas por API tardaban mas de una hora. Ahora esas rondas NO esperan: encolan los posts a los que querrian responder y usan las respuestas que un trabajador aparte
(`work`/`loop`) haya escrito antes, con UNA consulta a ChatGPT por tanda para todas las redes (mismo prompt, memoria y validaciones de `reply_writer`).

    python tools/reply_queue.py work [--max 40]            # una tanda: consulta a ChatGPT por todo lo pendiente
    python tools/reply_queue.py loop [--until 23:30]       # trabajador: una tanda cada ~15 s si hay pendientes
    python tools/reply_queue.py stats

Ficheros en 00_OPERATIVO/_cola_respuestas/: pending.json (clave -> post pendiente) y answers.json (clave -> respuesta o null, caduca a las 36 h).
La clave v3 incluye red, autor, texto completo y destino estable cuando existe.
La procedencia y el estado de la respuesta se revalidan antes de usarla.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import reply_writer as rw

ROOT = os.path.join(os.path.dirname(__file__), "..")
DIR = os.path.join(ROOT, "00_OPERATIVO", "_cola_respuestas")
PENDING = os.path.join(DIR, "pending.json")
ANSWERS = os.path.join(DIR, "answers.json")
LOCK = os.path.join(DIR, "worker.lock")
TTL_HOURS = 36
MAX_PENDING = 400
# Evitar bucles de gasto ante respuestas incompletas. Un cambio real de
# contexto reactiva la petición; un null explícito no consume reintentos.
INCOMPLETE_RETRY_MINUTES = (5, 15, 30)
MAX_INCOMPLETE_ATTEMPTS = 4


# Política R8 limitada a pending.json y answers.json. No es una base de
# datos transaccional: las escrituras concurrentes requieren otra PR.
RETRY_DELAYS = (0.05, 0.12)
RETENTION_DAYS = 14


class QueueStateCorrupted(RuntimeError):
    """El almacenamiento es inaccesible; no se debe generar/publicar texto."""


QueueStateUnavailable = QueueStateCorrupted  # Alias de compatibilidad R9; política R8 sigue siendo autoritativa.


def _retry_io(action):
    """Tres intentos solo ante bloqueo/compartición, no ante otros errores IO."""
    import random
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return action()
        except OSError as exc:
            transient = isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (32, 33)
            if not transient or attempt == len(RETRY_DELAYS):
                raise
            time.sleep(RETRY_DELAYS[attempt] + random.uniform(0, 0.03))


def _emit_event(code, path, reason, count=0, quarantined=None):
    """Evento mínimo; no contiene handles, publicaciones, ni rutas completas."""
    import uuid
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    directory = os.path.join(ROOT, "00_OPERATIVO", "cache", "errores_cola")
    try:
        os.makedirs(directory, exist_ok=True)
        event = {"code": code, "file": os.path.basename(path), "reason": reason,
                 "at": datetime.datetime.now().isoformat(timespec="seconds")}
        if count:
            event["count"] = count
        if quarantined:
            event["quarantined"] = os.path.basename(quarantined)
        with open(os.path.join(directory, f"{stamp}-{uuid.uuid4().hex[:8]}.json"),
                  "x", encoding="utf-8") as stream:
            json.dump(event, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        return True
    except OSError as exc:
        print(f"[reply_queue] ALERTA_NO_ESCRITA ({type(exc).__name__})", file=sys.stderr, flush=True)
        return False


def _backup_name(path):
    import uuid
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    return f"{path}.corrupto-{stamp}-{uuid.uuid4().hex[:8]}"


def _quarantine_corrupt(path, reason, expected=None):
    """Apartar la fuente ilegible sin destruir sus bytes; nunca ocultar fallo."""
    backup = _backup_name(path)
    try:
        if expected is not None:
            with _retry_io(lambda: open(path, "rb")) as stream:
                if stream.read() != expected:
                    raise QueueStateCorrupted("COLA_CAMBIO_CONCURRENTE: lectura distinta antes de cuarentena")
        _retry_io(lambda: os.rename(path, backup))
        # La retención cuenta desde el aislamiento, no desde el último cambio
        # al fichero original, que puede ser anterior a 14 días.
        try:
            os.utime(backup, None)
        except OSError:
            pass
    except QueueStateCorrupted:
        _emit_event("COLA_CUARENTENA_FALLIDA", path, "cambio_concurrente")
        raise
    except OSError as exc:
        _emit_event("COLA_CUARENTENA_FALLIDA", path, type(exc).__name__)
        raise QueueStateCorrupted(
            f"COLA_CUARENTENA_FALLIDA: {os.path.basename(path)} ({type(exc).__name__})"
        ) from exc
    _emit_event("COLA_CORRUPTA_RECUPERADA", path, reason, quarantined=backup)
    return {}


def _valid_entry(path, entry):
    if not isinstance(entry, dict):
        return False
    stamp = entry.get("ts")
    if not isinstance(stamp, str):
        return False
    try:
        parsed = datetime.datetime.fromisoformat(stamp)
    except (ValueError, OverflowError):
        return False
    if parsed.tzinfo is not None:
        return False  # formato previo: hora local sin offset
    if os.fspath(path) == os.fspath(PENDING):
        if not (isinstance(entry.get("network"), str)
                and entry["network"].strip().casefold() in rw.MAX_CHARS
                and isinstance(entry.get("text"), str) and entry["text"].strip()):
            return False
        if "incomplete_attempts" in entry:
            attempts = entry["incomplete_attempts"]
            if type(attempts) is not int or not 0 <= attempts <= MAX_INCOMPLETE_ATTEMPTS:
                return False
        if "retry_after" in entry:
            try:
                due = datetime.datetime.fromisoformat(entry["retry_after"])
            except (ValueError, TypeError, OverflowError):
                return False
            if due.tzinfo is not None:
                return False
        return True
    if os.fspath(path) == os.fspath(ANSWERS):
        if ("reply" not in entry
                or not (entry["reply"] is None or isinstance(entry["reply"], str))):
            return False
        if "state" in entry:
            state = entry["state"]
            if state not in ("written", "null", "rejected"):
                return False
            if state == "written" and not (isinstance(entry["reply"], str) and entry["reply"].strip()):
                return False
            if state != "written" and entry["reply"] is not None:
                return False
        if "source_hash" in entry:
            h = entry["source_hash"]
            if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
                return False
        return True
    return True


def _prune_recovery_files(path):
    """Purgar >14d, conservando la última copia y solo con fuente presente."""
    import pathlib
    if not os.path.isfile(path):
        return
    cutoff = time.time() - RETENTION_DAYS * 86400
    try:
        for pattern in (".corrupto-*", ".escritura-fallida-*"):
            copies = [p for p in pathlib.Path(os.path.dirname(path)).glob(
                os.path.basename(path) + pattern) if p.is_file() and not p.is_symlink()]
            copies.sort(key=lambda p: p.stat().st_mtime)
            for item in copies[:-1]:  # la última copia nunca se purga sola
                if item.stat().st_mtime < cutoff:
                    item.unlink()
        alerts = pathlib.Path(ROOT, "00_OPERATIVO", "cache", "errores_cola")
        if alerts.is_dir():
            for event in alerts.glob("*.json"):
                if event.is_file() and not event.is_symlink() and event.stat().st_mtime < cutoff:
                    event.unlink()
    except OSError:
        # Limpieza opcional: jamás invalidar la lectura de un estado válido.
        pass



# Protocolo compartido con #101, sin duplicar implementaciones ni inodos.
# Este helper protege pending/answers, distinto del singleton #126.
import contextlib
import functools
from reply_state_lock import state_guard


@contextlib.contextmanager
def _storage_lock():
    """Adaptador a la política R8: fail-closed con evento ante lock inaccesible."""
    guard = state_guard(PENDING, timeout=3.0)
    try:
        guard.__enter__()
    except (OSError, TimeoutError) as exc:
        _emit_event("COLA_BLOQUEO_FALLIDO", PENDING, type(exc).__name__)
        raise QueueStateCorrupted(
            f"COLA_BLOQUEO_FALLIDO ({type(exc).__name__})"
        ) from exc
    try:
        yield
    finally:
        try:
            guard.__exit__(None, None, None)
        except OSError as exc:
            _emit_event("COLA_BLOQUEO_FALLIDO", PENDING, type(exc).__name__)
            raise QueueStateCorrupted(
                f"COLA_BLOQUEO_FALLIDO al liberar ({type(exc).__name__})"
            ) from exc


def _locked_state(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        with _storage_lock():
            return func(*args, **kwargs)
    return wrapped


@_locked_state
def _load(path):
    try:
        with _retry_io(lambda: open(path, "rb")) as stream:
            raw = stream.read()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        _emit_event("COLA_INACCESIBLE", path, type(exc).__name__)
        raise QueueStateCorrupted(
            f"COLA_INACCESIBLE: {os.path.basename(path)} ({type(exc).__name__})"
        ) from exc
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        return _quarantine_corrupt(path, type(exc).__name__, raw)
    if not isinstance(data, dict):
        return _quarantine_corrupt(path, "raiz_no_objeto", raw)
    if os.fspath(path) not in (os.fspath(PENDING), os.fspath(ANSWERS)):
        return data
    valid = {k: v for k, v in data.items() if isinstance(k, str) and _valid_entry(path, v)}
    invalid = len(data) - len(valid)
    if invalid:
        # Copia exacta (incluidas entradas corruptas) ANTES de sanear. Si la
        # copia o el reemplazo fallan, se conserva el origen sin cambios.
        backup = _backup_name(path)
        try:
            with open(backup, "xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            _emit_event("COLA_CUARENTENA_FALLIDA", path, type(exc).__name__)
            raise QueueStateCorrupted("COLA_CUARENTENA_FALLIDA: copia imposible") from exc
        _save(path, valid)
        _emit_event("COLA_CORRUPTA_RECUPERADA", path, "entradas_invalidas",
                    count=invalid, quarantined=backup)
    _prune_recovery_files(path)
    return valid


@_locked_state
def _save(path, data):
    """Temporal exclusivo en el mismo directorio, flush/fsync y replace reintentable."""
    import tempfile
    directory = os.path.dirname(os.path.abspath(path))
    tmp = None
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=1)
            stream.flush()
            os.fsync(stream.fileno())
        _retry_io(lambda: os.replace(tmp, path))
    except OSError as exc:
        # Si GPT ya escribió respuestas en el temporal pero Windows niega
        # replace, conservar ese resultado para conciliación manual.
        failed = None
        if tmp and os.path.isfile(tmp):
            target = _backup_name(path).replace(".corrupto-", ".escritura-fallida-")
            try:
                os.rename(tmp, target)
                failed, tmp = target, None
            except OSError:
                # No borrar un temporal que contiene respuestas todavía no
                # confirmadas; marcarlo también como evidencia recuperable.
                failed, tmp = tmp, None
        _emit_event("COLA_ESCRITURA_FALLIDA", path, type(exc).__name__,
                    quarantined=failed)
        raise QueueStateCorrupted(
            f"COLA_ESCRITURA_FALLIDA: {os.path.basename(path)} ({type(exc).__name__})"
        ) from exc
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _remote_target(item, network=None):
    """Referencia estable del destino: mismo contrato que el escáner API.

    En la cola `post_uri` ya viene resuelto por api_comment_writer. Para
    candidatos API crudos usar el resolvedor central, nunca elegir el campo
    homónimo de otra red ni el id ordinal de un reescaneo.
    """
    if not isinstance(item, dict):
        return ""
    network = str(network or "").strip().casefold()
    from candidate_identity import is_scan_ordinal
    explicit = item.get("post_uri")
    if isinstance(explicit, (str, int)) and not isinstance(explicit, bool) and str(explicit).strip():
        value = str(explicit).strip()
        # G001-P1 / M001-P1 son posiciones del escaneo, no destinos remotos.
        return "" if network in ("bluesky", "mastodon") and is_scan_ordinal(value) else value
    if network in ("bluesky", "mastodon"):
        from candidate_identity import CandidateIdentityError, resolve_post_ref
        raw_field = "uri" if network == "bluesky" else "status_id"
        if raw_field in item:
            try:
                resolved = resolve_post_ref(network, item)
                # Mastodon permite IDs no numéricos; solo rechazar los
                # ordinales locales que nuestro propio escáner genera.
                return "" if is_scan_ordinal(resolved) else resolved
            except CandidateIdentityError:
                return ""
        # Datos antiguos sin referencia nativa: solo URLs verificables o
        # campos históricos, nunca confundir un id ordinal con una URI.
    fields = ("permalink", "url") if network in ("bluesky", "mastodon") else (
        "post_id", "permalink", "url",
    )
    return next(
        (str(item[field]).strip() for field in fields
         if isinstance(item.get(field), (str, int)) and not isinstance(item[field], bool)
         and str(item[field]).strip()),
        "",
    )

def _rekey_pending(pending):
    """Reindexa SOLO pendientes que tienen fuente verificable (no answers).

    Un pending heredado guarda network, author, text, context y ts:
    se puede recalcular su clave. answers solo tiene hash, reply y ts:
    migrarlo por coincidencias supondría una colisión peligrosa.
    """
    result = {}
    for key, entry in pending.items():
        if not isinstance(entry, dict) or not entry.get("network") or not entry.get("text"):
            result[key] = entry
            continue
        new_key = key_for(entry["network"], entry)
        if new_key in result and isinstance(result[new_key], dict):
            old = result[new_key]
            # Dos snapshots con la misma clave pueden tener hilos distintos.
            # No componer bio vieja con conversación nueva por elegir el texto
            # MÁS LARGO de cada campo: GPT inventaría una fuente que no existe.
            # Conservar íntegra la observación más reciente (ambos ts validados).
            newest = (entry if datetime.datetime.fromisoformat(entry["ts"]) >=
                      datetime.datetime.fromisoformat(old["ts"]) else old)
            result[new_key] = dict(newest)
        else:
            result[new_key] = dict(entry)
    return result

def _active_pending(data, now=None):
    """Nunca permitir que una entrada caducada gane al reindexar duplicados."""
    return _rekey_pending({key: value for key, value in data.items() if _fresh(value, now)})

def key_for(network, item):
    """Clave de contenido completo y contexto; nunca usar el ID efímero del lote.

    Antes dos posts del mismo autor con los primeros 80 caracteres iguales
    compartían la respuesta de caché aunque divergiesen en el resto o en el
    hilo. No basta con cambiar el texto generado; la identidad de destino
    debe incluirse cuando el escáner la proporciona.
    """
    target = _remote_target(item, network)
    # Con ID remoto ESTABLE, cambios de bio / contexto parcial-completo
    # no crean nuevos pendientes para el MISMO post. Sin ID fiable el
    # contexto se conserva en identidad para no juntar hilos distintos.
    parts = [
        "v3", str(network or "").casefold(),
        rw._fold(str(item.get("author") or "").strip().lstrip("@")),
        rw._fold(" ".join(str(item.get("text") or "").split())),
        bool(item.get("reply_to_us")),
        target,
    ]
    if not target:
        parts.extend([
            rw._fold(" ".join(str(item.get("context") or "").split())),
            rw._fold(" ".join(str(item.get("conversation_context") or "").split())),
        ])
    base = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def _fresh(entry, now=None):
    now = now or datetime.datetime.now()
    if not isinstance(entry, dict):
        return False
    try:
        stamp = datetime.datetime.fromisoformat(entry.get("ts", ""))
        if stamp.tzinfo is not None or now.tzinfo is not None:
            return False
        age = (now - stamp).total_seconds()
        return -300 <= age < TTL_HOURS * 3600
    except (ValueError, TypeError, OverflowError):
        return False


def _source_hash(source):
    """Misma huella contextual que #79; evita otra caché o clave paralela."""
    import reply_provenance as proof
    return proof.source_hash(source)


def _answer_matches(entry, source, network=None):
    """Un cambio de hilo/contexto no autoriza a reutilizar una respuesta.

    Las answers anteriores a #62 no llevan source_hash: su gate sigue siendo
    la prueba de procedencia de #79, nunca una huella reconstruida a ciegas.
    """
    if not isinstance(entry, dict):
        return False
    if network and entry.get("network"):
        import reply_provenance as proof
        if proof.norm_net(network) != proof.norm_net(entry["network"]):
            return False
    stamped = entry.get("source_hash")
    if stamped is None:
        return True  # legacy: requiere igualmente _proof_ready al emitir texto.
    return bool(stamped) and stamped == _source_hash(source)


def _retry_due(entry, now):
    """Nunca reconsultar inmediatamente un ID omitido por el modelo."""
    stamp = entry.get("retry_after") if isinstance(entry, dict) else None
    if not stamp:
        return True
    try:
        due = datetime.datetime.fromisoformat(stamp)
        if due.tzinfo is not None or now.tzinfo is not None:
            return False
        return due <= now
    except (TypeError, ValueError, OverflowError):
        return False


def _defer_incomplete(entry, now):
    attempts = entry.get("incomplete_attempts", 0)
    attempts = attempts if type(attempts) is int and 0 <= attempts <= MAX_INCOMPLETE_ATTEMPTS else 0
    attempts = min(attempts + 1, MAX_INCOMPLETE_ATTEMPTS)
    entry["incomplete_attempts"] = attempts
    if attempts >= MAX_INCOMPLETE_ATTEMPTS:
        # Se conserva hasta TTL para diagnóstico, pero no se generan
        # consultas indefinidas; solo contexto enriquecido reabre la petición.
        minutes = TTL_HOURS * 60
    else:
        minutes = INCOMPLETE_RETRY_MINUTES[attempts - 1]
    entry["retry_after"] = (now + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")


def _proof_ready(network, source, reply):
    """Cache answers legacy sin prueba no puede convertirse en plan remoto."""
    if (os.environ.get("RRSS_ALLOW_UNMARKED_TEXT") == "1"
            and os.environ.get("PYTEST_CURRENT_TEST")):
        return True  # Fixtures de las suites previas a #79; nunca una ronda real.
    import reply_provenance as proof
    if not proof.canonical(network, source):
        return False
    action = {**source, "text": reply}
    return proof.attach(action, source, network) is not None


class DuplicateHistoryUnavailable(RuntimeError):
    """No se puede acreditar que el texto no fue publicado."""


def already_used(reply):
    """08/10: una respuesta ya publicada (en cualquier red) que vuelve a salir de la cola de cache nunca llega a un plan: el preflight de los ejecutores
    rechaza el lote ENTERO ante un texto duplicado y una sola respuesta repetida dejaba sin ejecutar toda la ronda (Mastodon, 5 rondas seguidas)."""
    try:
        import check_duplicate_phrase as dup
        return bool(dup.check(reply))
    except Exception as exc:
        raise DuplicateHistoryUnavailable("Historial de publicaciones no verificable") from exc


def get_or_enqueue(items, network, log=print, wait_min=0):
    """Una ronda mantiene sus demás acciones si falla el almacenamiento."""
    try:
        return _get_or_enqueue_unchecked(items, network, log=log, wait_min=wait_min)
    except QueueStateCorrupted as exc:
        log(f"[reply_queue] {network}: sin comentarios (cola inaccesible: {str(exc)[:100]})")
        return {}


def _get_or_enqueue_unchecked(items, network, log=print, wait_min=0):
    """Obtiene respuestas o encola sin perder cambios de otros productores.

    La espera a ChatGPT (#119) sucede SIEMPRE fuera de la sección crítica.
    """
    # El productor puede recibir una fuente vacía o mal tipada. No encolar
    # entradas que luego darían source_hash vacío ni contaminar el JSON.
    candidates = [
        {**item, "network": (item.get("network") or network).strip().casefold()}
        for item in (items or [])
        if isinstance(item, dict)
        and isinstance(item.get("text"), str) and item["text"].strip()
        and isinstance(item.get("id"), (str, int)) and not isinstance(item["id"], bool)
        and str(item["id"]).strip()
        and isinstance(item.get("network") or network, str)
        and (item.get("network") or network).strip().casefold() in rw.MAX_CHARS
    ]
    items = rw.new_authors_only(candidates, network, log)
    if not items:
        return {}
    out, wanted = {}, set()
    hits = misses = negative = queued = duplicate = full = 0
    obsolete_proofs = missing_targets = 0
    with _storage_lock():
        answers = _load(ANSWERS)
        original = _load(PENDING)
        pending = _active_pending(original)
        dirty_pending = pending != original
        dirty_answers = False
        for item in items:
            net = item.get("network") or network
            key = key_for(net, item)
            entry = answers.get(key)
            if entry and _fresh(entry) and not _answer_matches(entry, item, net):
                # Mismo destino y texto, pero contexto nuevo: hay que volver
                # a generar; conservar el pending y no publicar texto antiguo.
                answers.pop(key, None)
                dirty_answers = True
                entry = None
            if entry and _fresh(entry) and entry.get("reply") and not _proof_ready(net, item, entry["reply"]):
                import reply_provenance as proof
                if not proof.canonical(net, item):
                    missing_targets += 1
                    continue  # No reconsultar GPT sin referencia verificable.
                answers.pop(key, None)
                dirty_answers = True
                obsolete_proofs += 1
                entry = None  # Recompone una vez; no asigna destino al legacy.
            if entry and _fresh(entry) and entry.get("reply"):
                try:
                    published = already_used(entry["reply"])
                except DuplicateHistoryUnavailable:
                    log("[reply_queue] historial no verificable: respuesta retenida sin invalidar")
                    continue
                if published:
                    answers.pop(key, None)
                    dirty_answers = True
                    entry = None
            if entry and _fresh(entry):
                if entry.get("reply"):
                    out[item["id"]] = entry["reply"]
                    hits += 1
                else:
                    negative += 1
                if key in pending:  # Recuperación tras crash entre guardar answers y pending.
                    pending.pop(key)
                    dirty_pending = True
                continue
            misses += 1
            if key in pending:
                duplicate += 1
                for field in ("context", "conversation_context"):
                    incoming = item.get(field)
                    if not isinstance(incoming, str) or not incoming.strip():
                        continue  # falta de dato no borra el hilo documentado
                    known = str(pending[key].get(field) or "")
                    # Si es truncamiento literal, conservar el más completo.
                    # Si las versiones difieren semánticamente, gana la lectura
                    # nueva (aunque sea más corta); nunca fusionar dos hilos.
                    selected = known if incoming in known else incoming
                    if selected != known:
                        pending[key][field] = selected
                        pending[key].pop("retry_after", None)
                        pending[key].pop("incomplete_attempts", None)
                        dirty_pending = True
                wanted.add(key)
            elif len(pending) < MAX_PENDING:
                pending[key] = {
                    "network": net, "author": item.get("author"),
                    "text": item.get("text"), "context": item.get("context", ""),
                    "conversation_context": item.get("conversation_context", ""),
                    "post_uri": _remote_target(item, net),
                    "url": item.get("permalink") or item.get("url"),
                    "reply_to_us": bool(item.get("reply_to_us")),
                    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                }
                dirty_pending = True
                queued += 1
                wanted.add(key)
            else:
                full += 1
        # Guardar primero la invalidación: una respuesta publicada no reaparece
        # por fallo posterior al persistir el estado de pendientes.
        if dirty_answers:
            _save(ANSWERS, answers)
        if dirty_pending:
            _save(PENDING, pending)
        pending_count = len(pending)
    # Métricas agregadas para integrar en el embudo C1 de #117, sin textos ni IDs.
    log(f"[reply_queue] {network}: cache_hits={hits} cache_null={negative} "
        f"cache_misses={misses} ya_pendientes={duplicate} encoladas={queued} "
        f"cola_llena={full} pendientes={pending_count} "
        f"pruebas_legacy_recompuestas={obsolete_proofs} objetivos_no_verificados={missing_targets}")
    if wait_min and wanted and worker_running():
        # wait_min viene de #119 y también cubre pendientes ya existentes.
        out.update(_wait_for_batch(items, network, {k: True for k in wanted}, wait_min, log))
    return out


def _wait_for_batch(items, network, pending, wait_min, log):
    """Espera a que el trabajador responda los items encolados de esta ronda. Devuelve {item_id: respuesta} de lo que llegue a tiempo."""
    wanted = {}
    for item in items:
        key = key_for(item.get("network") or network, item)
        if key in pending:
            wanted[key] = item
    if not wanted:
        return {}
    log(f"[reply_queue] {network}: esperando al trabajador de ChatGPT hasta {wait_min} min por {len(wanted)} textos")
    deadline = time.time() + wait_min * 60
    answers = {}
    while time.time() < deadline:
        time.sleep(15)
        answers = _load(ANSWERS)
        if all(k in answers and _fresh(answers[k]) for k in wanted):
            break
        if not worker_running():
            log(f"[reply_queue] {network}: el trabajador se paro; se sigue con lo que haya")
            break
    got = {}
    for key, item in wanted.items():
        entry = answers.get(key)
        if entry and _fresh(entry) and entry.get("reply"):
            try:
                if (_answer_matches(entry, item, item.get("network") or network)
                        and not already_used(entry["reply"])
                        and _proof_ready(item.get("network") or network, item, entry["reply"])):
                    got[item["id"]] = entry["reply"]
            except DuplicateHistoryUnavailable:
                log("[reply_queue] historial no verificable: respuesta en espera retenida")
    log(f"[reply_queue] {network}: {len(got)} de {len(wanted)} textos llegaron a tiempo")
    return got


# 09/10: antes 150 min. El 09/10 el chat quedo vacio a las 07:12 y el trabajador espero 2 h 20 min una respuesta que no iba a llegar (ninguna respuesta nueva en ese tiempo).
def work_once(max_items=40, wait_min=15, consult=None, log=print):
    """El modelo trabaja fuera del lock; al guardar se fusiona con el estado nuevo."""
    now = datetime.datetime.now()
    with _storage_lock():
        original = _load(PENDING)
        answers_before = _load(ANSWERS)
        # Crash con clave legada: retirar las respuestas YA guardadas ANTES
        # de reindexar los pendientes. De otro modo "k" pasa a sha256 y
        # se consulta GPT otra vez aunque answers["k"] siga vigente.
        outstanding = {
            k: v for k, v in original.items()
            if not (k in answers_before and _fresh(answers_before[k], now)
                    and _answer_matches(answers_before[k], v, v.get("network")))
        }
        pending = _active_pending(outstanding, now)
        # Cubrir también la recuperación posterior con clave v3.
        pending = {
            k: v for k, v in pending.items()
            if not (k in answers_before and _fresh(answers_before[k], now)
                    and _answer_matches(answers_before[k], v, v.get("network")))
        }
        if pending != original:
            _save(PENDING, pending)
        if not pending:
            return 0
        keys = sorted((k for k in pending if _retry_due(pending[k], now)),
                      key=lambda k: (
                          not pending[k].get("reply_to_us"), pending[k].get("ts", "")
                      ))[:max_items]
        if not keys:
            return 0
        snapshot = {k: dict(pending[k]) for k in keys}

    items = [
        {"id": f"q{n + 1}", "network": snapshot[k]["network"],
         "author": snapshot[k].get("author"), "text": snapshot[k]["text"],
         "context": snapshot[k].get("context", ""),
         "conversation_context": snapshot[k].get("conversation_context", ""),
         "reply_to_us": snapshot[k].get("reply_to_us"),
         "post_uri": snapshot[k].get("post_uri"),
         "url": snapshot[k].get("url") or snapshot[k].get("post_uri")}
        for n, k in enumerate(keys)
    ]
    status = {}
    written = rw.write_replies(items, "x", wait_min=wait_min, consult=consult, log=log, status=status)
    if not status.get("consulted"):
        log("[reply_queue] ChatGPT no respondio: los pendientes se conservan")
        return 0

    useful = committed = changed = incomplete = 0
    outcomes = status.get("outcomes") or {}
    with _storage_lock():
        original = _load(PENDING)
        pending = _active_pending(original)
        original_answers = _load(ANSWERS)
        answers = {k: v for k, v in original_answers.items() if _fresh(v)}
        for n, key in enumerate(keys):
            # Un productor puede ampliar el contexto durante la consulta.
            # No consumir ese pendiente con una respuesta desactualizada.
            if pending.get(key) != snapshot[key]:
                changed += 1
                continue
            if (key in answers and _fresh(answers[key])
                    and _answer_matches(answers[key], snapshot[key],
                                        snapshot[key].get("network"))):
                pending.pop(key)
                continue
            item_id = f"q{n + 1}"
            reply = written.get(item_id)
            outcome = outcomes.get(item_id)
            # Compatibilidad con escritores de prueba que devuelven texto sin
            # registrar outcomes; nunca asumir null por un ID ausente.
            if outcome is None and isinstance(reply, str) and reply.strip():
                outcome = "written"
            if (outcome not in ("written", "null", "rejected")
                    or (outcome == "written"
                        and not (isinstance(reply, str) and reply.strip()))):
                incomplete += 1
                _defer_incomplete(pending[key], datetime.datetime.now())
                continue
            answers[key] = {
                "reply": reply if outcome == "written" else None,
                "state": outcome,
                "source_hash": _source_hash(snapshot[key]),
                "network": snapshot[key]["network"],
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            pending.pop(key)
            committed += 1
            if outcome == "written":
                useful += 1
        if committed or answers != original_answers:
            # Orden de crash recuperable: answers primero, pending después.
            _save(ANSWERS, answers)
        if pending != original:
            _save(PENDING, pending)
    log(f"[reply_queue] tanda: {len(keys)} consultados, {committed} guardados, "
        f"{useful} utiles, {incomplete} pendientes sin decision, "
        f"{changed} pendientes con contexto nuevo")
    return useful

def _alive(pid):
    try:
        # Una única política de PID para los supervisores y el claim del
        # trabajador: no esperar horas por un zombi Linux ya terminado.
        import worker_singleton
        return worker_singleton._legacy_pid_alive(pid)
    except Exception:
        return False


def worker_running():
    try:
        with open(LOCK, encoding="utf-8") as stream:
            pid = int(stream.read().strip())
    except (OSError, ValueError):
        return False
    return _alive(pid)


def _snapshot_json(path):
    """Lectura de diagnóstico: nunca sanea, renombra, purga ni bloquea al worker."""
    try:
        with open(path, "rb") as stream:
            raw = stream.read()
    except FileNotFoundError:
        return {}, True
    except OSError as exc:
        raise QueueStateCorrupted(
            f"SNAPSHOT_INACCESIBLE: {os.path.basename(path)} ({type(exc).__name__})"
        ) from exc
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise QueueStateCorrupted(
            f"SNAPSHOT_CORRUPTO: {os.path.basename(path)} ({type(exc).__name__})"
        ) from exc
    if not isinstance(data, dict) or not all(
            isinstance(key, str) and _valid_entry(path, value)
            for key, value in data.items()):
        raise QueueStateCorrupted(
            f"SNAPSHOT_INVALIDO: {os.path.basename(path)}"
        )
    return data, False


def stats_snapshot():
    """Contadores sin efectos laterales; no representan un snapshot multi-JSON atómico."""
    pending, pending_missing = _snapshot_json(PENDING)
    answers, answers_missing = _snapshot_json(ANSWERS)
    return {
        "pendientes": len(pending),
        "respuestas": sum(bool(v["reply"]) for v in answers.values()),
        "descartadas": sum(not bool(v["reply"]) for v in answers.values()),
        "rechazadas": sum(v.get("state") == "rejected" for v in answers.values()),
        "pendientes_caducados": sum(not _fresh(v) for v in pending.values()),
        "pendientes_en_pausa": sum(_fresh(v) and not _retry_due(v, datetime.datetime.now())
                                   for v in pending.values()),
        "pendientes_reintentos_agotados": sum(
            v.get("incomplete_attempts") == MAX_INCOMPLETE_ATTEMPTS
            for v in pending.values()),
        "respuestas_caducadas": sum(not _fresh(v) for v in answers.values()),
        "respuestas_sin_huella_contextual": sum(
            bool(v["reply"]) and not v.get("source_hash") for v in answers.values()
        ),
        "trabajador": worker_running(),
        "ficheros_ausentes": [
            name for name, missing in (("pending.json", pending_missing),
                                       ("answers.json", answers_missing)) if missing
        ],
    }


def loop(until, pause_min=0.25):
    # Entrar SIEMPRE por el guard OS: una comprobación previa por PID puede
    # devolver True para un PID zombi o reutilizado y bloquear la recuperación.
    # claim() respeta un worker legado verdaderamente vivo.
    import worker_singleton
    import round_queue as ctrl
    with worker_singleton.claim(LOCK) as owns_worker:
        if not owns_worker:
            print("[reply_queue] otra instancia tiene el turno de trabajador")
            return 0
        started = time.time()
        while datetime.datetime.now() < until and not ctrl.control_signal(started):
            # También debe protegerse la lectura del estado previo a la tanda.
            # La cuarentena de #105 puede señalar una cola inaccesible aquí.
            try:
                if _load(PENDING):
                    work_once()
            except Exception as exc:  # la cola no debe abortar el worker
                print(f"[reply_queue] tanda fallida ({type(exc).__name__}: {str(exc)[:100]})", flush=True)
            end = time.time() + pause_min * 60
            while time.time() < end and not ctrl.control_signal(started):
                time.sleep(15)
    # La propiedad OS y worker.lock ya están liberados al relanzar.
    if ctrl.control_signal(started) == "recargar" and datetime.datetime.now() < until:
        print("[reply_queue] recarga pedida: se relanza con el codigo nuevo", flush=True)
        ctrl.relaunch([os.path.join("tools", "reply_queue.py"), "loop", "--until", f"{until:%H:%M}"], "reply_worker.log")
    return 0


def work_command(max_items=40):
    """Ejecución manual del lote: misma exclusión OS que loop()."""
    import worker_singleton
    with worker_singleton.claim(LOCK) as owns_worker:
        if not owns_worker:
            print("[reply_queue] otro trabajador ya ocupa la cola; no se lanza una segunda tanda")
            return 2
        useful = work_once(max_items)
        print(f"[reply_queue] {useful} respuestas utiles")
    return 0

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 0
    if argv[0] == "work":
        max_items = int(argv[argv.index("--max") + 1]) if "--max" in argv else 40
        return work_command(max_items)
    elif argv[0] == "loop":
        text = argv[argv.index("--until") + 1] if "--until" in argv else "23:30"
        hour, minute = (int(x) for x in text.split(":"))
        return loop(datetime.datetime.combine(datetime.date.today(), datetime.time(hour, minute)))
    elif argv[0] == "stats":
        if len(argv) > 2 or (len(argv) == 2 and argv[1] != "--readonly"):
            print("[reply_queue] usar: stats [--readonly]", file=sys.stderr)
            return 2
        try:
            print(json.dumps(stats_snapshot(), ensure_ascii=False))
        except QueueStateCorrupted as exc:
            print(f"[reply_queue] {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
