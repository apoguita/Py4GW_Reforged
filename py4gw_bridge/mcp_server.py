import argparse
import json
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

if __package__:
    from .transport import recv_json_message
    from .transport import send_json_message
else:
    from transport import recv_json_message
    from transport import send_json_message


SERVER_NAME = "py4gw-bridge-mcp"
SERVER_VERSION = "0.1.0"
SUPPORTED_MCP_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)
LOG_PATH = Path(__file__).with_name("py4gw_mcp_server.log")
STDIO_MODE = "auto"


def _log_stderr(message: str) -> None:
    print(f"[py4gw-mcp] {message}", file=sys.stderr, flush=True)


def _log_debug(message: str) -> None:
    _log_stderr(message)
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{message}\n")
    except Exception:
        pass


def _daemon_request(
    host: str,
    port: int,
    command: str,
    params: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    req = {
        "type": "request",
        "request_id": uuid.uuid4().hex,
        "command": command,
        "params": params or {},
    }
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        send_json_message(sock, req)
        return recv_json_message(sock, timeout=timeout)
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _read_stdio_message() -> dict[str, Any] | None:
    global STDIO_MODE
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            _log_debug("stdin eof")
            return None
        _log_debug(f"stdin line={line!r}")
        stripped = line.strip()
        if stripped.startswith(b"{"):
            STDIO_MODE = "jsonl"
            payload = json.loads(stripped.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("MCP payload must be an object")
            return payload
        if line in {b"\r\n", b"\n"}:
            break
        raw = line.decode("utf-8").strip()
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    content_length = int(headers.get("content-length") or 0)
    _log_debug(f"stdin headers={headers!r}")
    if content_length <= 0:
        _log_debug("stdin invalid content-length")
        return None
    body = sys.stdin.buffer.read(content_length)
    _log_debug(f"stdin body-bytes={len(body)}")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MCP payload must be an object")
    return payload


def _write_stdio_message(payload: dict[str, Any]) -> None:
    global STDIO_MODE
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    _log_debug(
        f"send mode={STDIO_MODE!r} id={payload.get('id')!r} keys={sorted(payload.keys())!r} bytes={len(raw)}"
    )
    if STDIO_MODE == "jsonl":
        sys.stdout.buffer.write(raw + b"\n")
    else:
        header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def _make_jsonrpc_result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _make_jsonrpc_error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_list() -> list[dict[str, Any]]:
    target_schema = {
        "type": "object",
        "properties": {
            "hwnd": {"type": "integer"},
            "pid": {"type": "integer"},
        },
        "minProperties": 1,
        "additionalProperties": False,
    }
    return [
        {
            "name": "list_clients",
            "description": "List connected Py4GW bridge clients.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "list_namespaces",
            "description": "List bridge namespaces and namespace metadata for a target client.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "list_commands",
            "description": "List bridge command metadata for a target client.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "describe_runtime",
            "description": "Get normalized runtime metadata for a target client.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "get_map_state",
            "description": "Get normalized map state for a target client.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "get_player_state",
            "description": "Get normalized player state for a target client.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "list_agents",
            "description": "List agent ids for a target client and group.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hwnd": {"type": "integer"},
                    "pid": {"type": "integer"},
                    "group": {
                        "type": "string",
                        "enum": ["all", "ally", "enemy", "item", "gadget", "npc"],
                    },
                },
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "run_script",
            "description": (
                "Load and run a Python script inside the injected client's console slot. "
                "The client keeps a single slot, so this replaces whatever was loaded before it. "
                "A script that defines main()/update()/draw() becomes a per-frame callback: the client "
                "keeps calling it on every tick until stop_script, so a one-shot script must not define them. "
                "Optional arguments are published to the script as the ARGS list and the KWARGS dict, "
                "and the script runs as __main__. "
                "The path is resolved by the client, so use an absolute path or one under the project root."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "hwnd": {"type": "integer"},
                    "pid": {"type": "integer"},
                    "path": {"type": "string"},
                    "args": {
                        "type": "array",
                        "description": "Positional values, exposed to the script as ARGS.",
                        "items": {},
                    },
                    "kwargs": {
                        "type": "object",
                        "description": "Named values, exposed to the script as KWARGS.",
                        "additionalProperties": True,
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "stop_script",
            "description": "Stop the script running in the target client's console slot.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
        {
            "name": "get_script_status",
            "description": "Report the state of the target client's console script slot.",
            "inputSchema": {
                "type": "object",
                "properties": target_schema["properties"],
                "minProperties": 1,
                "additionalProperties": False,
            },
        },
    ]


class Py4GWMcpServer:
    def __init__(self, daemon_host: str, daemon_port: int, timeout: float):
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.timeout = timeout

    def _target_params(self, arguments: dict[str, Any]) -> dict[str, Any]:
        target: dict[str, Any] = {}
        hwnd = arguments.get("hwnd")
        pid = arguments.get("pid")
        if hwnd is not None:
            target["hwnd"] = int(hwnd)
        if pid is not None:
            target["pid"] = int(pid)
        if not target:
            raise ValueError("Provide hwnd or pid")
        return {"target": target}

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "list_clients":
            return _daemon_request(self.daemon_host, self.daemon_port, "system.list_clients", timeout=self.timeout)
        if name == "list_namespaces":
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.list_namespaces",
                self._target_params(arguments),
                timeout=self.timeout,
            )
        if name == "list_commands":
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.list_commands",
                self._target_params(arguments),
                timeout=self.timeout,
            )
        if name == "describe_runtime":
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.describe_runtime",
                self._target_params(arguments),
                timeout=self.timeout,
            )
        if name == "get_map_state":
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.get_map_state",
                self._target_params(arguments),
                timeout=self.timeout,
            )
        if name == "get_player_state":
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.get_player_state",
                self._target_params(arguments),
                timeout=self.timeout,
            )
        if name == "list_agents":
            params = self._target_params(arguments)
            if "group" in arguments and arguments.get("group") is not None:
                params["group"] = str(arguments["group"])
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.list_agents",
                params,
                timeout=self.timeout,
            )
        if name == "run_script":
            params = self._target_params(arguments)
            path = str(arguments.get("path") or "").strip()
            if not path:
                raise ValueError("path is required")
            payload_params: dict[str, Any] = {"path": path}
            if "args" in arguments and arguments.get("args") is not None:
                if not isinstance(arguments["args"], list):
                    raise ValueError("args must be a list")
                payload_params["args"] = arguments["args"]
            if "kwargs" in arguments and arguments.get("kwargs") is not None:
                if not isinstance(arguments["kwargs"], dict):
                    raise ValueError("kwargs must be an object")
                payload_params["kwargs"] = arguments["kwargs"]
            params["payload"] = {"command": "script.run", "params": payload_params}
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.request",
                params,
                timeout=max(self.timeout, 15.0),
            )
        if name == "stop_script":
            params = self._target_params(arguments)
            params["payload"] = {"command": "script.stop", "params": {}}
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.request",
                params,
                timeout=self.timeout,
            )
        if name == "get_script_status":
            params = self._target_params(arguments)
            params["payload"] = {"command": "script.status", "params": {}}
            return _daemon_request(
                self.daemon_host,
                self.daemon_port,
                "client.request",
                params,
                timeout=self.timeout,
            )
        raise ValueError(f"Unknown tool: {name}")

    def _negotiate_protocol_version(self, requested_version: Any) -> str:
        requested = str(requested_version or "").strip()
        if requested in SUPPORTED_MCP_PROTOCOL_VERSIONS:
            return requested
        return SUPPORTED_MCP_PROTOCOL_VERSIONS[0]

    def _handle_initialize(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        protocol_version = self._negotiate_protocol_version(params.get("protocolVersion"))
        _log_debug(
            f"initialize requested={params.get('protocolVersion')!r} negotiated={protocol_version!r}"
        )
        return _make_jsonrpc_result(
            msg_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "logging": {},
                    "tools": {"listChanged": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    def _handle_tools_list(self, msg_id: Any) -> dict[str, Any]:
        return _make_jsonrpc_result(msg_id, {"tools": _tool_list()})

    @staticmethod
    def _result_is_error(result: Any) -> bool:
        """Whether a daemon response carries a failure, at either layer.

        The daemon answers ``ok: true`` as soon as it relayed the request, and
        the client's own verdict arrives nested in ``bridge_response``. Reading
        only the envelope turns a refused command (``unsupported command``, a
        guard, a script that failed to load) into a success for the caller.
        """
        if not isinstance(result, dict):
            return True
        if not bool(result.get("ok", False)):
            return True
        nested = result.get("result")
        if isinstance(nested, dict):
            bridge_response = nested.get("bridge_response")
            if isinstance(bridge_response, dict) and not bool(bridge_response.get("ok", True)):
                return True
        return False

    def _handle_tools_call(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "")
        arguments = params.get("arguments", {})
        if not name:
            return _make_jsonrpc_error(msg_id, -32602, "tools/call requires a tool name")
        if not isinstance(arguments, dict):
            return _make_jsonrpc_error(msg_id, -32602, "tools/call arguments must be an object")
        try:
            result = self._call_tool(name, arguments)
        except ValueError as exc:
            return _make_jsonrpc_error(msg_id, -32602, str(exc))
        except Exception as exc:
            return _make_jsonrpc_error(msg_id, -32000, str(exc))
        return _make_jsonrpc_result(
            msg_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2, ensure_ascii=False),
                    }
                ],
                "structuredContent": result,
                "isError": self._result_is_error(result),
            },
        )

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = str(message.get("method") or "")
        msg_id = message.get("id")
        params = message.get("params", {})
        _log_debug(f"recv method={method!r} id={msg_id!r}")
        if not isinstance(params, dict):
            params = {}
        if method == "initialize":
            return self._handle_initialize(msg_id, params)
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return _make_jsonrpc_result(msg_id, {})
        if method == "tools/list":
            return self._handle_tools_list(msg_id)
        if method == "tools/call":
            return self._handle_tools_call(msg_id, params)
        if msg_id is None:
            return None
        return _make_jsonrpc_error(msg_id, -32601, f"Method not found: {method}")

    def run(self) -> int:
        while True:
            try:
                message = _read_stdio_message()
            except Exception as exc:
                _write_stdio_message(_make_jsonrpc_error(None, -32700, f"Parse error: {exc}"))
                return 1
            if message is None:
                return 0
            response = self.handle_message(message)
            if response is not None:
                _write_stdio_message(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal MCP server for the Py4GW bridge daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Bridge daemon control host")
    parser.add_argument("--port", type=int, default=47812, help="Bridge daemon control port")
    parser.add_argument("--timeout", type=float, default=5.0, help="Bridge daemon request timeout seconds")
    args = parser.parse_args()
    _log_debug(
        f"start argv={sys.argv!r} daemon={args.host}:{args.port} timeout={args.timeout}"
    )
    server = Py4GWMcpServer(args.host, args.port, args.timeout)
    try:
        return server.run()
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
