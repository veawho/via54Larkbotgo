# 飞书 Inbox 协议

> **本文件是 Feishu bot daemon(WS 长连接或 Webhook)↔ AI Agent inbox_watcher
> 文件 IPC 协议**的权威参考。

本仓库的 Go skeleton (`main.go`) 和 Python daemon (`via54Larkfix/reference/
python-original/feishu_bot_daemon.py`) 都遵循本协议。单方修改而不通知
另一方会导致静默断链。

> 📄 **本文件从 `via54Larkfix/references/feishu_inbox_protocol.md` (22 KB)
> 直接移植**, 在 bot docs 站点内自包含。

## 1. 目录布局

所有路径绝对。两侧 daemon 必须一致。

| 目录 | 写入方 | 读出方 | 用途 |
|---|---|---|---|
| `/tmp/hermes_inbox/` | bot daemon | inbox_watcher | 新入站消息, 等 LLM 调用 |
| `/tmp/hermes_inbox/.processing/` | inbox_watcher | inbox_watcher | per-msg 锁; 仅 watcher 移动文件 |
| `/tmp/hermes_inbox/.done/` | inbox_watcher | nobody (终态) | 成功 LLM 回复; 永不重读 |
| `/tmp/hermes_inbox/.error/` | inbox_watcher | inbox_watcher | 失败; 60s 后可重试 |
| `/tmp/hermes_outbox/` | inbox_watcher | bot daemon | LLM 回复等飞书 POST |
| `/tmp/inbox_watcher.pid` | inbox_watcher | humans + tools | watcher pid, 供 status / kill |
| `~/.hermes/logs/inbox-watcher.out.log` | inbox_watcher | humans | 每轮一行, 含 text[:80] |
| `~/.hermes/logs/feishu_bot_daemon.out.log` | bot daemon | humans | ws 活动 + outbox POST |

**原子性不变量**: bot daemon 用 **write-then-rename** (`os.replace` on
Python, `os.WriteFile` + `os.Rename` on Go) 写 inbox, 并发 watcher 永不会
读到半截文件。watcher 接着 `os.rename` 同一文件到 `.processing/`, 该 rename
在同一 FS (macOS `/tmp` 是 1 个 FS) 上也原子。`.processing/` rename 是
**锁**: 两个并发 watcher 抢, 一个赢, 另一个拿到 `FileNotFoundError` 跳过
(safe, idempotent)。

## 2. Inbox JSON schema (bot daemon → watcher)

路径: `/tmp/hermes_inbox/<msg_id>.json`

```json
{
  "msg_id":      "om_xxxxxxxxxxxxxxxxxxxxxxxx",
  "chat_id":     "oc_xxxxxxxxxxxxxxxxxxxxxxxx",
  "text":        "用户发的文字 (already stripped)",
  "sender":      "ou_xxxxxxxxxxxxxxxxxxxxxxxx",
  "received_at": 1717920000.123
}
```

### 字段参考

| 字段 | 类型 | 必填 | 来源 | 示例 | 备注 |
|---|---|---|---|---|---|
| `msg_id` | string | yes | Feishu event `message_id` | `"om_a1b2c3d4..."` (om_ 前缀) | 每个状态目录的文件名 stem; 入站消息必须唯一 |
| `chat_id` | string | yes | Feishu event `chat_id` | `"oc_a1b2c3d4..."` (oc_ 前缀) | 回复目标。`oc_test_` 前缀时 bot daemon 的 outbox watcher 跳过 Feishu POST |
| `text` | string | yes | Feishu event message | `"今天天气怎么样"` | LLM 调用前必须非空。空 → reply="[empty input]", `ok=false` |
| `sender` | string | no | Feishu event `sender.sender_id.open_id` | `"ou_a1b2c3d4..."` (ou_ 前缀) | 信息性; watcher 不基于它路由 |
| `received_at` | float | no | 写盘时 `time.time()` | `1717920000.123` | Unix 秒, sub-millisecond。仅诊断用, 不用于排序 (filesystem mtime 是 sort key) |

## 3. Outbox JSON schema (watcher → bot daemon)

路径: `/tmp/hermes_outbox/<msg_id>.json`. **永远写**, 即便 LLM 失败
(让 bot daemon 发送系统错误消息)。

```json
{
  "msg_id":     "om_xxxxxxxxxxxxxxxxxxxxxxxx",
  "chat_id":    "oc_xxxxxxxxxxxxxxxxxxxxxxxx",
  "ok":         true,
  "reply":      "今天上海多云转晴...",
  "model":      "minimax-cn/MiniMax-M3",
  "duration_sec": 5.12
}
```

### 字段参考

| 字段 | 类型 | 来源 | 用途 |
|---|---|---|---|
| `msg_id` | string | inbox.msg_id 回声 | Bot daemon 用它关联回复跟入站队列。outbox 文件名 stem |
| `chat_id` | string | inbox.chat_id 回声 | Bot daemon 用作 `receive_id` 调 `im/v1/messages` POST。`oc_test_` 前缀跳过 |
| `ok` | bool | `rc==0 且 stdout 非空` | `false` → inbox 文件入 `.error/<msg_id>.retry<N>.json` 60s 退避重试, max 3 次 |
| `reply` | string | LLM 回复文本 | 发回飞书 |
| `model` | string | 例 `"minimax-cn/MiniMax-M3"` | 诊断 |
| `duration_sec` | float | LLM 调用 wall time | 诊断 |

## 4. 状态机 (路径)

```
/tmp/hermes_inbox/<msg_id>.json     ← bot daemon 写 (write-then-rename)
       │
       │  inbox_watcher `os.rename` (atomic on /tmp)
       ▼
/tmp/hermes_inbox/.processing/<msg_id>.json     ← per-msg 锁
       │
       ├─ ok=true    → /tmp/hermes_inbox/.done/<msg_id>.json    (终态)
       ├─ ok=false   → /tmp/hermes_inbox/.error/<msg_id>.retry<N>.json
       │                (N++ 每次重试, 60s 退避, max 3)
       │                成功 → .done; 耗尽 → .error
       └─ 坏 JSON   → /tmp/hermes_inbox/.error/<msg_id>.badjson  (不重试)
```

Bot daemon 的 outbox watcher 轮询 `/tmp/hermes_outbox/*.json` 并 POST
每条到飞书。成功 POST 移到 `/tmp/hermes_outbox/.done/`。
失败 POST (网络/API 错) 退避重试; 永久失败 (404 chat deleted) 移到
`/tmp/hermes_outbox/.error/`。

## 5. 重试语义

| 失败 | 地点 | 退避 | 最大次数 |
|---|---|---|---|
| LLM `rc!=0` 或 stdout 空 | inbox_watcher | 60s | 3 |
| 坏 JSON 解析 | inbox_watcher | none (立即 `.error/badjson`) | 1 |
| 飞书 POST 4xx (bad request) | bot daemon | none (跳过重试) | 1 |
| 飞书 POST 5xx (server error) | bot daemon | 60s | 3 |
| 飞书 POST 404 chat not found | bot daemon | none (跳过) | 1 |

## 6. `oc_test_` 逃生口

如果 `chat_id` 以 `oc_test_` 开头, bot daemon **完全跳过飞书 POST**,
只 log 假设的回复。开发者在开发时可测全 pipeline, 不骚扰真实用户。

## 7. 跨 OS 原子性

| OS | `/tmp` FS | atomic rename? | 备注 |
|---|---|---|---|
| macOS | APFS | yes | `/tmp` 跟 `/tmp/hermes_inbox/` 同 FS |
| Linux | tmpfs 或 ext4 | yes | 同 FS |
| Windows / WSL2 | WSL2 `/tmp` 是 `tmpfs`, 跟 Windows `%TEMP%` (NTFS) 不同 | **NO** if 跨 FS | bot daemon 跟 watcher 同 FS |

**规则**: bot daemon 跟 inbox_watcher **必须同一台机 + 同一 FS**。

## 8. 运维 runbook

### "inbox 持续增长" (watcher 没消费)

```bash
ls /tmp/hermes_inbox/*.json 2>/dev/null | wc -l
pgrep -fl inbox_watcher
cat /tmp/inbox_watcher.pid
ps -p $(cat /tmp/inbox_watcher.pid) -o pid,stat,etime
```

常见原因: LLM API 限速 (429), Hermes CLI binary 丢失, LLM API key 过期。

### "outbox 持续增长" (bot daemon 没 POST)

```bash
ls /tmp/hermes_outbox/*.json 2>/dev/null | wc -l
pgrep -fl via54Larkbotgo
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier
```

常见原因: 飞书撤销 ws 能力, App ID/Secret 旋转, 网络切换。

## 9. 跨实现 conformance

两侧都遵循本协议:

- **Python**: `via54Larkfix/reference/python-original/feishu_bot_daemon.py` (419 行, v20.7) + `inbox_watcher.py` (570 行)
- **Go**: `via54Larkbotgo/main.go` (本仓库, skeleton)

## 10. 参考

- `reference/protocol/inbox_schema.md` — 字段速查
- `reference/python-original/feishu_bot_daemon.py` — Python 实现
