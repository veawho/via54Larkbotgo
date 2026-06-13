# Linux install guide

> Ubuntu 22.04 LTS + Hermes Agent is supported (planned, not run
> locally). Main difference from macOS: **systemd** instead of launchd.

## Prerequisites

| Component | Version | Check |
|---|---|---|
| Ubuntu | 22.04 LTS (recommended) | `lsb_release -a` |
| Python | 3.11+ | `python3 --version` |
| Go | 1.20+ | `go version` |
| systemd | 250+ (default in Ubuntu 22.04) | `systemctl --version` |

## Full install

```bash
# === 1. System deps ===
sudo apt update
sudo apt install python3.11 python3-pip

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# === 2. Feishu deps ===
~/.local/bin/uv venv --python 3.11 ~/.local/share/feishu-cli/venv
~/.local/bin/uv pip install --python ~/.local/share/feishu-cli/venv/bin/python3 \
  lark-oapi websockets cryptography requests

# === 3. via54Larkbotgo ===
cd ~/developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin/via54Larkbotgo ./
ln -sf $PWD/bin/via54Larkbotgo ~/.local/bin/via54Larkbotgo
chmod +x ~/.local/bin/via54Larkbotgo

# === 4. Credentials ===
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

# 6. Start + enable
systemctl --user daemon-reload
systemctl --user enable feishu-bot.service
systemctl --user start feishu-bot.service
systemctl --user status feishu-bot.service
```

## Verify

```bash
# 1. Service status
systemctl --user status feishu-bot.service
# → active (running) + main PID + "Started Feishu/Lark WS bot daemon"

# 2. WS connection
ss -tnp | grep via54Larkbotgo
# → ESTAB to msg-frontier.feishu.cn:443

# 3. Feishu test
# DM the bot in Feishu, expect to receive LLM reply
```

## Differences from macOS

| Dimension | macOS | Linux |
|---|---|---|
| Service manager | launchd (user agent) | systemd (user instance) |
| Restart trigger | launchd throttle (5 I/O errors) | systemd auto `Restart=on-failure` |
| Credentials path | `~/Library/Application Support/lark-cli/` (mac convention) | `~/.config/lark-cli/` (Linux convention) |
| File monitoring | fsevents (kqueue) | inotify |
| Webhook inbound | needs port-forwarding tool (ngrok) | direct port 443 listen + Nginx + Let's Encrypt |

## Known issues

| Issue | Cause | Workaround |
|---|---|---|
| `systemctl --user status` shows "Failed to connect to bus" | missing `--user` flag | add `--user` explicitly |
| systemd user service doesn't auto-start at boot | `default.target` not in user instance startup scope | `loginctl enable-linger <user>` for user service persistence |
| certbot auto-renewal of webhook cert doesn't work | port 80 held by systemd-resolved | use `--http-01-port 8080` |

## Related

- [macOS install](install-macos.md)
- [Windows install](install-windows.md)
- [Connection modes](connection-modes.md)
- [Hermes integration](ai-tools-hermes.md)