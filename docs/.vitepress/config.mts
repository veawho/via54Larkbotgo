import { defineConfig } from 'vitepress'
import { generateSidebar } from 'vitepress-sidebar'

// Per repository definition (主人原话):
// "在不同系统(macOS/Windows/Linux)中,让 aiagent 和 AI 工具等可以更好地
//  接入飞书 bot/Lark bot,需要集成 bot 的私聊/群聊/飞书文档等全能力的
//  权限开通说明、长连接和 webhook 两种连接方式的说明等等"
//
// This site documents:
//   1. Feishu/Lark bot permission scopes (per OS)
//   2. WebSocket (long-connection) vs Webhook (per OS, per AI tool)
//   3. Multi-OS install: macOS / Windows / Linux
//   4. AI tool integration matrix: Hermes, OpenClaw, Codex, Claude,
//      Qclaw, antigravity, minimax-code, AI-IDE tools
//   5. inbox/outbox IPC protocol (cross-language contract)
//   6. End-to-end integration example (Hermes inbox_watcher.py)

const base = '/via54Larkbotgo/' // GitHub Pages project URL
// For local dev: `npm run docs:dev` then http://localhost:5173/via54Larkbotgo/
// (VitePress respects base in dev too — URLs look like /via54Larkbotgo/zh/)

// ----------------------------------------------------------------------------
// Sidebar auto-generation: scan docs/{zh,en}/guides/*.md and docs/{zh,en}/
// reference/*.md and docs/{zh,en}/protocol/*.md. When you add a new .md
// file, sidebar updates on next build — no config edit needed.
// ----------------------------------------------------------------------------

function buildLocaleSidebar(opts: {
  scanPath: string
  basePath: string
  homeText: string
  homeGroup: string
}) {
  const items = generateSidebar({
    documentRootPath: '/docs',
    scanStartPath: opts.scanPath,
    resolvePath: opts.scanPath,
    basePath: opts.basePath,
    rootGroupText: '指南', // 'Guides' for en
    capitalizeFirst: false,
    hyphenToSpace: false,
    underscoreToSpace: false,
    sortMenusByName: true,
    collapsed: false,
  }) as Array<Record<string, any>>

  return [
    {
      text: opts.homeGroup,
      items: [{ text: opts.homeText, link: opts.basePath }],
    },
    ...items,
  ]
}

const zhSidebar = buildLocaleSidebar({
  scanPath: 'zh',
  basePath: '/zh/',
  homeText: '首页',
  homeGroup: '开始',
})

const enSidebar = buildLocaleSidebar({
  scanPath: 'en',
  basePath: '/en/',
  homeText: 'Home',
  homeGroup: 'Get started',
})

export default defineConfig({
  title: 'via54Larkbotgo',
  description: '飞书/Lark bot 跨 OS 集成 (macOS/Windows/Linux), 支持 AI agent (Hermes/OpenClaw/Codex/Claude 等)',
  lang: 'zh-CN',
  lastUpdated: true,
  cleanUrls: true,
  base,

  // VitePress dead-link check: README.md / UPGRADE.md filenames are
  // mentioned as string literals in code examples; turn off to avoid
  // false positives.
  ignoreDeadLinks: true,

  locales: {
    'zh-CN': {
      label: '中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [
          { text: '首页', link: '/zh/' },
          { text: 'English', link: '/en/' },
        ],
        sidebar: {
          '/zh/': zhSidebar,
          '/zh/guides/': zhSidebar,
          '/zh/reference/': zhSidebar,
          '/zh/protocol/': zhSidebar,
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/veawho/via54Larkbotgo' },
        ],
        search: { provider: 'local' },
      },
    },
    'en': {
      label: 'English',
      lang: 'en-US',
      themeConfig: {
        nav: [
          { text: 'Home', link: '/en/' },
          { text: '中文', link: '/zh/' },
        ],
        sidebar: {
          '/en/': enSidebar,
          '/en/guides/': enSidebar,
          '/en/reference/': enSidebar,
          '/en/protocol/': enSidebar,
        },
        socialLinks: [
          { icon: 'github', link: 'https://github.com/veawho/via54Larkbotgo' },
        ],
        search: { provider: 'local' },
      },
    },
  },
})