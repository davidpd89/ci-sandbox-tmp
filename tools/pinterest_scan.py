"""Compatibilidad: la auditoría remota de Pinterest mediante Metricool está retirada.

David canceló Metricool y desde el 28/09/2026 la publicación/programación se
hace manualmente en cada red. Este módulo se conserva solo para que llamadas
antiguas fallen de forma explícita; NO conecta a Metricool ni a Pinterest.
"""


class RetiredPinterestAudit(RuntimeError):
    pass


def scan(*_args, **_kwargs):
    raise RetiredPinterestAudit(
        "pinterest_scan.py retirado: Metricool ya no forma parte del flujo. "
        "Revisar publicaciones manualmente en Pinterest y usar "
        "pinterest_execute.py únicamente como preflight offline."
    )


if __name__ == "__main__":
    try:
        scan()
    except RetiredPinterestAudit as exc:
        print(exc)
        raise SystemExit(2)
