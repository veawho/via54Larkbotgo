# Hermes integration (Pattern A in depth)

> **Pattern A in depth**: Hermes is the only AI tool currently running in
> this setup, so this section is the end-to-end landing reference. Other
> AI tools (OpenClaw / Codex / Qclaw / antigravity / minimax-code) use the
> same inbox/outbox pattern; the only difference is the inbox_watcher side
> is each framework's own daemon.

## System architecture (running locally)

```
┌────────────────────────────────────────────────────────┐
│  macOS 26.5.1 (daviddeMac-mini)                          │
│                                                            │
│  ┌──────────────────┐    ┌────────────────────────────┐  │
│  │ feishu_bot_      │    │  feishu                    │  │
│  │ daemon.py        │←──→│  ~/.local/bin/feishu       │  │
│  │ (851 lines,      │    │  (CLI wrapper, 19KB)        │  │
│  │  v20.7)          │    └────────────────────────────┘  │
│  │                  │                                    │
│  │ ~/hermes/scripts/│    ┌────────────────────────────┐  │
│  │ feishu_bot_      │    │ inbox_watcher.py            │  │
│  │ daemon.py        │    │ ~/hermes/scripts/          │  │
│  └──────────────────┘    │  (570 lines, fsnotify)      │  │
│           │                └────────────────────────────┘  │
│           │                           │                  │
│           ▼                           ▼                  │
│  ┌──────────────────────────────────────────────┐         │
│  │ /tmp/hermes_inbox/  (bot → watcher)         │         │
│  │ /tmp/hermes_outbox/  (watcher → bot)        │         │
│  │ /tmp/feishu_bot.pid /tmp/inbox_watcher.pid   │         │
│  └──────────────────────────────────────────────┘         │
│                                                            │
│  Hermes Agent LLM call (minimax-cn / GLM-4.6)           │
└────────────────────────────────────────────────────────┘
            │
            ▼
   Feishu WS long-connection (wss://msg-frontier.feishu.cn/ws/v2)
            │
            ▼
   Feishu user (DM / group @bot)
```

## Install (macOS, currently running)

### Prerequisites

```bash
# 1. Feishu app already created
#    In https://open.feishu.cn/app backend, create enterprise custom app:
#    - Capability: bot
#    - Event subscription: im.message.receive_v1 (mandatory)
#    - Permissions: see reference/permissions.md

# 2. App ID + App Secret at ~/.config/feishu/credentials.json
echo '{"app_id": "cli_xxxx", "app_secret": "yyyyy"}' > ~/.config/feishu/credentials.json
chmod 600 ~/.config/feishu/credentials.json
```

### Install Python dependencies

```bash
~/.hermes/bin/uv pip install --python ~/.venvs/feishu-cli/bin/python3 \
  lark-oapi websockets cryptography requests
```

### Deploy bot daemon (Python version; Go skeleton is the future replacement target)

```bash
# 1. Copy daemons
cp /Users/david/.hermes/scripts/feishu_bot_daemon.py ~/.hermes/scripts/
cp /Users/david/.hermes/scripts/inbox_watcher.py ~/.hermes/scripts/

# 2. Install launchd plists (macOS auto-start)
cp /Users/david/.hermes/scripts/com.david.feishu-bot.plist ~/Library/LaunchAgents/
cp /Users/david/.hermes/scripts/com.david.inbox-watcher.plist ~/Library/LaunchAgents/

# 3. Start
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.david.feishu-bot.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.david.inbox-watcher.plist
```

### Verify

```bash
# Check feishu bot process
ps aux | grep feishu_bot_daemon | grep -v grep
# See PID = really running

# Check Feishu WS connection
lsof -nP -p <PID> | grep "msg-frontier"
# See wss://msg-frontier.feishu.cn/ws/v2 = WS long-connection established

# Test: in Feishu, DM the bot or @bot in a group
# Expected: ~/.hermes/logs/inbox-watcher.out.log shows "processing msg_id=..."
# Expected: Feishu receives LLM reply
```

## Configure inbox_watcher

`inbox_watcher.py` defaults to calling the `hermes` CLI (at `~/.hermes/hermes-agent/venv/bin/`):
```python
HERMES_CMD = [
    "/Users/david/.hermes/hermes-agent/venv/bin/hermes",
    "agent", "run", "--model", "minimax-cn/MiniMax-M3",
    "--prompt", "{text}",
    "--max-turns", "5",
]
```

Switch model: change `--model` (e.g. `--model anthropic/claude-sonnet-4`).

## Replace with Go skeleton (TODO)

`main.go` is the Go skeleton; once Hermes E2E verifies, replace the Python daemon:

1. Edit `~/Library/LaunchAgents/com.david.feishu-bot.plist`:
   ```xml
   <key>ProgramArguments</key>
   <array>
     <string>~/Desktop/developments/via54Larkbotgo/bin/via54Larkbotgo</string>
     <string>--app-id</string>
     <string>cli_xxx</string>
     <string>--app-secret</string>
     <string>yyy</string>
   </array>
   ```

2. `launchctl bootout` + `launchctl bootstrap` to restart

3. Hermes `inbox_watcher.py` **stays unchanged** — it only reads inbox JSON, doesn't care what language the bot is in

## Known issues

| Issue | Workaround | Permanent fix |
|---|---|---|
| `Bootstrap failed: 5: Input/output error` (launchd throttle) | wait 60-90s, or `sudo launchctl` | reduce rapid restart cycles |
| `WARN: running with non-venv python` (hermes-agent venv path detection) | ignore (defensive warn) | fix daemon.py detection logic |
| macOS Sequoia `com.apple.provenance` xattr | call `~/.local/bin/feishu` directly, not via launchd plist | (known limitation) |
| `/usr/local/bin/via54` install rejected by spctl | install to `~/.local/bin/via54` to skip quarantine | (macOS standard practice) |

## Migration to other AI tools

`inbox_watcher` is decoupled from Hermes. Any AI tool that can implement
"read /tmp/hermes_inbox/*.json → call LLM → write /tmp/hermes_outbox/*.json"
is compatible:

- **OpenClaw**: write `openclaw_inbox_bridge.py` using OpenClaw's `agent.run()` API
- **Codex CLI**: write `codex_inbox_bridge.sh` calling `codex --prompt {text}`
- **Claude Code**: write `claude_bridge.py` using Anthropic SDK + Feishu streaming
- **Qclaw / antigravity / minimax-code**: each framework similar

## Related

- [inbox/outbox protocol](../protocol/feishu-inbox-protocol.md)
- [Permissions](../reference/permissions.md)
- [AI tools matrix](../reference/ai-tools-matrix.md)
- [macOS install](../guides/install-macos.md)
- [E2E example](../guides/e2e-hermes-bot.md)
