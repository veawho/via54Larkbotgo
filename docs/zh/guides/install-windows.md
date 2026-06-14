# Windows 安装指南

> Windows 10/11 + WSL2 + Hermes Agent 实测可行(2026-06-14)。
> 原生 Windows (无 WSL) 走 NSSM + Task Scheduler, 本节给 stub, 实测待补。

## 前置要求

| 组件 | 版本 | 检查 |
|---|---|---|
| Windows | 10 1909+ / 11 (推荐 WSL2) | `ver` |
| WSL2 | Ubuntu 22.04 LTS (推荐) | `wsl --status` |
| Python | 3.11+ (WSL 内) | `wsl python3 --version` |
| Go | 1.20+ (WSL 内) | `wsl go version` |

## WSL2 推荐路径 (90% 用户)

WSL2 Ubuntu 内 跟 macOS 安装**几乎一致**:

```bash
# WSL 内
sudo apt update
sudo apt install python3.11 python3-pip

# 装 uv (Hermes 风格 venv 管理)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 装飞书 deps
~/.cargo/bin/uv venv --python 3.11 ~/.venvs/feishu-cli
~/.cargo/bin/uv pip install --python ~/.venvs/feishu-cli/bin/python3 \
  lark-oapi websockets cryptography requests

# 装 via54Larkbotgo
cd /mnt/c/Users/<you>/Desktop/developments  # 或 ~/developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin/via54Larkbotgo ./
ln -sf $PWD/bin/via54Larkbotgo ~/.local/bin/via54Larkbotgo
chmod +x ~/.local/bin/via54Larkbotgo
```

## 原生 Windows 路径 (无 WSL)

⚠️ **stub**: 本仓库未实测原生 Windows, 下面是基于 Task Scheduler + NSSM
标准做法的模板。

```powershell
# 1. 装 Python 3.11 (Python.org installer, 勾 "Add to PATH")
# 2. 装 uv
irm https://astral.sh/uv/install.ps1 | iex

# 3. 装飞书 deps
uv venv --python 3.11 C:\Users\<you>\.local\share\feishu-cli\venv
uv pip install --python C:\Users\<you>\.local\share\feishu-cli\venv\Scripts\python.exe `
  lark-oapi websockets cryptography requests

# 4. 装 via54Larkbotgo
cd C:\Users\<you>\Desktop\developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin\via54Larkbotgo.exe .\
# 加到 PATH 或者记绝对路径

# 5. 凭证
echo {"app_id": "cli_xxx", "app_secret": "yyy"} | Out-File -Encoding utf8 $env:USERPROFILE\.config\feishu\credentials.json
icacls $env:USERPROFILE\.config\feishu\credentials.json /inheritance:r /grant:r "$env:USERNAME:(R)"

# 6. NSSM 注册服务 (用 NSSM, 不要用 Task Scheduler + python 启动, 复杂)
# 下载 https://nssm.cc/release/nssm-2.24.zip
nssm install FeishuBotDaemon C:\path\to\via54Larkbotgo\bin\via54Larkbotgo.exe
nssm set FeishuBotDaemon AppParameters --app-id cli_xxx --app-secret yyy
nssm set FeishuBotDaemon AppStdout C:\path\to\logs\feishu-bot.out.log
nssm set FeishuBotDaemon AppStderr C:\path\to\logs\feishu-bot.err.log
nssm start FeishuBotDaemon
```

## 验证 (WSL2)

```bash
# binary
~/.local/bin/via54Larkbotgo --help

# ws 连接
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier

# 飞书私聊测试
```

## 已知问题

| 问题 | 原因 | 解 |
|---|---|---|
| WSL2 装 `wslview` 后 Win 资源管理器打开, 但 feishu 推送路径不工作 | 飞书 SDK 在 WSL2 内不能直接读 Windows 注册表 | 用 WSL 内 fsnotify, 不要用 Windows event log |
| NSSM + Go binary 在 Windows 11 偶尔崩溃 (exit code 3221225781) | Go runtime 跟 Windows MinGW 不兼容 | 改用 `start /B` + Task Scheduler 启 Python 包装层 |
| 原生 Windows feishu-cli 没有官方 build | lark-oapi 主要 Linux/macOS 优先 | 用 WSL2 |

## 相关

- [macOS 安装](install-macos.md) (更详细)
- [Linux 安装](install-linux.md)
- [连接方式对比](connection-modes.md)
