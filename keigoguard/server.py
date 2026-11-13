"""MCP server (stdio, JSON-RPC 2.0). Python standard library only, no network.

Start: python -m keigoguard.server
"""
import json
import sys

from . import __version__
from .guard import check, fix

PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
RO = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
MAX_CHARS = 200_000

TOOLS = [
    {
        "name": "jp_keigo_check",
        "title": "Find double honorifics (二重敬語) and mismatched honorific chains in Japanese text",
        "annotations": RO,
        "description": ("Before you send a Japanese business email, notice or reply you wrote, pass the text here. "
                        "Finds 二重敬語 (お読みになられる, おっしゃられる, いらっしゃられる, ご覧になられる, "
                        "召し上がられる) and the honorific chains that the Japanese government guideline 「敬語の指針」 "
                        "(文化審議会答申 2007, p.31-32) lists as inappropriate (伺っていただく, ご案内していただく, "
                        "ご説明してくださる). Forms the guideline accepts as settled by custom (お召し上がりになる, "
                        "お見えになる, お伺いする/いたす/申し上げる) are not flagged. Returns ok, issues (code, severity, "
                        "text, start, end, fix, reason, source), accepted, counts. Codes: E_DOUBLE_KEIGO, "
                        "W_DOUBLE_KEIGO_NOUN (ご+noun+になられる, may be correct), E_BAD_KEIGO_LINK, W_BAD_KEIGO_LINK. "
                        "Deterministic, offline. It checks word forms only, not whether 尊敬語 is used for the "
                        "writer's own action. 二重敬語と不適切な敬語連結を見つけて直し案を返す。"),
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "description": "Japanese text"}},
                        "required": ["text"]},
    },
    {
        "name": "jp_keigo_fix",
        "title": "Rewrite double honorifics in Japanese text to the single form",
        "annotations": RO,
        "description": ("Returns the text with error-level fixes applied (お読みになられました → お読みになりました, "
                        "おっしゃられた → おっしゃった, ご案内していただけますか → ご案内いただけますか). Warning-level fixes "
                        "only when apply_warnings is true. Issues that need a different verb (伺っていただく → "
                        "お越しいただく) are returned in unfixed for you to rewrite. Returns text, applied, unfixed, remaining."),
        "inputSchema": {"type": "object", "properties": {
            "text": {"type": "string"},
            "apply_warnings": {"type": "boolean", "description": "Also apply warning-level fixes. Default false"}},
            "required": ["text"]},
    },
]


def _str(args, key):
    v = args.get(key)
    if not isinstance(v, str):
        raise ValueError(f"'{key}' must be a string")
    if len(v) > MAX_CHARS:
        raise ValueError(f"'{key}' is longer than {MAX_CHARS} characters; split it")
    return v


def _bool(args, key):
    v = args.get(key, False)
    if not isinstance(v, bool):
        raise ValueError(f"'{key}' must be true or false")
    return v


HANDLERS = {
    "jp_keigo_check": lambda a: check(_str(a, "text")),
    "jp_keigo_fix": lambda a: fix(_str(a, "text"), _bool(a, "apply_warnings")),
}


def _handle_legacy(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None
    try:
        if method == "initialize":
            want = params.get("protocolVersion")
            result = {"protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "jp-keigo-guard", "version": __version__},
                      "instructions": ("After writing Japanese business text, call jp_keigo_check. Fix every error "
                                       "(or call jp_keigo_fix) and rewrite the items in unfixed before sending.")}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name = params.get("name")
            if name not in HANDLERS:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool: {name}"}}
            try:
                out = HANDLERS[name](params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}],
                          "structuredContent": out, "isError": False}
            except ValueError as e:
                result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    except Exception as e:  # keep the server alive
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"Internal error: {e}"}}


# --- MCP 2026-07-28 (stateless) support. The legacy initialize flow above stays as it was. ---
# Spec: https://modelcontextprotocol.io/specification/2026-07-28/changelog
MODERN_PROTOCOLS = ["2026-07-28"]
_K = "io.modelcontextprotocol/"
_TOOLS_TTL_MS = 300000


def _legacy_info():
    r = _handle_legacy({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})["result"]
    return r["serverInfo"], r.get("instructions"), {k: {} for k in r.get("capabilities", {})}


def _modern_error(mid, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": mid, "error": err}


def _handle_modern(msg):
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:
        return None
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    version = meta.get(_K + "protocolVersion")
    if not isinstance(version, str):
        return _modern_error(mid, -32602, "Missing _meta io.modelcontextprotocol/protocolVersion")
    if version not in MODERN_PROTOCOLS:
        return _modern_error(mid, -32022, "Unsupported protocol version",
                             {"supported": MODERN_PROTOCOLS + PROTOCOLS, "requested": version})
    if not isinstance(meta.get(_K + "clientCapabilities"), dict):
        return _modern_error(mid, -32602, "Missing _meta io.modelcontextprotocol/clientCapabilities")
    server_info, instructions, caps = _legacy_info()
    if method == "server/discover":
        result = {"resultType": "complete", "supportedVersions": list(MODERN_PROTOCOLS), "capabilities": caps,
                  "_meta": {_K + "serverInfo": server_info}, "ttlMs": 3600000, "cacheScope": "public"}
        if instructions:
            result["instructions"] = instructions
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    if method not in ("tools/list", "tools/call"):
        return _modern_error(mid, -32601, f"Method not found: {method}")
    resp = _handle_legacy(msg)
    if "result" in resp:
        result = dict(resp["result"])
        result["resultType"] = "complete"
        result.setdefault("_meta", {})[_K + "serverInfo"] = server_info
        if method == "tools/list":
            result["ttlMs"] = _TOOLS_TTL_MS
            result["cacheScope"] = "public"
        resp = {"jsonrpc": "2.0", "id": mid, "result": result}
    return resp


def handle(msg):
    """Dual-era: server/discover or a request with modern _meta is stateless 2026-07-28; initialize keeps the old flow."""
    params = msg.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    method = msg.get("method")
    if method == "server/discover" or (method != "initialize" and isinstance(meta, dict)
                                       and _K + "protocolVersion" in meta):
        return _handle_modern(msg)
    return _handle_legacy(msg)


def main():
    for s in (sys.stdin, sys.stdout):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(msg) if isinstance(msg, dict) else None
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
