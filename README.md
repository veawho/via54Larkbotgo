# via54Larkbotgo

> **飞书 (Feishu/Lark) WS 长连接 bot,Go 改写中**

Go skeleton,目标是**完全替代** [`/Users/david/.hermes/scripts/feishu_bot_daemon.py`](https://github.com/veawho/via54Larkfix)(原 851 行 Python daemon,v20.7)。

## 状态

| 维度 | 状态 | 备注 |
|---|---|---|
| Build | ✅ `go build ./` 1.17 s | macOS arm64, Go 1.26.4 |
| 飞书 SDK | ✅ `larksuite/oapi-sdk-go/v3@v3.9.5` | `channel.NewClient` + `Channel.OnMessage` |
| 业务路径 | ✅ `/tmp/hermes_inbox/`, `/tmp/hermes_outbox/`, `/tmp/feishu_bot.pid` | 跟 `inbox_watcher.py` 共用 |
| InboxMessage schema | ⚠️ 跟 Larkfix protocol 6/4 一致 | 4 个核心字段 (`msg_id`/`chat_id`/`text`/`received_at`) 完全一致;`sender_open_id`/`sender_name` 是 Go 端的额外 informational 字段(protocol 的 `sender` 字段 Go 端重命名以明示语义) |
| 功能 | 🚧 skeleton | 收消息 + 写 inbox + outbox 转发, 其他 (name cache / @bot 过滤 / 群白名单 / vision subprocess / heartbeat 进度) 是 TODO |
| E2E 跑通 | ❌ 未测试 | 跟 inbox_watcher.py 真实对接还没做 |

## 目录

```
via54Larkbotgo/
├── main.go                        # skeleton: WS connect + Channel + inbox writer + outbox poller
├── go.mod / go.sum                # larksuite/oapi-sdk-go/v3 + transitive deps
├── bin/via54Larkbotgo             # 已编译 binary (gitignored)
│
├── reference/                     # 拆自 via54Larkfix 仓库的"参考真相源"
│   ├── python-original/
│   │   ├── feishu_bot_daemon.py   # 419 行, 完整 daemon (被 Go 替代的对象)
│   │   └── cli_bot_group.py       # 163 行, Click group "feishu bot start --foreground"
│   └── protocol/
│       ├── feishu_inbox_protocol.md   # 22 KB, IPC 契约 (paths + schema + state machine)
│       └── inbox_schema.md            # 字段速查表 (auto-generated 摘要)
│
└── README.md (本文件)
```

## 跟 `via54Larkfix` 的关系

`veawho/via54Larkfix` 是飞书集成的**完整归档**(Python CLI + bot + 4 OS 平台适配 + 修复历史 + 60+ 文档)。

本仓库只拿走**Go 替代直接需要的 3 个文件**(reference/ 下),作为:
1. **Go 实现的真相源** — 字段命名、路径常量、outbox 格式跟 Python 严格一致
2. **Go 替代的对比对象** — 之后可写 `go test` 跑同一组 inbox fixtures,验证两实现行为一致
3. **TODO 实现的指引** — Python daemon 里的 name cache / @bot 过滤逻辑,Go 端要复刻时直接参考

**没拿**的(Larkfix 留):
- `inbox/inbox_watcher.py`, `common/inbox_watcher.py` — Python consumer,跟 Go producer **不依赖同一份**,两边各自持有
- `platforms/darwin/`, `platforms/linux/`, `platforms/windows/` — Python 飞书的部署,跟 Go 无关
- `common/cli/feishu`(12 子命令) — Python CLI 主体,跟 Go 是竞争/替代关系,不重复持有
- `references/v20.*` — Python f-string bug 修复历史,跟 Go 无关
- `docs/`, `skills/`, `reports/` — 跟 Python 飞书业务绑定的非协议内容

## 重新同步 (从 Larkfix 拉最新)

```bash
cd /Users/david/Desktop/developments
gh repo sync veawho/via54Larkfix   # 拉 Larkfix 最新
cp via54Larkfix/common/bot/feishu_bot_daemon.py \
   via54Larkbotgo/reference/python-original/feishu_bot_daemon.py
cp via54Larkfix/bot/feishu_bot_daemon.py \
   via54Larkbotgo/reference/python-original/cli_bot_group.py
cp via54Larkfix/references/feishu_inbox_protocol.md \
   via54Larkbotgo/reference/protocol/feishu_inbox_protocol.md
md5 -q via54Larkfix/common/bot/feishu_bot_daemon.py \
       via54Larkbotgo/reference/python-original/feishu_bot_daemon.py
# 期望: 两次 md5 一致
```

## 部署(待实现)

跟 Python daemon 共用 launchd plist 路径 (`~/Library/LaunchAgents/com.david.feishu-bot.plist`),但需要:
1. 重写 plist 的 `ProgramArguments` 从 `~/.local/bin/feishu` 改成 `~/Desktop/developments/via54Larkbotgo/bin/via54Larkbotgo`
2. 同样的 `EnvironmentVariables` (FEISHU_BOT_APP_ID, ALLOWED_CHATS)
3. venv 依赖变成 go binary 自包含,不需要 `~/.local/share/feishu-cli/venv/`

## 关联项目

- [`veawho/via54Larkfix`](https://github.com/veawho/via54Larkfix) — 飞书完整归档(本仓库的协议真相源)
- `~/.hermes/scripts/feishu_bot_daemon.py` — 当前在跑的实现(替代前)
- `~/.hermes/scripts/inbox_watcher.py` — Go producer 的 consumer
- `via54goport` skill — Python → Go 改写评估流程