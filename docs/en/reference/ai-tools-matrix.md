# AI tool integration matrix

> **This repo's scope (per owner definition) is integrating Feishu/Lark bot
> with multiple AI tools** — Hermes, OpenClaw, Codex, AI-IDE tools,
> Antigravity, Claude, Qclaw, minimax-code, etc. Each tool has a different
> integration surface: official SDK adapter, inbox/outbox bridge, or
> IDE plugin interface.

## Tool × integration mode

| Tool | Type | Integration mode | Status | Doc |
|---|---|---|---|---|
| **Hermes** | AI Agent | inbox/outbox bridge (`inbox_watcher.py`) | ✅ running locally | [→](ai-tools-hermes.md) |
| **OpenClaw** | AI Agent | inbox/outbox bridge (same as Hermes) | 🚧 documented | [→](ai-tools-hermes.md) |
| **Codex CLI** | AI Agent | inbox/outbox bridge | 🚧 documented | [→](ai-tools-hermes.md) |
| **Claude Code** | AI-IDE tool | API adapter (direct HTTP) | 🚧 documented | [→](ai-tools-hermes.md) |
| **Qclaw** | AI Agent | inbox/outbox bridge | 🚧 documented | [→](ai-tools-hermes.md) |
| **antigravity** | AI Agent | inbox/outbox bridge | 🚧 documented | [→](ai-tools-hermes.md) |
| **minimax-code** | AI Agent | inbox/outbox bridge | 🚧 documented | [→](ai-tools-hermes.md) |
| **AI-IDE tools** | IDE plugin | LSP / VSCode extension | ❌ TODO | (TBD) |

## Two integration patterns

### Pattern A: inbox/outbox bridge (for AI Agents)

**For**: Hermes / OpenClaw / Codex / Qclaw / antigravity / minimax-code

**Mechanism**:
```
Feishu user
  ↓ DM / @bot
bot daemon (Go skeleton)
  ↓ write /tmp/hermes_inbox/<msg_id>.json
AI Agent inbox_watcher (ps-watches /tmp/hermes_inbox/)
  ↓ calls LLM, writes /tmp/hermes_outbox/<msg_id>.json
bot daemon (Go skeleton) outbox poller
  ↓ Feishu reply API
Feishu user receives reply
```

**Protocol**: `reference/protocol/feishu_inbox_protocol.md` (22 KB)

**Implementation**:
- bot daemon side: any process that can write JSON to disk (Go / Python / Node)
- inbox_watcher side: AI Agent framework's own daemon; e.g. `inbox_watcher.py` is what Hermes uses

### Pattern B: API adapter (for AI-IDE tools)

**For**: Claude Code, Cursor, Windsurf

**Mechanism**:
```
Feishu user
  ↓ DM
bot daemon
  ↓ directly calls Claude Code API (Anthropic)
  ↓ receives streaming response
  ↓ Feishu reply (also supports streaming)
Feishu user
```

**Traits**:
- No inbox/outbox intermediate layer
- bot daemon IS the LLM client
- Simpler, but loses the audit / retry / state machine of inbox_watcher

**Current state**: this repo's skeleton uses Pattern A; Pattern B is TODO.

## Per-tool details

Per-tool integration specifics are in separate docs:

- [Hermes integration (Pattern A in depth)](ai-tools-hermes.md)
- [AI-IDE tools integration (TODO)](ai-tools-ide.md) — Pattern B
- (More tool docs maintained by owner)

## Universal steps (cross-tool)

1. **bot daemon runs** (local or server): receives Feishu messages → writes inbox
2. **AI Agent inbox_watcher runs**: monitors inbox → calls LLM → writes outbox
3. **bot daemon reads outbox → Feishu reply**
4. (Optional) use launchd / systemd / NSSM for auto-start + restart-on-crash

## Credential management

All AI tools share the same Feishu bot credentials:
- App ID + App Secret at `~/.config/feishu/credentials.json` (90 B plaintext)
  or `~/Library/Application Support/lark-cli/appsecret_cli_*.enc` (60 B lark-cli-encrypted)
- Each AI tool's own LLM credentials (Anthropic API key, OpenAI API key, etc.)
  live in `~/.config/<tool>/` or environment variables

**Don't** copy the Feishu App Secret into every AI tool's config — bot
daemon is the sole holder; AI tools only see user message text via inbox
(no credentials).

## Per-OS notes

| Tool | macOS | Windows | Linux |
|---|---|---|---|
| Hermes | ✅ `~/.hermes/scripts/inbox_watcher.py` | ✅ WSL-compatible | ✅ `~/.local/bin/hermes` |
| OpenClaw | ❌ not installed locally | (TBD) | (TBD) |
| Codex | ❌ not installed locally | (TBD) | (TBD) |
| Claude Code | (TBD) | (TBD) | (TBD) |
| Qclaw | ❌ not installed locally | (TBD) | (TBD) |

> **2026-06-14 status**: macOS 26.5.1 + Hermes Agent running locally, other tools
> pending test.

## Related

- [inbox/outbox protocol](../protocol/feishu-inbox-protocol.md) — cross-tool contract
- [Permissions](permissions.md) — open in Feishu app backend
- [Hermes integration in depth](ai-tools-hermes.md) — the only tool currently running