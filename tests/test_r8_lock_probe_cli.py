"""R8: ensayo CLI real de exclusión; no ejecuta rondas ni Scheduler."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "tools" / "round_queue.py"
CONTROL = ROOT / "tools" / "rondas_control.ps1"


class LockProbeCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def command(self, hold="0"):
        return [
            sys.executable, "-u", str(QUEUE), "--only", "web", "--dry",
            "--lock-probe", self.temp.name, "--probe-hold", hold,
        ]

    def test_two_real_cli_processes_have_single_owner(self):
        """Ejercita main(), no un import ni una implementación de juguete."""
        first = subprocess.Popen(
            self.command("2"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            self.assertEqual(first.stdout.readline().strip(), "[probe] HELD")
            second = subprocess.run(
                self.command(), capture_output=True, text=True,
                encoding="utf-8", timeout=12,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), "[probe] BLOCKED")
            first.communicate(timeout=12)
            self.assertEqual(first.returncode, 0)
            third = subprocess.run(
                self.command(), capture_output=True, text=True,
                encoding="utf-8", timeout=12,
            )
            self.assertEqual(third.returncode, 0, third.stderr)
            self.assertEqual(third.stdout.strip(), "[probe] HELD")
            self.assertFalse(Path(self.temp.name, "cola_rondas_web.lock").exists())
            self.assertFalse(Path(self.temp.name, "cola_rondas_web.lock.reclaim").exists())
        finally:
            if first.poll() is None:
                first.kill()
                first.communicate(timeout=5)

    def test_probe_cannot_write_repository_or_skip_dry_guard(self):
        cmd = self.command()
        cmd[cmd.index("--lock-probe") + 1] = str(ROOT)
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=12,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("directorio operativo prohibido", result.stdout)
        cmd = self.command()
        cmd.remove("--dry")
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", timeout=12,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requiere --dry", result.stdout)
        self.assertFalse(Path(self.temp.name, "cola_rondas_web.lock").exists())

    @unittest.skipUnless(os.name == "nt", "limpieza PowerShell solo en Windows")
    def test_parar_reclaim_command_cleans_only_temp_marker(self):
        """Ejecuta la línea real de limpieza de PARAR sobre una copia temporal.

        No invoca PARAR_RONDAS, Scheduler, procesos del repo ni Edge.
        """
        if shutil.which("powershell.exe") is None:
            self.skipTest("powershell.exe no disponible")
        lines = CONTROL.read_text(encoding="utf-8").splitlines()
        cleanup = next(
            i for i, line in enumerate(lines)
            if "Get-ChildItem $Op -Filter 'cola_rondas_*.lock.reclaim'" in line
        )
        guard = next(i for i, line in enumerate(lines)
                     if "if ($survivors.Count -gt 0)" in line)
        self.assertGreater(cleanup, guard, "PARAR limpia antes de comprobar vivos")
        marker = Path(self.temp.name, "cola_rondas_web.lock.reclaim")
        stable = Path(self.temp.name, "cola_rondas_web.lock.guard")
        other = Path(self.temp.name, "no_tocar.reclaim")
        for path in (marker, stable, other):
            path.write_text("fixture", encoding="ascii")
        escaped = self.temp.name.replace("'", "''")
        script = f"$Op = '{escaped}'; {lines[cleanup].strip()}"
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists())
        self.assertTrue(stable.exists())
        self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main()
