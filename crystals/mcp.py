"""Minimal read-only MCP stdio adapter (newline-delimited UTF-8 JSON-RPC)."""
import argparse
import json
import sys
from . import ACTS, __version__, match

VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
TOOL = {
    "name": "match", "description": "Read act-bound knowings before an action. No shell or store writes.",
    "inputSchema": {"type": "object", "properties": {
        "act": {"type": "string", "enum": list(ACTS)},
        "text": {"type": "string"}, "target": {"type": "string"},
        "who": {"type": "string", "enum": ["all", "frontier", "7b", "resident"]}},
        "required": ["act", "text"], "additionalProperties": False},
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
}


class Server:
    def __init__(self, store):
        self.store = store
        self.initialized = False
        self.ready = False

    def handle(self, message):
        request_id = message.get("id") if isinstance(message, dict) else None
        def error(code, text):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": text}}
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str)
                or ("id" in message and (isinstance(request_id, bool)
                    or not isinstance(request_id, (str, int))))):
            return error(-32600, "Invalid Request")
        method = message["method"]
        if "id" not in message:
            if method == "notifications/initialized" and self.initialized:
                self.ready = True
            return None
        params = message.get("params", {})
        if not isinstance(params, dict):
            return error(-32602, "params must be an object")
        if method == "initialize":
            if self.initialized:
                return error(-32600, "Already initialized")
            if not isinstance(params.get("protocolVersion"), str):
                return error(-32602, "protocolVersion is required")
            version = params["protocolVersion"]
            self.initialized = True
            result = {"protocolVersion": version if version in VERSIONS else VERSIONS[-1],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "crystals", "version": __version__}}
        elif method == "ping":
            result = {}
        elif not self.ready:
            return error(-32600, "Initialize and send notifications/initialized first")
        elif method == "tools/list":
            result = {"tools": [TOOL]}
        elif method == "tools/call":
            if params.get("name") != "match":
                return error(-32602, "Unknown tool")
            args = params.get("arguments", {})
            if (not isinstance(args, dict) or not {"act", "text"} <= args.keys()
                    or args.keys() - {"act", "text", "target", "who"}
                    or any(not isinstance(v, str) for v in args.values())
                    or args.get("act") not in ACTS
                    or args.get("who", "all") not in ("all", "frontier", "7b", "resident")):
                return error(-32602, "Invalid match arguments")
            try:
                knowings = match(store=self.store, **args)
                result = {"content": [{"type": "text", "text": json.dumps(knowings, ensure_ascii=False)}],
                          "isError": False}
            except (OSError, ValueError, TypeError) as exc:
                result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        else:
            return error(-32601, "Method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--store", required=True, help="project containing memory/")
    args = parser.parse_args()
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    server = Server(args.store)
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except (ValueError, UnicodeError):
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = server.handle(message)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
