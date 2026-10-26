# hermes-grok-bot-bridge

Hermes 聊天 model 派工，Grok Bot 做完交返同一個對話。唔用 gbot，唔拆 app session。

聊天 model 可以係 DeepSeek、Grok 訂閱，或者你而家 pin 住嘅任何一個。呢個插件唔改 model。

## 環

1. 聊天 model 叫 `grok_bot_task`。
2. 插件用 Standard Webhooks 簽好名，POST 去你喺 Grok 開嘅 webhook。`202` 先算派到。工具即刻返 job id，唔阻塞。
3. Grok Bot 做完，POST 結果去 callback。
4. 插件把結果注入原對話。聊天 model 再整理答你。

## 你要做嘅一步

喺 Grok automation / Bot routine 加 **Webhook** trigger。secret 只顯示一次。

```bash
export GROK_BOT_WAKE_URL='https://...'
export GROK_BOT_WAKE_SECRET='whsec_...'
```

`whsec_` secrets are signed as Standard Webhooks. Any other secret is sent as `Authorization: Bearer`. The live Grok Bot webhook uses the bearer form. Keep both values in `~/.hermes/grok-bot-bridge/wake.env` (mode 600), not in this repo.

把 `bot-skill.md` 存成 Grok Bot skill，等 Bot 知道要打 callback，唔好只留喺自己個 chat。

## 安裝

```bash
ln -s "$PWD" ~/.hermes/plugins/grok-bot-bridge
```

`config.yaml`：

```yaml
plugins:
  enabled:
    - grok-bot-bridge
  entries:
    grok-bot-bridge:
      allow_gateway_injection: true
```

Gateway 要重新載入先見到工具。呢步會影響成個 fleet，要你自己批，插件唔會自己重啟。

雲端 Bot 打唔到 `127.0.0.1`。要交返雲端結果，設 `GROK_BOT_BRIDGE_PUBLIC_URL` 做一個 Bot 打到嘅地址，再 `GROK_BOT_BRIDGE_LISTEN=1`。預設只聽 `127.0.0.1:8766`，俾本機 local-exec 交還。

## 測試

```bash
python3 tests/test_bridge.py
```

冇 wake URL 就唔會打出去。live 派工要你自己嘅 endpoint。

## 唔做

- gbot / grok-bot-cli
- 讀 Grok Bot app session 或 `CURSOR_ACCESS_TOKEN`
- 把 secret 放進 repo
