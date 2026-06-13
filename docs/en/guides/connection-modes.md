# Connection modes: WebSocket (long-connection) vs Webhook

> **TL;DR**: Default to **WebSocket long-connection**. Use **Webhook**
> only when your AI tool runs in a restricted network (no outbound
> allowed, corporate firewall) or when you need server-initiated pushes
> at high volume.

## Comparison

| Dimension | WebSocket long-connection | Webhook (HTTPS callback) |
|---|---|---|
| **Direction** | bot actively connects to Feishu | Feishu actively POSTs you |
| **Outbound vs Inbound** | Outbound 443 only | Inbound 443 + publicly reachable URL |
| **Where to deploy** | Anywhere (no public IP/DNS needed) | Public IP + DNS + TLS cert required |
| **Latency** | Real-time (< 100ms) | Near-real-time (200ms-2s, with public RTT) |
| **Reconnect** | SDK auto-reconnects | Feishu retries 3×, then drops |
| **Multi-instance** | Mutex (only 1 connection) | Arbitrary; Feishu load-balances |
| **Code complexity** | SDK handles ws protocol | Public HTTP server + signature verify |
| **Best for** | AI tool (local) ↔ bot | SaaS, multi-replica, public deploy |
| **Typical user** | Hermes/OpenClaw/Codex local daemon | via54Design's `webhook_handler` |

## Decision tree

```
Where does your AI tool run?
  ├── Local / Intranet (no public IP)
  │     ↓
  │     Choose WebSocket long-connection (default)
  │
  └── Public server (public IP + DNS + TLS cert)
        ↓
        Do you need multi-replica / high-availability?
        ├── Yes → Choose Webhook (Feishu side load-balances)
        └── No  → Choose WebSocket (simpler)
```

## Choose WebSocket long-connection (default)

**Prerequisites**:
- Your AI tool (local or intranet) can reach `wss://msg-frontier.feishu.cn/ws/v2`
- No multi-replica requirement
- No public IP needed

**Implementation**:
- Feishu SDK (Python `lark-oapi` / Go `larksuite/oapi-sdk-go` / Node
  `@larksuiteoapi/node-sdk`) all provide ws clients
- Feishu pushes `im.message.receive_v1` events to your handler
- Heartbeat (ping/pong) managed by SDK

**Code skeleton** (Go):
```go
ch := larkws.NewClient(
    larkws.WithAppCredential(cfg.AppID, cfg.AppSecret),
    larkws.WithEventHandler(dispatch),
)
ch.Start(ctx) // blocks until ctx cancel
```

**Code skeleton** (Python):
```python
from lark_oapi.api.im.v1 import EventMessageHandler
ws = lark_oapi.ws.Client(
    "cli_xxx", "yyy", event_handler=handler,
    log_level=lark_oapi.LogLevel.DEBUG,
)
ws.start()  # blocks
```

**Typical use**: your AI tool and bot are on the same machine or intranet.
Hermes uses this — `feishu_bot_daemon.py` at `~/.hermes/scripts/`, talking
to `inbox_watcher.py` via `/tmp/hermes_inbox/` IPC.

## Choose Webhook (HTTPS callback)

**Prerequisites**:
- You have public IP + DNS domain + TLS cert
- Multi-replica / high-availability needed
- Accept the additional HTTP server maintenance cost

**Implementation**:
- Your service runs an HTTPS server (Nginx / Caddy / Go http.Server)
- Feishu side: configure "Event Subscription URL" = `https://yourdomain.example/feishu/webhook`
- Feishu POSTs events to your URL; verify `Encrypt Key` (encrypted mode)
  or `Verification Token` (plain mode)
- Your handler parses → writes to inbox / processes / replies

**Code skeleton** (Go):
```go
http.HandleFunc("/feishu/webhook", func(w http.ResponseWriter, r *http.Request) {
    // 1. Verify Encrypt Key / Verification Token
    // 2. Parse event JSON
    // 3. Write to inbox_watcher queue (or process inline)
    // 4. Return 200 OK within 3s (Feishu side timeout 3s)
})
```

**Typical use**: your bot runs on a cloud server (Aliyun ECS / AWS EC2),
multiple replicas run, Feishu side load-balances events across replicas.

## Both at once? Advanced pattern

**Possible**. Common scenario:
- **Main path WebSocket**: receive + send messages
- **Side path Webhook**: receive specific event types (e.g.
  `im.message.message_read_v1` message-read events) — these events don't
  have a ws push channel, only webhook

But **not recommended for beginners** — increases debug complexity.

## This repo's default

`main.go` skeleton uses **WebSocket long-connection**. Webhook mode requires
a separate `webhook_server.go` entry point (not implemented in this repo,
left as TODO).

## Relation to inbox/outbox protocol

Regardless of WebSocket or Webhook, after the bot receives a message,
the format written to `inbox/` is the same — follows the JSON schema
defined in [`reference/protocol/feishu_inbox_protocol.md`](../protocol/feishu-inbox-protocol.md).
The AI tool side (`inbox_watcher`) doesn't care which connection mode the
bot uses.

## Per-OS notes

| OS | WebSocket recommended | Webhook recommended |
|---|---|---|
| macOS | ✅ default (lark-oapi + auto-reconnect) | Need local HTTPS server (Nginx + mkcert) |
| Windows | ✅ default (lark-oapi ws client) | Need IIS / Nginx + cert |
| Linux | ✅ default (lark-oapi under systemd) | Need Nginx + Let's Encrypt (certbot) |

## Related

- [inbox/outbox protocol](../protocol/feishu-inbox-protocol.md) — what the bot writes to disk after receiving
- [Permissions](../reference/permissions.md) — event subscription must be opened regardless of connection mode
- [macOS install](install-macos.md)
- [Windows install](install-windows.md)
- [Linux install](install-linux.md)