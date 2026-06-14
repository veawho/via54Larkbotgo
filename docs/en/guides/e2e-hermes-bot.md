# E2E example: Hermes inbox_watcher ↔ Feishu bot (Go skeleton)

> **Goal**: take this repo's Go skeleton (or Python daemon) end-to-end
> with `inbox_watcher.py` — see a Feishu user message flow from ws
> long-connection → inbox → LLM → outbox → Feishu reply.

## Prerequisites

```bash
# 1. Already installed per ../guides/install-macos.md
# 2. inbox_watcher.py at ~/.hermes/scripts/
# 3. Feishu app credentials at ~/.config/feishu/credentials.json
# 4. Python venv at ~/.venvs/feishu-cli/ (lark-oapi + click + websockets)
```

## Step 1: start inbox_watcher (foreground)

```bash
~/.hermes/hermes-agent/venv/bin/python3 \\
  /Users/david/.hermes/scripts/inbox_watcher.py --foreground \\
  > ~/.hermes/logs/inbox-watcher.out.log 2>&1 &
echo "  started pid=$!"
sleep 3
# Expect log: "fsnotify enabled on /tmp/hermes_inbox"
tail -2 ~/.hermes/logs/inbox-watcher.out.log
```

## Step 2: start bot daemon (Go skeleton, foreground)

```bash
# First run: get app_id + app_secret
~/.local/bin/via54Larkbotgo --app-id cli_xxx --app-secret yyy \\
  > /tmp/via54Larkbotgo.log 2>&1 &
echo "  started pid=$!"
sleep 3
# Expect log: "via54Larkbotgo starting, app_id=cli_..." + ws connected
tail -3 /tmp/via54Larkbotgo.log

# Verify ws connection
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier
# Expect: wss://msg-frontier.feishu.cn/ws/v2 ... ESTABLISHED
```

## Step 3: send a Feishu message

In Feishu, DM the bot (or @bot in a group), send: "How is the weather today?"

## Step 4: watch the message flow

```bash
# 1. bot daemon receives message → writes inbox
ls /tmp/hermes_inbox/*.json | head
# Expect: om_xxxxxx.json (Feishu message_id)

# 2. inbox_watcher picks up → calls Hermes LLM
tail -5 ~/.hermes/logs/inbox-watcher.out.log
# Expect: "processing msg_id=om_xxxxxx text='How is the weather today'"

# 3. LLM writes outbox
ls /tmp/hermes_outbox/*.json | head
# Expect: om_xxxxxx.json (same msg_id)

# 4. bot daemon reads outbox → Feishu reply
tail -5 /tmp/via54Larkbotgo.log
# Expect: "outbox: POST reply msg_id=om_xxxxxx"
```

## Step 5: receive LLM reply in Feishu

Expect Feishu to receive something like:
> "Today in Shanghai: cloudy turning sunny, high 28°C, low 22°C..."

## Step 6: error handling tests

### 6.1 Test the `.error/` path

Deliberately send a message that makes the LLM fail (e.g. an extremely long prompt):

```bash
# 1. Expect watcher log: "WARN: LLM call failed ..."
# 2. Expect inbox/.error/om_xxxxxx.retry1.json to appear
# 3. After 60s, watcher retries (max 3 attempts)
ls /tmp/hermes_inbox/.error/
```

### 6.2 Test the `.done/` path

```bash
ls /tmp/hermes_inbox/.done/ | head
# Successfully processed messages end up in .done/ (terminal)
```

### 6.3 Test the `oc_test_` chat_id skip (offline dev)

```bash
# In the Feishu app backend, give a test group chat_id the oc_test_ prefix
# Expect: bot daemon receives message, but does NOT actually POST Feishu
# (prevents development-time spam to real users)
tail /tmp/via54Larkbotgo.log
# Expect: "chat_id starts with oc_test_, skip POST"
```

## Step 7: clean up

```bash
pkill -f via54Larkbotgo
pkill -f inbox_watcher.py
# Clean up inbox / outbox test data
rm -f /tmp/hermes_inbox/{om_*}.json /tmp/hermes_inbox/.processing/* /tmp/hermes_outbox/{om_*}.json
```

## Complete E2E in one diagram

```
[Feishu user]  DM "How is the weather?"
     │
     ▼ ws://msg-frontier.feishu.cn
[bot daemon] ← via54Larkbotgo
     │  larkws.NewClient().OnMessage()
     │  Unmarshal → InboxMessage{MsgID, ChatID, Text, SenderOpenID, SenderName, ReceivedAt}
     │  write-then-rename → /tmp/hermes_inbox/om_xxx.json
     ▼
[inbox_watcher.py]  fsnotify enabled
     │  Path.iterdir() new om_xxx.json
     │  rename → /tmp/hermes_inbox/.processing/om_xxx.json  (lock)
     │  HERMES_CMD = [hermes, agent, run, --prompt {text}]
     │  subprocess.run(HERMES_CMD, ...)  →  5.12s duration
     │  write-then-rename → /tmp/hermes_outbox/om_xxx.json
     ▼
[bot daemon outbox poller]  5s poll
     │  Path.iterdir() new om_xxx.json
     │  ch.Send(ctx, &SendInput{ReceiveID: chat_id, MsgType: "text", Text: reply})
     │  lark-sdk → POST wss://open.feishu.cn/open-apis/im/v1/messages
     │  mv → /tmp/hermes_outbox/.done/om_xxx.json
     ▼
[Feishu user]  receives LLM reply

[inbox_watcher.py]  mv → /tmp/hermes_inbox/.done/om_xxx.json
     ▼
     terminal: all 8 directories updated
```

## Cross-OS note

| OS | inbox path | Note |
|---|---|---|
| macOS | `/tmp/hermes_inbox/` | macOS default `/tmp` is same FS, atomic rename OK |
| Linux | `/tmp/hermes_inbox/` | same |
| Windows (WSL2) | `/tmp/hermes_inbox/` (inside WSL) | WSL vs Windows FS differs, atomic rename fails cross-FS |

**Cross-OS deploy rule**: inbox_watcher and bot daemon **must be on
the same machine + same FS**; otherwise atomic rename fails and the
watcher reading partial JSON will lose messages.

## Related

- [inbox/outbox protocol](../protocol/feishu-inbox-protocol.md) — 22 KB detailed spec
- [Hermes integration](../guides/ai-tools-hermes.md)
- [macOS install](../guides/install-macos.md)