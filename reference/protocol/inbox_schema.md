# Inbox JSON Schema (Quick Reference)

> **TL;DR** of `feishu_inbox_protocol.md` — the 6 fields the Go skeleton
> writes into `/tmp/hermes_inbox/<msg_id>.json`. For full state machine
> and atomicity rules, read the full protocol doc.

## Inbox (bot daemon → inbox_watcher)

Path: `/tmp/hermes_inbox/<msg_id>.json`

| field | type | required | source | example |
|---|---|---|---|---|
| `msg_id` | string | yes | `message.message_id` | `"om_a1b2c3d4..."` (om_ prefix) |
| `chat_id` | string | yes | `message.chat_id` | `"oc_a1b2c3d4..."` (oc_ prefix) |
| `text` | string | yes | `message.text` (stripped) | `"今天天气怎么样"` |
| `sender_open_id` | string | no | `sender.sender_id.open_id` | `"ou_a1b2c3d4..."` (ou_ prefix) |
| `sender_name` | string | no | name cache lookup | `"张三"` (may be empty on cold cache) |
| `received_at` | float | no | `time.time()` at write | `1717920000.123` (Unix sec) |

Note on Go vs Python drift:
- Python's `feishu_bot_daemon.py` writes this field as `sender` (per
  protocol spec), but the Go skeleton's `InboxMessage` struct renames
  it to `sender_open_id` to make the semantic explicit (it IS an open_id,
  not a chat_id or user_id). Both formats are accepted by
  `inbox_watcher.py` because that consumer only reads `text`/`msg_id`/
  `chat_id` (verified 2026-06-14).
- The `sender_name` field is **Go-only**, populated by the future name
  cache resolver. Python's daemon doesn't write it.

## Outbox (inbox_watcher → bot daemon)

Path: `/tmp/hermes_outbox/<msg_id>.json`

| field | type | source | purpose |
|---|---|---|---|
| `msg_id` | string | echo of inbox.msg_id | correlate with inbound queue |
| `chat_id` | string | echo of inbox.chat_id | `receive_id` for Feishu POST; skipped if `oc_test_` prefix |
| `ok` | bool | `rc==0 AND non-empty stdout` | `false` → retry with 60s backoff, max 3 attempts |
| `reply` | string | LLM reply text | sent back to Feishu |
| `model` | string | e.g. `"minimax-cn/MiniMax-M3"` | diagnostics |
| `duration_sec` | float | LLM call wall time | diagnostics |

## State Machine (paths)

```
/tmp/hermes_inbox/<msg_id>.json     ← bot daemon writes (write-then-rename)
       │
       │  inbox_watcher does `os.rename` (atomic on /tmp)
       ▼
/tmp/hermes_inbox/.processing/<msg_id>.json     ← per-msg lock
       │
       ├─ ok=true    → /tmp/hermes_inbox/.done/<msg_id>.json    (terminal)
       ├─ ok=false   → /tmp/hermes_inbox/.error/<msg_id>.retry<N>.json
       │                (N++ each retry, after 60s backoff, max 3)
       │                on success → .done; on exhausted → .error
       └─ bad JSON   → /tmp/hermes_inbox/.error/<msg_id>.badjson  (no retry)
```

Bot daemon's outbox watcher polls `/tmp/hermes_outbox/*.json` and POSTs
each to Feishu. Successful POSTs move to `/tmp/hermes_outbox/.done/`.
Failed POSTs (network / API error) retry with backoff; permanent
failures (404 chat deleted) go to `/tmp/hermes_outbox/.error/`.

## Atomicity Invariant

Both daemons use `write-then-rename` (`os.replace` on Python, `os.WriteFile`
+ `os.Rename` on Go) so a concurrent consumer never reads a half-written
file. The `mv-into-.processing` is the **lock** — two concurrent
watchers race on it, one wins, the other gets `FileNotFoundError` and
moves on (safe, idempotent).

See the full protocol doc for failure modes, retry semantics, and
the `oc_test_` prefix escape hatch for offline development.