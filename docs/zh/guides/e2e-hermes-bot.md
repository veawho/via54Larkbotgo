# E2E Example: Hermes inbox_watcher ↔ Feishu bot (Go skeleton)

> **目标**: 用本仓库的 Go skeleton (或 Python daemon) 跟 `inbox_watcher.py`
> 端到端跑通一次, 看到飞书用户消息从 ws 长连接 → inbox → LLM → outbox → 飞书回复。

## 前提

```bash
# 1. 已按 ../guides/install-macos.md 装好
# 2. inbox_watcher.py 在 ~/.hermes/scripts/
# 3. 飞书 app 凭据在 ~/.config/feishu/credentials.json
# 4. Python venv 在 ~/.local/share/feishu-cli/venv/ (lark-oapi + click + websockets)
```

## 步骤 1: 启 inbox_watcher (前台)

```bash
~/.hermes/hermes-agent/venv/bin/python3 \
  /Users/david/.hermes/scripts/inbox_watcher.py --foreground \
  > ~/.hermes/logs/inbox-watcher.out.log 2>&1 &
echo "  started pid=$!"
sleep 3
# 期望 log: "fsnotify enabled on /tmp/hermes_inbox"
tail -2 ~/.hermes/logs/inbox-watcher.out.log
```

## 步骤 2: 启 bot daemon (Go skeleton, 前台)

```bash
# 第一次跑: 拿 app_id + app_secret
~/.local/bin/via54Larkbotgo --app-id cli_xxx --app-secret yyy \
  > /tmp/via54Larkbotgo.log 2>&1 &
echo "  started pid=$!"
sleep 3
# 期望 log: "via54Larkbotgo starting, app_id=cli_..." + ws connected
tail -3 /tmp/via54Larkbotgo.log

# 验证 ws 连接
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier
# 期望: wss://msg-frontier.feishu.cn/ws/v2 ... ESTABLISHED
```

## 步骤 3: 在飞书发消息

在飞书私聊 bot(或群 @bot),发:"今天天气怎么样?"

## 步骤 4: 看消息流

```bash
# 1. bot daemon 收到消息 → 写 inbox
ls /tmp/hermes_inbox/*.json | head
# 期望: om_xxxxxx.json (Feishu message_id)

# 2. inbox_watcher 拾起 → 调 Hermes LLM
tail -5 ~/.hermes/logs/inbox-watcher.out.log
# 期望: "processing msg_id=om_xxxxxx text='今天天气怎么样'"

# 3. LLM 写 outbox
ls /tmp/hermes_outbox/*.json | head
# 期望: om_xxxxxx.json (同 msg_id)

# 4. bot daemon 读 outbox → 飞书回复
tail -5 /tmp/via54Larkbotgo.log
# 期望: "outbox: POST reply msg_id=om_xxxxxx"
```

## 步骤 5: 在飞书收到 LLM 回复

期望飞书收到类似:
> "今天上海多云转晴, 最高温度 28°C, 最低 22°C..."

## 步骤 6: 错误处理测试

### 6.1 测试 .error/ 路径

故意发一个让 LLM 失败的消息(比如超长 prompt):

```bash
# 1. 期望 watcher log: "WARN: LLM call failed ..."
# 2. 期望 inbox/.error/om_xxxxxx.retry1.json 出现
# 3. 60s 后 watcher 重试 (max 3 次)
ls /tmp/hermes_inbox/.error/
```

### 6.2 测试 .done/ 路径

```bash
ls /tmp/hermes_inbox/.done/ | head
# 成功处理的消息最终落 .done/ (terminal)
```

### 6.3 测试 oc_test_ chat_id 跳过 (offline dev)

```bash
# 在飞书 app 后台, 给测试群 chat_id 改 oc_test_xxx 前缀
# 期望: bot daemon 收消息, 但不实际 POST 飞书 (避免开发时骚扰真实用户)
tail /tmp/via54Larkbotgo.log
# 期望: "chat_id starts with oc_test_, skip POST"
```

## 步骤 7: 退出清理

```bash
pkill -f via54Larkbotgo
pkill -f inbox_watcher.py
# 清理 inbox / outbox 测试数据
rm -f /tmp/hermes_inbox/{om_*}.json /tmp/hermes_inbox/.processing/* /tmp/hermes_outbox/{om_*}.json
```

## 完整 E2E 一图流

```
[飞书用户]  私聊 "今天天气?"
     │
     ▼ ws://msg-frontier.feishu.cn
[bot daemon] ← via54Larkbotgo
     │  larkws.NewClient().OnMessage()
     │  Unmarshal → InboxMessage{MsgID, ChatID, Text, SenderOpenID, SenderName, ReceivedAt}
     │  write-then-rename → /tmp/hermes_inbox/om_xxx.json
     ▼
[inbox_watcher.py]  fsnotify enabled
     │  Path.iterdir() 新增 om_xxx.json
     │  rename → /tmp/hermes_inbox/.processing/om_xxx.json  (lock)
     │  HERMES_CMD = [hermes, agent, run, --prompt {text}]
     │  subprocess.run(HERMES_CMD, ...)  →  5.12s duration
     │  write-then-rename → /tmp/hermes_outbox/om_xxx.json
     ▼
[bot daemon outbox 轮询]  5s poll
     │  Path.iterdir() 新增 om_xxx.json
     │  ch.Send(ctx, &SendInput{ReceiveID: chat_id, MsgType: "text", Text: reply})
     │  lark-sdk → POST wss://open.feishu.cn/open-apis/im/v1/messages
     │  mv → /tmp/hermes_outbox/.done/om_xxx.json
     ▼
[飞书用户]  收到 LLM 回复

[inbox_watcher.py]  mv → /tmp/hermes_inbox/.done/om_xxx.json
     ▼
     终态: 8 个 directory 都更新
```

## 跨 OS 注意

| OS | inbox 路径 | 备注 |
|---|---|---|
| macOS | `/tmp/hermes_inbox/` | macOS 默认 `/tmp` 是同 FS, atomic rename OK |
| Linux | `/tmp/hermes_inbox/` | 同上 |
| Windows (WSL2) | `/tmp/hermes_inbox/` (在 WSL 内) | WSL 跟 Windows FS 不同, atomic rename 跨 FS 失败 |

**跨 OS 部署**: inbox_watcher 跟 bot daemon **必须在同一台机 + 同一 FS**,
否则 atomic rename 失败, watcher 读到半截 JSON 会丢消息。

## 相关

- [inbox/outbox 协议](../protocol/feishu-inbox-protocol.md) — 22KB 详细规范
- [Hermes 集成](../guides/ai-tools-hermes.md)
- [macOS 安装](../guides/install-macos.md)
