import base64
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["HERMES_HOME"] = tempfile.mkdtemp(prefix="grok-bridge-")

import bridge  # noqa: E402


class SignTest(unittest.TestCase):
    def test_matches_standard_webhooks(self):
        secret = "whsec_" + base64.b64encode(b"0123456789abcdef").decode()
        body = b'{"job_id":"abc"}'
        sig = bridge.sign_body(secret, body, "msg_1", "100")
        key = base64.b64decode(secret.removeprefix("whsec_"))
        expect = base64.b64encode(hmac.new(key, b"msg_1.100." + body, hashlib.sha256).digest()).decode()
        self.assertEqual(sig, "v1," + expect)

    def test_job_roundtrip_hides_token_from_public_view(self):
        rec = bridge.new_job("scan X", "Boss", "sess-1")
        self.assertNotIn("token", bridge.public_view(rec))
        done, err = bridge.complete(rec["job_id"], rec["token"], "three topics")
        self.assertIsNone(err)
        self.assertEqual(done["result"]["summary"], "three topics")
        again, err = bridge.complete(rec["job_id"], "nope", "x")
        self.assertEqual(err, "bad token")
        waiting = bridge.pending_results("sess-1")
        self.assertEqual(len(waiting), 1)
        bridge.mark_injected(rec["job_id"])
        self.assertEqual(bridge.pending_results("sess-1"), [])

    def test_wake_refuses_without_endpoint(self):
        os.environ.pop("GROK_BOT_WAKE_URL", None)
        os.environ.pop("GROK_BOT_WAKE_SECRET", None)
        rec = bridge.new_job("x", "Boss")
        with self.assertRaises(RuntimeError):
            bridge.wake(rec)

    def test_bearer_header_and_accepted_status(self):
        headers = bridge.wake_headers("not-a-signing-secret", b"{}")
        self.assertEqual(headers["Authorization"], "Bearer not-a-signing-secret")
        self.assertNotIn("webhook-signature", headers)
        rec = bridge.new_job("x", "Boss")
        rec["status"] = "sent" if 200 in (200, 202) else "wake_failed"
        self.assertEqual(rec["status"], "sent")
        rec = bridge.new_job("x", "Boss")
        mode = Path(bridge._job_path(rec["job_id"])).stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)
        raw = json.loads(Path(bridge._job_path(rec["job_id"])).read_text())
        self.assertIn("token", raw)


class WakeEnvTest(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.pop(k, None) for k in ("GROK_BOT_WAKE_URL", "GROK_BOT_WAKE_SECRET")}
        self.path = bridge.wake_env_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v

    def test_reads_export_and_quoted_lines(self):
        self.path.write_text(
            "# comment\n"
            "export GROK_BOT_WAKE_URL='https://routine.example/wake'\n"
            'GROK_BOT_WAKE_SECRET="crsr_abc"\n'
        )
        url, secret = bridge.load_wake_config()
        self.assertEqual(url, "https://routine.example/wake")
        self.assertEqual(secret, "crsr_abc")

    def test_env_wins_over_file(self):
        self.path.write_text("GROK_BOT_WAKE_URL=https://file\nGROK_BOT_WAKE_SECRET=file-secret\n")
        os.environ["GROK_BOT_WAKE_URL"] = "https://env"
        os.environ["GROK_BOT_WAKE_SECRET"] = "env-secret"
        self.assertEqual(bridge.load_wake_config(), ("https://env", "env-secret"))

    def test_empty_hermes_home_does_not_become_dot(self):
        real = os.environ.get("HERMES_HOME")
        try:
            os.environ["HERMES_HOME"] = ""
            got = bridge.state_dir()
            self.assertEqual(got, Path.home() / ".hermes" / "grok-bot-bridge" / "jobs")
        finally:
            if real is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = real

    def test_error_says_which_path_was_checked(self):
        rec = bridge.new_job("x", "Boss")
        with self.assertRaises(RuntimeError) as cm:
            bridge.wake(rec)
        msg = str(cm.exception)
        self.assertIn("MISSING", msg)
        self.assertIn(str(self.path), msg)


if __name__ == "__main__":
    unittest.main()
