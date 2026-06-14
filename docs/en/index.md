# via54Larkbotgo

> **🌐 Language / 语言**: [← 中文(默认)](zh/) · **English**(you are here)

Cross-OS integration for Feishu / Lark bot, with multi-AI-tool
adapter layer.

This repository solves one specific problem: **on macOS / Windows / Linux,
let AI agents and AI tools (including but not limited to Hermes, OpenClaw,
Codex, AI-IDE tools, Antigravity, Claude, Qclaw, minimax-code, etc.)
plug into a Feishu / Lark bot more cleanly**.

Covers:

- ✅ **Permission scopes for Feishu / Lark bot** (DM, group chat, Feishu
  Docs — per OS) — opening the right scopes in the developer console
- ✅ **Long-connection (WebSocket) vs Webhook** — comparison + selection
  guide for each OS and each AI tool
- ✅ **Multi-OS install guides** (macOS spctl / Windows NSSM / Linux systemd)
- ✅ **AI tool integration matrix** — 8+ AI tools, their plugin / bridge /
  injection points for consuming a Feishu bot
- ✅ **inbox / outbox protocol** — cross-language contract between bot
  daemon and AI agent bridge
- ✅ **End-to-end integration example** (Hermes `inbox_watcher.py` ↔
  Go bot skeleton)

## Repository structure

```
via54Larkbotgo/
├── main.go                            # Go skeleton: WS long-connection + inbox writer + outbox poller
├── go.mod / go.sum                    # github.com/veawho/via54Larkbotgo
├── bin/via54Larkbotgo                 # build artifact (gitignored)
│
├── docs/                              # VitePress site (this file)
│   ├── .vitepress/config.mts          # zh/en + vitepress-sidebar + RSS
│   ├── zh/{guides,reference,protocol}/*.md
│   └── en/{guides,reference,protocol}/*.md
│
├── reference/                         # protocol-of-truth sourced from via54Larkfix
│   ├── python-original/
│   │   ├── feishu_bot_daemon.py       # 419 lines, full Python daemon (the Go replacement target)
│   │   └── feishu_cli_bot_group.py    # 163 lines, Click "feishu bot start --foreground" (sourced from Larkfix root bot/feishu_bot_daemon.py)
│   └── protocol/
│       ├── feishu_inbox_protocol.md   # 22 KB, IPC contract
│       └── inbox_schema.md            # field quick-reference
│
└── README.md (this file)
```

## Quick nav

| You want to… | Read |
|---|---|
| Install Feishu bot for Hermes | [Hermes integration](guides/ai-tools-hermes.md) |
| Install Feishu bot for OpenClaw / Codex | [AI tools matrix](reference/ai-tools-matrix.md) |
| Choose WebSocket vs Webhook | [Connection modes](guides/connection-modes.md) |
| Install on macOS Sequoia | [macOS install](guides/install-macos.md) |
| Install on Windows | [Windows install](guides/install-windows.md) |
| Install on Linux (systemd) | [Linux install](guides/install-linux.md) |
| Open Feishu app permissions | [Permissions](reference/permissions.md) |
| Read the inbox/outbox protocol | [inbox protocol](protocol/feishu-inbox-protocol.md) |
| Run Hermes ↔ bot end-to-end | [E2E example](guides/e2e-hermes-bot.md) |

## Status

| Dimension | Status | Note |
|---|---|---|
| Go skeleton | ✅ builds, 11 MB binary | macOS arm64, Go 1.26.4 |
| Feishu SDK | ✅ `larksuite/oapi-sdk-go/v3@v3.9.5` | `channel.NewClient` + `Channel.OnMessage` |
| Protocol (inbox/outbox) | ✅ field-compatible with `via54Larkfix` Python daemon | md5-verified |
| Multi-OS install | 🚧 macOS running locally; Windows/Linux docs only | |
| Multi-AI-tool integration | 🚧 Hermes running; others documented | |
| E2E Go skeleton ↔ Hermes | ❌ not yet | TODO: replace local Python daemon with Go |
| SSG (VitePress) | ✅ 1.6.4 + zh/en + sidebar + RSS | docs/ in this repo |

## Related projects

- [`veawho/via54Larkfix`](https://github.com/veawho/via54Larkfix) — full archive of Feishu CLI + multi-OS deployment (private)
- [`veawho/via54Skills`](https://github.com/veawho/via54Skills) — high-value skills (including Feishu integration skill)
- [`veawho/via54Design`](https://github.com/veawho/via54Design) — Go design engine (binary at `~/.local/bin/via54`)
- Local Feishu daemon: `~/.hermes/scripts/feishu_bot_daemon.py` (Python, v20.7, 851 lines)
- Local inbox bridge: `~/.hermes/scripts/inbox_watcher.py` (Python, fsnotify enabled)/bin/bash: line 4: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-snap-d3c394fd5e1f.sh: No such file or directory
/bin/bash: line 5: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-cwd-d3c394fd5e1f.txt: No such file or directory
