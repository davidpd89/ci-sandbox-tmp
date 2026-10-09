import base64
import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import mobile_client as mc


class FakeRpc:
    def __init__(self):
        self.calls = []

    def __call__(self, _url, payload, _timeout):
        self.calls.append(payload)
        method = payload["method"]
        result = {
            "server.info": {"name": "mobilecli", "version": "1.0.17"},
            "devices.list": {
                "devices": [
                    {
                        "id": "xiaomi-1",
                        "name": "Xiaomi",
                        "model": "Test",
                        "platform": "android",
                        "state": "online",
                        "type": "real",
                        "version": "16",
                    }
                ]
            },
            "device.info": {
                "device": {
                    "id": "xiaomi-1",
                    "name": "Xiaomi",
                    "model": "Test",
                    "platform": "android",
                    "state": "online",
                    "type": "real",
                    "version": "16",
                    "screenSize": {"width": 1080, "height": 2400, "scale": 1},
                }
            },
            "device.apps.list": [{"packageName": "com.example"}],
            "device.apps.foreground": {"packageName": "com.example"},
            "device.apps.launch": {"launched": True},
            "device.apps.terminate": {"terminated": True},
            "device.url": {"success": True},
            "device.clipboard.get": {"text": "https://www.tiktok.com/@foo/video/1"},
            "device.clipboard.set": {"success": True},
            "server.shutdown": {"success": True},
            "device.dump.ui": {
                "elements": [
                    {
                        "type": "Frame",
                        "rect": {"x": 0, "y": 0, "width": 100, "height": 200},
                        "children": [
                            {
                                "type": "Button",
                                "text": "Buscar",
                                "identifier": "search",
                                "rect": {"x": 10, "y": 20, "width": 40, "height": 20},
                            }
                        ],
                    }
                ]
            },
            "device.io.tap": {"success": True},
            "device.io.text": {"success": True},
            "device.io.swipe": {"success": True},
            "device.io.button": {"success": True},
            "device.screenshot": {
                "format": "png",
                "data": "data:image/png;base64,"
                + base64.b64encode(b"png").decode("ascii"),
            },
        }[method]
        return {"jsonrpc": "2.0", "id": payload["id"], "result": result}


class MobileClientTests(unittest.TestCase):
    def setUp(self):
        self.rpc = FakeRpc()
        self.client = mc.MobileCliClient(transport=self.rpc)

    def test_selects_single_android_physical_device(self):
        device = self.client.select_device()
        self.assertEqual(device.id, "xiaomi-1")
        call = self.rpc.calls[-1]
        self.assertEqual(call["method"], "devices.list")
        self.assertEqual(call["params"]["platform"], "android")
        self.assertEqual(call["params"]["type"], "real")
        self.assertEqual(device.state, "online")
        self.assertEqual(device.device_type, "real")
        self.assertEqual(device.version, "16")

    def test_server_info_and_device_info_match_1017_envelopes(self):
        self.assertEqual(self.client.server_info()["version"], "1.0.17")
        info = self.client.device_info()
        self.assertEqual(info["version"], "16")
        self.assertEqual(info["screenSize"]["width"], 1080)

    def test_selected_device_is_cached_between_rpc_calls(self):
        self.client.select_device()
        self.client.device_info()
        methods = [call["method"] for call in self.rpc.calls]
        self.assertEqual(methods.count("devices.list"), 1)
        self.assertEqual(methods[-1], "device.info")

    def test_refuses_ambiguous_device_selection(self):
        def transport(_url, payload, _timeout):
            devices = {
                "devices": [
                    {
                        "id": "a", "name": "A", "model": "A",
                        "platform": "android", "state": "online",
                        "type": "real", "version": "16",
                    },
                    {
                        "id": "b", "name": "B", "model": "B",
                        "platform": "android", "state": "online",
                        "type": "real", "version": "16",
                    },
                ]
            }
            return {"jsonrpc": "2.0", "id": payload["id"], "result": devices}

        client = mc.MobileCliClient(transport=transport)
        with self.assertRaises(mc.MobileDeviceSelectionError):
            client.select_device()

    def test_devices_accepts_legacy_direct_list_shape_but_still_requires_real_android(self):
        def transport(_url, payload, _timeout):
            result = [
                {
                    "id": "real", "name": "Xiaomi", "model": "X",
                    "platform": "android", "state": "online",
                    "type": "real", "version": "16",
                },
                {
                    "id": "emu", "name": "Emulator", "model": "AVD",
                    "platform": "android", "state": "online",
                    "type": "emulator", "version": "16",
                },
            ]
            return {"jsonrpc": "2.0", "id": payload["id"], "result": result}

        client = mc.MobileCliClient(transport=transport)
        devices = client.devices()
        self.assertEqual([device.id for device in devices], ["real"])

    def test_nested_ui_search_and_unique_tap_use_element_center(self):
        tree = self.client.dump_ui()
        matches = mc.find_elements(tree, text="buscar")
        self.assertEqual(len(matches), 1)
        self.assertEqual(mc.element_center(matches[0]), (30, 30))
        mc.tap_unique(self.client, tree, text="Buscar")
        call = self.rpc.calls[-1]
        self.assertEqual(call["method"], "device.io.tap")
        self.assertEqual(call["params"]["x"], 30)
        self.assertEqual(call["params"]["y"], 30)

    def test_screenshot_decodes_data_uri(self):
        self.assertEqual(self.client.screenshot_bytes(), b"png")

    def test_url_clipboard_and_shutdown_rpc(self):
        self.client.open_url("https://www.tiktok.com/@foo/video/1")
        self.assertEqual(self.rpc.calls[-1]["method"], "device.url")
        self.client.clipboard_set("")
        self.assertEqual(self.rpc.calls[-1]["method"], "device.clipboard.set")
        self.assertIn("tiktok.com", self.client.clipboard_get())
        self.client.server_shutdown()
        self.assertEqual(self.rpc.calls[-1]["method"], "server.shutdown")

    def test_open_url_rejects_non_http_schemes(self):
        with self.assertRaises(ValueError):
            self.client.open_url("intent://unsafe")

    def test_rpc_errors_fail_closed(self):
        def transport(_url, payload, _timeout):
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {"code": -32000, "message": "boom"},
            }

        client = mc.MobileCliClient(transport=transport)
        with self.assertRaisesRegex(mc.MobileCliProtocolError, "boom"):
            client.devices()

    def test_rpc_error_includes_server_detail(self):
        def transport(_url, payload, _timeout):
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "error": {"code": -32000, "message": "Server error", "data": "INJECT_EVENTS"},
            }

        client = mc.MobileCliClient(transport=transport)
        with self.assertRaisesRegex(mc.MobileCliProtocolError, "INJECT_EVENTS"):
            client.devices()

    def test_dump_ui_uses_long_timeout(self):
        seen = []

        def transport(_url, payload, timeout):
            seen.append((payload["method"], timeout))
            result = {"devices": [{"id": "A", "platform": "android", "type": "real",
                                   "state": "online"}]} if payload["method"] == "devices.list" else {}
            return {"jsonrpc": "2.0", "id": payload["id"], "result": result}

        client = mc.MobileCliClient(transport=transport)
        client.dump_ui()
        self.assertEqual(dict(seen)["device.dump.ui"], mc.DUMP_UI_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
