"""Contrato documental de #69. No abre redes ni escribe datos operativos."""
from pathlib import Path
import ast

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEEME = ROOT / "SISTEMA_DIARIO_INFOGENERAL" / "LEEME_CONTINUAR.md"
RUNBOOK = ROOT / "00_OPERATIVO" / "RUNBOOK_OPERACION_VERIFICADA.md"
REDES = ("BLUESKY", "MASTODON", "X", "THREADS", "FACEBOOK",
         "PINTEREST", "REDDIT", "TIKTOK", "INSTAGRAM")


@pytest.fixture(scope="module")
def docs():
    if not LEEME.is_file() or not RUNBOOK.is_file():
        pytest.skip("El espejo público saneado no exporta los documentos; validar en repo privado")
    return LEEME.read_text(encoding="utf-8"), RUNBOOK.read_text(encoding="utf-8")


def test_topologia_en_runbook(docs):
    _guia, runbook = docs
    for termino in ("WEB", "API", "MÓVIL", "Reddit", "Instagram"):
        assert termino in runbook


def test_leeme_remite_al_runbook(docs):
    guia, _runbook = docs
    assert "## 0. Precedencia y auditoría de consistencia" in guia
    assert "RUNBOOK_OPERACION_VERIFICADA.md" in guia
    assert "Instagram comparte condicionalmente la cadena MÓVIL" in guia
    assert "run_round(\"instagram\")" in guia
    assert "\r" not in guia and "\t" not in guia, "LEEME contiene controles ocultos en rutas Windows"


def test_comandos_diferenciados_de_acciones(docs):
    _guia, runbook = docs
    for comando in ("stats --readonly", "round_canaries.py --check-only",
                    "round_queue.py --only web --dry"):
        assert comando in runbook
    for comando_peligroso in ("INICIAR_RONDAS.bat", "PARAR_RONDAS.bat",
                               "VER_ESTADO_RONDAS.bat", "circuit_breaker.py RED reset"):
        assert comando_peligroso in runbook
    assert "Excluidos de pruebas de solo lectura" in runbook



def test_matriz_no_clasifica_ejecucion_como_lectura(docs):
    _guia, runbook = docs
    rows = [line.split("|")[1:3] for line in runbook.splitlines()
            if line.startswith("| ") and not line.startswith("| Comando")]
    assert len(rows) == 8, "La matriz debe inventariar los ocho comandos explícitos"
    commands = [cells[0].strip() for cells in rows]
    assert not any("INICIAR_RONDAS" in cmd or "PARAR_RONDAS" in cmd
                   or "VER_ESTADO_RONDAS" in cmd or " reset" in cmd
                   for cmd in commands)
    assert any("--readonly" in cmd for cmd in commands)
    assert any("--lock-probe DIRECTORIO_TEMP" in cmd for cmd in commands)


def test_lanzador_de_estado_se_corresponde_con_checkout(docs):
    _guia, runbook = docs
    lanzador = ROOT / "SISTEMA_DIARIO_INFOGENERAL" / "VER_ESTADO_RONDAS.bat"
    code = lanzador.read_text(encoding="utf-8")
    assert "VER_ESTADO_RONDAS.bat" in runbook
    if "daily_review.py" in code:
        assert "escribe" in runbook
    else:
        assert "estado_rondas.py" in code
        assert (ROOT / "tools" / "estado_rondas.py").is_file()
        assert "#86" in runbook


def test_fallback_instagram_corresponde_al_codigo(docs):
    _guia, runbook = docs
    source = (ROOT / "tools" / "round_queue.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    phone = next(node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == "phone_chain")
    calls = [node for node in ast.walk(phone) if isinstance(node, ast.Call)]
    names = {node.func.id for node in calls if isinstance(node.func, ast.Name)}
    assert "instagram_due" in names
    assert any(isinstance(node.func, ast.Name) and node.func.id == "run_round"
               and node.args and isinstance(node.args[0], ast.Constant)
               and node.args[0].value == "instagram" for node in calls)
    assert "fallback" in runbook.lower()




def test_leeme_edicion_directa_sin_patches_que_envejecen(docs):
    guia, _runbook = docs
    assert "## 0. Precedencia y auditoría de consistencia" in guia
    assert "RUNBOOK_OPERACION_VERIFICADA.md" in guia
    assert "Instagram comparte condicionalmente la cadena MÓVIL" in guia
    assert 'run_round("instagram")' in guia
    assert chr(13) not in guia and chr(9) not in guia, "Rutas con caracteres de control reales"
    for name in ("PR69_LEEME_APLICAR.patch",
                 "PR69_LEEME_CORRECCION_MOVIL.patch",
                 "PR69_LEEME_SANEAMIENTO_RUTAS.patch"):
        assert not (ROOT / "00_OPERATIVO" / name).exists(), (
            "No reaplicar parches históricos al LEEME: " + name)


@pytest.mark.parametrize("red", REDES)
def test_estados_advierten_historico(docs, red):
    ruta = ROOT / f"SISTEMA_DIARIO_{red}" / "ESTADO.md"
    assert ruta.is_file(), f"Falta estado {red}"
    contenido = ruta.read_text(encoding="utf-8")
    assert "Auditoría de vigencia PR #69 (09/10/2026)" in contenido
    assert "RUNBOOK_OPERACION_VERIFICADA.md" in contenido
    assert "no el estado de hoy" in contenido



def test_readme_no_confunde_publicacion_manual_y_automatica(docs):
    _guia, _runbook = docs
    readme = (ROOT / "00_OPERATIVO" / "README.md").read_text(encoding="utf-8")
    assert "flujo **mixto**" in readme
    assert "content_publisher.py" in readme
    assert "auto_publicacion.json" in readme
    assert (ROOT / "tools" / "content_publisher.py").is_file()
    assert "No ejecutar `--apply` como prueba" in readme


def test_rutas_de_inventario(docs):
    for relative in (
        "tools/round_queue.py", "tools/reply_queue.py",
        "tools/round_canaries.py", "tools/instagram_interact.py",
        "SISTEMA_DIARIO_INFOGENERAL/INICIAR_RONDAS.bat",
        "SISTEMA_DIARIO_INFOGENERAL/PARAR_RONDAS.bat",
        "SISTEMA_DIARIO_INFOGENERAL/VER_ESTADO_RONDAS.bat",
    ):
        assert (ROOT / relative).is_file(), relative
