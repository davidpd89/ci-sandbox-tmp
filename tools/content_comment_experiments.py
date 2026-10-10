"""Experimentos de contenido y comentarios: ledger SQLite local, sin acceso a redes.

Contrato genérico para nueve redes y colas WEB/API/MOBILE. Nunca publica ni
modifica planes operativos. Los datos de entrada deben ser seudónimos sintéticos
o revisados externamente; la marca 'confirmed' no constituye prueba remota.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"))
QUEUES = frozenset(("WEB", "API", "MOBILE"))
# Variantes: instrucciones editoriales, NO plantillas de texto.
INITIAL_EXPERIMENTS = {
    "apertura": ("post", ("detalle_concreto", "dilema_narrativo"), "interaction", 7),
    "pregunta": ("post", ("pregunta_abierta", "reto_especifico"), "interaction", 7),
    "hashtag": ("post", ("sin_hashtag", "hashtag_relevante"), "interaction", 7),
    "contexto": ("comment", ("detalle_observable", "cita_verificada"), "reply_received", 14),
}
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")


def _identifier(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError("identificador inválido: usar solo IDs opacos")
    return value


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp ISO UTC requerido")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp inválido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp debe ser UTC explícito")
    # Canonicalizar Z y +00:00; resolución microsegundos incluida.
    return parsed.astimezone(timezone.utc).isoformat()


def _digest(seed, experiment, network, unit_id):
    payload = json.dumps([seed, experiment, network, unit_id],
                         ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _posterior(successes, complete, rng, draws):
    # Beta(1,1) previa uniforme, estimación exploratoria para Bernoulli.
    a, b = 1 + successes, 1 + complete - successes
    values = sorted(rng.betavariate(a, b) for _ in range(draws))
    return {"mean": round(a / (a + b), 4),
            "interval_95": [round(values[int(draws * 0.025)], 4),
                            round(values[int(draws * 0.975)], 4)]}, values


class ExperimentStore:
    """Abrir SIEMPRE sobre un fichero nuevo/de pruebas elegido por el llamador."""

    def __init__(self, path):
        path = Path(path)
        if str(path) == ":memory:":
            raise ValueError("usar una ruta temporal explícita")
        if not path.parent.is_dir():
            raise ValueError("el directorio de experimentos no existe")
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS experiments(
                name TEXT PRIMARY KEY, seed TEXT NOT NULL, definition TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assignments(
                name TEXT NOT NULL, network TEXT NOT NULL, subject TEXT NOT NULL,
                queue TEXT NOT NULL, arm TEXT NOT NULL,
                PRIMARY KEY(name,network,subject),
                FOREIGN KEY(name) REFERENCES experiments(name)
            );
            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY, name TEXT NOT NULL, network TEXT NOT NULL,
                subject TEXT NOT NULL, event_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL, fingerprint TEXT NOT NULL,
                value INTEGER, source TEXT,
                FOREIGN KEY(name,network,subject)
                REFERENCES assignments(name,network,subject)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_exposure
                ON events(name,network,subject) WHERE event_type='exposure';
            CREATE UNIQUE INDEX IF NOT EXISTS one_result
                ON events(name,network,subject) WHERE event_type='outcome';
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def register(self, name, *, seed):
        """Congelar definición y semilla; nunca alterar brazos ya asignados."""
        if name not in INITIAL_EXPERIMENTS:
            raise ValueError("experimento desconocido")
        _identifier(seed)
        definition = json.dumps(INITIAL_EXPERIMENTS[name], separators=(",", ":"))
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT seed,definition FROM experiments WHERE name=?", (name,)
            ).fetchone()
            if row and (row["seed"], row["definition"]) != (seed, definition):
                raise ValueError("diseño/semilla inmutables")
            if row is None:
                self.db.execute("INSERT INTO experiments VALUES(?,?,?)",
                                (name, seed, definition))

    def _design(self, name):
        row = self.db.execute("SELECT seed,definition FROM experiments WHERE name=?",
                              (name,)).fetchone()
        if row is None:
            raise ValueError("registrar experimento antes de asignar")
        return row["seed"], json.loads(row["definition"])

    def assign(self, name, network, unit_id, queue):
        """Asignación estable por unidad+red; idempotente ante reintentos."""
        if network not in NETWORKS or queue not in QUEUES:
            raise ValueError("red o cola desconocida")
        _identifier(unit_id)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            seed, (_, arms, _, _) = self._design(name)
            subject = _digest(seed, name, network, unit_id)
            arm = arms[int(subject[:16], 16) % len(arms)]
            existing = self.db.execute(
                "SELECT queue,arm FROM assignments WHERE name=? AND network=? AND subject=?",
                (name, network, subject)).fetchone()
            if existing and (existing["queue"], existing["arm"]) != (queue, arm):
                raise ValueError("asignación existente con cola distinta")
            if existing is None:
                self.db.execute("INSERT INTO assignments VALUES(?,?,?,?,?)",
                                (name, network, subject, queue, arm))
            return arm

    def _record(self, *, event_id, name, network, unit_id, queue, kind,
                occurred_at, value=None, source=None):
        _identifier(event_id)
        _identifier(unit_id)
        if network not in NETWORKS or queue not in QUEUES:
            raise ValueError("red o cola desconocida")
        occurred_at = _utc(occurred_at)
        if kind == "exposure":
            if value is not None or source != "confirmed":
                raise ValueError("exposición debe estar confirmada")
        elif kind == "outcome":
            if type(value) is not bool or source not in ("confirmed_snapshot", "manual_review"):
                raise ValueError("resultado binario final requiere procedencia")
        else:
            raise ValueError("evento desconocido")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            seed, (_, _, _, days) = self._design(name)
            subject = _digest(seed, name, network, unit_id)
            assignment = self.db.execute(
                "SELECT queue FROM assignments WHERE name=? AND network=? AND subject=?",
                (name, network, subject)).fetchone()
            if assignment is None or assignment["queue"] != queue:
                raise ValueError("evento sin asignación de esta cola")
            signature = json.dumps([event_id, name, network, subject, queue, kind,
                                    occurred_at, value, source], separators=(",", ":"))
            prev = self.db.execute(
                "SELECT fingerprint FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
            if prev:
                if prev["fingerprint"] != signature:
                    raise ValueError("event_id reutilizado con otro contenido")
                return False
            existing = self.db.execute(
                "SELECT occurred_at FROM events WHERE name=? AND network=? "
                "AND subject=? AND event_type=?",
                (name, network, subject, kind)).fetchone()
            if existing:
                raise ValueError("unidad ya tiene este tipo de evento")
            if kind == "outcome":
                exposure = self.db.execute(
                    "SELECT occurred_at FROM events WHERE name=? AND network=? "
                    "AND subject=? AND event_type='exposure'",
                    (name, network, subject)).fetchone()
                if exposure is None:
                    raise ValueError("resultado sin exposición confirmada")
                minimum = datetime.fromisoformat(exposure["occurred_at"]) + timedelta(days=days)
                if datetime.fromisoformat(occurred_at) < minimum:
                    raise ValueError("resultado inmaduro")
            self.db.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",
                (event_id, name, network, subject, kind, occurred_at, signature,
                 int(value) if kind == "outcome" else None, source))
            return True

    def expose(self, event_id, name, network, unit_id, queue, occurred_at):
        return self._record(event_id=event_id, name=name, network=network,
                            unit_id=unit_id, queue=queue, kind="exposure",
                            occurred_at=occurred_at, source="confirmed")

    def outcome(self, event_id, name, network, unit_id, queue, occurred_at,
                converted, source):
        return self._record(event_id=event_id, name=name, network=network,
                            unit_id=unit_id, queue=queue, kind="outcome",
                            occurred_at=occurred_at, value=converted, source=source)

    def report(self, *, draws=4096):
        """Agregados por experimento/red, sin identificadores ni escritura."""
        if type(draws) is not int or not 256 <= draws <= 100_000:
            raise ValueError("draws fuera de rango")
        rows = self.db.execute("""
            SELECT a.name,a.network,a.arm,COUNT(*) AS assigned,
                   SUM(CASE WHEN e.event_id IS NOT NULL THEN 1 ELSE 0 END) AS exposed,
                   SUM(CASE WHEN o.event_id IS NOT NULL THEN 1 ELSE 0 END) AS mature,
                   SUM(CASE WHEN o.value=1 THEN 1 ELSE 0 END) AS successes
            FROM assignments a
            LEFT JOIN events e ON e.name=a.name AND e.network=a.network
              AND e.subject=a.subject AND e.event_type='exposure'
            LEFT JOIN events o ON o.name=a.name AND o.network=a.network
              AND o.subject=a.subject AND o.event_type='outcome'
            GROUP BY a.name,a.network,a.arm ORDER BY a.name,a.network,a.arm
        """).fetchall()
        groups = {}
        for row in rows:
            key = (row["name"], row["network"])
            group = groups.setdefault(key, {})
            group[row["arm"]] = {
                "assigned": row["assigned"], "exposed": row["exposed"],
                "mature": row["mature"], "successes": row["successes"]}
        results = []
        for (name, network), arms in sorted(groups.items()):
            _, variants, metric, days = INITIAL_EXPERIMENTS[name]
            posteriors, simulations = {}, {}
            for arm in variants:
                stats = arms.setdefault(arm, {
                    "assigned": 0, "exposed": 0, "mature": 0, "successes": 0})
                rng = random.Random(int(hashlib.sha256(
                    f"{name}|{network}|{arm}|posterior-v1".encode()).hexdigest(), 16))
                posteriors[arm], simulations[arm] = _posterior(
                    stats["successes"], stats["mature"], rng, draws)
            a, b = variants
            # Comparación MC: emparejar muestras de las dos marginales, sin
            # elegir variantes ni modificar asignaciones basándose en ella.
            probability = round(sum(x < y for x, y in
                                    zip(simulations[a], simulations[b])) / draws, 4)
            total_assigned = sum(x["assigned"] for x in arms.values())
            total_exposed = sum(x["exposed"] for x in arms.values())
            total_mature = sum(x["mature"] for x in arms.values())
            results.append({
                "experiment": name, "network": network, "metric": metric,
                "window_days": days, "variants": arms, "posterior": posteriors,
                "p_second_better_exploratory": probability,
                "coverage": {"assigned": total_assigned, "exposed": total_exposed,
                             "mature": total_mature,
                             "unexposed": total_assigned - total_exposed,
                             "pending_maturity": total_exposed - total_mature},
                "status": ("exploratory_only" if min(arms[a]["mature"],
                                                   arms[b]["mature"]) else "insufficient_outcomes")
            })
        return {"schema": 1, "mode": "offline_descriptive", "adaptive": False,
                "causal_claim_approved": False, "networks": sorted(NETWORKS),
                "studies": results}

    def markdown(self):
        lines = ["# Aprendizaje acumulado de contenido y comentarios", "",
                 "Datos locales; resultados exploratorios, no causalidad ni autorización de ejecución.",
                 "", "| Experimento | Red | Asignadas | Expuestas | Maduras | P(variante B > A)* |",
                 "|---|---|---:|---:|---:|---:|"]
        for row in self.report()["studies"]:
            c = row["coverage"]
            lines.append(f"| {row['experiment']} | {row['network']} | "
                         f"{c['assigned']} | {c['exposed']} | {c['mature']} | "
                         f"{row['p_second_better_exploratory']:.3f} |")
        lines += ["", "* Beta(1,1), Monte Carlo determinista; comparación descriptiva.",
                  "Sin atribución validada, ventanas completas ni aleatorización auditada, no decidir ganadores.",
                  "Los no expuestos y los pendientes no son fracasos. Sin agregación entre redes.",
                  ""]
        return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Panel offline de experimentos")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    # La CLI lee una base existente, NUNCA crea una base vacía accidentalmente.
    if not args.db.is_file():
        parser.error("base de experimentos inexistente")
    with ExperimentStore(args.db) as store:
        result = store.report() if args.format == "json" else store.markdown()
    print(json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, dict) else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
