"""Informe Pinterest offline: presencia observada, nunca reciprocidad inventada.

Fuente permitida: páginas previamente obtenidas de GET /user_account/followers
con permiso user_accounts:read verificado fuera de este módulo. No hace HTTP,
no abre perfiles/CSV ni escribe sobre cuentas. No exporta identificadores.
"""
from __future__ import annotations

import datetime as dt
import re

_SOURCE = "GET /user_account/followers"
_USERNAME = re.compile(r"[a-z0-9_.-]{1,64}")
_MAX_PAGES = 200
_MAX_ROWS = 250


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None or when.utcoffset() is None:
        return None
    return when.astimezone(dt.timezone.utc)


def _snapshot(data, *, now):
    """(estado, identificadores efímeros, cuenta, hora); no devuelve PII al informe."""
    if data is None:
        return "no_aportado", None, None, None
    if not isinstance(data, dict):
        return "formato_invalido", None, None, None
    if data.get("permiso_verificado") is not True:
        return "permiso_no_verificado", None, None, None
    when = _timestamp(data.get("observado_en"))
    account = data.get("cuenta_id")
    pages = data.get("paginas")
    if (data.get("fuente") != _SOURCE or not when
            or not isinstance(account, str) or not account.strip()
            or not isinstance(pages, list) or not 1 <= len(pages) <= _MAX_PAGES):
        return "formato_invalido", None, None, None
    if when > now.astimezone(dt.timezone.utc) + dt.timedelta(minutes=5):
        return "fecha_futura", None, None, None
    seen = set()
    expected = None
    used_cursors = set()
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or "solicitado_con_bookmark" not in page:
            return "formato_invalido", None, None, None
        requested = page["solicitado_con_bookmark"]
        if requested == "":
            requested = None
        if requested != expected:
            return "paginacion_invalida", None, None, None
        new_on_page = set()
        response = page.get("respuesta")
        if (not isinstance(response, dict) or "error" in response
                or "errors" in response or not isinstance(response.get("items"), list)):
            return "formato_invalido", None, None, None
        items = response["items"]
        if len(items) > _MAX_ROWS:
            return "formato_invalido", None, None, None
        for row in items:
            if not isinstance(row, dict) or not isinstance(row.get("username"), str):
                return "formato_invalido", None, None, None
            user = row["username"].strip().casefold()
            if not _USERNAME.fullmatch(user) or row.get("type") != "user":
                return "formato_invalido", None, None, None
            if user in seen:
                # La paginación cambió mientras se recorría, no es un
                # snapshot coherente: no calcular falsas altas/bajas.
                return "paginacion_inestable", None, None, None
            new_on_page.add(user)
        seen.update(new_on_page)
        cursor = response.get("bookmark")
        if cursor in (None, ""):
            expected = None
        elif isinstance(cursor, str) and cursor.strip() and len(cursor) <= 2048:
            if cursor in used_cursors:
                return "paginacion_invalida", None, None, None
            used_cursors.add(cursor)
            expected = cursor
        else:
            return "formato_invalido", None, None, None
        if index < len(pages) - 1 and expected is None:
            return "paginacion_invalida", None, None, None
    if expected is not None:
        return "paginacion_incompleta", None, None, None
    return "observado", seen, account, when


def build_report(actual=None, anterior=None, *, now=None, max_age_hours=48):
    """Comparación de snapshots completos de la MISMA cuenta, sin IDs exportados.

    `max_age_hours` sólo etiqueta frescura; no convierte capturas pasadas
    en actuales. Un productor no autenticado NO es evidencia del permiso.
    """
    now = dt.datetime.now(dt.timezone.utc) if now is None else now
    if not isinstance(now, dt.datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now debe ser un datetime con zona horaria")
    if (isinstance(max_age_hours, bool)
            or not isinstance(max_age_hours, (int, float))
            or not 0 < max_age_hours <= 720):
        raise ValueError("max_age_hours inválido")
    estado, current, account, when = _snapshot(actual, now=now)
    result = {
        "red": "pinterest", "version_esquema": 1,
        "estado_seguidores": estado,
        "fuente_permisos": ("declarados_por_el_productor_no_autenticados"
                            if isinstance(actual, dict)
                            and actual.get("permiso_verificado") is True
                            else "no_acreditados"),
        "fecha_observacion_utc": when.isoformat() if when is not None else None,
        "fecha_anterior_utc": None,
        "instantanea_atomica": False,  # páginas tomadas sucesivamente
        "vigencia": ("sin_dato" if when is None else
                    "desfase_adelantado" if when > now.astimezone(dt.timezone.utc) else
                    "reciente" if now.astimezone(dt.timezone.utc) - when <=
                    dt.timedelta(hours=max_age_hours) else "historica"),
        "identificadores_visibles": len(current) if current is not None else None,
        "identificadores_antes_no_visibles": None,
        "identificadores_que_ya_no_aparecen": None,
        "estado_comparacion": "sin_comparacion",
        "likes_entrantes_identificados": None,
        "comentarios_entrantes_identificados": None,
        "guardados_entrantes_identificados": None,
        "reciprocidad_atribuida": None,
        "visitas_atribuidas": None,
    }
    if estado != "observado":
        result["estado_comparacion"] = "actual_no_verificado"
        return result
    prior_status, previous, previous_account, previous_when = _snapshot(anterior, now=now)
    if prior_status == "observado":
        result["fecha_anterior_utc"] = previous_when.isoformat()
    if prior_status != "observado":
        result["estado_comparacion"] = ("anterior_no_aportado" if anterior is None
                                         else "anterior_" + prior_status)
    elif account != previous_account or previous_when >= when:
        result["estado_comparacion"] = "cuenta_o_orden_no_verificado"
    else:
        result["estado_comparacion"] = "snapshots_completos"
        result["identificadores_antes_no_visibles"] = len(current - previous)
        result["identificadores_que_ya_no_aparecen"] = len(previous - current)
    return result
