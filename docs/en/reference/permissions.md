# Permissions — opening scopes in the Feishu app backend

> **Every Feishu/Lark bot needs scopes opened in the app backend before it
> can read messages, send replies, or interact with Feishu Docs**. This
> page is the canonical checklist of which scopes to open for which
> capabilities, and the per-OS path to verify they were opened.

## Per-capability scope list

| Capability | Required scope (Chinese) | Required scope (English) | Why needed |
|---|---|---|---|
| **Receive DM** | `im:message` | `im:message` | Subscribe to `im.message.receive_v1` events |
| **Receive @bot in group** | `im:message.group_at_msg` (or `im:message` for all group messages) | `im:message.group_at_msg` | Only messages @bot or all (per app config) |
| **Send DM / group message** | `im:message.send_as_bot` | `im:message.send_as_bot` | POST to `/im/v1/messages` |
| **Read user open_id** | `contact:user.id:readonly` | `contact:user.id:readonly` | `sender.sender_id.open_id` lookup |
| **Upload / send image** | `im:resource` | `im:resource` | image messages via `/im/v1/images` |
| **Upload / send file** | `im:resource` | `im:resource` | file messages via `/im/v1/files` |
| **Read Feishu Docs** | `docx:document:readonly` | `docx:document:readonly` | fetch doc content via `/docx/v1/documents/:id/raw_content` |
| **Edit Feishu Docs** | `docx:document` | `docx:document` | edit doc content via `/docx/v1/documents/:id/...` |
| **Create Feishu Docs** | `docx:document:create` | `docx:document:create` | POST `/docx/v1/documents` |
| **Search Feishu Wiki / Docs** | `wiki:wiki:readonly` | `wiki:wiki:readonly` | search via `/wiki/v1/spaces/.../nodes/search` |
| **Read user email (rarely needed)** | `contact:user.email:readonly` | `contact:user.email:readonly` | only if your bot sends email notifications |

**Per the owner definition** (hermes/larkbot requires **all 3** top-level capabilities):
1. **DM** (私聊)
2. **Group chat** (群聊)
3. **Feishu Docs** (飞书文档)

→ open scopes for all three blocks above.

## Per-OS verification path

### macOS

1. Open `https://open.feishu.cn/app` in Safari
2. Click your app → "权限管理" (Permissions)
3. Verify the 3 blocks above are checked
4. Also click "事件订阅" (Event Subscription):
   - Add "接收消息 im.message.receive_v1" (Receive messages v1)
   - Verification Token / Encrypt Key — copy these, paste into your
     `credentials.json` (only for Webhook mode; WS mode doesn't need
     these)
5. From a terminal, verify the bot process can read them:
   ```bash
   cat ~/.config/feishu/credentials.json
   #  {"app_id": "cli_xxx", "app_secret": "yyy"}
   ```

### Windows (WSL2)

Same as macOS but from inside WSL2:
1. `wsl` to enter Ubuntu
2. `xdg-open https://open.feishu.cn/app` (or copy URL to Windows browser)
3. Follow macOS steps 2-5

### Linux (no GUI)

1. On another machine, open `https://open.feishu.cn/app` in a browser
2. Apply scopes, copy Encrypt Key / Verification Token
3. SSH / scp the credentials file:
   ```bash
   # On your Linux box:
   mkdir -p ~/.config/feishu
   # (paste the credentials JSON from clipboard)
   cat > ~/.config/feishu/credentials.json << 'EOF'
   {"app_id": "cli_xxx", "app_secret": "yyy"}
   EOF
   chmod 600 ~/.config/feishu/credentials.json
   ```

## Per-deployment-mode token management

| Deployment | Token storage | Encrypted at rest? |
|---|---|---|
| macOS  (this repo) | `~/Library/Application Support/lark-cli/master.key.file` + `appsecret_cli_<appid>.enc` | ✅ lark-cli AES-256-GCM |
| macOS  (alt) | `~/.config/feishu/credentials.json` (plaintext) | ❌ (chmod 600) |
| Windows | `%APPDATA%\lark-cli\...` or `~/.config/feishu/credentials.json` | depends |
| Linux | `~/.config/feishu/credentials.json` (plaintext) or systemd credential store | ❌ or ✓ |

**Recommendation**: use the lark-cli-encrypted form when available
(macOS this repo does), plaintext + `chmod 600` is the fallback.

## "权限被回收" (permission revoked) symptoms

| Symptom | Cause | Fix |
|---|---|---|
| ws connection dies after 1-2 messages, log shows "permission denied" | Feishu admin removed a scope | re-open in app backend; restart bot daemon |
| Send API returns `99991663` (no scope) | Your code calls a scope not opened | add the scope; wait 1-2 minutes for Feishu cache |
| Receive API works but `sender` field is empty | Missing `contact:user.id:readonly` | add the scope |
| `reply` POST returns 404 (chat not found) | Bot is not in that chat (group) | invite bot to the group first |

## Cross-OS note: re-open scopes in 1 place, propagate

When you re-open a scope in the Feishu app backend:
- The change propagates to all clients (WS, Webhook) within 1-2 minutes
- The bot daemon does **NOT** need to be restarted
- BUT: the Feishu SDK may cache the scope list at connection time; if you
  open a scope while the bot is running, the bot may need to reconnect
  (i.e. kill + restart)

## Related

- [Connection modes](../guides/connection-modes.md) — WS vs Webhook
- [Hermes integration](../guides/ai-tools-hermes.md)
- [inbox/outbox protocol](../protocol/feishu-inbox-protocol.md)