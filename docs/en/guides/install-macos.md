# macOS install guide

> **Locally running on macOS 26.5.1 + Hermes Agent**. This guide is the
> hardened version of that setup.

## Prerequisites

| Component | Version | Check |
|---|---|---|
| macOS | 12+ (15 Sequoia recommended) | `sw_vers` |
| Python | 3.11+ | `python3 --version` |
| Go | 1.20+ (to build skeleton) | `go version` |
| uv | 0.11+ (venv management) | `uv --version` |
| Node | 18+ (VitePress build) | `node --version` |

## macOS-specific gotchas (SPCTL + Sequoia)

### Gotcha 1: `/usr/local/bin` rejects binaries via spctl

```bash
# ❌ Don't install here
cp via54 /usr/local/bin/
# → Gatekeeper refuses: "cannot be opened because the developer cannot be verified"

# ✅ Install to ~/.local/bin/ to skip quarantine
mkdir -p ~/.local/bin
cp via54 ~/.local/bin/
chmod +x ~/.local/bin/via54
# → immediately executable (because $HOME is not in spctl's monitored paths)
```

### Gotcha 2: macOS Sequoia `com.apple.provenance` xattr

```bash
# Check whether a binary has the new provenance xattr
xattr -l ~/.local/bin/via54
# com.apple.provenance: ...  ← new in Sequoia, launchd-launched children can't read it

# Workaround: call the bot from the command line directly, not via launchd plist
# Or: use launchctl bootstrap + stdin/stdout redirect to bypass
```

### Gotcha 3: launchd throttle (Bootstrap failed: 5)

```bash
# Multiple launchctl bootstrap calls in quick succession trigger throttle (5-15 min)
# Wait + retry:
sleep 90
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.david.feishu-bot.plist
```

## Full install flow

```bash
# === 1. Install system deps (if not present) ===
brew install python@3.11 go node uv

# === 2. Install Feishu deps ===
mkdir -p ~/.local/bin ~/.local/share/feishu-cli/venv
~/.hermes/bin/uv venv --python 3.11 ~/.local/share/feishu-cli/venv
~/.hermes/bin/uv pip install --python ~/.local/share/feishu-cli/venv/bin/python3 \
  lark-oapi websockets cryptography requests aiohttp

# === 3. Install via54Larkbotgo (Go skeleton) ===
cd ~/Desktop/developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin/via54Larkbotgo ./
ln -sf $PWD/bin/via54Larkbotgo ~/.local/bin/via54Larkbotgo
chmod +x ~/.local/bin/via54Larkbotgo

# === 4. Credentials ===
echo '{"app_id": "cli_xxx", "app_secret": "yyy"}' > ~/.config/feishu/credentials.json
chmod 600 ~/.config/feishu/credentials.json

# === 5. Start ===
~/.local/bin/via54Larkbotgo --app-id cli_xxx --app-secret yyy
# Or run daemon + watcher in foreground (see ../guides/ai-tools-hermes.md)
```

## Verify

```bash
# 1. binary runs
~/.local/bin/via54Larkbotgo --help

# 2. WS connection to Feishu
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier

# 3. Test: DM the bot in Feishu, receive LLM reply
```

## Docs site (this repo's docs/)

```bash
cd ~/Desktop/developments/via54Larkbotgo
npm install
npm run docs:dev
# Open http://localhost:5173/via54Larkbotgo/
```

## Related

- [Windows install](install-windows.md)
- [Linux install](install-linux.md)
- [Connection modes](connection-modes.md)
- [Hermes integration](ai-tools-hermes.md)