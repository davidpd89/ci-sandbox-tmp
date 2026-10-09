"""Cliente mínimo para el servidor HTTP/JSON-RPC de mobilecli.

No instala herramientas, no abre apps por sí solo y no conoce redes sociales.
El servidor esperado es `mobilecli server start --listen 127.0.0.1:12000`.

Referencia upstream:
https://github.com/mobile-next/mobilecli/blob/1.0.17/docs/openrpc.json
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterable


DEFAULT_BASE_URL = "http://127.0.0.1:12000"
DUMP_UI_TIMEOUT = 60.0


class MobileCliError(RuntimeError):
    """Error base de la capa mobilecli."""


class MobileCliTransportError(MobileCliError):
    """No se pudo hablar con el servidor local de mobilecli."""


class MobileCliProtocolError(MobileCliError):
    """Respuesta JSON-RPC inválida o error devuelto por mobilecli."""


class MobileDeviceSelectionError(MobileCliError):
    """No puede seleccionarse un Android físico de forma inequívoca."""


Transport = Callable[[str, dict[str, Any], float], dict[str, Any]]


def _http_transport(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # Endpoint estrictamente local: no heredar proxies HTTP del entorno.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as exc:
        raise MobileCliTransportError(
            f"mobilecli no responde en {url}; ejecutar "
            "`mobilecli server start --listen 127.0.0.1:12000`"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MobileCliProtocolError("mobilecli devolvió JSON inválido") from exc
    if not isinstance(data, dict):
        raise MobileCliProtocolError("mobilecli devolvió una respuesta JSON-RPC no válida")
    return data


@dataclass(frozen=True)
class MobileDevice:
    id: str
    name: str
    model: str
    platform: str
    state: str
    device_type: str
    version: str

    @classmethod
    def from_rpc(cls, data: dict[str, Any]) -> "MobileDevice":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            model=str(data.get("model", "")),
            platform=str(data.get("platform", "")),
            state=str(data.get("state", data.get("status", ""))),
            device_type=str(data.get("type", "")),
            version=str(data.get("version", "")),
        )


class MobileCliClient:
    """Cliente síncrono y sin dependencias externas para mobilecli 1.x."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 15.0,
        device_id: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.device_id = device_id
        self._transport = transport or _http_transport
        self._request_id = 0
        self._selected_device: MobileDevice | None = None

    @property
    def rpc_url(self) -> str:
        return f"{self.base_url}/rpc"

    def _rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        response = self._transport(self.rpc_url, payload, timeout or self.timeout)
        if response.get("jsonrpc") != "2.0":
            raise MobileCliProtocolError("versión JSON-RPC ausente o inesperada")
        if response.get("id") != self._request_id:
            raise MobileCliProtocolError("id JSON-RPC no coincide con la petición")
        if "error" in response and response["error"] is not None:
            error = response["error"]
            if isinstance(error, dict):
                code = error.get("code")
                message = error.get("message", "error sin mensaje")
                detail = error.get("data")
                suffix = f" | {detail}" if detail else ""
                raise MobileCliProtocolError(f"mobilecli RPC {method}: {code}: {message}{suffix}")
            raise MobileCliProtocolError(f"mobilecli RPC {method}: {error}")
        if "result" not in response:
            raise MobileCliProtocolError(f"mobilecli RPC {method}: falta result")
        return response["result"]

    def server_info(self) -> dict[str, Any]:
        result = self._rpc("server.info")
        if not isinstance(result, dict):
            raise MobileCliProtocolError("server.info no devolvió un objeto")
        if result.get("name") not in (None, "mobilecli"):
            raise MobileCliProtocolError(
                f"servidor inesperado en {self.rpc_url}: {result.get('name')!r}"
            )
        return result

    def devices(self, *, platform: str = "android") -> list[MobileDevice]:
        result = self._rpc(
            "devices.list",
            {"includeOffline": False, "platform": platform, "type": "real"},
        )
        # mobilecli 1.0.17 devuelve {"devices": [...]}; el OpenRPC de esa
        # versión aún describe una lista directa. Aceptamos ambas formas.
        if isinstance(result, dict):
            result = result.get("devices")
        if not isinstance(result, list):
            raise MobileCliProtocolError("devices.list no devolvió devices[]")
        devices = [
            MobileDevice.from_rpc(item)
            for item in result
            if isinstance(item, dict) and item.get("id")
        ]
        return [
            device for device in devices
            if device.platform == platform
            and device.device_type == "real"
            and device.state == "online"
        ]

    def select_device(self, device_id: str | None = None) -> MobileDevice:
        candidates = self.devices(platform="android")
        wanted = device_id or self.device_id
        if wanted:
            matches = [device for device in candidates if device.id == wanted]
            if len(matches) != 1:
                raise MobileDeviceSelectionError(
                    f"Android {wanted!r} no está disponible o no está autorizado por ADB"
                )
            self._selected_device = matches[0]
            return matches[0]
        if len(candidates) != 1:
            raise MobileDeviceSelectionError(
                f"se esperaba exactamente 1 Android físico disponible y hay {len(candidates)}; "
                "usar --device/ANDROID_DEVICE_ID"
            )
        self._selected_device = candidates[0]
        return candidates[0]

    def _device(self, device_id: str | None) -> str:
        wanted = device_id or self.device_id
        if self._selected_device is not None:
            if wanted is None or self._selected_device.id == wanted:
                return self._selected_device.id
        return self.select_device(wanted).id

    def device_info(self, device_id: str | None = None) -> dict[str, Any]:
        result = self._rpc("device.info", {"deviceId": self._device(device_id)})
        if not isinstance(result, dict):
            raise MobileCliProtocolError("device.info no devolvió un objeto")
        # mobilecli 1.0.17 envuelve FullDeviceInfo en {"device": {...}}.
        device = result.get("device")
        if isinstance(device, dict):
            return device
        return result

    def apps(self, device_id: str | None = None) -> list[dict[str, Any]]:
        result = self._rpc("device.apps.list", {"deviceId": self._device(device_id)})
        if not isinstance(result, list):
            raise MobileCliProtocolError("device.apps.list no devolvió una lista")
        return [item for item in result if isinstance(item, dict)]

    def foreground_app(self, device_id: str | None = None) -> dict[str, Any]:
        result = self._rpc("device.apps.foreground", {"deviceId": self._device(device_id)})
        if not isinstance(result, dict):
            raise MobileCliProtocolError("device.apps.foreground no devolvió un objeto")
        return result

    def launch_app(self, bundle_id: str, device_id: str | None = None) -> dict[str, Any]:
        if not bundle_id or any(ch.isspace() for ch in bundle_id):
            raise ValueError("bundle_id inválido")
        result = self._rpc(
            "device.apps.launch",
            {"deviceId": self._device(device_id), "bundleId": bundle_id},
        )
        if not isinstance(result, dict):
            raise MobileCliProtocolError("device.apps.launch no devolvió un objeto")
        return result

    def terminate_app(self, bundle_id: str, device_id: str | None = None) -> dict[str, Any]:
        result = self._rpc(
            "device.apps.terminate",
            {"deviceId": self._device(device_id), "bundleId": bundle_id},
        )
        if not isinstance(result, dict):
            raise MobileCliProtocolError("device.apps.terminate no devolvió un objeto")
        return result

    def open_url(self, url: str, device_id: str | None = None) -> Any:
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError("url móvil inválida")
        return self._rpc(
            "device.url",
            {"deviceId": self._device(device_id), "url": url},
        )

    def clipboard_get(self, device_id: str | None = None) -> str:
        result = self._rpc(
            "device.clipboard.get",
            {"deviceId": self._device(device_id)},
        )
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise MobileCliProtocolError("device.clipboard.get no devolvió text")
        return result["text"]

    def clipboard_set(self, text: str, device_id: str | None = None) -> Any:
        if not isinstance(text, str):
            raise ValueError("clipboard_set exige texto")
        return self._rpc(
            "device.clipboard.set",
            {"deviceId": self._device(device_id), "text": text},
        )

    def server_shutdown(self) -> Any:
        return self._rpc("server.shutdown")

    def dump_ui(self, device_id: str | None = None, *, full: bool = False) -> dict[str, Any]:
        result = self._rpc(
            "device.dump.ui",
            {"deviceId": self._device(device_id), "format": "json", "full": full},
            # En el Xiaomi real el dump UI tarda 3-12 s (agente UiAutomation en frío).
            timeout=max(self.timeout, DUMP_UI_TIMEOUT),
        )
        if not isinstance(result, dict):
            raise MobileCliProtocolError("device.dump.ui no devolvió un objeto")
        return result

    def tap(self, x: int, y: int, device_id: str | None = None) -> Any:
        return self._rpc(
            "device.io.tap",
            {"deviceId": self._device(device_id), "x": int(x), "y": int(y)},
        )

    def type_text(self, text: str, device_id: str | None = None) -> Any:
        if not isinstance(text, str) or not text:
            raise ValueError("text debe ser una cadena no vacía")
        return self._rpc(
            "device.io.text",
            {"deviceId": self._device(device_id), "text": text},
        )

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        *,
        duration_ms: int | None = None,
        device_id: str | None = None,
    ) -> Any:
        params: dict[str, Any] = {
            "deviceId": self._device(device_id),
            "x1": int(x1),
            "y1": int(y1),
            "x2": int(x2),
            "y2": int(y2),
        }
        if duration_ms is not None:
            if duration_ms <= 0:
                raise ValueError("duration_ms debe ser > 0")
            params["duration"] = int(duration_ms)
        return self._rpc("device.io.swipe", params)

    def press(self, button: str, device_id: str | None = None) -> Any:
        if not button or any(ch.isspace() for ch in button):
            raise ValueError("button inválido")
        return self._rpc(
            "device.io.button",
            {"deviceId": self._device(device_id), "button": button},
        )

    def screenshot_bytes(
        self,
        device_id: str | None = None,
        *,
        max_size: int = 1200,
    ) -> bytes:
        result = self._rpc(
            "device.screenshot",
            {
                "deviceId": self._device(device_id),
                "format": "png",
                "maxSize": int(max_size),
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("data"), str):
            raise MobileCliProtocolError("device.screenshot no devolvió data")
        data = result["data"]
        encoded = data.split(",", 1)[1] if "," in data else data
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise MobileCliProtocolError("screenshot base64 inválido") from exc


def walk_ui(tree: Any) -> Iterable[dict[str, Any]]:
    """Recorre una jerarquía mobilecli sin asumir una forma raíz concreta."""
    if isinstance(tree, list):
        for item in tree:
            yield from walk_ui(item)
        return
    if not isinstance(tree, dict):
        return
    if isinstance(tree.get("rect"), dict):
        yield tree
    children = tree.get("children")
    if isinstance(children, list):
        for child in children:
            yield from walk_ui(child)
    else:
        for key in ("elements", "root", "roots"):
            if key in tree:
                yield from walk_ui(tree[key])


def element_texts(element: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("text", "label", "name", "value", "placeholder", "contentDescription"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


def find_elements(
    tree: Any,
    *,
    text: str | None = None,
    identifier: str | None = None,
    case_sensitive: bool = False,
) -> list[dict[str, Any]]:
    """Busca coincidencias exactas; nunca selecciona silenciosamente la primera."""
    if text is None and identifier is None:
        raise ValueError("indicar text o identifier")
    wanted_text = text if case_sensitive or text is None else text.casefold()
    wanted_id = identifier if case_sensitive or identifier is None else identifier.casefold()
    matches: list[dict[str, Any]] = []
    for element in walk_ui(tree):
        ok = True
        if wanted_text is not None:
            texts = element_texts(element)
            if not case_sensitive:
                texts = [value.casefold() for value in texts]
            ok = wanted_text in texts
        if ok and wanted_id is not None:
            value = element.get("identifier")
            if not isinstance(value, str):
                ok = False
            else:
                current = value if case_sensitive else value.casefold()
                ok = current == wanted_id
        if ok:
            matches.append(element)
    return matches


def element_center(element: dict[str, Any]) -> tuple[int, int]:
    rect = element.get("rect")
    if not isinstance(rect, dict):
        raise MobileCliProtocolError("elemento sin rect")
    try:
        x = float(rect["x"])
        y = float(rect["y"])
        width = float(rect["width"])
        height = float(rect["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MobileCliProtocolError("rect de elemento inválido") from exc
    if width <= 0 or height <= 0:
        raise MobileCliProtocolError("elemento sin área pulsable")
    return round(x + width / 2), round(y + height / 2)


def tap_unique(
    client: MobileCliClient,
    tree: Any,
    *,
    text: str | None = None,
    identifier: str | None = None,
    device_id: str | None = None,
) -> Any:
    matches = find_elements(tree, text=text, identifier=identifier)
    if len(matches) != 1:
        target = f"text={text!r}" if text is not None else f"identifier={identifier!r}"
        raise MobileCliError(
            f"objetivo móvil ambiguo o ausente ({target}): {len(matches)} coincidencias"
        )
    x, y = element_center(matches[0])
    return client.tap(x, y, device_id=device_id)
