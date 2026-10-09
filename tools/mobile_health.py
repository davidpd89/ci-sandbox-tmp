"""Preflight local de Android/mobilecli sin tocar ninguna red social.

Requisitos externos:
  adb devices
  npm install -g mobilecli@1.0.17
  mobilecli server start

Uso:
  python tools/mobile_health.py
  python tools/mobile_health.py --device SERIAL
  python tools/mobile_health.py --probe-settings
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from mobile_client import (  # noqa: E402
    MobileCliClient,
    MobileCliError,
    walk_ui,
)


SETTINGS_PACKAGE = "com.android.settings"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=os.getenv("ANDROID_DEVICE_ID"))
    parser.add_argument(
        "--base-url",
        default=os.getenv("MOBILECLI_URL", "http://127.0.0.1:12000"),
    )
    parser.add_argument(
        "--probe-settings",
        action="store_true",
        help="abre Ajustes, lee su árbol de accesibilidad y vuelve a HOME",
    )
    args = parser.parse_args()

    client = MobileCliClient(base_url=args.base_url, device_id=args.device)
    try:
        server = client.server_info()
        version = str(server.get("version", ""))
        if version != "1.0.17":
            raise MobileCliError(
                f"esta PR está validada contra mobilecli 1.0.17 y responde {version!r}; "
                "instalar el pin documentado antes de probar"
            )
        device = client.select_device()
        info = client.device_info(device.id)
        print(f"OK mobilecli {version}")
        print(
            "OK Android físico: "
            f"{device.name or '[sin-nombre]'} | {device.model or '[sin-modelo]'} "
            f"| state={device.state or '[sin-state]'}"
        )
        android_version = info.get("version") or device.version
        if isinstance(android_version, str) and android_version:
            print(f"Android: {android_version}")

        if args.probe_settings:
            client.launch_app(SETTINGS_PACKAGE, device.id)
            time.sleep(1.0)
            tree = client.dump_ui(device.id)
            count = sum(1 for _ in walk_ui(tree))
            if count == 0:
                raise MobileCliError(
                    "Ajustes abrió pero device.dump.ui no expuso elementos; "
                    "revisar permisos/compatibilidad del Xiaomi"
                )
            print(f"OK control/UI: Ajustes expone {count} elemento(s)")
            client.press("HOME", device.id)
        else:
            foreground = client.foreground_app(device.id)
            package = (
                foreground.get("packageName")
                or foreground.get("bundleId")
                or foreground.get("id")
                or "[desconocido]"
            )
            print(f"Foreground: {package}")

        print("PRECHECK MÓVIL OK")
        return 0
    except MobileCliError as exc:
        print(f"PRECHECK MÓVIL FALLÓ: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
