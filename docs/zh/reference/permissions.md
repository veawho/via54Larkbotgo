# 权限开通说明

> **每个飞书/Lark bot 在能收消息、发回复、跟飞书文档交互之前,都必须在
> app 后台开通 scopes**。本页是哪些能力对应哪些 scopes 的清单,以及
> 怎么在 3 个 OS 上验证已开通。

## 按能力的 scope 清单

| 能力 | 必须 scope (中文) | 必须 scope (英文) | 用途 |
|---|---|---|---|
| **接收私聊** | `im:message` | `im:message` | 订阅 `im.message.receive_v1` 事件 |
| **接收群 @bot** | `im:message.group_at_msg` (或 `im:message` 收全部群消息) | `im:message.group_at_msg` | 仅 @bot 或全部(per app 配置) |
| **发送私聊 / 群消息** | `im:message.send_as_bot` | `im:message.send_as_bot` | POST `/im/v1/messages` |
| **读 user open_id** | `contact:user.id:readonly` | `contact:user.id:readonly` | `sender.sender_id.open_id` 查询 |
| **上传 / 发送图片** | `im:resource` | `im:resource` | 图片消息经 `/im/v1/images` |
| **上传 / 发送文件** | `im:resource` | `im:resource` | 文件消息经 `/im/v1/files` |
| **读飞书文档** | `docx:document:readonly` | `docx:document:readonly` | 通过 `/docx/v1/documents/:id/raw_content` 取内容 |
| **编辑飞书文档** | `docx:document` | `docx:document` | 通过 `/docx/v1/documents/:id/...` 编辑 |
| **创建飞书文档** | `docx:document:create` | `docx:document:create` | POST `/docx/v1/documents` |
| **搜索飞书知识库 / 文档** | `wiki:wiki:readonly` | `wiki:wiki:readonly` | 通过 `/wiki/v1/spaces/.../nodes/search` 搜索 |
| **读 user email (少见)** | `contact:user.email:readonly` | `contact:user.email:readonly` | 仅当 bot 发送邮件通知时 |

**Per 主人定义**(hermes/larkbot 需要 **3 大块** 全能力):
1. **私聊**
2. **群聊**
3. **飞书文档**

→ 上述 3 大块对应的 scope 都要开。

## 按 OS 验证路径

### macOS

1. Safari 打开 `https://open.feishu.cn/app`
2. 点你的 app → "权限管理"
3. 验证上述 3 大块的 scopes 已勾选
4. 也点 "事件订阅":
   - 加 "接收消息 im.message.receive_v1"
   - Verification Token / Encrypt Key — 复制下来,粘到 `credentials.json` (仅 Webhook 模式需要;WS 模式不需要)
5. 终端验证 bot 进程能读:
   ```bash
   cat ~/.config/feishu/credentials.json
   #  {"app_id": "cli_xxx", "app_secret": "yyy"}
   ```

### Windows (WSL2)

跟 macOS 相同,但在 WSL 内:
1. `wsl` 进 Ubuntu
2. `xdg-open https://open.feishu.cn/app` (或复制 URL 到 Windows 浏览器)
3. 跟 macOS 步骤 2-5

### Linux (无 GUI)

1. 在另一台机打开 `https://open.feishu.cn/app`
2. 应用 scopes,复制 Encrypt Key / Verification Token
3. SSH / scp 凭据:
   ```bash
   # 在 Linux box:
   mkdir -p ~/.config/feishu
   cat > ~/.config/feishu/credentials.json << 'EOF'
   {"app_id": "cli_xxx", "app_secret": "yyy"}
   EOF
   chmod 600 ~/.config/feishu/credentials.json
   ```

## 按部署模式的 token 存储

| 部署 | Token 存储 | 静态加密? |
|---|---|---|
| macOS (本仓库) | `~/Library/Application Support/lark-cli/master.key.file` + `appsecret_cli_<appid>.enc` | ✅ lark-cli AES-256-GCM |
| macOS (备选) | `~/.config/feishu/credentials.json` (明文) | ❌ (chmod 600) |
| Windows | `%APPDATA%\lark-cli\...` 或 `~/.config/feishu/credentials.json` | 取决 |
| Linux | `~/.config/feishu/credentials.json` (明文) 或 systemd credential store | ❌ 或 ✓ |

**推荐**: 能用 lark-cli 加密就用(macOS 本仓库这样),明文 + `chmod 600` 是 fallback。

## "权限被回收" 症状

| 症状 | 原因 | 修 |
|---|---|---|
| ws 连上后 1-2 消息就死, log "permission denied" | 飞书 admin 移除了一个 scope | 后台重开;重启 bot daemon |
| Send API 返回 `99991663` (no scope) | 代码调了未开的 scope | 加 scope;等 1-2 分钟(飞书 cache) |
| Receive API 工作但 `sender` 字段空 | 缺 `contact:user.id:readonly` | 加 scope |
| `reply` POST 返回 404 (chat not found) | Bot 不在该群 | 先 invite bot 进群 |

## 跨 OS: 后台改 1 处,自动传播

你在飞书后台重开 scope:
- 1-2 分钟内传播到所有客户端(WS / Webhook)
- **不需要** 重启 bot daemon
- 但: 飞书 SDK 在连接时可能 cache scope 列表;bot 跑着时开 scope,可能需重连 (kill + restart)

## 相关

- [连接方式对比](../guides/connection-modes.md) — WS vs Webhook
- [Hermes 集成](../guides/ai-tools-hermes.md)
- [inbox/outbox 协议](../protocol/feishu-inbox-protocol.md)
