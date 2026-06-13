# Hermes 集成 (范式 A 详解)

> **范式 A 详解**: Hermes 是本仓库唯一已实跑的 AI 工具,本节是它的端到端
> 落地参考。其他 AI 工具(OpenClaw / Codex / Qclaw / antigravity / minimax-code)
> 走相同的 inbox/outbox 范式,只是 inbox_watcher 端是各自框架自己的 daemon。

## 系统架构 (本机实跑)

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
   飞书 ws 长连接 (wss://msg-frontier.feishu.cn/ws/v2)
            │
            ▼
   飞书用户 (私聊 / 群聊)
```

## 安装步骤 (本机 macOS)

### 前置

```bash
# 1. 飞书 app 已建
#    在 https://open.feishu.cn/app 后台, 创建企业自建应用:
#    - 能力: 机器人 (bot)
#    - 事件订阅: im.message.receive_v1 (必须)
#    - 权限: 见 reference/permissions.md

# 2. App ID + App Secret 落到 ~/.config/feishu/credentials.json
echo '{"app_id": "cli_xxxx", "app_secret": "yyyyy"}' > ~/.config/feishu/credentials.json
chmod 600 ~/.config/feishu/credentials.json
```

### 装 Python 依赖

```bash
~/.hermes/bin/uv pip install --python ~/.local/share/feishu-cli/venv/bin/python3 \
  lark-oapi websockets cryptography requests
```

### 部署 bot daemon (Python 版本, Go skeleton 是后继替换目标)

```bash
# 1. 复制 daemon
cp /Users/david/.hermes/scripts/feishu_bot_daemon.py ~/.hermes/scripts/
cp /Users/david/.hermes/scripts/inbox_watcher.py ~/.hermes/scripts/

# 2. 装 launchd plist (macOS 开机自启)
cp /Users/david/.hermes/scripts/com.david.feishu-bot.plist ~/Library/LaunchAgents/
cp /Users/david/.hermes/scripts/com.david.inbox-watcher.plist ~/Library/LaunchAgents/

# 3. 启动
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.david.feishu-bot.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.david.inbox-watcher.plist
```

### 验证

```bash
# 看 feishu bot 进程
ps aux | grep feishu_bot_daemon | grep -v grep
# 看到 PID = 真的在跑

# 看飞书 ws 连接
lsof -nP -p <PID> | grep "msg-frontier"
# 看到 wss://msg-frontier.feishu.cn/ws/v2 = ws 长连接已建立

# 测试: 在飞书给 bot 发私聊 / 群 @bot
# 期望: ~/.hermes/logs/inbox-watcher.out.log 出现 "processing msg_id=..."
# 期望: 飞书收到 LLM 回复
```

## 配置 inbox_watcher

`inbox_watcher.py` 默认调 `hermes` CLI (在 `~/.hermes/hermes-agent/venv/bin/`):
```python
HERMES_CMD = [
    "/Users/david/.hermes/hermes-agent/venv/bin/hermes",
    "agent", "run", "--model", "minimax-cn/MiniMax-M3",
    "--prompt", "{text}",
    "--max-turns", "5",
]
```

切换模型:改 `--model` 参数 (e.g. `--model anthropic/claude-sonnet-4`)。

## 替换为 Go skeleton (TODO)

`main.go` 是 Go skeleton,等 Hermes 端 E2E 验证后替换 Python daemon:

1. 改 `~/Library/LaunchAgents/com.david.feishu-bot.plist`:
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

2. `launchctl bootout` + `launchctl bootstrap` 重启

3. Hermes `inbox_watcher.py` **不动**——它只读 inbox JSON,跟 bot 实现语言无关

## 已知问题

| 问题 | 临时解 | 永久解 |
|---|---|---|
| `Bootstrap failed: 5: Input/output error` (launchd throttle) | 等 60-90s 重试,或 `sudo launchctl` | 减少 plist 错误重启次数 |
| `WARN: running with non-venv python` (hermes-agent venv 路径检测) | 忽略(防御性 warn) | 改 daemon.py 检测逻辑 |
| macOS Sequoia `com.apple.provenance` xattr | bot 路径直接调 `~/.local/bin/feishu`,不走 launchd plist | (已知 limitation) |
| `/usr/local/bin/via54` 装被 spctl 拒绝 | 装到 `~/.local/bin/via54` 跳过 quarantine | (macOS 标准做法) |

## 迁移到其他 AI 工具

inbox_watcher 跟 Hermes 解耦,任一 AI 工具只要实现"读 /tmp/hermes_inbox/*.json → 调 LLM → 写 /tmp/hermes_outbox/*.json"就行:

- **OpenClaw**: 写 `openclaw_inbox_bridge.py`,用 OpenClaw 的 `agent.run()` API
- **Codex CLI**: 写 `codex_inbox_bridge.sh`,调 `codex --prompt {text}`
- **Claude Code**: 写 `claude_bridge.py`,用 Anthropic SDK + 飞书 streaming
- **Qclaw / antigravity / minimax-code**: 各自 framework 类似

## 相关文档

- [inbox/outbox 协议](../protocol/feishu-inbox-protocol.md)
- [权限开通说明](../reference/permissions.md)
- [AI 工具集成矩阵](../reference/ai-tools-matrix.md)
- [macOS 安装指南](../guides/install-macos.md)
- [E2E example](../guides/e2e-hermes-bot.md)
