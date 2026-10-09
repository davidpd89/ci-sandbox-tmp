"""Protección offline de idempotencia para publicar fichas propias en Instagram.

UNCERTAIN se persiste antes del POST final. La reconciliación es manual.
"""
import hashlib
import os

from action_ledger import ActionLedger, FAILED, RESERVED, UNCERTAIN, RoundBusy, exclusive

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GUARD_DB = os.path.join(ROOT, "00_OPERATIVO", "instagram_publish_intents.sqlite3")
KIND = "instagram_publish"


class InstagramPublicationHeld(RuntimeError):
    """Una ficha tiene un intento ya reservado o de resultado incierto."""


def _key(account_id, item_path):
    if not account_id or not item_path:
        raise ValueError("cuenta y ruta de ficha obligatorias")
    raw = (str(account_id) + "\0" + os.path.normcase(os.path.abspath(item_path))).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def publish_guarded(item_path, account_id, submit, *, db_path=None):
    """submit(before_publish) debe llamar al callback justo antes del POST final."""
    path = os.path.abspath(db_path or GUARD_DB)
    target = _key(account_id, item_path)
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    # ActionLedger activa WAL al abrir cada conexión. Serializar desde ANTES de
    # su inicialización evita el SQLITE_BUSY al arrancar dos workers juntos.
    # El candado de fichero también impide dos envíos simultáneos de esta ficha.
    try:
        with exclusive("instagram_publish_" + target, directory=directory):
            return _publish_under_lock(path, target, submit)
    except RoundBusy as exc:
        raise InstagramPublicationHeld("Instagram: publicación concurrente en curso") from exc


def _publish_under_lock(db_path, target, submit):
    ledger = ActionLedger(db_path)
    state = ledger.reserve(KIND, target)
    if state != "ok":
        raise InstagramPublicationHeld(
            "Ficha de Instagram ya reservada o de resultado incierto: "
            "verificar manualmente antes de reintentar"
        )

    def before_publish(container_id):
        if not container_id:
            raise ValueError("contenedor sin ID")
        ledger.settle(KIND, target, UNCERTAIN, "container=" + str(container_id)[:80])

    try:
        result = submit(before_publish)
    except Exception:
        if ledger.status(KIND, target) == RESERVED:
            ledger.settle(KIND, target, FAILED, "fallo antes del punto de publicacion")
        raise

    if ledger.status(KIND, target) != UNCERTAIN:
        ledger.settle(KIND, target, UNCERTAIN, "falta checkpoint obligatorio")
        raise RuntimeError("El publicador de Instagram omitio el checkpoint")
    return result
