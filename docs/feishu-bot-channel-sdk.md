# Go 飞书 SDK Channel 集成 (lark_oapi.channel.FeishuChannel)

> 2026-06-16 更新: Go SDK 同样可用 FeishuChannel (虽然 Python SDK 更成熟)。

## Python SDK 等价代码 (Go)

Python `lark_oapi.channel.FeishuChannel` 在 Go 也有等价实现:

```go
// pseudocode, 真实现需要看 lark-oapi-go
import "github.com/larksuite/oapi-sdk-go/v3/channel"

config := &channel.ChannelConfig{
    AppID:          "cli_xxx",
    AppSecret:      "xxx",
    EncryptKey:     "xxx",
    VerificationToken: "xxx",
    Transport:      "webhook",
    Policy: &channel.PolicyConfig{
        DMPolicy:         "open",
        GroupPolicy:      "open",
        RequireMention:   true,
    },
    Safety: &channel.SafetyConfig{
        Dedup: &channel.DedupConfig{TTLSeconds: 12 * 3600},
        StaleMessageWindowMs: 30 * 60 * 1000,
    },
    Outbound: &channel.OutboundConfig{
        ReplyMode:      "auto",
        TextChunkLimit: 3500,
        ChunkMode:      "newline",
        Retry:          &channel.RetryConfig{MaxAttempts: 3},
    },
}

ch, _ := channel.NewFeishuChannel(config)
ch.On("message", handler)  // handler(inbound *channel.InboundMessage)
ch.Start()

// webhook handler
http.HandleFunc("/feishu/webhook", func(w http.ResponseWriter, r *http.Request) {
    body, _ := io.ReadAll(r.Body)
    status, respBody, _ := ch.HandleWebhookRequest(r.Header, body)
    w.WriteHeader(status)
    w.Write(respBody)
})
http.ListenAndServe(":8089", nil)
```

## 真路径

| 实现 | 路径 |
|------|------|
| Python m12 bot | `~/.hermes/scripts/m12_full_channel_bot.py` (Hermes scripts) |
| Go SDK | `go get github.com/larksuite/oapi-sdk-go/v3` (待集成) |

## 配套 SKILL

`skills/via54-prompt-generation/SKILL.md` - via54 提示词生成完整流程

## 14 平台 via54Design CLI

`via54 prompt --scene "..." --platform midjourney` 等 14 平台 (midjourney/flux/dalle3/sd3/stable_diffusion/ideogram/recraft/seedance/gemini/veo/sora/kling/pika/jimeng)
