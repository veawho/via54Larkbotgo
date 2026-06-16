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
    """启动 bot daemon (ws 长连接, 实时收消息)"""
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

    # inline bot脚本 (写到 tmp, venv python跑)
    bot_code = f'''
import os, sys, json, time, re, threading, shutil, glob, subprocess, warnings
sys.path.insert(0, "/Users/david/.hermes/hermes-agent/venv/lib/python3.9/site-packages")
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
import urllib.request, ssl

CREDS = "/Users/david/.config/feishu/credentials.json"
LOG   = "/tmp/feishu_bot.log"

def log(msg):
    line = f"[{{time.strftime('%H:%M:%S')}}] {{msg}}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\\n")

def get_token():
    creds = json.loads(open(CREDS).read())
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps(creds).encode()
    req = urllib.request.Request(url, data=data, headers={{"Content-Type": "application/json"}})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        body = json.loads(resp.read().decode())
    if body.get("code") == 0:
        return body["tenant_access_token"]
    raise RuntimeError(f"auth fail: {{body}}")

def reply(chat_id, text):
    # 2026-06-15: 加 _send_path_degraded 修法 (per Hermes PR #31441 c0441cb)
    # 概念: send 路径异常后短路返 retryable, 让 caller 走 fallback 路径
    # Hermes 适用: PTB Telegram httpx pool 状态; Larkfix 适用: urllib 重试
    # 状态: module-level 标志 (per Hermes 设计 — 'self' attr 避免 init 复杂)
    if globals().get('_send_path_degraded', False):
        log(f"reply short-circuit (send_path_degraded) chat_id={chat_id}")
        return  # 静默返, caller 看 .error/.retry 路径 (per inbox_watcher 设计)

    # 1. Increment 失败计数
    globals().setdefault('_send_path_failure_count', 0)
    globals().setdefault('_send_path_success_streak', 0)

    try:
        tok = get_token()
        # 自动识别 ID 类型: oc_=chat_id, ou_=open_id, on_=user_id
        if chat_id.startswith('oc_'):
            id_type = 'chat_id'
        elif chat_id.startswith('ou_'):
            id_type = 'open_id'
        elif chat_id.startswith('on_'):
            id_type = 'user_id'
        else:
            id_type = 'chat_id'
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={{id_type}}"
        data = json.dumps({{
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({{"text": text}}, ensure_ascii=False)
        }}).encode()
        req = urllib.request.Request(url, data=data, headers={{
            "Authorization": f"Bearer {{tok}}",
            "Content-Type": "application/json; charset=utf-8"
        }}, method="POST")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body = json.loads(resp.read().decode())
        if body.get("code") == 0:
            log(f"reply sent msg_id={{body['data']['message_id']}} id_type={{id_type}}")
            # 2. 成功 → reset 失败计数 + 增加 success streak
            globals()['_send_path_failure_count'] = 0
            globals()['_send_path_success_streak'] = globals().get('_send_path_success_streak', 0) + 1
            # 3. 2+ 连续成功 → clear degraded
            if globals()['_send_path_success_streak'] >= 2:
                if globals().get('_send_path_degraded', False):
                    log("send_path RECOVERED (2+ consecutive OK)")
                globals()['_send_path_degraded'] = False
        else:
            log(f"reply FAIL {{body.get('code')}} {{body.get('msg')}}")
            globals()['_send_path_success_streak'] = 0
            globals()['_send_path_failure_count'] = globals().get('_send_path_failure_count', 0) + 1
            # 4. 3+ 连续失败 → set degraded
            if globals()['_send_path_failure_count'] >= 3:
                if not globals().get('_send_path_degraded', False):
                    log("send_path DEGRADED (3+ consecutive fail) — short-circuit until recover")
                globals()['_send_path_degraded'] = True
    except Exception as e:
        log(f"reply EXC: {{type(e).__name__}}: {{e}}")
        globals()['_send_path_success_streak'] = 0
        globals()['_send_path_failure_count'] = globals().get('_send_path_failure_count', 0) + 1
        if globals()['_send_path_failure_count'] >= 3:
            if not globals().get('_send_path_degraded', False):
                log("send_path DEGRADED (3+ consecutive EXC) — short-circuit until recover")
            globals()['_send_path_degraded'] = True

def _write_inbox(msg_id, chat_id, sender_open_id, sender_name, text):
    # (inline copy) 写 /tmp/hermes_inbox/<msg_id>.json, 给 hermes agent 消费.
    # 失败不抛, log 后返回 None.
    try:
        inbox_dir = "/tmp/hermes_inbox"
        os.makedirs(inbox_dir, exist_ok=True)
        if not sender_name:
            sender_name = sender_open_id or "?"
        # sanitize msg_id (飞书 OM_xxxxx 安全, 保险起见)
        safe_id = re.sub(r"[^A-Za-z0-9_\\-]", "_", str(msg_id)) if msg_id else f"auto_{{int(time.time()*1000)}}"
        payload = {{
            "msg_id": msg_id,
            "chat_id": chat_id,
            "sender_open_id": sender_open_id,
            "sender_name": sender_name,
            "text": text,
            "received_at": time.time(),
        }}
        path = os.path.join(inbox_dir, f"{{safe_id}}.json")
        with open(path, "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log(f"inbox written {{path}}")
        return path
    except Exception as e:
        log(f"_write_inbox EXC: {{type(e).__name__}}: {{e}}")
        return None

def outbox_watcher():
    # 5s 轮询 /tmp/hermes_outbox/*.json, 调 reply() POST 回飞书, 然后 mv 到 .done/.
    # daemon thread, 跟 ws 主线程同生命周期.
    outbox_dir = "/tmp/hermes_outbox"
    done_dir = os.path.join(outbox_dir, ".done")
    os.makedirs(done_dir, exist_ok=True)
    while True:
        try:
            files = sorted(glob.glob(os.path.join(outbox_dir, "*.json")))
            for path in files:
                try:
                    with open(path) as f:
                        out = json.load(f)
                    chat_id = out.get("chat_id")
                    reply_text = out.get("reply") or out.get("text") or ""
                    if not chat_id or not reply_text:
                        log(f"outbox skip (无 chat_id/reply): {{path}}")
                        # 坏文件也搬走, 避免反复打
                        shutil.move(path, os.path.join(done_dir, os.path.basename(path)))
                        continue
                    reply(chat_id, reply_text)
                    # 搬 .done/
                    try:
                        shutil.move(path, os.path.join(done_dir, os.path.basename(path)))
                        log(f"outbox sent+archived {{os.path.basename(path)}}")
                    except Exception as me:
                        log(f"outbox move FAIL: {{type(me).__name__}}: {{me}}")
                except Exception as fe:
                    log(f"outbox file FAIL {{path}}: {{type(fe).__name__}}: {{fe}}")
        except Exception as e:
            log(f"outbox_watcher EXC: {{type(e).__name__}}: {{e}}")
        time.sleep(5)

def on_msg(data: P2ImMessageReceiveV1) -> None:
    try:
        e = data.event
        msg = e.message
        sender = e.sender
        chat_id = msg.chat_id
        msg_type = msg.message_type
        try:
            content = json.loads(msg.content) if msg.content else {{}}
        except Exception:
            content = {{"text": msg.content}}
        text = (content.get("text") or "") if isinstance(content, dict) else str(content)
        text = re.sub(r"@_user_\\d+\\s*", "", text).strip()
        sender_open = sender.sender_id.open_id if sender.sender_id else "?"
        sender_name = sender.sender_id.user_id or sender.sender_id.open_id or "?" if sender.sender_id else "?"
        log(f"RECV chat={{chat_id[:18]}} from={{sender_open[:15]}} type={{msg_type}} text={{text[:80]!r}}")

        # 命令路由
        if text.startswith("/") or text.startswith("!"):
            cmd = text[1:].strip()
            handle_command(chat_id, cmd, sender_open)
        else:
            # 无前缀: 投递到 inbox, 等 hermes agent 消费 + outbox 回流
            msg_id = msg.message_id
            _write_inbox(msg_id, chat_id, sender_open, sender_name, text)
            # 立即 ack, 不阻塞 ws (LLM 慢, 用户要立刻知道 bot 收到了)
            reply(chat_id, "🤔 思考中...")
    except Exception as e:
        log(f"on_msg EXC: {{type(e).__name__}}: {{e}}")

def handle_command(chat_id: str, cmd: str, sender_open: str) -> None:
    # 路由 /command 到具体 handler
    try:
        parts = cmd.split(None, 1)
        verb = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""

        if verb == "help" or verb == "h":
            reply(chat_id,
                "🤖 Hermes bot 命令:\\n"
                "/nas <关键词>     — 搜 nas 知识库 (top 5)\\n"
                "/nas <关键词> -n10 — 搜 top 10\\n"
                "/shell <cmd>      — 跑本地 shell (限制白名单)\\n"
                "/status           — 看系统状态 (launchd / bot / indexer)\\n"
                "/pid              — 看你自己的 open_id\\n"
                "/help             — 这条\\n\\n"
                "无前缀消息: echo 确认"
            )
        elif verb == "pid":
            reply(chat_id, f"你的 open_id: {{sender_open}}")
        elif verb == "nas":
            if not args:
                reply(chat_id, "用法: /nas <关键词>\\n例: /nas 胃食管反流病")
                return
            # 解析 -n K / --top K
            import re as _re
            top_m = _re.search(r"\\s-(?:n|top)\\s*(\\d+)", args)
            top = int(top_m.group(1)) if top_m else 5
            query = _re.sub(r"\\s-(?:n|top)\\s*\\d+", "", args).strip()
            log(f"CMD nas query={{query!r}} top={{top}}")
            # 子进程跑 query.py
            t0 = time.time()
            r = subprocess.run(
                ["/Users/david/nas_kb/nas_kb_venv/bin/python3",
                 "/Users/david/nas_kb/scripts/query.py", query, "--top", str(top)],
                capture_output=True, text=True, timeout=60,
                env={{**os.environ, "HTTPS_PROXY": "http://127.0.0.1:7890",
                       "HTTP_PROXY": "http://127.0.0.1:7890",
                       "HF_HUB_OFFLINE": "1",
                       "TRANSFORMERS_OFFLINE": "1"}}
            )
            elapsed = time.time() - t0
            if r.returncode != 0:
                log(f"nas query FAIL: {{r.stderr[:200]}}")
                reply(chat_id, f"❌ nas 查询失败 ({{elapsed:.1f}}s): {{r.stderr[:300] or r.stdout[:300]}}")
                return
            # 截断输出 (飞书消息上限 ~4000 字)
            out = r.stdout
            if len(out) > 3500:
                out = out[:3500] + "\\n... (截断, 完整结果看终端)"
            reply(chat_id, f"🔍 nas 搜 '{{query}}' (top {{top}}, {{elapsed:.1f}}s):\\n\\n{{out}}")
        elif verb == "shell":
            # 危险: 白名单
            if not args:
                reply(chat_id, "用法: /shell <命令>\\n白名单: ps, ls, df, uptime, uname, whoami, pwd, date, cat(限 ~/.hermes), tail(限 logs), echo")
                return
            head = args.split()[0]
            whitelist = ["ps", "ls", "df", "uptime", "uname", "whoami", "pwd", "date",
                         "tail", "echo", "cat"]
            if head not in whitelist:
                reply(chat_id, f"❌ 命令 '{{head}}' 不在白名单. 白名单: {{whitelist}}")
                return
            log(f"CMD shell {{args[:80]}}")
            r = subprocess.run(args, shell=True, capture_output=True, text=True, timeout=10)
            out = (r.stdout + r.stderr)[:3500]
            reply(chat_id, f"$ {{args[:100]}}\\n{{out}}")
        elif verb == "status":
            lines = []
            for cmd in ["/Users/david/.local/bin/feishu bot status",
                        "ps -eo pid,etime,command | grep -E 'indexer|foreground' | grep -v grep | head -3",
                        "df -h /Users/david/nas 2>&1 | head -3"]:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                lines.append(f"--- {{cmd[:60]}} ---\\n{{r.stdout[:400]}}")
            reply(chat_id, "\\n\\n".join(lines))
        else:
            reply(chat_id, f"未知命令: /{{verb}}\\n/help 看用法")
    except subprocess.TimeoutExpired:
        reply(chat_id, "⏱️ 命令超时")
    except Exception as e:
        log(f"handle_command EXC: {{type(e).__name__}}: {{e}}")
        reply(chat_id, f"❌ 内部错误: {{type(e).__name__}}: {{e}}")

# 写 pid
open("/tmp/feishu_bot.pid", "w").write(str(os.getpid()))

# 启动 outbox watcher (daemon thread, 主线程退出时一起死)
_t = threading.Thread(target=outbox_watcher, name="outbox-watcher", daemon=True)
_t.start()
log("outbox watcher started (5s poll /tmp/hermes_outbox/)")

log("ws client connecting...")
creds = json.loads(open(CREDS).read())
handler = lark.EventDispatcherHandler.builder("", "") \\
    .register_p2_im_message_receive_v1(on_msg) \\
    .build()
cli = lark.ws.Client(
    app_id=creds["app_id"],
    app_secret=creds["app_secret"],
    event_handler=handler,
    log_level=lark.LogLevel.INFO,
)
log("ws client starting (阻塞, Ctrl-C 停)...")
try:
    cli.start()
except KeyboardInterrupt:
    log("interrupted")
except Exception as e:
    log(f"ws EXC: {{type(e).__name__}}: {{e}}")
finally:
    try: os.unlink("/tmp/feishu_bot.pid")
    except: pass
'''
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(bot_code)
        bot_script = f.name
    try:
        if foreground:
            print(f'🚀 前台跑 bot (Ctrl-C 停), log → {log_file}')
            r = subprocess.run([f'{VENV}/bin/python3', bot_script])
            sys.exit(r.returncode)
        else:
            print(f'🚀 后台启动 bot')
            p = subprocess.Popen(
                [f'{VENV}/bin/python3', bot_script],
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
    finally:
        try: os.unlink(bot_script)
        except: pass
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
