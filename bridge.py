"""Sign a Grok wake and store the job until the Bot posts a result.

Stdlib only. Secrets stay in the environment. This file does not import Hermes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

WAKE_URL = "GROK_BOT_WAKE_URL"
WAKE_SECRET = "GROK_BOT_WAKE_SECRET"
PUBLIC_URL = "GROK_BOT_BRIDGE_PUBLIC_URL"
PORT = "GROK_BOT_BRIDGE_PORT"


def state_dir() -> Path:
    root = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    path = root / "grok-bot-bridge" / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sign_body(secret: str, body: bytes, webhook_id: str, timestamp: str) -> str:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{webhook_id}.{timestamp}.".encode() + body
    digest = hmac.new(key, signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def _job_path(job_id: str) -> Path:
    if not job_id or "/" in job_id or job_id.startswith("."):
        raise ValueError("bad job id")
    return state_dir() / f"{job_id}.json"


def save_job(rec: dict) -> None:
    path = _job_path(rec["job_id"])
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    os.chmod(path, 0o600)


def load_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def new_job(task: str, bot: str, session_key: str | None = None) -> dict:
    rec = {
        "job_id": uuid.uuid4().hex[:16],
        "token": uuid.uuid4().hex,
        "bot": bot or "Boss",
        "task": task,
        "status": "pending",
        "session_key": session_key,
        "created_at": int(time.time()),
        "result": None,
        "injected": False,
        "wake_http": None,
    }
    save_job(rec)
    return rec


def callback_url(job_id: str) -> str:
    base = os.environ.get(PUBLIC_URL, "").rstrip("/")
    if not base:
        base = "http://127.0.0.1:" + os.environ.get(PORT, "8766")
    return f"{base}/result/{job_id}"


def wake(rec: dict) -> tuple[int, str]:
    url = os.environ.get(WAKE_URL, "")
    secret = os.environ.get(WAKE_SECRET, "")
    if not url or not secret:
        raise RuntimeError("set GROK_BOT_WAKE_URL and GROK_BOT_WAKE_SECRET")
    payload = {
        "job_id": rec["job_id"],
        "bot": rec["bot"],
        "task": rec["task"],
        "callback_url": callback_url(rec["job_id"]),
        "callback_token": rec["token"],
        "instruction": (
            "Do this task. When finished, POST JSON "
            '{"status":"done","summary":"..."} to callback_url with header '
            "Authorization: Bearer <callback_token>. Do not leave the result only in this chat."
        ),
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    webhook_id = "msg_" + uuid.uuid4().hex
    timestamp = str(int(time.time()))
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "webhook-id": webhook_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": sign_body(secret, body, webhook_id, timestamp),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            text = resp.read(300).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read(300).decode("utf-8", "replace")
    rec["status"] = "sent" if status == 202 else "wake_failed"
    rec["wake_http"] = status
    save_job(rec)
    return status, text


def complete(job_id: str, token: str, summary: str, status: str = "done") -> tuple[dict | None, str | None]:
    rec = load_job(job_id)
    if rec is None:
        return None, "unknown job"
    if not hmac.compare_digest(str(rec.get("token", "")), token or ""):
        return None, "bad token"
    if rec.get("status") == "done" and rec.get("result"):
        return rec, None
    rec["status"] = status
    rec["result"] = {"summary": summary, "at": int(time.time())}
    save_job(rec)
    return rec, None


def mark_injected(job_id: str) -> None:
    rec = load_job(job_id)
    if not rec:
        return
    rec["injected"] = True
    save_job(rec)


def pending_results(session_key: str | None = None) -> list[dict]:
    found = []
    for path in state_dir().glob("*.json"):
        rec = json.loads(path.read_text())
        if rec.get("status") != "done" or rec.get("injected") or not rec.get("result"):
            continue
        if session_key and rec.get("session_key") not in (None, "", session_key):
            continue
        found.append(rec)
    return found


def public_view(rec: dict) -> dict:
    return {
        "job_id": rec.get("job_id"),
        "bot": rec.get("bot"),
        "status": rec.get("status"),
        "wake_http": rec.get("wake_http"),
        "summary": (rec.get("result") or {}).get("summary"),
        "callback_url": callback_url(rec["job_id"]) if rec.get("job_id") else None,
    }
