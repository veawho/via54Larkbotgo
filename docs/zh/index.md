# via54Larkbotgo

> **🌐 Language / 语言**: **中文(默认 · you are here)** · [English →](en/)

飞书 / Lark bot **跨 OS 集成 + 多 AI 工具接入**参考实现。

本仓库解决一个具体问题:**在 macOS / Windows / Linux 中,让 AI Agent
和 AI 工具(包括但不限于 Hermes、OpenClaw、Codex、AI-IDE 工具、
Antigravity、Claude、Qclaw、minimax-code 等等)可以更好地接入
飞书 / Lark bot**。

涵盖内容:

- ✅ **飞书 / Lark bot 私聊、群聊、飞书文档全能力的权限开通说明**(每个 OS 一份)
- ✅ **长连接(WebSocket)和 Webhook 两种连接方式的对比和选择指南**
- ✅ **多 OS 安装指南**(macOS spctl / Windows NSSM / Linux systemd)
- ✅ **AI 工具集成矩阵**:把 bot 接到 8+ AI 工具的 plugin / 桥 / 注入点
- ✅ **inbox / outbox 协议**(跨语言契约,bot daemon ↔ AI agent 桥)
- ✅ **端到端集成 example**(Hermes `inbox_watcher.py` ↔ Go bot skeleton)

## 仓库结构

```
via54Larkbotgo/
├── main.go                            # Go skeleton: WS 长连接 + inbox writer + outbox poller
├── go.mod / go.sum                    # github.com/veawho/via54Larkbotgo
├── bin/via54Larkbotgo                 # 编译产物 (gitignored)
│
├── docs/                              # VitePress 站点 (本文件)
│   ├── .vitepress/config.mts          # zh/en + vitepress-sidebar + RSS
│   ├── zh/{guides,reference,protocol}/*.md
│   └── en/{guides,reference,protocol}/*.md
│
├── reference/                         # 拆自 via54Larkfix 的"协议真相源"
│   ├── python-original/
│   │   ├── feishu_bot_daemon.py       # 419 行, 完整 Python daemon (被 Go 替代的对象)
│   │   └── feishu_cli_bot_group.py    # 163 行, Click group "feishu bot start --foreground" (源自 Larkfix root bot/feishu_bot_daemon.py)
│   └── protocol/
│       ├── feishu_inbox_protocol.md   # 22 KB, IPC 契约
│       └── inbox_schema.md            # 字段速查表
│
└── README.md (你正在读)
```

## 快速导航

| 你想… | 看这里 |
|---|---|
| 给 Hermes 装飞书 bot | [Hermes 集成](guides/ai-tools-hermes.md) |
| 给 OpenClaw / Codex 装飞书 bot | [AI 工具集成矩阵](reference/ai-tools-matrix.md) |
| 选 WebSocket 还是 Webhook | [连接方式对比](guides/connection-modes.md) |
| 在 macOS Sequoia 上安装 | [macOS 安装](guides/install-macos.md) |
| 在 Windows 上安装 | [Windows 安装](guides/install-windows.md) |
| 在 Linux (systemd) 上安装 | [Linux 安装](guides/install-linux.md) |
| 给飞书 app 开通权限 | [权限开通说明](reference/permissions.md) |
| 看 inbox/outbox 协议 | [inbox 协议](protocol/feishu-inbox-protocol.md) |
| 端到端跑通 Hermes ↔ bot | [E2E example](guides/e2e-hermes-bot.md) |

## 状态

| 维度 | 状态 | 备注 |
|---|---|---|
| Go skeleton | ✅ 编译通过, 11 MB binary | macOS arm64, Go 1.26.4 |
| 飞书 SDK | ✅ `larksuite/oapi-sdk-go/v3@v3.9.5` | `channel.NewClient` + `Channel.OnMessage` |
| 协议 (inbox/outbox) | ✅ 跟 `via54Larkfix` Python daemon 字段一致 | md5 验证 |
| 多 OS 安装 | 🚧 macOS 已配 (本机实跑), Windows/Linux 待补 | 文档先写, 实现后跟 |
| 多 AI 工具集成 | 🚧 Hermes 已实跑 (本机 inbox_watcher.py ↔ bot daemon), 其他待写 | |
| E2E Go skeleton ↔ Hermes | ❌ 未对接 | TODO: 把 Go skeleton 替换本机 Python daemon |
| SSG (VitePress) | ✅ 1.6.4 + zh/en + sidebar + RSS | 本仓库 docs/ |

## 关联项目

- [`veawho/via54Larkfix`](https://github.com/veawho/via54Larkfix) — 飞书 CLI + 多 OS 部署的完整归档(private)
- [`veawho/via54Skills`](https://github.com/veawho/via54Skills) — 高价值 skills 集合(含飞书集成 skill)
- [`veawho/via54Design`](https://github.com/veawho/via54Design) — Go 设计引擎(本机二进制装在 `~/.local/bin/via54`)
- 本机飞书 daemon: `~/.hermes/scripts/feishu_bot_daemon.py` (Python, v20.7, 851 行)
- 本机 inbox 桥: `~/.hermes/scripts/inbox_watcher.py` (Python, fsnotify enabled)/bin/bash: line 4: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-snap-d3c394fd5e1f.sh: No such file or directory
/bin/bash: line 5: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-cwd-d3c394fd5e1f.txt: No such file or directory
