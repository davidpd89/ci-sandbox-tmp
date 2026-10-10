"""Libro de acciones transaccional (03/10) y bloqueo entre procesos.

Problema (revision de ChatGPT, verificado): las rondas programadas, los seguimientos y
los pipelines manuales son procesos distintos; los CSV son append sin bloqueo y el
patron "compruebo si ya respondi -> respondo" no es atomico, asi que dos procesos
pueden actuar sobre el mismo objetivo. Aqui:

* `ActionLedger`: SQLite con clave unica (kind, target). Antes de escribir en la red
  se hace `reserve()`; solo UN proceso gana la reserva. Estados: reserved ->
  confirmed | failed | uncertain. confirmed/uncertain bloquean (una escritura incierta
  no se reintenta sin comprobar el estado remoto); failed se puede reintentar; una
  reserva abandonada (proceso caido) caduca tras `stale_after` segundos.
* `exclusive(name)`: bloqueo por fichero para que no corran a la vez dos ejecutores o
  dos rondas de la misma red (por ejemplo la tarea de las 10:05 y una ronda manual).

El ledger NO limita volumen: solo evita el doble gasto sobre el mismo objetivo.
"""
import contextlib
import errno
import os
import sqlite3
import sys
import tempfile
import threading
import time

from process_identity import creation_token, valid_token

CONFIRMED = "confirmed"
FAILED = "failed"
UNCERTAIN = "uncertain"
RESERVED = "reserved"
HOLDOUT = "holdout"     # grupo de control: detectado a proposito SIN tocar (nunca se actua)
SKIPPED_POLICY = "skipped_policy"  # no cuenta ni como acción ni como fallo
DEFAULT_POLICY_TTL = 6 * 3600  # desconocidos: evitar bucles sin bloqueo permanente
# Clasificación única por código exacto. Cada valor es (estado, TTL o None).
# No se usa 'saltado_ya_*' genérico: los éxitos previos deben estar enumerados.
OUTCOME_CLASS = {
    "saltado_ya_seguido": (CONFIRMED, None),
    "saltado_ya_no_seguido": (CONFIRMED, None),
    "saltado_ya_like": (CONFIRMED, None),
    "saltado_ya_comentado": (CONFIRMED, None),
    "saltado_ya_reaccionado": (CONFIRMED, None),
    "saltado_ya_reposteado": (CONFIRMED, None),
    "saltado_ya_citado": (CONFIRMED, None),
    "saltado_ya_votado": (CONFIRMED, None),
    "saltado_ya_hecho": (CONFIRMED, None),
    # Mastodon forma saltado_ya_{kind}: lista cerrada de kinds ejecutables.
    "saltado_ya_follow": (CONFIRMED, None),
    "saltado_ya_favourite": (CONFIRMED, None),
    "saltado_ya_boost": (CONFIRMED, None),
    "saltado_ya_reply": (CONFIRMED, None),
    "saltado_perfil": (SKIPPED_POLICY, 7 * 86400),
    "saltado_cierre_conversacion": (SKIPPED_POLICY, 86400),
<<<<<<< HEAD
    "saltado_like_contexto": (SKIPPED_POLICY, 86400),
    "saltado_fase_calentamiento": (SKIPPED_POLICY, 6 * 3600),
    "saltado_techo_sesion": (SKIPPED_POLICY, 6 * 3600),
    "saltado_duplicado": (SKIPPED_POLICY, 6 * 3600),
=======
    "saltado_contexto_api_no_verificado": (SKIPPED_POLICY, 6 * 3600),
    "saltado_like_contexto": (SKIPPED_POLICY, 86400),
    "saltado_politica_auto_like": (SKIPPED_POLICY, 86400),
    "saltado_fase_calentamiento": (SKIPPED_POLICY, 6 * 3600),
    "saltado_techo_sesion": (SKIPPED_POLICY, 6 * 3600),
    "saltado_techo_diario": (SKIPPED_POLICY, 6 * 3600),
    "saltado_limite_follow": (SKIPPED_POLICY, 4 * 3600),     # limite de seguir de TikTok: se reintenta tras el descanso
    # El ejecutor web de TikTok solo localiza vídeos por fragmento visual:
    # no reintentar comentarios sin un destino remoto comprobable.
    "saltado_destino_web_no_verificable": (SKIPPED_POLICY, 7 * 86400),
    "saltado_duplicado": (SKIPPED_POLICY, 6 * 3600),
    # Omisión confirmada solo dentro de preflight: nunca una acción remota.
    "saltado_preflight_texto_publicado": (SKIPPED_POLICY, 6 * 3600),
    "saltado_preflight_texto_repetido_lote": (SKIPPED_POLICY, 6 * 3600),
    "saltado_preflight_objetivo_repetido_lote": (SKIPPED_POLICY, 6 * 3600),
    "saltado_preflight_relacion_repetida_lote": (SKIPPED_POLICY, 6 * 3600),
    "saltado_preflight_microtexto_publicado": (SKIPPED_POLICY, 6 * 3600),
    "saltado_preflight_post_antiguo": (SKIPPED_POLICY, 7 * 86400),
>>>>>>> origin/research/public-reuse-parent
    "saltado_en_ledger": (FAILED, None),
    "saltado_api_*": (FAILED, None),
    "saltado_sin_contexto": (FAILED, None),
    "saltado_objetivo_no_resuelto": (FAILED, None),
}


def _outcome_key(detail):
    """Código antes de ':'; errores HTTP son la única familia con comodín."""
    code = str(detail or "").split(":", 1)[0]
    return "saltado_api_*" if code.startswith("saltado_api_") else code


def _policy_ttl(detail):
    classified = OUTCOME_CLASS.get(_outcome_key(detail))
    return classified[1] if classified and classified[0] == SKIPPED_POLICY else DEFAULT_POLICY_TTL


# PID es DWORD en Windows y pid_t con signo en POSIX. Los tokens fuera
# de rango del fichero se consideran ilegibles, no proceso existente.
_MAX_PID = 0xFFFFFFFF if os.name == "nt" else 0x7FFFFFFF


class RoundBusy(RuntimeError):
    pass


class ActionLedger:
    def __init__(self, path, stale_after=3600, clock=time.time):
        self.path = path
        self.stale_after = stale_after
        self.clock = clock
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with contextlib.closing(self._conn()) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS actions ("
                "kind TEXT NOT NULL, target TEXT NOT NULL, status TEXT NOT NULL, detail TEXT DEFAULT '', "
                "created REAL NOT NULL, updated REAL NOT NULL, PRIMARY KEY (kind, target))"
            )

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def target_for(kind, item):
        """Identificador canonico del objetivo: AT-URI/ID de status/handle en minusculas."""
        if kind in ("follow", "unfollow"):
            return str(item.get("handle") or "").lstrip("@").casefold()
        for key in ("_target_uri", "status_id", "url"):
            if item.get(key):
                return str(item[key]).strip()
        return str(item.get("handle") or "").lstrip("@").casefold()

    def reserve(self, kind, target):
        """Devuelve "ok" si este proceso puede actuar, o el estado que lo impide."""
        if not target:
            return "ok"
        now = self.clock()
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status, updated, detail FROM actions WHERE kind=? AND target=?",
                               (kind, target)).fetchone()
            if row is None:
                conn.execute("INSERT INTO actions VALUES (?,?,?,?,?,?)", (kind, target, RESERVED, "", now, now))
                conn.execute("COMMIT")
                return "ok"
            status, updated, detail = row
            if status in (CONFIRMED, UNCERTAIN, HOLDOUT):
                conn.execute("COMMIT")
                return status
            if status == RESERVED and now - updated < self.stale_after:
                conn.execute("COMMIT")
                return RESERVED
            if status == SKIPPED_POLICY and now - updated < _policy_ttl(detail):
                conn.execute("COMMIT")
                return SKIPPED_POLICY
            # failed, o reserva abandonada: se puede intentar de nuevo
            conn.execute("UPDATE actions SET status=?, updated=? WHERE kind=? AND target=?",
                         (RESERVED, now, kind, target))
            conn.execute("COMMIT")
            return "ok"
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            conn.close()

    def settle(self, kind, target, status, detail=""):
        if not target:
            return
        with contextlib.closing(self._conn()) as conn:
            # Una respuesta tardía no puede degradar confirmed/uncertain/holdout
            # ni convertir un skip ya persistido en un fallo reintentable.
            conn.execute("UPDATE actions SET status=?, detail=?, updated=? "
                         "WHERE kind=? AND target=? AND status=?",
                         (status, str(detail)[:300], self.clock(), kind, target, RESERVED))

    def hold(self, kind, target):
        """Marca un objetivo como control (holdout): ningun ejecutor volvera a actuar sobre el."""
        now = self.clock()
        with contextlib.closing(self._conn()) as conn:
            conn.execute("INSERT OR REPLACE INTO actions VALUES (?,?,?,?,?,?)",
                         (kind, target, HOLDOUT, "grupo de control", now, now))

    def release(self, kind, target):
        """Borra la fila (p. ej. tras un unfollow confirmado, para poder volver a seguir)."""
        with contextlib.closing(self._conn()) as conn:
            conn.execute("DELETE FROM actions WHERE kind=? AND target=?", (kind, target))

    def release_after_unfollow(self, target):
        """Liberación atómica: requiere unfollow confirmado y respeta el holdout."""
        with contextlib.closing(self._conn()) as conn:
            conn.execute(
                "DELETE FROM actions WHERE kind=? AND target=? AND status<>? "
                "AND EXISTS (SELECT 1 FROM actions AS u "
                "WHERE u.kind=? AND u.target=? AND u.status=? "
                "AND actions.updated <= u.updated)",
                ("follow", target, HOLDOUT, "unfollow", target, CONFIRMED),
            )

    def settle_results(self, reserved, results):
        settle_results(self, reserved, results)

    def count_since(self, since):
        """Acciones confirmadas desde `since` (epoch): lo hecho hoy, para repartir el presupuesto diario."""
        with contextlib.closing(self._conn()) as conn:
            row = conn.execute("SELECT COUNT(*) FROM actions WHERE status=? AND updated>=?",
                               (CONFIRMED, since)).fetchone()
        return row[0] if row else 0

    def status(self, kind, target):
        with contextlib.closing(self._conn()) as conn:
            row = conn.execute("SELECT status FROM actions WHERE kind=? AND target=?", (kind, target)).fetchone()
        return row[0] if row else None


def outcome_to_status(resultado):
    """Traduce resultados sin inventar éxito ni reintentar omisiones editoriales."""
    import logging
    resultado = str(resultado or "")
    # Incluso si el texto comienza por un prefijo de éxito, prima UNCERTAIN.
    if "incierto" in resultado or "pendiente_verificacion" in resultado:
        return UNCERTAIN
    if resultado in ("confirmado", "publicado"):
        return CONFIRMED
    if resultado.startswith("saltado_"):
        classified = OUTCOME_CLASS.get(_outcome_key(resultado))
        if classified is not None:
            return classified[0]
        logging.getLogger(__name__).warning(
            "Resultado saltado sin catalogar: %s; reexaminar tras 6 h",
            resultado[:100],
        )
        return SKIPPED_POLICY
    return FAILED


def settle_results(ledger, reserved, results):
    """`reserved`: conjunto de (kind, target) reservados por ESTE proceso; `results`: lista de
    resultados del ejecutor. Cierra cada reserva con el estado que corresponda; lo reservado y
    sin resultado (el proceso paro) queda reintentable."""
    seen = set()
    confirmed_unfollows = set()
    for result in results:
        kind = result.get("kind")
        key = (kind, ledger.target_for(kind, result))
        if key in reserved and key not in seen:
            seen.add(key)
            status = outcome_to_status(result.get("resultado"))
            ledger.settle(key[0], key[1], status, result.get("resultado"))
            if kind == "unfollow" and status == CONFIRMED:
                confirmed_unfollows.add(key[1])
    for kind, target in reserved - seen:
        ledger.settle(kind, target, FAILED, "sin resultado")
    # Solo la PRIMERA respuesta de una reserva propia puede liberar el follow.
    # Un evento ajeno o un duplicado posterior no tiene autoridad para hacerlo.
    for target in confirmed_unfollows:
        ledger.release_after_unfollow(target)


def _pid_alive(pid):
    """True si el propietario sigue ejecutándose; duda = ocupado.

    Linux: un zombi conserva PID, pero ya no ejecuta ni retiene descriptores.
    Windows: esperar cero ms al objeto de proceso, no comparar exit code 259.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return False
    if pid > _MAX_PID:
        return True  # no consultar un PID que se truncaría: conservar el lock
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        open_process.restype = ctypes.c_void_p
        handle = open_process(0x00100000, 0, pid)  # SYNCHRONIZE; no permisos para matar
        if not handle:
            # 87: PID inexistente (o inválido); otros errores se bloquean.
            return ctypes.get_last_error() != 87
        try:
            wait = kernel32.WaitForSingleObject
            wait.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            wait.restype = ctypes.c_uint32
            return wait(handle, 0) != 0  # WAIT_OBJECT_0: terminó; demás: bloquear
        finally:
            close = kernel32.CloseHandle
            close.argtypes = (ctypes.c_void_p,)
            close.restype = ctypes.c_int
            close(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/status", encoding="ascii") as stream:
                for line in stream:
                    if line.startswith("State:"):
                        state = line.partition(":")[2].strip()[:1]
                        return state not in ("Z", "X", "x")
        except FileNotFoundError:
            return False  # murió entre kill(0) y la lectura de proc
        except (OSError, UnicodeError):
            pass  # /proc inaccesible: proteger el propietario potencial
    return True


@contextlib.contextmanager
def _os_guard_for_exclusive(path, name):
    """Guard OS permanente: excluye reclamadores concurrentes."""
    fd = os.open(path + ".oslock", os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0), 0o600)
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN) or getattr(exc, "winerror", None) in (33, 36):
                raise RoundBusy(f"{name}: guard ocupado") from exc
            raise
        locked = True
        yield
    finally:
        try:
            if locked:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


@contextlib.contextmanager
<<<<<<< HEAD
def exclusive(name, stale_after=7200, directory=None):
    """Bloqueo por fichero entre procesos. Lanza RoundBusy si otro proceso lo tiene
    (y no esta caducado)."""
    # RRSS_LOCK_DIR permite aislar los tests de una ronda real en curso (comparten la carpeta temporal).
    directory = directory or os.environ.get("RRSS_LOCK_DIR") or tempfile.gettempdir()
    path = os.path.join(directory, f"rrss_lock_{name}.lock")
=======
def exclusive(name, stale_after=7200, directory=None, *, lock_path=None):
    """Turno exclusivo entre procesos, también para una ruta móvil heredada.

    ``lock_path`` es optativo: sin él se conserva exactamente la ruta Edge.
    No se roba un turno vivo por edad; un guard OS serializa reclamadores.
    """
    # RRSS_LOCK_DIR permite aislar los tests de una ronda real en curso (comparten la carpeta temporal).
    directory = directory or os.environ.get("RRSS_LOCK_DIR") or tempfile.gettempdir()
    path = os.path.abspath(os.fspath(lock_path)) if lock_path is not None else os.path.join(directory, f"rrss_lock_{name}.lock")
    if lock_path is not None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
>>>>>>> origin/research/public-reuse-parent
    with _os_guard_for_exclusive(path, name):
        for _ in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    own_stat = os.stat(path)
                except BaseException:
                    os.close(fd)  # nunca filtrar el descriptor si falla la inspección
                    raise
                own_identity = (own_stat.st_dev, own_stat.st_ino)
                birth = creation_token(os.getpid())
                own_text = f"{os.getpid()} {int(time.time())}" + (f" {birth}" if birth else "")
                try:
                    with os.fdopen(fd, "w") as stream:
                        stream.write(own_text)
                except BaseException:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    try:
                        stat = os.stat(path)
                        if (stat.st_dev, stat.st_ino) == own_identity:
                            os.remove(path)
                    except OSError:
                        pass
                    raise
                break
            except FileExistsError:
                try:
                    age = time.time() - os.path.getmtime(path)
                    with open(path, encoding="utf-8") as stream:
                        owner = stream.read(256).strip()
                except UnicodeError:
                    owner = ""
                except OSError:
                    continue
                # La EDAD del fichero no demuestra que el propietario haya
                # muerto. Un proceso Edge legítimo puede durar > stale_after
                # (suspensión del equipo, espera de red): nunca robarle el lock.
                try:
<<<<<<< HEAD
                    old_pid = int(owner.split()[0])
=======
                    old_pid = int(owner.split()[0].split(":", 1)[0])  # admite tokens móviles anteriores PID:timestamp
>>>>>>> origin/research/public-reuse-parent
                except (IndexError, TypeError, ValueError):
                    old_pid = 0
                if old_pid > _MAX_PID:
                    old_pid = 0  # token fuera de rango: respetar 60 s
                if old_pid > 0 and _pid_alive(old_pid):
                    parts = owner.split()
                    saved_birth = parts[2] if len(parts) >= 3 else None
                    # La vida de un PID no prueba que siga siendo el mismo
                    # proceso. Solo recuperar si hay prueba positiva de cambio.
                    current_birth = creation_token(old_pid) if valid_token(saved_birth) else None
                    if not saved_birth or current_birth is None or current_birth == saved_birth:
                        raise RoundBusy(f"{name}: otro proceso lo esta usando ({owner}, hace {int(age)} s)")
                    if not valid_token(saved_birth):
                        raise RoundBusy(f"{name}: identidad de propietario ilegible")
                if old_pid <= 0 and age < 60:
                    # Un fichero vacío puede ser un escritor que acaba de hacer
                    # O_EXCL pero aún no ha escrito su PID. No pisarlo.
                    raise RoundBusy(f"{name}: fichero de propietario reciente sin PID válido")
                try:
                    os.remove(path)  # PID muerto o fichero ilegible claramente antiguo
                except OSError:
                    pass
        else:
            raise RoundBusy(f"{name}: no se pudo obtener el bloqueo")
        try:
            yield path
        finally:
            try:
                stat = os.stat(path)
                if (stat.st_dev, stat.st_ino) == own_identity:
                    with open(path, encoding="utf-8") as stream:
                        owned = stream.read() == own_text
                    if owned:
                        os.remove(path)
            except (OSError, UnicodeError):
                pass  # fichero propio manipulado/corrupto: no abortar al salir


# Solo el hilo que obtuvo el turno puede omitir la reacquisición local.
# os.environ se comparte entre hilos y NO prueba propiedad del navegador.
_browser_session_local = threading.local()


def _delegated_browser_owner(name, directory):
    """Valida el marcador heredado por un proceso hijo de mechanical_round.

    No basta la variable RRSS_BROWSER_LOCK_HELD: otro hilo del padre la
    puede observar y el hijo puede sobrevivir a un padre que ya terminó.
    """
    if os.environ.get("RRSS_BROWSER_LOCK_HELD") != name:
        return False
    try:
        parent_pid = int(os.environ["RRSS_BROWSER_LOCK_OWNER_PID"])
    except (KeyError, ValueError, TypeError):
        return False
    if parent_pid <= 0 or parent_pid == os.getpid() or not _pid_alive(parent_pid):
        return False
    directory = directory or os.environ.get("RRSS_LOCK_DIR") or tempfile.gettempdir()
    path = os.path.join(directory, f"rrss_lock_{name}.lock")
    try:
        with open(path, encoding="utf-8") as stream:
            parts = stream.read(256).split()
        owner_pid = int(parts[0])
        if owner_pid != parent_pid:
            return False
        if len(parts) >= 3:
            saved_birth = parts[2]
            if (not valid_token(saved_birth)
                    or os.environ.get("RRSS_BROWSER_LOCK_OWNER_BIRTH") != saved_birth
                    or creation_token(parent_pid) != saved_birth):
                return False
        elif os.environ.get("RRSS_BROWSER_LOCK_OWNER_BIRTH"):
            # Un marcador moderno no debe legitimar un lock legado sin identidad.
            return False
        # Un PID escrito no demuestra que el guard OS siga en posesión.
        # Si se puede reclamar, el padre ya no conserva el turno.
        try:
            with _os_guard_for_exclusive(path, name):
                return False
        except RoundBusy:
            return True
    except (OSError, ValueError, IndexError, UnicodeError):
        return False


@contextlib.contextmanager
def browser_session(wait_minutes=40, directory=None, name="edge_browser"):
    """Turno del Edge compartido (CDP 9223) para herramientas lanzadas a mano: espera hasta `wait_minutes`
    a que acabe la ronda programada que lo use, en vez de pisarla (dos Playwright a la vez en un mismo Edge)."""
    # 05/10: una ronda programada (mechanical_round) ya tiene el turno y lanza las herramientas como procesos hijos; si cada hijo
    # pidiera el turno otra vez se bloquearia con el de su propio padre (asi fallo Pinterest el 04/10: RoundBusy contra si mismo).
    if getattr(_browser_session_local, "owner", None) == name or _delegated_browser_owner(name, directory):
        yield None
        return
    deadline = time.monotonic() + max(0, wait_minutes) * 60
    while True:
        lock = exclusive(name, directory=directory)
        try:
            path = lock.__enter__()
            break
        except RoundBusy:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(20, remaining))
    previous_owner = getattr(_browser_session_local, "owner", None)
    _browser_session_local.owner = name
    try:
        yield path
    finally:
        _browser_session_local.owner = previous_owner
        lock.__exit__(None, None, None)
