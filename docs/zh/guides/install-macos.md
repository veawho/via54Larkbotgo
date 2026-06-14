# macOS 安装指南

> 本机 macOS 26.5.1 + Hermes Agent 已实跑, 本指南是该套路的固化。

## 前置要求

| 组件 | 版本 | 检查 |
|---|---|---|
| macOS | 12+ (推荐 15 Sequoia) | `sw_vers` |
| Python | 3.11+ | `python3 --version` |
| Go | 1.20+ (编译 skeleton 用) | `go version` |
| uv | 0.11+ (venv 管理) | `uv --version` |
| Node | 18+ (VitePress build) | `node --version` |

## macOS 特定坑 (SPCTL + Sequoia)

### 坑 1: `/usr/local/bin` 装 binary 会被 spctl 拒绝

```bash
# ❌ 不要装这里
cp via54 /usr/local/bin/
# → Gatekeeper 拒执行, 错误: "cannot be opened because the developer cannot be verified"

# ✅ 装到 ~/.local/bin/ 跳过 quarantine
mkdir -p ~/.local/bin
cp via54 ~/.local/bin/
chmod +x ~/.local/bin/via54
# → 立即可执行 (因为 $HOME 不在 spctl 监控路径)
```

### 坑 2: macOS Sequoia `com.apple.provenance` xattr

```bash
# 检查 binary 是否有 provenance xattr (Sequoia 加的新限制)
xattr -l ~/.local/bin/via54
# com.apple.provenance: ...  ← 这是新的, launchd plist 启的子进程会拒读

# 解决: 不要用 launchd plist 启 bot (用直接命令行)
# 或者: 用 launchctl bootstrap + stdin/stdout 重定向绕开
```

### 坑 3: launchd throttle (Bootstrap failed: 5)

```bash
# 短时间内多次 launchctl bootstrap 会触发 throttle (5-15 分钟)
# 等 + 重试:
sleep 90
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.david.feishu-bot.plist
```

## 完整安装流程

```bash
# === 1. 装 system deps (假设都没有) ===
brew install python@3.11 go node uv

# === 2. 装飞书相关 ===
mkdir -p ~/.local/bin ~/.venvs/feishu-cli
~/.hermes/bin/uv venv --python 3.11 ~/.venvs/feishu-cli
~/.hermes/bin/uv pip install --python ~/.venvs/feishu-cli/bin/python3 \
  lark-oapi websockets cryptography requests aiohttp

# === 3. 装 via54Larkbotgo (Go skeleton) ===
cd ~/Desktop/developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin/via54Larkbotgo ./
ln -sf $PWD/bin/via54Larkbotgo ~/.local/bin/via54Larkbotgo
chmod +x ~/.local/bin/via54Larkbotgo

# === 4. 凭证 ===
echo \'{"app_id": "cli_xxx", "app_secret": "yyy"}' > ~/.config/feishu/credentials.json
chmod 600 ~/.config/feishu/credentials.json

# === 5. 启动 ===
~/.local/bin/via54Larkbotgo --app-id cli_xxx --app-secret yyy
# 或前台跑 daemon + watcher (详见 ../guides/ai-tools-hermes.md)
```

## 验证

```bash
# 1. binary 能跑
~/.local/bin/via54Larkbotgo --help

# 2. ws 连接到飞书
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier

# 3. 在飞书给 bot 发私聊, 收到 LLM 回复
```

## 文档站 (本仓库 docs/)

```bash
cd ~/Desktop/developments/via54Larkbotgo
npm install
npm run docs:dev
# 打开 http://localhost:5173/via54Larkbotgo/
```

## 相关

- [Windows 安装](install-windows.md)
- [Linux 安装](install-linux.md)
- [连接方式对比](connection-modes.md)
- [Hermes 集成](ai-tools-hermes.md)
