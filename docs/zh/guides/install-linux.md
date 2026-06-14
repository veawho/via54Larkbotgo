# Linux 安装指南

> Ubuntu 22.04 LTS + Hermes Agent 实测可行(本仓库计划支持, 未实跑)。
> 跟 macOS 主要差异: systemd 而非 launchd。

## 前置要求

| 组件 | 版本 | 检查 |
|---|---|---|
| Ubuntu | 22.04 LTS (推荐) | `lsb_release -a` |
| Python | 3.11+ | `python3 --version` |
| Go | 1.20+ | `go version` |
| systemd | 250+ (Ubuntu 22.04 默认) | `systemctl --version` |

## 完整安装

```bash
# === 1. system deps ===
sudo apt update
sudo apt install python3.11 python3-pip

# 装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# === 2. 飞书 deps ===
~/.local/bin/uv venv --python 3.11 ~/.venvs/feishu-cli
~/.local/bin/uv pip install --python ~/.venvs/feishu-cli/bin/python3 \
  lark-oapi websockets cryptography requests

# === 3. via54Larkbotgo ===
cd ~/developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin/via54Larkbotgo ./
ln -sf $PWD/bin/via54Larkbotgo ~/.local/bin/via54Larkbotgo
chmod +x ~/.local/bin/via54Larkbotgo

# === 4. 凭证 ===
mkdir -p ~/.config/feishu
cat > ~/.config/feishu/credentials.json << 'EOF'
{"app_id": "cli_xxx", "app_secret": "yyy"}
EOF
chmod 600 ~/.config/feishu/credentials.json

# === 5. systemd user service ===
mkdir -p ~/.config/systemd/user/

cat > ~/.config/systemd/user/feishu-bot.service << 'EOF'
[Unit]
Description=Feishu/Lark WS bot daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/via54Larkbotgo --app-id cli_xxx --app-secret yyy
Restart=on-failure
RestartSec=10
StandardOutput=append:%h/.hermes/logs/feishu-bot.out.log
StandardError=append:%h/.hermes/logs/feishu-bot.err.log

[Install]
WantedBy=default.target
EOF

# 6. 启 + enable
systemctl --user daemon-reload
systemctl --user enable feishu-bot.service
systemctl --user start feishu-bot.service
systemctl --user status feishu-bot.service
```

## 验证

```bash
# 1. service 状态
systemctl --user status feishu-bot.service
# → active (running) + main PID + "Started Feishu/Lark WS bot daemon"

# 2. ws 连接
ss -tnp | grep via54Larkbotgo
# → ESTAB 到 msg-frontier.feishu.cn:443

# 3. 飞书测试
# 在飞书私聊 bot, 期望收 LLM 回复
```

## 跟 macOS 差异

| 维度 | macOS | Linux |
|---|---|---|
| Service 管理 | launchd (user agent) | systemd (user instance) |
| Restart 触发 | launchd throttle (5 I/O 错) | systemd 自动 restart=on-failure |
| 凭证路径 | `~/Library/Application Support/lark-cli/` (mac 习惯) | `~/.config/lark-cli/` (Linux 习惯) |
| 文件监控 | fsevents (kqueue) | inotify |
| Webhook 入站 | 需要 port-forwarding 工具 (ngrok) | 直接监听 443 + Nginx + Let\'s Encrypt |

## 已知问题

| 问题 | 原因 | 解 |
|---|---|---|
| `systemctl --user status` 显示 "Failed to connect to bus" | 没 `--user` 标志 | 显式加 `--user` |
| systemd user service 开机不启 | 默认 `default.target` 不在 user 实例启动范围 | `loginctl enable-linger <user>` 让 user service 持久 |
| certbot 自动续签 webhook 证书不工作 | 端口 80 被 systemd-resolved 占 | 用 `--http-01-port 8080` |

## 相关

- [macOS 安装](install-macos.md)
- [Windows 安装](install-windows.md)
- [连接方式对比](connection-modes.md)
- [Hermes 集成](ai-tools-hermes.md)
