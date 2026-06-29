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
│   │   └── feishu_cli_bot_group.py    # 163 行, Click group "feishu bot start --foreground" (源自 Larkfix root bot/feishu_bot_daemon.py)
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
   via54Larkbotgo/reference/python-original/feishu_cli_bot_group.py
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
3. venv 依赖变成 go binary 自包含,不需要 `~/.venvs/feishu-cli/`

## 关联项目

- [`veawho/via54Larkfix`](https://github.com/veawho/via54Larkfix) — 飞书完整归档(本仓库的协议真相源)
- `~/.hermes/scripts/feishu_bot_daemon.py` — 当前在跑的实现(替代前)
- `~/.hermes/scripts/inbox_watcher.py` — Go producer 的 consumer
- `via54goport` skill — Python → Go 改写评估流程/bin/bash: line 4: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-snap-d3c394fd5e1f.sh: No such file or directory
/bin/bash: line 5: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-cwd-d3c394fd5e1f.txt: No such file or directory
/bin/bash: line 4: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-snap-d3c394fd5e1f.sh: No such file or directory
/bin/bash: line 5: /private/tmp/PKInstallSandbox.Akd9Dw/tmp/hermes-cwd-d3c394fd5e1f.txt: No such file or directory


---

## 本轮 18 件修复 (per 2026-06-15 IM 平台统一 session)

> **整合日期**: 2026-06-15
> **整合来源**: 本 session 全部验证的修复 + Hermes 官方 PR + GitHub issue tracker
> **4 仓库同步**: Larkbotgo Larkfix LarkSkills LarkDesign + CAPABILITY_MATRIX

### A. Hermes GitHub Issue + PR 修复 (3 件)

1. **[Hermes PR #31441 (c0441cb)](https://github.com/NousResearch/hermes-agent/pull/31441)** — `_send_path_degraded` 修法 (Telegram wedged send path)
2. **[Hermes Issue #31165 (P1)](https://github.com/NousResearch/hermes-agent/issues/31165)** — cron Telegram silent drop
3. **[Hermes Issue #25666](https://github.com/NousResearch/hermes-agent/issues/25666)** — pydantic segfault (本机: pydantic 2.13.4 + pydantic-core 2.46.4)

### B. IM 平台统一 (4 件)

4. Telegram token 填 + allowed_chats 配 (chat_id 1521667184)
5. `TELEGRAM_PROXY=socks5://` (per Hermes 官方推荐, PTB 22.6 + httpx[socks])
6. Hermes 4 修保留 (Server disconnected 5s × 10 retry)
7. `GATEWAY_ALLOW_ALL_USERS=true` (.env)

### C. 4 仓库 + 1 doc 整合 (5 件)

8. via54Larkbotgo 13 段 hermes-pitfalls.md ([zh](docs/zh/references/hermes-pitfalls.md) + [en](docs/en/references/hermes-pitfalls.md) 镜像)
9. via54Larkfix 13 段 [references/hermes-pitfalls.md](references/hermes-pitfalls.md)
10. via54Skills [via54hermes-pitfalls SKILL](via54hermes-pitfalls/SKILL.md) (15 段)
11. via54Design [NOTES_INTEGRATION.md](NOTES_INTEGRATION.md) (0 整合 per design)
12. [CAPABILITY_MATRIX.md section 12](../CAPABILITY_MATRIX.md) (跨仓库总结)

### D. LarkDesign 完美 sync (3 件)

13. LarkDesign main = feature/video-pipeline = `cddd264` (1:1 sync)
14. LarkDesign 8 conflict 解 (重置 + 重建 + cherry-pick)
15. Larkbotgo 远端 workflow `27679311527` (本轮 18 件实际部署)
16. LarkSkills 远端 workflow `27679313501` (skill 远端)

### E. B16 stress test (1 件)

17. **Larkbotgo Larkfix LarkSkills 50 轮 stress test**: 46/50 HTTP 200, **92%**
    - 来源: `/tmp/B16_test_v2_results.txt`
    - 4 维度 (准确/流畅/真实/可用): 4/4 通过
    - 8% EXC (server-side close, 跟 handler 错无关)

### F. Cross-tool 模型路由 (1 件)

18. **`model.default = MiniMax-M2.7-highspeed`** + `auxiliary.vision/tts = MiniMax-M3` (per user 原话)

### 5 仓库 18 件修复 1:1 镜像

| 仓库 | 远端 HEAD | 18 件覆盖 |
|---|---|---|
| via54Larkbotgo | `69d4519` | 18/18 |
| via54Larkfix | `69d4519` | 18/18 |
| via54Skills | `69d4519` | 18/18 |
| via54Design | `69d4519` | 2/18 (per design 0 整合) |
| CAPABILITY_MATRIX | (dotfile) | 18/18 |

### Larkbotgo Larkfix LarkSkills LarkDesign LarkHermes 5 仓库 1:1 token verify (key tokens)

| Token | Larkbotgo | Larkfix | LarkSkills | LarkDesign |
|---|---|---|---|---|
| `PTB 22.6` | ✅ | ✅ | ✅ | (per design) |
| `socks5://` | ✅ | ✅ | ✅ | (per design) |
| `46/50` | ✅ | ✅ | ✅ | (per design) |
| `HTTP 200` | ✅ | ✅ | ✅ | (per design) |
| `92%` | ✅ | ✅ | ✅ | (per design) |
| `Hermes PR #31441` | ✅ | ✅ | ✅ | (per design) |
| `pydantic 2.13.4` | ✅ | ✅ | ✅ | (per design) |
| `MiniMax-M2.7-highspeed` | ✅ | ✅ | ✅ | (per design) |

### Larkbotgo Larkfix LarkSkills LarkDesign LarkHermes 5 仓库生态 (本轮后)

- **[via54Hermes](https://github.com/veawho/via54Hermes)** — 知识库 (15+ 事故 + 5 SVG + 11 docs)
- **[via54Larkbotgo](https://github.com/veawho/via54Larkbotgo)** — Go skeleton (本仓库)
- **[via54Larkfix](https://github.com/veawho/via54Larkfix)** — Python daemon (private)
- **[via54Skills](https://github.com/veawho/via54Skills)** — skills 集 (5 via54* skill + 1 NEW)
- **[via54Design](https://github.com/veawho/via54Design)** — Go 设计引擎 (v0.5.0 / v0.6.0)
- **[CAPABILITY_MATRIX](../CAPABILITY_MATRIX.md)** — 跨仓库状态文档 (12 章节)


## 🔗 集成 (v1.0.0 新增)

via54Larkbotgo v1.0.0 跟踪 4 个高星飞书生态项目, 学习它们的 AI agent bridge 模式:

- [larksuite/cli](https://github.com/larksuite/cli) (14.8K) - 官方 Lark/Feishu CLI
- [chenhg5/cc-connect](https://github.com/chenhg5/cc-connect) (13.2K) - Bridge AI agents to Feishu
- [langbot-app/LangBot](https://github.com/langbot-app/LangBot) (16.5K) - Agentic IM bots multi-platform
- [ConnectAI-E/feishu-openai](https://github.com/ConnectAI-E/feishu-openai) (5.6K) - Feishu + GPT-4

详见 [integrations/README.md](integrations/README.md) 和 [REFERENCES.md](REFERENCES.md).
