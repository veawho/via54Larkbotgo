---
title: Hermes 整合 Pitfalls
description: 跟 Hermes Agent 整合的 5 个常见坑 (Telegram socks5 / chat_id / write_file silent fail / memory old_text / model flatten)
---

# Hermes 整合 Pitfalls

> **来源**: [veawho/via54Hermes](https://github.com/veawho/via54Hermes) 知识库
> (private) — Hermes Agent 自身运维 15+ 事故案例 + 5 架构 SVG
> **整合日期**: 2026-06-15
> **跟本文关系**: via54Larkbotgo 是 Go 飞书 bot skeleton, 跟 Hermes
> gateway 共享 Telegram / state.db / .env 字段, 以下 5 个坑直接相关

---

## 坑 1: `TELEGRAM_PROXY` 用 `socks5://` 推荐 (PTB 22.6+)

> Source: [Hermes 官方 docs](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram/) + [incidents/2026-05/28-telegram-proxy-http-vs-socks5.md](https://github.com/veawho/via54Hermes/blob/main/incidents/2026-05/28-telegram-proxy-http-vs-socks5.md)

**Hermes 官方 (2026-06-15 v0.16 文档)**: `http://`, `https://`, `socks5://` **3 个 scheme 都支持**

```yaml
# config.yaml (官方推荐)
telegram:
  proxy_url: "socks5://127.0.0.1:7890"
```

```bash
# .env (备选, Hermes 优先读这个)
TELEGRAM_PROXY=socks5://127.0.0.1:7890
```

**真相**: incident 28 写"MUST be socks5://"是**telethon 库**时代——跟现在 PTB 22.6 + httpx[socks] **不同**。PTB 22.6 走 `HTTPXRequest` + `httpx[socks]==0.28.1` (装 `socksio`), 3 scheme 都通过, **但 socks5:// GFW 抵抗最强**。本机 macOS 优先用 socks5:// 跑稳 (per 2026-06-15 实测 http 9/10 vs socks5 8/10, 差 1 次属 Clash 端间歇)。

**Hermes auto-detect 顺序**:
1. `TELEGRAM_PROXY` env (highest)
2. `HTTPS_PROXY/HTTP_PROXY/ALL_PROXY` env
3. macOS `scutil --proxy` (auto-fallback, 返 `http://127.0.0.1:7890` by default)

**Clash proxy 配置**: `mixed-port: 7890` 同时 listen http + socks5, **不需要单独设 socks 端口**。

---

## 坑 2: `telegram.allowed_chats` 必须是 `chat_id` 不是 `bot_id`

> Source: [incidents/2026-05/20-telegram-chatid-vs-botid.md](https://github.com/veawho/via54Hermes/blob/main/incidents/2026-05/20-telegram-chatid-vs-botid.md)

**问题**: `@BotFather` 给的 bot `bot_id` (例如 `8765399418`) 跟你的 personal
`chat_id` (例如 `1521667184`) 是**两个不同数字**。填错就 bot 收自己消息循环
或无消息。

**正解**: 从 gateway.log 找 inbound message:

```yaml
# config.yaml
telegram:
  allowed_chats: 1521667184    # 你的 chat_id, 不是 bot_id
```

**找你的 chat_id**:

```bash
# 临时清 allowlist 让所有消息都进
sed -i.bak 's/allowed_chats: .*/allowed_chats: ""/' ~/.hermes/config.yaml
hermes gateway restart
# 给 bot 发任何消息
grep "inbound message" ~/.hermes/logs/gateway.log | tail -1
# chat_id=<你的数字>  ← 这个
# 恢复 + 加 allowlist
```

---

## 坑 3: `write_file` / `patch` 对中国古典文本 silent fail

> Source: [incidents/2026-06/04-write-file-sensitive-string-silent-fail.md](https://github.com/veawho/via54Hermes/blob/main/incidents/2026-06/04-write-file-sensitive-string-silent-fail.md)

**问题**: 写大段**中国古诗 / 古典文本** (>1500 字符 + parallel couplet 模式)
时, 工具返 `{"success": true, "bytes_written": N}` 但**实际没写**到磁盘。

**对策**:

- 写完后**必 verify** (`wc -c file` 对比期望, 或 `head -3 file` 看头 3 行)
- 大段古文**拆成 2-3 段**写
- SKILL.md 写完必 `grep -c '关键词' SKILL.md` 验关键 token 真写入

```bash
# 写完后验证 (铁律)
wc -c reference/protocol/feishu_inbox_protocol.md
md5 -q reference/protocol/feishu_inbox_protocol.md
# 对比 git HEAD 同路径
```

---

## 坑 4: `memory` 工具用 `old_text` 不是 `old_string`

> Source: [incidents/2026-06/05-memory-old-string-vs-old-text.md](https://github.com/veawho/via54Hermes/blob/main/incidents/2026-06/05-memory-old-string-vs-old-text.md) + [references/memory-api-pitfalls.md](https://github.com/veawho/via54Hermes/blob/main/references/memory-api-pitfalls.md)

**问题**: `memory` 跟 `patch` 工具字段名**故意不同**, 用错**silent fail**:

| 工具 | 字段 |
|---|---|
| `patch` | `old_string` / `new_string` |
| `memory` | `old_text` / `content` |

**正解**:

```python
# ✅ 正确
memory(action="replace", target="memory",
       old_text="model: MiniMax-M2.7 (default)",
       content="model: MiniMax-M3 (default)")

# ❌ silent fail (用 patch 字段名)
memory(action="replace", target="memory",
       old_string="model: MiniMax-M2.7 (default)",  # 错字段名
       content="model: MiniMax-M3 (default)")
```

**自查**:

```bash
# 改 memory 后必 verify (memory 没 diff output, 用 get 看实际内容)
```

---

## 坑 5: `hermes config set model` flatten nested mapping

> Source: [incidents/2026-06/09-config-set-model-flattened.md](https://github.com/veawho/via54Hermes/blob/main/incidents/2026-06/09-config-set-model-flattened.md)

**问题**: `hermes config set model <name>` 是 flat key-value setter, **不保留
nested mappings**:

```yaml
# 改前 (嵌套)
model:
  default: MiniMax-M3
  provider: minimax-cn
  base_url: ''

# 改后 (collapsed, provider 字段丢了)
model: MiniMax-M3
```

**对策**:

- **不要用** `hermes config set model <name>` 改 model — 改完会丢 `provider`
- **手动改** `~/.hermes/config.yaml` 保持嵌套:

```bash
# ✅ 推荐: 直接 sed 改 nested
sed -i 's/  default: .*/  default: MiniMax-M3/' ~/.hermes/config.yaml
hermes gateway restart
```

---

## 5 架构 SVG (per via54Hermes)

via54Hermes 提供了 5 个**dark-themed SVG** 架构图 (无外部依赖):

| SVG | 节点数 | 主题 | 跟 Larkbotgo 关系 |
|---|---|---|---|
| `deployment-topology.svg` | 144 | Windows + WSL 全部署 (流程/端口/路径) | ⚠ 跟 macOS 单机**不直接对应** |
| `gateway-lifecycle.svg` | 112 | gateway state machine (start/stop/restart/crash) | ✅ Hermes gateway 状态机一致 |
| `state-db-pipeline.svg` | 119 | FTS5 corruption 5 步 recovery | ✅ 跟 Larkfix `state.db` 整合 |
| `api-server-routing.svg` | 156 | Desktop → api_server :8642 routes | ✅ 跟 `~/.hermes/api` 整合 |
| `telegram-data-flow.svg` | 145 | User → socks5 → telethon → gateway → LLM | ✅ 跟坑 1 完全对应 |

SVG 路径: `~/Desktop/developments/via54Hermes/assets/diagrams/*.svg`

---

## 真相源 (Source of Truth)

via54Larkbotgo 跟 Hermes 整合的所有真相, 都在:

- **本地**: `~/Desktop/developments/via54Hermes/` (cloned from `veawho/via54Hermes`)
- **README**: [github.com/veawho/via54Hermes](https://github.com/veawho/via54Hermes) (private)
- **incidents 索引**: [incidents/TIMELINE.md](https://github.com/veawho/via54Hermes/blob/main/incidents/TIMELINE.md)
- **references 索引**: [references/](https://github.com/veawho/via54Hermes/tree/main/references)
