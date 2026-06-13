# Feishu Inbox/Outbox Protocol Reference

Authoritative reference for the file-IPC protocol that connects the
`feishu bot daemon` (lark-oapi ws long-connection) to the Hermes LLM
through `inbox_watcher.py`. This is the schema + state machine + error
handling contract that the two daemons honor; if you change one side
without the other, replies will silently break.

If you want a high-level overview first, read `../SKILL.md` and come
back here when debugging a specific failure mode.

---

## 1. Directory layout

All paths are absolute. Both daemons must agree on these.

| directory                            | written by            | read by                | purpose                                      |
|--------------------------------------|-----------------------|------------------------|----------------------------------------------|
| `/tmp/hermes_inbox/`                 | bot daemon            | inbox_watcher          | fresh inbound messages, awaiting LLM call    |
| `/tmp/hermes_inbox/.processing/`     | inbox_watcher         | inbox_watcher          | per-msg lock; only the watcher moves files   |
| `/tmp/hermes_inbox/.done/`           | inbox_watcher         | nobody (terminal)      | successful LLM replies; never re-consumed    |
| `/tmp/hermes_inbox/.error/`          | inbox_watcher         | inbox_watcher          | failures; eligible for retry after 60s       |
| `/tmp/hermes_outbox/`                | inbox_watcher         | bot daemon             | LLM replies awaiting Feishu POST             |
| `/tmp/inbox_watcher.pid`             | inbox_watcher         | humans + tools         | watcher pid for status / kill                |
| `~/.hermes/logs/inbox_watcher.log`   | inbox_watcher         | humans                 | one line per cycle, including text[:80]      |
| `~/.hermes/logs/feishu_bot_daemon.log`| bot daemon            | humans                 | lark-oapi ws activity + outbox POSTs         |

Atomicity invariant: the bot daemon writes a fresh inbox file with
`write-then-rename` (`os.replace`) so a concurrent watcher never reads a
half-written file. The watcher then `os.rename`s the same file into
`.processing/`; this rename is also atomic on the same filesystem
(`/tmp` is one FS on macOS). The `.processing/` rename is the **lock**:
two concurrent watchers will race on it, one wins, the other gets
`FileNotFoundError` and moves on (safe, idempotent — see the PID file
race note in `../SKILL.md` Security).

---

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

| field         | type     | required | source                  | example                            | notes                                                                                                                |
|---------------|----------|----------|-------------------------|------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `msg_id`      | string   | yes      | Feishu event `message_id` | `"om_a1b2c3d4..."`               | `om_` prefix; used as the filename stem in every state dir. Must be unique per inbound message.                       |
| `chat_id`     | string   | yes      | Feishu event `chat_id`  | `"oc_a1b2c3d4..."`                | `oc_` prefix; reply target. If it starts with `oc_test_`, the bot daemon's outbox watcher skips the Feishu POST.       |
| `text`        | string   | yes      | Feishu event message    | `"今天天气怎么样"`                | Non-empty after `.strip()` is required for the LLM call. Empty text → `reply="[empty input]"`, `ok=false`.          |
| `sender`      | string   | no       | Feishu event `sender.sender_id.open_id` | `"ou_a1b2c3d4..."`   | `ou_` prefix; informational. Watcher does not route on it.                                                           |
| `received_at` | float    | no       | `time.time()` at write  | `1717920000.123`                  | Unix seconds, sub-millisecond. Used only for diagnostics, not for ordering (filesystem mtime is the sort key).       |

### Validation rules (watcher side)

- File must be valid JSON. `json.JSONDecodeError` → log
  `WARN: bad payload at <path>; moving to .error` and the file is moved
  straight to `.error/` (no retry — the content will never become valid).
- `text` after `.strip()` must be non-empty. Empty → reply `"[empty input]"`,
  `ok=false`, file moved to `.done/` (terminal — the watcher made a
  *decision*, not a *failure*).
- All other fields may be missing. Defaults:
  - `msg_id` → `inbox_path.stem` (the filename)
  - `chat_id` → `""` (the bot daemon will see an empty `chat_id` and skip
    the Feishu POST in addition to the `oc_test_` rule)
  - `sender` → not echoed to outbox
  - `received_at` → not echoed to outbox

---

## 3. Outbox JSON schema (watcher → bot daemon)

Path: `/tmp/hermes_outbox/<msg_id>.json`. **Always written**, even on
`ok=false`, so the bot daemon can decide whether to POST or just log.

```json
{
  "msg_id":        "om_xxxxxxxxxxxxxxxxxxxxxxxx",
  "chat_id":       "oc_xxxxxxxxxxxxxxxxxxxxxxxx",
  "reply":         "LLM 纯文本回复 (stdout, trimmed)",
  "model":         "hermes",
  "duration_sec":  5.234,
  "completed_at":  1717920006.357,
  "ok":            true
}
```

### Per-field reference

| field           | type    | source                              | notes                                                                                                                |
|-----------------|---------|-------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `msg_id`        | string  | echo from inbox                     | Bot daemon uses this to correlate the reply with its inbound queue. Filename stem of the outbox file.                 |
| `chat_id`       | string  | echo from inbox                     | Bot daemon uses this as `receive_id` for the `im/v1/messages` POST. Skipped if starts with `oc_test_`.                 |
| `reply`         | string  | LLM stdout (trimmed)                | Posted to Feishu as `msg_type=text`. Sentinels: `"[LLM returned empty output]"` (rc=0, empty stdout), `"[LLM timeout after 90s]"`, `"[LLM failed rc=N: <stderr-tail>]"` (last 500 chars), `"[LLM invocation error: <e>]"`, `"[empty input]"`. |
| `model`         | string  | hardcoded `"hermes"`                | Stable token; the CLI does not self-identify. Future: could echo actual model name.                                  |
| `duration_sec`  | float   | `time.time()` wall-clock            | Rounded to 3 decimal places. Includes the full subprocess lifecycle.                                                 |
| `completed_at`  | float   | `time.time()` after subprocess exits| Unix seconds.                                                                                                        |
| `ok`            | bool    | `rc==0` AND non-empty stdout        | `false` → inbox file staged in `.error/<msg_id>.retry<N>.json` for 60s backoff retry, max 3 attempts.                |

### Reply sentinels — what to look for in the log

| reply starts with                       | meaning                                        | user-visible?                                  |
|-----------------------------------------|------------------------------------------------|------------------------------------------------|
| `[LLM timeout after 90s]`               | hermes subprocess hit `LLM_TIMEOUT`            | yes — bot POSTs the bracket string verbatim   |
| `[LLM failed rc=N: ...]`                | hermes subprocess exited non-zero              | yes — bot POSTs the bracket string verbatim   |
| `[LLM invocation error: ...]`           | watcher could not even spawn the subprocess    | yes — bot POSTs the bracket string verbatim   |
| `[LLM returned empty output]`           | rc=0, empty stdout                             | yes — bracket string                           |
| `[empty input]`                         | watcher received `text=""`                     | yes — bracket string                           |
| anything else                           | real LLM reply                                 | yes — actual text                              |

These sentinels are intentional: the bot daemon posts whatever is in
`reply`, no filtering. If you see brackets in the Feishu chat, the LLM
backend is the problem; if you see the actual LLM text, the bridge is
working.

---

## 4. State machine (per `<msg_id>`)

ASCII diagram of directory transitions for a single message as it
flows through `/tmp/hermes_inbox/`:

```
                      bot daemon writes
                              |
                              v
                  +-----------------------+
                  |  /tmp/hermes_inbox/   |   <-- root, "fresh"
                  |  <msg_id>.json        |
                  +----------+------------+
                             |
                  watcher: os.rename (atomic)
                             |
                             v
                  +-----------------------+
                  |  .processing/         |   <-- locked
                  |  <msg_id>.json        |
                  +----+-----------+------+
                       |           |
              ok=true  |           |  ok=false
                       |           |
                       v           v
              +-----------+   +--------------------------+
              |  .done/   |   |  .error/                 |
              |  <id>.json|   |  <id>.retry<N>.json      |   N in [1..3]
              | (terminal)|   +------------+-------------+
              +-----------+                |
                                           |  60s elapsed
                                           |  AND attempt < 3
                                           v
                              +-----------------------------+
                              | back to /tmp/hermes_inbox/  |   <-- retry
                              | <msg_id>.json               |       (new mtime)
                              +-------------+---------------+
                                            |
                                            | (loop until ok=true OR attempts > 3)
                                            v
                              +-----------------------------+
                              |  .error/                    |
                              |  <msg_id>.json              |   <-- terminal give-up
                              |  (no .retryN suffix)        |       (no further retries)
                              +-----------------------------+
```

### States (5)

1. **root** — `/tmp/hermes_inbox/<msg_id>.json`. Fresh, unconsumed.
   Lexicographic order of `iterdir()` is the polling order.
2. **processing** — `/tmp/hermes_inbox/.processing/<msg_id>.json`.
   Watcher holds this rename. If the watcher dies here, the file is
   stranded (see "Stuck in `.processing/`" in the SKILL troubleshooting
   section).
3. **done** — `/tmp/hermes_inbox/.done/<msg_id>.json`. Terminal success.
   Never re-consumed. Safe to delete for disk space.
4. **error (retry-pending)** — `/tmp/hermes_inbox/.error/<msg_id>.retry<N>.json`,
   `N ∈ {1, 2, 3}`. Will be re-queued after 60s of mtime age.
5. **error (terminal)** — `/tmp/hermes_inbox/.error/<msg_id>.json` (no
   `.retryN` suffix). Given up. Safe to delete; not re-consumed.

### Retry counting

`_count_retries(msg_id)` (in `inbox_watcher.py`) counts all files in
`.error/` whose name is either `<msg_id>.json` or starts with
`<msg_id>.retry`. So **the counter is filesystem-resident**: a manual
`rm` of a `.retry1.json` file effectively un-retries a message. Useful
for manual recovery, dangerous for "I deleted some `.error/` files to
save space" — those deletions can cause a poisoned message to be
re-attempted indefinitely.

### Retry timing

- `RETRY_AFTER = 60.0` seconds (in `inbox_watcher.py` constants).
- Eligible retry: `time.time() - error_path.stat().st_mtime >= 60.0`.
- `MAX_RETRIES = 3` — after the 3rd failure, the next `.retry4` write is
  renamed to `<msg_id>.json` (no suffix) and the message is terminal.

### Why `.processing/` cannot be a real lock

A real lock would be `flock(fd, LOCK_EX)`. We don't use one because
`/tmp` on macOS does not guarantee POSIX advisory locks survive across
all NFS-mounted locations, and the file is being moved by the locking
process anyway. The atomic `os.rename` is the lock: at most one watcher
wins; the other gets `FileNotFoundError` and moves on. This is correct
behavior, not a bug.

---

## 5. Error cases and recovery

### 5.1 LLM call fails 3 times in a row

Symptoms:
- `inbox_watcher.log` shows three `LLM failed rc=N: ...` or
  `LLM timeout after 90s` lines for the same `msg_id`.
- The inbox file ends up at `/tmp/hermes_inbox/.error/<msg_id>.json`
  (no `.retryN` suffix — terminal give-up).
- The bot daemon will still POST the bracket-string reply to Feishu
  (last attempt's `reply` field), so the user *does* see something —
  just not a useful answer.

Recovery (in order of preference):
1. Check `MINIMAX_CN_API_KEY` / `GLM_API_KEY` rotation. Most common
   cause: an API key was rotated on the provider side and `.env` was
   not refreshed.
2. Check connectivity: `curl -sS -o /dev/null -w '%{http_code}\n' \
   https://api.minimaxi.com/anthropic`. Should be 200 or 401 (auth
   challenge), not timeout.
3. Manual retry: move the file from `.error/` back to the root:
   `mv /tmp/hermes_inbox/.error/<msg_id>.json /tmp/hermes_inbox/<msg_id>.json`
   — the next polling cycle will re-process it. The retry counter
   resets to 0 because no `.retryN` file is in `.error/` for this
   `msg_id` anymore.
4. Give up: delete `/tmp/hermes_inbox/.error/<msg_id>.json` and the
   matching outbox `/tmp/hermes_outbox/<msg_id>.json`. The user will
   not get a reply.

### 5.2 Bot daemon dead (pid 71631 gone)

Symptoms:
- `ps -p 71631` returns nothing.
- `/tmp/hermes_inbox/` is **empty** (the bot daemon is the only writer).
- `/tmp/hermes_outbox/` may still have old replies; nothing is reading
  them anymore.
- LLM replies from in-flight messages before the crash are stranded in
  `outbox/` and will never be POSTed to Feishu.

Recovery:
1. Restart the bot daemon. The launchd plist (when you add it — see
   the SKILL.md "launchd integration" section) will do this
   automatically; without it, restart manually with the nohup wrapper.
2. Confirm ws is up: `lsof -p <new-pid> | grep websockets`.
3. Stranded outbox files: post them manually or just delete. The
   user's chat is now in a "user asked, no reply ever came" state; the
   user will likely re-send, which is fine.

### 5.3 Inbox watcher dead

Symptoms:
- `inbox_watcher.py --status` says `NOT running` (or the pid file is
  stale — i.e. exists but the pid is gone).
- `/tmp/hermes_inbox/` accumulates `<msg_id>.json` files (the bot
  daemon keeps writing; nothing is consuming).
- `/tmp/hermes_outbox/` is empty for new messages.
- LLM does work fine in isolation (`hermes -z 'ping'` returns).

Recovery:
1. `python3 /Users/david/.hermes/scripts/inbox_watcher.py --daemon`.
2. If the daemon refuses to start with "already running pid=N", the
   pid file is stale. `rm /tmp/inbox_watcher.pid` and retry.
3. The accumulated inbox files are safe — atomic writes mean the
   watcher can pick them up in arrival order on the next cycle.

### 5.4 Stuck in `.processing/`

Symptoms:
- `/tmp/hermes_inbox/.processing/<msg_id>.json` exists but is old
  (mtime > 90s).
- No matching outbox file.

Cause: a previous watcher run was `kill -9`'d (or the Mac slept and
lost the subprocess) mid-LLM-call. The atomic move from
`.processing/` to `.done/`/`.error/` never happened.

Recovery:
- **Preferred:** move back to root and let the watcher retry:
  `mv /tmp/hermes_inbox/.processing/<msg_id>.json /tmp/hermes_inbox/<msg_id>.json`.
  The LLM call inside cannot be resumed (the subprocess is gone), so
  this is a full re-attempt — a brand-new 4–7s LLM call.
- **If the message is no longer relevant:** delete both
  `.processing/<msg_id>.json` and the (absent) outbox file. The user
  will not get a reply.

### 5.5 `/tmp` full

Symptoms:
- `OSError: [Errno 28] No space left on device` in either daemon's log.
- Daemons may crash on the next write.

Recovery:
1. `rm /tmp/hermes_inbox/.done/*` — terminal, never re-consumed.
2. `rm /tmp/hermes_inbox/.error/*` — terminal give-up, never re-consumed.
3. **Do NOT** delete `/tmp/hermes_inbox/.processing/*` while a
   watcher cycle is in flight. The watcher will then re-pick a file
   it has already started processing and double-POST a reply.
4. The `inbox/` root and `outbox/` directories are also deletable if
   you are willing to lose those messages. The bot daemon will write
   a new inbox file the next time a message arrives.

### 5.6 Duplicate replies in Feishu

Symptoms:
- The same Feishu message has two replies from the bot in quick
  succession.

Cause: two `inbox_watcher.py` daemons running concurrently (the PID
file race was lost). One wins the `.processing/` rename and posts
once; the other has lost the race on the inbox file but the outbox
file is also being raced on by the bot daemon's outbox watcher, which
POSTs it to Feishu. Or: the user resent the message, which is the
*correct* behavior, not a bug.

Recovery:
1. `pgrep -f inbox_watcher.py` — should return exactly one pid.
2. If two, kill the older one: `kill <pid>`. The `.pid` file points
   to whichever watcher wrote it last, which may not be the one you
   want to keep — `ps -ef | grep inbox_watcher` for the truth.

---

## 6. Debugging checklist

When "the bot is alive but not replying", work through this in order:

1. **Is the bot daemon up?** `ps -p 71631 -o pid,command`. If gone,
   restart (see 5.2). If present, `lsof -p 71631 | grep websockets` —
   you want a live ws socket.
2. **Is the inbox watcher up?** `python3
   /Users/david/.hermes/scripts/inbox_watcher.py --status`. If `NOT
   running`, start it (see 5.3). If "already running" but actually
   dead, `rm /tmp/inbox_watcher.pid` and retry.
3. **Are messages reaching the inbox?** `ls -lt /tmp/hermes_inbox/ |
   head -5`. If empty while the user is actively sending, the bot
   daemon is the failure — check `feishu_bot_daemon.log` for ws
   reconnect storms or auth errors.
4. **Is the watcher picking them up?** Tail
   `~/.hermes/logs/inbox_watcher.log`. You should see one
   `processing msg_id=...` line per 5 seconds. If not, the watcher
   is stuck — kill -9 and restart (it will pick up the stranded
   `.processing/` file on the next cycle if you also follow step 5).
5. **Is the LLM call returning?** Look for `done msg_id=... ok=True
   duration=...s` lines. If you see `ok=False`, the LLM is the
   problem — see 5.1.
6. **Is the outbox being written?** `ls -lt /tmp/hermes_outbox/ |
   head -5`. Should mirror the inbox arrival rate (modulo the 4–7s
   LLM latency).
7. **Is the bot daemon reading the outbox?** Tail
   `feishu_bot_daemon.log` for `POST https://open.feishu.cn/open-apis/im/v1/messages`
   lines. If the outbox is being written but no POST is happening,
   the bot daemon's outbox watcher is broken or stopped.
8. **Is the reply reaching Feishu?** Check the user's chat on the
   phone. If you see a `[LLM failed rc=N: ...]`-style bracket
   string, the bridge is working end-to-end but the LLM is the
   bottleneck.
9. **Reproduce in isolation:** `bash
   /Users/david/.hermes/scripts/test_feishu_e2e.sh`. This bypasses
   the bot daemon entirely and exercises the inbox → LLM → outbox
   pipeline. If this fails, the watcher or LLM is the problem; the
   bot daemon is innocent.

If the e2e test passes but real messages still don't get replies, the
problem is between step 6 and step 7 — the bot daemon's outbox
watcher is not draining `/tmp/hermes_outbox/`. Restart the bot
daemon; that watcher is in-process, not a separate file, so a restart
is the only fix.

---

## 7. Quick reference — file paths

| path                                                | role                                                |
|-----------------------------------------------------|-----------------------------------------------------|
| `/tmp/hermes_inbox/`                                | fresh inbound (root)                                |
| `/tmp/hermes_inbox/.processing/`                    | per-msg watcher lock                                |
| `/tmp/hermes_inbox/.done/`                          | terminal success (safe to `rm`)                     |
| `/tmp/hermes_inbox/.error/`                         | failures; `.retryN` = retry-pending, no suffix = terminal |
| `/tmp/hermes_outbox/`                               | LLM replies awaiting Feishu POST                    |
| `/tmp/inbox_watcher.pid`                            | watcher pid                                         |
| `~/.hermes/logs/inbox_watcher.log`                  | watcher per-cycle log (includes text[:80])          |
| `~/.hermes/logs/feishu_bot_daemon.log`              | bot daemon ws + outbox POST log                     |
| `/Users/david/.hermes/scripts/inbox_watcher.py`     | the watcher source (read this if the schema drifts) |
| `/Users/david/.hermes/scripts/test_feishu_e2e.sh`   | the e2e smoke test                                  |
| `~/Library/LaunchAgents/com.david.feishu-bot.plist` | bot daemon launchd unit (see SKILL.md Advanced)     |
| `~/Library/LaunchAgents/com.david.inbox-watcher.plist` | watcher launchd unit (see SKILL.md Advanced)     |
