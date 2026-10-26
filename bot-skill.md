# Report back to Hermes

Use this when a task contains `job_id`, `callback_url`, and `callback_token`.

1. Do the task on this Bot. Do not ask the chat model to redo it.
2. When finished, POST JSON to `callback_url`:

```json
{"status":"done","summary":"<what you did and the result, under 2000 characters>"}
```

Header: `Authorization: Bearer <callback_token>`

3. A 200 response means Hermes has the result. Stop. Do not send the same result again.
4. If `callback_url` is on this Mac and the cloud computer cannot reach it, use local execution on the registered Mac to run the same POST. Do not invent another channel.
5. Never print `callback_token` into a public chat, a commit, or a screenshot.
