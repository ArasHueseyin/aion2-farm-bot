import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aion2_farm.control import ControlServer, call_app
from aion2_farm.mcp_server import dispatch


class ControlTests(unittest.TestCase):
    def test_authenticated_local_roundtrip_and_session_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            server = ControlServer(lambda method, args: {"method":method, "key":args.get("key")}, path)
            try:
                result = call_app("test", {"key":"1"}, path=path)
                self.assertEqual(result, {"method":"test", "key":"1"})
                self.assertEqual(server.http.server_address[0], "127.0.0.1")
            finally:
                server.close()
            self.assertFalse(path.exists())

    def test_missing_or_wrong_token_cannot_call_handler(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            server = ControlServer(lambda method, args: calls.append(method), Path(directory) / "session.json")
            try:
                for token in ("", "Bearer wrong"):
                    request = Request(f"http://127.0.0.1:{server.http.server_port}/rpc", data=b'{"method":"test"}',
                                      headers={"Authorization":token})
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request, timeout=2)
                    self.assertEqual(error.exception.code, 403)
                self.assertEqual(calls, [])
            finally:
                server.close()

    def test_app_errors_are_returned_without_exposing_connection_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            def fail(method, args):
                raise ValueError("Game not foreground")
            server = ControlServer(fail, path)
            try:
                with self.assertRaisesRegex(RuntimeError, "Game not foreground"):
                    call_app("test", path=path)
            finally:
                server.close()


class McpProtocolTests(unittest.TestCase):
    def test_initialize_and_list_real_tools(self):
        initialized = dispatch({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{"protocolVersion":"2025-11-25"}})
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-11-25")
        listed = dispatch({"jsonrpc":"2.0", "id":2, "method":"tools/list"})
        self.assertEqual({tool["name"] for tool in listed["result"]["tools"]},
                         {"farm_status", "farm_stop", "farm_test_input", "farm_capture_hud"})

    def test_notifications_have_no_response(self):
        self.assertIsNone(dispatch({"jsonrpc":"2.0", "method":"notifications/initialized"}))

    def test_tool_arguments_and_live_preview_flag_reach_app_unchanged(self):
        calls=[]
        def caller(method, arguments):
            calls.append((method, arguments))
            return {"started":True}
        response=dispatch({"jsonrpc":"2.0", "id":3, "method":"tools/call", "params":{
            "name":"farm_test_input", "arguments":{"key":"leftmouse", "preview":False, "seconds":1}}}, caller)
        self.assertEqual(calls, [("test", {"key":"leftmouse", "preview":False, "seconds":1})])
        self.assertNotIn("isError",response["result"])

    def test_capture_returns_native_mcp_image_block(self):
        result=dispatch({"jsonrpc":"2.0", "id":4, "method":"tools/call", "params":{"name":"farm_capture_hud"}},
                        lambda method, arguments:{"original_size":[100,100], "image":"imagebytes"})
        self.assertEqual(result["result"]["content"][1], {"type":"image", "mimeType":"image/png", "data":"imagebytes"})

    def test_app_failure_is_a_tool_error(self):
        def fail(method, args):
            raise RuntimeError("No active MCP app")
        result=dispatch({"jsonrpc":"2.0", "id":5, "method":"tools/call", "params":{"name":"farm_status"}}, fail)
        self.assertTrue(result["result"]["isError"])

    def test_unknown_methods_do_not_reach_app(self):
        called=[]
        result=dispatch({"jsonrpc":"2.0", "id":6, "method":"run_code"}, lambda *args:called.append(args))
        self.assertEqual(result["error"]["code"],-32601)
        self.assertEqual(called,[])


if __name__ == "__main__":
    unittest.main()
