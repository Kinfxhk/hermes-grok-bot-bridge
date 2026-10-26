"""Hermes plugin: chat model dispatches, Grok Bot returns into the same chat."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import bridge, schemas

_ctx = None
_server = None


def _session_key(kwargs: dict) -> str | None:
    for key in ("session_key", "session_id", "task_id"):
        value = kwargs.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def handle_task(args: dict, **kwargs) -> str:
    task = (args or {}).get("task", "").strip()
    if not task:
        return json.dumps({"success": False, "error": "task is required"})
    rec = bridge.new_job(task, (args or {}).get("bot") or "Boss", _session_key(kwargs))
    try:
        status, text = bridge.wake(rec)
    except Exception as exc:
        rec["status"] = "wake_failed"
        rec["wake_http"] = None
        bridge.save_job(rec)
        return json.dumps({"success": False, "error": str(exc), "job_id": rec["job_id"]})
    view = bridge.public_view(rec)
    view["success"] = status == 202
    if status != 202:
        view["error"] = text[:200]
    view["note"] = "Queued. Do not poll. The result comes back into this chat."
    return json.dumps(view, ensure_ascii=False)


def handle_job(args: dict, **kwargs) -> str:
    rec = bridge.load_job((args or {}).get("job_id", ""))
    if not rec:
        return json.dumps({"success": False, "error": "unknown job"})
    return json.dumps({"success": True, **bridge.public_view(rec)}, ensure_ascii=False)


def _inject(rec: dict) -> None:
    if _ctx is None or rec.get("injected"):
        return
    summary = (rec.get("result") or {}).get("summary") or ""
    text = (
        f"[Grok Bot result job {rec['job_id']}]\n"
        f"{summary}\n"
        "Summarise this for the user. Do not dispatch it again."
    )
    ok = False
    try:
        ok = bool(_ctx.inject_message(
            text,
            role="user",
            session_key=rec.get("session_key") or None,
        ))
    except TypeError:
        ok = bool(_ctx.inject_message(text))
    except Exception:
        ok = False
    if ok:
        bridge.mark_injected(rec["job_id"])


def _inject_pending(**kwargs) -> str | None:
    key = _session_key(kwargs)
    lines = []
    for rec in bridge.pending_results(key):
        summary = (rec.get("result") or {}).get("summary") or ""
        lines.append(f"job {rec['job_id']}: {summary}")
        bridge.mark_injected(rec["job_id"])
    if not lines:
        return None
    return "Grok Bot results waiting in this chat:\n" + "\n".join(lines)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) != 2 or parts[0] != "result":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 100_000:
            self.send_error(413)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_error(400)
            return
        token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        rec, err = bridge.complete(parts[1], token, str(body.get("summary", ""))[:4000], body.get("status") or "done")
        if err:
            self.send_error(401 if err == "bad token" else 404)
            return
        _inject(rec)
        raw = b'{"ok":true}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _listen() -> None:
    global _server
    if os.environ.get("GROK_BOT_BRIDGE_LISTEN") != "1" or _server is not None:
        return
    host = os.environ.get("GROK_BOT_BRIDGE_BIND", "127.0.0.1")
    port = int(os.environ.get(bridge.PORT, "8766"))
    _server = ThreadingHTTPServer((host, port), _Handler)
    threading.Thread(target=_server.serve_forever, name="grok-bot-bridge", daemon=True).start()


def register(ctx) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_tool(
        name="grok_bot_task",
        toolset="grok_bot_bridge",
        schema=schemas.TASK,
        handler=handle_task,
    )
    ctx.register_tool(
        name="grok_bot_job",
        toolset="grok_bot_bridge",
        schema=schemas.JOB,
        handler=handle_job,
    )
    ctx.register_hook("pre_llm_call", _inject_pending)
    _listen()
