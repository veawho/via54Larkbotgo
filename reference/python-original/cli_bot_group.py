#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot/feishu_bot_daemon.py — 飞书 WebSocket bot daemon (extracted from feishu CLI)

历史: 2026-06-09 19:30+ UTC, david 在 Hermes session 里为
      inbox_watcher + feishu-bot 端到端跑通, 把 bot 子命令从
      /Users/david/.local/bin/feishu 抽出独立维护.

依赖: lark-oapi 1.6.8, Python 3.9+ venv at ~/.local/share/feishu-cli/venv
环境: ALLOWED_CHATS=oc_xxx,oc_xxx (白名单群, 逗号分隔)
      FEISHU_BOT_APP_ID=cli_xxx (robot app_id, 默认 <APP_ID>)
启动: feishu bot start (前台, 用于 launchd)
"""

# === bot (WebSocket 长连接收消息) ===
@main.group()
def bot():
    """WebSocket 长连接 bot daemon, 实时收消息 + 自动回复"""
    pass
@bot.command('start')
@click.option('--foreground', '-f', is_flag=True, help='前台跑 (不 fork), Ctrl-C 停')
def bot_start(foreground):
    """启动 bot daemon (ws 长连接, 实时收消息).

    v3.0 拆 daemon: 直接 Popen 独立 .py 脚本, 不再 f-string 模板生成
    (Python 3.11 PEP 701 严格化, dict literal 踩雷).
    daemon: ~/hermes/scripts/feishu_bot_daemon.py
    """
    import subprocess, time
    creds = load_creds()
    if not creds:
        print('❌ 无凭据, 跑 `feishu auth login`')
        sys.exit(1)
    app_id, _ = creds
    pid_file = Path('/tmp/feishu_bot.pid')
    log_file = Path('/tmp/feishu_bot.log')
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text())
            os.kill(pid, 0)
            print(f'⚠️  bot 已在跑 pid={pid}, log={log_file}')
            return
        except (OSError, ValueError):
            pid_file.unlink(missing_ok=True)

    # v3.0: daemon 是独立 .py, 用 venv 绝对路径 (避免 env python3 跳到 brew 3.14)
    daemon_py = '/Users/david/.hermes/scripts/feishu_bot_daemon.py'
    python_bin = f'{VENV}/bin/python3'
    if not Path(daemon_py).exists():
        print(f'❌ daemon 脚本不存在: {daemon_py}')
        sys.exit(1)
    try:
        if foreground:
            print(f'🚀 前台跑 bot (Ctrl-C 停), log → {log_file}')
            r = subprocess.run([python_bin, daemon_py])
            sys.exit(r.returncode)
        else:
            print(f'🚀 后台启动 bot (v3.0 daemon, Python 3.11)')
            p = subprocess.Popen(
                [python_bin, daemon_py],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f'   pid={p.pid}  (2s 后确认)')
            time.sleep(2)
            if Path('/tmp/feishu_bot.pid').exists():
                pid = Path('/tmp/feishu_bot.pid').read_text()
                print(f'   ✅ 起来了, pid={pid}, log={log_file}')
                print(f'   停: feishu bot stop  /  看 log: feishu bot log')
            else:
                print(f'   ⚠️  还没起, 看 {log_file}')
    except Exception as e:
        print(f'❌ 启动失败: {type(e).__name__}: {e}')
        sys.exit(1)
@bot.command('stop')
def bot_stop():
    """停 bot"""
    pid_file = Path('/tmp/feishu_bot.pid')
    if not pid_file.exists():
        print('没在跑')
        return
    pid = int(pid_file.read_text())
    import signal
    try:
        os.kill(pid, signal.SIGTERM)
        print(f'SIGTERM → {pid}')
        for _ in range(10):
            time.sleep(0.5)
            try: os.kill(pid, 0)
            except OSError: break
        else:
            os.kill(pid, signal.SIGKILL)
        pid_file.unlink(missing_ok=True)
        print('✅ 已停')
    except OSError as e:
        print(f'⚠️  {e}')
        pid_file.unlink(missing_ok=True)
@bot.command('status')
def bot_status():
    """看 bot 状态"""
    pid_file = Path('/tmp/feishu_bot.pid')
    log_file = Path('/tmp/feishu_bot.log')
    if pid_file.exists():
        pid = int(pid_file.read_text())
        try:
            os.kill(pid, 0)
            print(f'✅ bot 在跑 pid={pid}')
        except OSError:
            print(f'⚠️  pid file 残留, 清理')
            pid_file.unlink(missing_ok=True)
    else:
        print('❌ bot 没在跑')
    if log_file.exists():
        print(f'\\n--- log last 8 lines ---')
        for line in log_file.read_text().splitlines()[-8:]:
            print(f'  {line}')
@bot.command('log')
def bot_log():
    """tail -f log"""
    log_file = Path('/tmp/feishu_bot.log')
    if not log_file.exists():
        print('log 还没')
        return
    print(f'>>> tail -f {log_file} (Ctrl-C 退出) <<<')
    try:
        with open(log_file, 'r') as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.5)
    except KeyboardInterrupt:
        pass
# === whoami ===
@main.command('whoami')
def whoami():
    """实调飞书 API 验证凭据: 拿 tenant_access_token"""
    creds = load_creds()
    if not creds:
        print('❌ 无凭据')
        sys.exit(1)
    app_id, app_secret = creds
    print(f'app_id:  {app_id}')
    print(f'SDK:     lark-oapi 1.6.8 (在 venv)')
    print(f'domain:  https://open.feishu.cn')
    print()
    print('--- 申请 tenant_access_token (raw HTTP) ---')
    try:
        token, expire = _get_tenant_token(app_id, app_secret)
        print(f'✅ 凭据 OK!')
        print(f'   expire:    {expire} 秒 ({expire // 60} 分钟)')
        print(f'   token:     {token[:8]}…{token[-4:]}')
        print()
        print('🎉 飞书 CLI 已可用. 试试:')
        print('   feishu drive spaces    (列云空间)')
        print('   feishu docs list       (列根目录文件)')
        print('   feishu msg send <chat_id> "hello"  (发消息)')
    except Exception as e:
        print(f'❌ 凭据失败: {e}')
        sys.exit(1)
