# Windows install guide

> Windows 10/11 + WSL2 + Hermes Agent is verified working (2026-06-14).
> Native Windows (no WSL) uses NSSM + Task Scheduler — this section is
> a stub, real testing is TODO.

## Prerequisites

| Component | Version | Check |
|---|---|---|
| Windows | 10 1909+ / 11 (WSL2 recommended) | `ver` |
| WSL2 | Ubuntu 22.04 LTS (recommended) | `wsl --status` |
| Python | 3.11+ (inside WSL) | `wsl python3 --version` |
| Go | 1.20+ (inside WSL) | `wsl go version` |

## WSL2 recommended path (90% of users)

Inside WSL2 Ubuntu, install is **almost identical to macOS**:

```bash
# Inside WSL
sudo apt update
sudo apt install python3.11 python3-pip

# Install uv (Hermes-style venv management)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Feishu deps
~/.cargo/bin/uv venv --python 3.11 ~/.venvs/feishu-cli
~/.cargo/bin/uv pip install --python ~/.venvs/feishu-cli/bin/python3 \
  lark-oapi websockets cryptography requests

# Install via54Larkbotgo
cd /mnt/c/Users/<you>/Desktop/developments  # or ~/developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin/via54Larkbotgo ./
ln -sf $PWD/bin/via54Larkbotgo ~/.local/bin/via54Larkbotgo
chmod +x ~/.local/bin/via54Larkbotgo
```

## Native Windows path (no WSL)

⚠️ **stub**: this repo has not tested native Windows. The following
is a template based on Task Scheduler + NSSM standard practice.

```powershell
# 1. Install Python 3.11 (Python.org installer, check "Add to PATH")
# 2. Install uv
irm https://astral.sh/uv/install.ps1 | iex

# 3. Install Feishu deps
uv venv --python 3.11 C:\Users\<you>\.local\share\feishu-cli\venv
uv pip install --python C:\Users\<you>\.local\share\feishu-cli\venv\Scripts\python.exe `
  lark-oapi websockets cryptography requests

# 4. Install via54Larkbotgo
cd C:\Users\<you>\Desktop\developments
git clone https://github.com/veawho/via54Larkbotgo.git
cd via54Larkbotgo
go build -o bin\via54Larkbotgo.exe .\
# Add to PATH or remember absolute path

# 5. Credentials
echo {"app_id": "cli_xxx", "app_secret": "yyy"} | Out-File -Encoding utf8 $env:USERPROFILE\.config\feishu\credentials.json
icacls $env:USERPROFILE\.config\feishu\credentials.json /inheritance:r /grant:r "$env:USERNAME:(R)"

# 6. NSSM to register as a service (use NSSM, not Task Scheduler + python launcher, complex)
# Download https://nssm.cc/release/nssm-2.24.zip
nssm install FeishuBotDaemon C:\path\to\via54Larkbotgo\bin\via54Larkbotgo.exe
nssm set FeishuBotDaemon AppParameters --app-id cli_xxx --app-secret yyy
nssm set FeishuBotDaemon AppStdout C:\path\to\logs\feishu-bot.out.log
nssm set FeishuBotDaemon AppStderr C:\path\to\logs\feishu-bot.err.log
nssm start FeishuBotDaemon
```

## Verify (WSL2)

```bash
# binary
~/.local/bin/via54Larkbotgo --help

# WS connection
lsof -nP -p $(pgrep -f via54Larkbotgo) | grep msg-frontier

# Feishu DM test
```

## Known issues

| Issue | Cause | Workaround |
|---|---|---|
| WSL2 `wslview` opens Windows Explorer, but Feishu push path doesn't work | Feishu SDK in WSL2 can't read Windows registry directly | Use WSL's fsnotify, not Windows event log |
| NSSM + Go binary on Windows 11 occasionally crashes (exit 3221225781) | Go runtime incompatibility with Windows MinGW | Use `start /B` + Task Scheduler + Python wrapper |
| No official `feishu-cli` build for native Windows | lark-oapi prioritizes Linux/macOS | Use WSL2 |

## Related

- [macOS install](install-macos.md) (more detailed)
- [Linux install](install-linux.md)
- [Connection modes](connection-modes.md)