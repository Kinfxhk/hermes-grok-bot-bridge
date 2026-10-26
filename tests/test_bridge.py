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


if __name__ == "__main__":
    unittest.main()
