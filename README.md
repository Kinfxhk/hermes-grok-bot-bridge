# hermes-grok-bot-bridge

Hermes owns the chat. A Grok Bot does the computer work, then posts the result back into the same Hermes chat. The plugin does not change which model is pinned for chat.

An HTTP 200 from the wake endpoint means the run started. It does not mean the work finished. The finished result is the callback into Hermes, which replaces opening the Bot chat.

## Loop

1. The chat model calls `grok_bot_task`.
2. The plugin POSTs the task to a Grok Bot routine webhook and returns a job id immediately.
3. The Bot does the work on its cloud computer. Closing the desktop app does not stop that run.
4. The Bot POSTs the result to the callback. Hermes injects it into the same chat.

## What it can do

| Use | |
| --- | --- |
| Start a cloud run on one webhook routine you already created | ✓ |
| Keep the Hermes chat free while that run is in flight | ✓ |
| Treat HTTP 200 or 202 as "run started", not "work finished" | ✓ |
| Take the Bot's callback and inject the summary into the same chat | ✓ |
| Run that cloud job with the Grok Bot window closed | ✓ |

The callback URL must be reachable from the cloud computer. `127.0.0.1` is not.

## Wake auth

Create a routine with a Webhook trigger in Grok Bot. The secret is shown once.

```bash
export GROK_BOT_WAKE_URL='https://...'
export GROK_BOT_WAKE_SECRET='...'
```

A secret that starts with `whsec_` is signed as a Standard Webhook. Any other secret is sent as `Authorization: Bearer`. The routine webhook uses the bearer form.

Prefer `~/.hermes/grok-bot-bridge/wake.env` (mode 600) over the environment. Never commit the URL or the secret.

`wake.env` takes one `KEY=value` per line. A pasted shell line works too: `export KEY='value'` — the `export ` prefix and surrounding quotes are stripped. Values already in the environment win over the file.

Save `bot-skill.md` as a Grok Bot skill so the Bot posts the callback instead of leaving the result only in its own chat.

## Install

```bash
ln -s "$PWD" ~/.hermes/plugins/grok-bot-bridge
```

```yaml
plugins:
  enabled:
    - grok-bot-bridge
  entries:
    grok-bot-bridge:
      allow_gateway_injection: true
```

Reload the gateway before the tool appears in a new session. This plugin does not restart the gateway.

**Editing this plugin's Python does nothing until the gateway restarts.** Hermes imports a plugin module once and keeps it for the life of the gateway process, so a running gateway keeps executing the code it loaded, even after the file on disk changes. Restart after any edit to `bridge.py`, `__init__.py` or `schemas.py`.

The cloud computer cannot reach `127.0.0.1`. Set `GROK_BOT_BRIDGE_PUBLIC_URL` to an address the Bot can reach, and `GROK_BOT_BRIDGE_LISTEN=1`. The default listener is `127.0.0.1:8766`, for a local return only.

## Test

```bash
python3 tests/test_bridge.py
```

Without a wake URL the plugin does not send. A live dispatch needs your own endpoint.

## Troubleshooting

`grok_bot_task` fails with "set GROK_BOT_WAKE_URL and GROK_BOT_WAKE_SECRET" although `wake.env` exists.

1. Read the job record at `~/.hermes/grok-bot-bridge/jobs/<job_id>.json`. `"status": "wake_failed"` together with `"wake_http": null` means nothing left the machine — the config was not found, not rejected by the endpoint.
2. Compare the gateway start time with the file mtimes (`ps -o lstart= -p <gateway_pid>`). A gateway that started before `wake.env` or the plugin was last written is running the older code and cannot see either. Restart it.
3. Confirm the file itself: mode 600, plain `KEY=value`, at `$HERMES_HOME/grok-bot-bridge/wake.env` (`HERMES_HOME` defaults to `~/.hermes`).

## Out of scope

- Reading the Grok Bot app session or a Cursor access token
- Putting a secret in this repo

## Support

Free to use. If it helps: https://buymeacoffee.com/kinfxhk
