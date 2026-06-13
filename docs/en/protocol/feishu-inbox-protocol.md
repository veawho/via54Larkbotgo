# Feishu Inbox Protocol

> **This document is the authoritative reference for the file-IPC protocol
> between a Feishu bot daemon (WebSocket long-connection OR Webhook) and
> the AI Agent's inbox_watcher.**

The Go skeleton in this repo (`main.go`) and the Python daemon
(`via54Larkfix/reference/python-original/feishu_bot_daemon.py`) both
honor this schema. If you change one side without the other, replies
will silently break.

> 📄 **This is a direct port of `via54Larkfix/references/feishu_inbox_protocol.md`
> (22 KB)**, kept here for self-containment of the bot docs site.

## 1. Directory layout

All paths absolute. Both daemons MUST agree on these.

| directory | written by | read by | purpose |
|---|---|---|---|
| `/tmp/hermes_inbox/` | bot daemon | inbox_watcher | fresh inbound messages, awaiting LLM call |
| `/tmp/hermes_inbox/.processing/` | inbox_watcher | inbox_watcher | per-msg lock; only the watcher moves files |
| `/tmp/hermes_inbox/.done/` | inbox_watcher | nobody (terminal) | successful LLM replies; never re-consumed |
| `/tmp/hermes_inbox/.error/` | inbox_watcher | inbox_watcher | failures; eligible for retry after 60s |
| `/tmp/hermes_outbox/` | inbox_watcher | bot daemon | LLM replies awaiting Feishu POST |
| `/tmp/inbox_watcher.pid` | inbox_watcher | humans + tools | watcher pid for status / kill |
| `~/.hermes/logs/inbox-watcher.out.log` | inbox_watcher | humans | one line per cycle, including text[:80] |
| `~/.hermes/logs/feishu_bot_daemon.out.log` | bot daemon | humans | ws activity + outbox POSTs |

**Atomicity invariant**: the bot daemon writes a fresh inbox file with
**write-then-rename** (`os.replace` on Python, `os.WriteFile` + `os.Rename`
on Go) so a concurrent watcher never reads a half-written file. The watcher
then `os.rename`s the same file into `.processing/`; this rename is also
atomic on the same filesystem (`/tmp` is one FS on macOS). The
`.processing/` rename is the **lock**: two concurrent watchers race on
it, one wins, the other gets `FileNotFoundError` and moves on (safe,
idempotent).

## 2. Inbox JSON schema (bot daemon → watcher)

Path: `/tmp/hermes_inbox/<msg_id>.json`

```json
{
  "msg_id":      "om_xxxxxxxxxxxxxxxxxxxxxxxx",
  "chat_id":     "oc_xxxxxxxxxxxxxxxxxxxxxxxx",
  "text":        "用户发的文字 (already stripped)",
  "sender":      "ou_xxxxxxxxxxxxxxxxxxxxxxxx",
  "received_at": 1717920000.123
}
```

### Per-field reference

| field | type | required | source | example | note |
|---|---|---|---|---|---|
| `msg_id` | string | yes | Feishu event `message_id` | `"om_a1b2c3d4..."` (om_ prefix) | filename stem in every state dir; must be unique per inbound message |
| `chat_id` | string | yes | Feishu event `chat_id` | `"oc_a1b2c3d4..."` (oc_ prefix) | reply target. If starts with `oc_test_`, bot daemon's outbox watcher skips Feishu POST |
| `text` | string | yes | Feishu event message | `"今天天气怎么样"` | Non-empty after `.strip()` required for LLM call. Empty text → reply="[empty input]", `ok=false` |
| `sender` | string | no | Feishu event `sender.sender_id.open_id` | `"ou_a1b2c3d4..."` (ou_ prefix) | informational. Watcher does not route on it |
| `received_at` | float | no | `time.time()` at write | `1717920000.123` | Unix seconds, sub-millisecond. Diagnostics only; not for ordering (filesystem mtime is sort key) |

## 3. Outbox JSON schema (watcher → bot daemon)

Path: `/tmp/hermes_outbox/<msg_id>.json`. **Always written**, even on
LLM failure (so bot daemon can send a system error message).

```json
{
  "msg_id":     "om_xxxxxxxxxxxxxxxxxxxxxxxx",
  "chat_id":    "oc_xxxxxxxxxxxxxxxxxxxxxxxx",
  "ok":         true,
  "reply":      "今天上海多云转晴...",
  "model":      "minimax-cn/MiniMax-M3",
  "duration_sec": 5.12
}
```

### Per-field reference

| field | type | source | purpose |
|---|---|---|---|
| `msg_id` | string | echo of inbox.msg_id | Bot daemon uses to correlate reply with inbound queue. Filename stem of outbox file |
| `chat_id` | string | echo of inbox.chat_id | Bot daemon uses as `receive_id` for `im/v1/messages` POST. Skipped if `oc_test_` prefix |
| `ok` | bool | `rc==0 AND non-empty stdout` | `false` → inbox file staged in `.error/<msg_id>.retry<N>.json` for 60s backoff retry, max 3 attempts |
| `reply` | string | LLM reply text | sent back to Feishu |
| `model` | string | e.g. `"minimax-cn/MiniMax-M3"` | diagnostics |
| `duration_sec` | float | LLM call wall time | diagnostics |

## 4. State machine (paths)

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

## 5. Retry semantics

| Failure | Where | Backoff | Max attempts |
|---|---|---|---|
| LLM `rc!=0` or empty stdout | inbox_watcher | 60 s | 3 |
| Bad JSON parse | inbox_watcher | none (immediate `.error/badjson`) | 1 |
| Feishu POST 4xx (bad request) | bot daemon | none (skip retry) | 1 |
| Feishu POST 5xx (server error) | bot daemon | 60 s | 3 |
| Feishu POST 404 chat not found | bot daemon | none (skip) | 1 |

After max attempts, the file lands in `.error/<msg_id>.retry<N>.json`
**without being moved further**. Operators manually inspect `.error/`
periodically to diagnose root causes.

## 6. The `oc_test_` escape hatch

If `chat_id` starts with `oc_test_`, the bot daemon **skips the Feishu
POST entirely** and just logs the would-be reply. This lets developers
test the full pipeline without spamming real users.

## 7. Cross-OS atomicity

| OS | `/tmp` filesystem | atomic rename works? | Note |
|---|---|---|---|
| macOS | APFS | yes | `/tmp` is same FS as `/tmp/hermes_inbox/` |
| Linux | tmpfs or ext4 | yes | same FS |
| Windows / WSL2 | WSL2's `/tmp` is `tmpfs`, distinct from Windows' `%TEMP%` (NTFS) | **NO** if cross-FS | keep both daemons in same FS |

**Rule**: bot daemon and inbox_watcher MUST be on the same machine
and same filesystem.

## 8. Operational runbook

### "inbox keeps growing" (watcher not consuming)

```bash
ls /tmp/hermes_inbox/*.json 2>/dev/null | wc -l
pgrep -fl inbox_watcher
cat /tmp/inbox_watcher.pid
ps -p $(cat /tmp/inbox_watcher.pid) -o pid,stat,etime
```

Common causes: LLM API rate-limited (429), Hermes CLI binary missing,
LLM API key expired.

### "outbox keeps growing" (bot daemon not POSTing)

```bash
ls /tmp/hermes_outbox/*.json 2>/dev/null | wc -l
pgrep -fl via54Larkbotgo
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier
```

Common causes: Feishu revoked ws capability, App ID/Secret rotated,
network change.

## 9. Cross-implementation conformance

Both implementations honor this protocol:

- **Python**: `via54Larkfix/reference/python-original/feishu_bot_daemon.py` (419 lines, v20.7) + `inbox_watcher.py` (570 lines)
- **Go**: `via54Larkbotgo/main.go` (this repo, skeleton)

## 10. References

- `reference/protocol/inbox_schema.md` — quick-reference of all fields
- `reference/python-original/feishu_bot_daemon.py` — Python implementation
