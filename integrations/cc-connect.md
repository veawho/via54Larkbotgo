# cc-connect 集成计划

> **Source**: https://github.com/chenhg5/cc-connect (13.2K stars)
> **目的**: larkbotgo 学习 cc-connect 的 AI agent bridge 模式

## cc-connect 核心

| 组件 | 描述 |
|------|------|
| Bridge Core | 连接 AI CLI (Claude Code/Cursor/Gemini) to IM (Feishu/Slack) |
| Long connection | WebSocket 长连接 (vs Webhook) |
| Multi-tenant | 多个 AI CLI 同时连接一个 IM |
| Per-chat session | 每个 chat 独立 session (Hermes/Doc/Task) |

## 集成步骤

### Phase 1: v1.0 (现在)
- 文档化 cc-connect 模式
- 加 "AI agent bridge" 架构设计

### Phase 2: v1.1
- 实现 Hermes session (vs Doc/Task session)
- 加 multi-CLI support (Claude Code, Codex, OpenClaw)
- WebSocket 长连接 (已有, 优化)

### Phase 3: v1.2
- 多平台 (Slack/Discord/Telegram) - 学 LangBot
