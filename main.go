// feishu-bot-go — 飞书 WS 长连接 bot (Go skeleton)
//
// 替代 /Users/david/.hermes/scripts/feishu_bot_daemon.py (851 行 Python).
//
// 使用 larksuite/oapi-sdk-go/v3@v3.9.5 的高层 channel 模式:
//   - WS 长连接 (larkws.NewClient)
//   - Channel 封装 (消息归一化、去重、bot identity 缓存)
//   - OnMessage 接 NormalizedMessage
//   - 写 /tmp/hermes_inbox/<msg_id>.json (inbox_watcher.py 消费)
//   - outbox watcher 轮询 /tmp/hermes_outbox → ch.Send → 飞书
//
// 启动: ./feishu-bot-go --app-id cli_xxx --app-secret yyy
//
// TODO (留给后续 PR,skeleton 不实现):
//   - name cache (/tmp/feishu_user_name_cache.json)
//   - @bot 过滤 / 群聊白名单
//   - vision 跨 venv subprocess fallback
//   - heartbeat 进度报告
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"time"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	larkchannel "github.com/larksuite/oapi-sdk-go/v3/channel"
	larktypes "github.com/larksuite/oapi-sdk-go/v3/channel/types"
	larkcore "github.com/larksuite/oapi-sdk-go/v3/core"
	larkws "github.com/larksuite/oapi-sdk-go/v3/ws"
)

// 业务路径(必须和 inbox_watcher.py 严格一致)
const (
	InboxDir    = "/tmp/hermes_inbox"
	OutboxDir   = "/tmp/hermes_outbox"
	OutboxDone  = "/tmp/hermes_outbox/.done"
	PidFilePath = "/tmp/feishu_bot.pid"
)

// InboxMessage 写到 /tmp/hermes_inbox/<msg_id>.json 的格式。
// 字段名/顺序必须和 Python daemon 的 _write_inbox() 一致:
// inbox_watcher.py 的 _read_json() 直接读这些字段。
type InboxMessage struct {
	MsgID        string  `json:"msg_id"`
	ChatID       string  `json:"chat_id"`
	SenderOpenID string  `json:"sender_open_id"`
	SenderName   string  `json:"sender_name"`
	Text         string  `json:"text"`
	ReceivedAt   float64 `json:"received_at"`
}

// writeInbox 原子写(临时文件 + rename)。
// 避免 inbox_watcher 读到半截 JSON 触发解析失败。
func writeInbox(msg *InboxMessage) error {
	if err := os.MkdirAll(InboxDir, 0755); err != nil {
		return fmt.Errorf("mkdir inbox: %w", err)
	}
	safeID := sanitizeFilename(msg.MsgID)
	if safeID == "" {
		safeID = fmt.Sprintf("auto_%d", time.Now().UnixNano())
	}
	dst := filepath.Join(InboxDir, safeID+".json")
	tmp := dst + ".tmp"

	data, err := json.MarshalIndent(msg, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return fmt.Errorf("write tmp: %w", err)
	}
	return os.Rename(tmp, dst)
}

// sanitize 飞书 message_id → 合法文件名(只保留 [A-Za-z0-9_-])
func sanitizeFilename(s string) string {
	out := make([]rune, 0, len(s))
	for _, r := range s {
		switch {
		case r >= 'A' && r <= 'Z', r >= 'a' && r <= 'z', r >= '0' && r <= '9', r == '_', r == '-':
			out = append(out, r)
		default:
			out = append(out, '_')
		}
	}
	return string(out)
}

// runOutboxWatcher 轮询 /tmp/hermes_outbox/*.json → ch.Send → mv 到 .done/
func runOutboxWatcher(ctx context.Context, ch larktypes.Channel) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			files, err := filepath.Glob(filepath.Join(OutboxDir, "*.json"))
			if err != nil {
				log.Printf("outbox glob: %v", err)
				continue
			}
			for _, f := range files {
				if err := processOutboxFile(ctx, ch, f); err != nil {
					log.Printf("process outbox %s: %v", f, err)
					continue
				}
				os.MkdirAll(OutboxDone, 0755)
				if err := os.Rename(f, filepath.Join(OutboxDone, filepath.Base(f))); err != nil {
					log.Printf("rename to .done: %v", err)
				}
			}
		}
	}
}

// OutboxReply 是 inbox_watcher 处理完后写回的格式
// (详见 inbox_watcher.py 的 process_file 函数返回结构)
type OutboxReply struct {
	MsgID  string `json:"msg_id"`
	ChatID string `json:"chat_id"`
	Reply  string `json:"reply"`
}

func processOutboxFile(ctx context.Context, ch larktypes.Channel, path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var reply OutboxReply
	if err := json.Unmarshal(data, &reply); err != nil {
		return fmt.Errorf("unmarshal: %w", err)
	}
	if reply.Reply == "" {
		log.Printf("outbox %s: empty reply, skip", path)
		return nil
	}
	// Channel.Send 通过 Channel 高层 API 发文本
	if _, err := ch.Send(ctx, &larktypes.SendInput{
		ReceiveID: reply.ChatID,
		MsgType:   "text",
		Text:      reply.Reply,
	}); err != nil {
		return fmt.Errorf("send: %w", err)
	}
	log.Printf("✓ replied to %s (msg_id=%s, %d bytes)", reply.ChatID, reply.MsgID, len(reply.Reply))
	return nil
}

func main() {
	var (
		appID     = flag.String("app-id", "", "Feishu app_id (or FEISHU_APP_ID env)")
		appSecret = flag.String("app-secret", "", "Feishu app_secret (or FEISHU_APP_SECRET env)")
		verbose   = flag.Bool("v", false, "verbose logging")
	)
	flag.Parse()

	if *appID == "" {
		*appID = os.Getenv("FEISHU_APP_ID")
	}
	if *appSecret == "" {
		*appSecret = os.Getenv("FEISHU_APP_SECRET")
	}
	if *appID == "" || *appSecret == "" {
		log.Fatal("must provide --app-id + --app-secret (or FEISHU_APP_ID/FEISHU_APP_SECRET env)")
	}

	// 写 pid file (与 Python daemon 兼容)
	if err := os.WriteFile(PidFilePath, []byte(fmt.Sprintf("%d", os.Getpid())), 0644); err != nil {
		log.Printf("warn: write pid file: %v", err)
	}
	defer os.Remove(PidFilePath)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 1. REST client (发消息用)
	restClient := lark.NewClient(*appID, *appSecret)

	// 2. WS 长连接
	wsClient := larkws.NewClient(*appID, *appSecret,
		larkws.WithLogLevel(larkcore.LogLevelInfo),
	)

	// 3. Channel 高层封装 (消息归一化、去重、bot identity 缓存)
	ch := larkchannel.NewChannel(restClient, wsClient)

	// 4. 收消息 handler
	ch.OnMessage(func(ctx context.Context, msg *larktypes.NormalizedMessage) error {
		if *verbose {
			log.Printf("recv: msg_id=%s chat=%s chat_type=%s text=%q",
				msg.MessageID, msg.ChatID, msg.ChatType, truncate(msg.Content, 80))
		}
		// 只处理文本消息(text 类型 → raw_content_type "text")
		if msg.RawContentType != "text" {
			log.Printf("skip non-text: %s", msg.RawContentType)
			return nil
		}
		// 写 inbox
		inboxMsg := &InboxMessage{
			MsgID:        msg.MessageID,
			ChatID:       msg.ChatID,
			SenderOpenID: msg.UserID,
			SenderName:   "", // TODO: name cache
			Text:         msg.Content,
			ReceivedAt:   float64(time.Now().Unix()),
		}
		if err := writeInbox(inboxMsg); err != nil {
			log.Printf("writeInbox: %v", err)
			return err
		}
		log.Printf("✓ inbox: msg_id=%s chat_id=%s text=%q",
			inboxMsg.MsgID, inboxMsg.ChatID, truncate(inboxMsg.Text, 60))
		return nil
	})

	// 5. 生命周期 hook
	ch.OnReady(func() {
		log.Printf("✓ ws connected to feishu, app_id=%s...", truncate(*appID, 12))
	})
	ch.OnError(func(err error) {
		log.Printf("✗ ws error: %v", err)
	})

	// 6. outbox watcher 后台跑
	go runOutboxWatcher(ctx, ch)

	// 7. 启动 WS (阻塞)
	log.Printf("feishu-bot-go starting, app_id=%s...", truncate(*appID, 12))
	if err := ch.Start(ctx); err != nil {
		log.Fatalf("channel start: %v", err)
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}