# 连接方式:WebSocket (长连接) vs Webhook

> **TL;DR**: 默认用 **WebSocket 长连接**;只有当你的 AI 工具运行在
> 受限网络(无出站连接、企业防火墙)或者需要服务器端主动推送大量
> 数据时,才用 **Webhook**。

## 两种方式对比

| 维度 | WebSocket 长连接 | Webhook (HTTPS 回调) |
|---|---|---|
| **方向** | bot 主动连飞书 | 飞书主动 POST 你 |
| **出站 vs 入站** | 仅需出站 443 | 需入站 443 + 公网可达 URL |
| **部署位置** | 任意(无需公网 IP/DNS) | 必须有公网 IP/DNS + HTTPS 证书 |
| **延迟** | 实时(< 100ms) | 近实时(200ms-2s,含公网 RTT) |
| **断线恢复** | SDK 自动重连 | 飞书侧 retry 3 次,之后丢弃 |
| **多实例** | 互斥(只能 1 个连接) | 任意多个,飞书轮询负载均衡 |
| **代码复杂度** | SDK 内置 ws 协议 | 需要处理公网 HTTP server + 验签 |
| **适合** | AI 工具(本机) ↔ bot | SaaS 服务,多副本,公网部署 |
| **典型用户** | Hermes/OpenClaw/Codex 本机 daemon | via54Design 的 `webhook_handler` |

## 决策树

```
你 AI 工具跑在哪里?
  ├── 本机/内网 (无公网 IP)
  │     ↓
  │     选 WebSocket 长连接 (默认)
  │
  └── 公网服务器 (有公网 IP + DNS + TLS 证书)
        ↓
        是否需要多副本 / 高可用?
        ├── 是 → 选 Webhook (飞书侧负载均衡)
        └── 否 → 选 WebSocket 更简单
```

## 选 WebSocket 长连接 (默认)

**前提**:
- 你的 AI 工具本机或内网能访问 `wss://msg-frontier.feishu.cn/ws/v2`
- 不需要多副本
- 不需要公网 IP

**实现**:
- 飞书 SDK (Python `lark-oapi` / Go `larksuite/oapi-sdk-go` / Node `@larksuiteoapi/node-sdk`)都有 ws client
- 飞书侧推送 `im.message.receive_v1` 事件 → 你的 handler
- 心跳 (ping/pong) 由 SDK 管理

**代码 skeleton** (Go):
```go
ch := larkws.NewClient(
    larkws.WithAppCredential(cfg.AppID, cfg.AppSecret),
    larkws.WithEventHandler(dispatch),
)
ch.Start(ctx) // 阻塞,直到 ctx cancel
```

**代码 skeleton** (Python):
```python
from lark_oapi.api.im.v1 import EventMessageHandler
ws = lark_oapi.ws.Client(
    "cli_xxx", "yyy", event_handler=handler,
    log_level=lark_oapi.LogLevel.DEBUG,
)
ws.start()  # 阻塞
```

**典型用**: 你的 AI 工具和 bot 都在同一台机或同一内网。Hermes 用的就是这个
方式 (`feishu_bot_daemon.py` 在 `~/.hermes/scripts/`,跟 `inbox_watcher.py` 走
`/tmp/hermes_inbox/` IPC)。

## 选 Webhook (HTTPS 回调)

**前提**:
- 你有公网 IP + DNS 域名 + TLS 证书
- 需要多副本 / 高可用
- 接受额外的 HTTP server 维护成本

**实现**:
- 你的服务起一个 HTTPS server (Nginx / Caddy / Go http.Server)
- 飞书侧配 "事件订阅 URL" = `https://yourdomain.example/feishu/webhook`
- 飞书 POST 事件到你的 URL,需 verify `Encrypt Key` (加密模式) 或校验 `Verification Token` (明文模式)
- 你的 handler 解析后写 inbox / 处理 / 回 reply

**代码 skeleton** (Go):
```go
http.HandleFunc("/feishu/webhook", func(w http.ResponseWriter, r *http.Request) {
    // 1. Verify Encrypt Key / Verification Token
    // 2. Parse event JSON
    // 3. Write to inbox_watcher queue (or process inline)
    // 4. Return 200 OK within 3s (飞书侧 timeout 3s)
})
```

**典型用**: 你的 bot 跑在云服务器 (阿里云 ECS / AWS EC2),多个副本同时跑,
飞书侧会轮询分发事件给不同副本。

## 同时用两种? 高级模式

**可以**。常见场景:
- **主路 WebSocket**: 收消息 + 发消息
- **旁路 Webhook**: 收特定事件类型(如 `im.message.message_read_v1` 消息已读),
  这些事件没开 ws push 通道,只能 webhook

但 **不推荐入门者同时用两种**——增加调试复杂度。

## 本仓库默认

`main.go` skeleton 用 **WebSocket 长连接**。Webhook 模式需另写一个
`webhook_server.go` 入口(本仓库未实现,留 TODO)。

## 跟 inbox/outbox 协议的关系

无论 WebSocket 还是 Webhook,bot 收到消息后写 `inbox/` 的格式都一样——
遵循 [`reference/protocol/feishu_inbox_protocol.md`](../protocol/feishu-inbox-protocol.md)
定义的 JSON schema。AI 工具侧(inbox_watcher)不用关心 bot 用哪种连接方式。

## 跨 OS 注意事项

| OS | WebSocket 推荐 | Webhook 推荐 |
|---|---|---|
| macOS | ✅ 默认 (lark-oapi + 自动重连) | 需要本机起 HTTPS server (Nginx + mkcert) |
| Windows | ✅ 默认 (lark-oapi ws client) | 需要 IIS / Nginx + cert |
| Linux | ✅ 默认 (lark-oapi 在 systemd 跑) | 需要 Nginx + Let's Encrypt (certbot) |

## 相关文档

- [inbox/outbox 协议](../protocol/feishu-inbox-protocol.md) — 收消息后写到磁盘的格式
- [权限开通说明](../reference/permissions.md) — 无论选哪种连接方式,event subscription 都要先开通
- [macOS 安装指南](install-macos.md)
- [Windows 安装指南](install-windows.md)
- [Linux 安装指南](install-linux.md)
