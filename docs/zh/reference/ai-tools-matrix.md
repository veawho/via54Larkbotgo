# AI 工具集成矩阵

> **本仓库按"主人在定义里列的 AI 工具"统一处理集成**。每个工具有
> 不同集成方式:有的有官方 SDK adapter,有的走 inbox/outbox 桥,有的
> 走 IDE plugin 接口。

## 工具 × 集成方式

| 工具 | 类型 | 集成方式 | 状态 | 文档 |
|---|---|---|---|---|
| **Hermes** | AI Agent | inbox/outbox 桥 (`inbox_watcher.py`) | ✅ 已实跑 (本机) | [→](ai-tools-hermes.md) |
| **OpenClaw** | AI Agent | inbox/outbox 桥 (与 Hermes 相同) | 🚧 文档已写 | [→](ai-tools-hermes.md) |
| **Codex CLI** | AI Agent | inbox/outbox 桥 | 🚧 文档已写 | [→](ai-tools-hermes.md) |
| **Claude Code** | AI-IDE 工具 | API adapter (直接 HTTP) | 🚧 文档已写 | [→](ai-tools-hermes.md) |
| **Qclaw** | AI Agent | inbox/outbox 桥 | 🚧 文档已写 | [→](ai-tools-hermes.md) |
| **antigravity** | AI Agent | inbox/outbox 桥 | 🚧 文档已写 | [→](ai-tools-hermes.md) |
| **minimax-code** | AI Agent | inbox/outbox 桥 | 🚧 文档已写 | [→](ai-tools-hermes.md) |
| **AI-IDE 工具** | IDE 插件 | LSP / VSCode extension | ❌ 需写 | (TODO) |

## 两种集成范式

### 范式 A: inbox/outbox 桥 (适合 AI Agent)

**适用**: Hermes / OpenClaw / Codex / Qclaw / antigravity / minimax-code

**机制**:
```
飞书用户
  ↓ 私聊 / @bot
bot daemon (Go skeleton)
  ↓ 写 /tmp/hermes_inbox/<msg_id>.json
AI Agent inbox_watcher (ps 监控 /tmp/hermes_inbox/)
  ↓ 调 LLM, 写 /tmp/hermes_outbox/<msg_id>.json
bot daemon (Go skeleton) outbox 轮询
  ↓ 飞书回复 API
飞书用户收到回复
```

**协议**:`reference/protocol/feishu_inbox_protocol.md` (22KB)

**实现**:
- bot daemon 端:任一能写 JSON 到磁盘的进程(Go / Python / Node 都行)
- inbox_watcher 端:每个 AI Agent 框架自带的 daemon,如 `inbox_watcher.py`
  是 Hermes 用的

### 范式 B: API adapter (适合 AI-IDE 工具)

**适用**: Claude Code, Cursor, Windsurf

**机制**:
```
飞书用户
  ↓ 私聊
bot daemon
  ↓ 直接调 Claude Code API (Anthropic)
  ↓ 拿 streaming response
  ↓ 飞书回复 (也支持流式)
飞书用户
```

**特点**:
- 不需要 inbox/outbox 中间层
- bot daemon 就是 LLM 客户端
- 简化但失去 inbox_watcher 那种"消息审计、retries、状态机"

**现状**:本仓库 skeleton 用范式 A;范式 B 留 TODO。

## 工具详细说明

每个工具的集成细节在分文档里:

- [Hermes 集成 (范式 A 详解)](ai-tools-hermes.md)
- [AI-IDE 工具集成 (TODO)](ai-tools-ide.md) — 范式 B
- (更多工具分文档将由主人维护)

## 跨工具通用步骤

1. **bot daemon 跑起来**(本机或服务): 收飞书消息 → 写 inbox
2. **AI Agent 端 inbox_watcher 跑起来**: 监控 inbox → 调 LLM → 写 outbox
3. **bot daemon 读 outbox → 飞书回复**
4. (可选) 用 launchd / systemd / NSSM 让 daemon 开机自启 + 异常自动重启

## 凭证管理

所有 AI 工具都共享同一组飞书 bot 凭证:
- App ID + App Secret 在 `~/.config/feishu/credentials.json` (90B 明文)
  或 `~/Library/Application Support/lark-cli/appsecret_cli_*.enc` (60B lark-cli 加密)
- AI 工具自己的 LLM 凭证 (Anthropic API key, OpenAI API key, 等) 各自存
  在 `~/.config/<tool>/` 或环境变量

**不要** 把飞书 App Secret 复制到每个 AI 工具的 config 里——bot daemon
是唯一持有方,AI 工具只通过 inbox 看到用户消息文本(不含凭证)。

## 跨 OS 注意事项

| 工具 | macOS | Windows | Linux |
|---|---|---|---|
| Hermes | ✅ `~/.hermes/scripts/inbox_watcher.py` | ✅ WSL 兼容 | ✅ `~/.local/bin/hermes` |
| OpenClaw | ❌ 未装本机 | (TBD) | (TBD) |
| Codex | ❌ 未装本机 | (TBD) | (TBD) |
| Claude Code | (TBD) | (TBD) | (TBD) |
| Qclaw | ❌ 未装本机 | (TBD) | (TBD) |

> **2026-06-14 状态**: 本机 macOS 26.5.1 + Hermes Agent 实跑, 其他工具待测。

## 相关文档

- [inbox/outbox 协议](../protocol/feishu-inbox-protocol.md) — 跨工具通用契约
- [权限开通说明](permissions.md) — 飞书 app 后台开通
- [Hermes 集成详解](ai-tools-hermes.md) — 唯一已实跑的工具
