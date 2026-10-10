import os
import tempfile

# La rampa de volumen de Bluesky (tools/volume_ramp.py) cambia de etapa sola: los tests usan siempre una ruta inexistente = etapa 0.
os.environ.setdefault("RRSS_RAMP_PATH", os.path.join(tempfile.gettempdir(), "rrss_test_no_ramp.json"))

# La reserva de candidatos (tools/bluesky_pool.py) y su tabla `touch` (primera fuente por handle) viven en SQLite: los tests nunca tocan la real.
os.environ.setdefault("RRSS_POOL_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_pool_"), "pool.sqlite3"))

os.environ.setdefault("RRSS_RAMP_PATH_MASTODON", os.path.join(tempfile.gettempdir(), "rrss_test_no_ramp_mastodon.json"))
os.environ.setdefault("RRSS_MASTODON_POOL_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_mpool_"), "pool.sqlite3"))

os.environ.setdefault("RRSS_RAMP_PATH_THREADS", os.path.join(tempfile.gettempdir(), "rrss_test_no_ramp_threads.json"))
os.environ.setdefault("RRSS_THREADS_POOL_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_tpool_"), "pool.sqlite3"))

# El registro de entradas (quien nos da like/comenta) es dato real: los tests nunca lo tocan.
os.environ.setdefault("RRSS_INBOUND_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_inbound_"), "inbound.csv"))

# Los tests de los ejecutores usan textos de ejemplo: la barrera de procedencia (reply_writer.require_gpt) se prueba aparte quitando esta variable.
os.environ.setdefault("RRSS_ALLOW_UNMARKED_TEXT", "1")

# El registro de textos escritos por ChatGPT (reply_writer.mark_gpt) es dato real: los tests escriben en uno temporal.
os.environ.setdefault("RRSS_GPT_TEXTS_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_gpt_texts_"), "gpt_texts.json"))


# Protección de red para el propio pytest y los Python hijos de los tests.
# Nunca tocar esto en entornos productivos: se ejecuta solo dentro de pytest.
import pathlib
import sys

_guard_dir = str(pathlib.Path(__file__).resolve().parent / "offline_guard")
sys.path.insert(0, _guard_dir)
from test_network_guard import install as _install_network_guard

_install_network_guard()  # ANTES de recoger tests

# Los Python hijos que heredan el entorno cargan sitecustomize automáticamente.
# Conservamos el PYTHONPATH previo, sin imponer hooks a producción.
_previous_path = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = (
    _guard_dir + (os.pathsep + _previous_path if _previous_path else "")
)

# Un HTTPS_PROXY apuntando a localhost escaparía del filtro de sockets: el
# proceso de pruebas no necesita intermediarios. Requests usa estas variables.
for _proxy_name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                    "http_proxy", "https_proxy", "all_proxy", "no_proxy"):
    os.environ.pop(_proxy_name, None)

# Los cortacircuitos productivos son estado real. La barrera de escritura
# de los publicadores independientes debe leer solo el árbol de pruebas.
os.environ["RRSS_BREAKER_TEST_MODE"] = "1"
os.environ["RRSS_BREAKER_ROOT"] = tempfile.mkdtemp(prefix="rrss_test_breaker_")

# El descanso de seguridad de TikTok (tools/tiktok_safety.py) es estado real: los tests nunca lo leen ni lo escriben.
os.environ.setdefault("RRSS_TIKTOK_COOLDOWN_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_tt_cd_"), "bulk_cooldown.json"))
