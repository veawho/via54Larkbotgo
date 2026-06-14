import { defineConfig } from 'vitepress'
import { readFileSync } from 'node:fs'
import { generateSidebar } from 'vitepress-sidebar'
import { RssPlugin } from 'vitepress-plugin-rss'

// ----------------------------------------------------------------------------
// Helpers: read the inline SW registrar at build time.
// This file lives at docs/.vitepress/config.mts, so the SW registrar
// (docs/.vitepress/sw-registrar.js) is at ./sw-registrar.js (one level).
// ----------------------------------------------------------------------------
const SW_REGISTRAR = readFileSync(
  new URL('./sw-registrar.js', import.meta.url),
  'utf8',
)

// ----------------------------------------------------------------------------
// JSON-LD: WebSite schema describing the via54Larkbotgo site.
// Schema.org / Google Rich Results understand this for indexing.
// ----------------------------------------------------------------------------
const JSON_LD_SOFTWARE = JSON.stringify({
  '@context': 'https://schema.org',
  '@type': 'WebSite',
  name: 'via54Larkbotgo',
  alternateName: 'via54 Lark bot Go',
  url: 'https://veawho.github.io/via54Larkbotgo/',
  description:
    'Feishu/Lark bot cross-OS integration for AI agents and AI tools (Hermes, OpenClaw, Codex, AI-IDE tools, Antigravity, Claude, Qclaw, minimax-code).',
  inLanguage: ['zh-CN', 'en-US'],
  author: {
    '@type': 'Person',
    name: 'veawho',
    url: 'https://github.com/veawho',
  },
  potentialAction: {
    '@type': 'SearchAction',
    target: {
      '@type': 'EntryPoint',
      urlTemplate: 'https://veawho.github.io/via54Larkbotgo/{search_term_string}',
    },
    'query-input': 'required name=search_term_string',
  },
})

// Per repository definition (主人原话):
//  "在不同系统(macOS/Windows/linux)中,让 aiagent 和 AI 工具等(包括但不
//   限于 hermes、openclaw、codex、AI-IDE 工具、antigravity、claude、Qclaw、
//   minimax-code 等等)可以更好地接入飞书 bot/Lark bot,需要集成 bot 的
//   私聊/群聊/飞书文档等全能力的权限开通说明、长连接和 webhook 两种
//   连接方式的说明等等"
//
// This site documents 6 capability segments per definition:
//   1. Feishu/Lark bot permission scopes (per OS)
//   2. WebSocket (long-connection) vs Webhook (per OS, per AI tool)
//   3. Multi-OS install: macOS / Windows / Linux
//   4. AI tool integration matrix
//   5. inbox/outbox IPC protocol (cross-language contract)
//   6. End-to-end integration example (Hermes inbox_watcher.py)

const base = '/via54Larkbotgo/' // GitHub Pages project URL
// For local dev: `npm run docs:dev` then http://localhost:5173/via54Larkbotgo/

// ----------------------------------------------------------------------------
// Sidebar auto-generation via vitepress-sidebar (v1.36+).
// One sidebar per locale (zh/en), each scanning docs/<locale>/{guides,reference,protocol}/.
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
  description: '飞书/Lark bot 跨 OS 集成 + 多 AI 工具接入 — Hermes / OpenClaw / Codex / Claude',
  lang: 'zh-CN',
  lastUpdated: true,
  cleanUrls: true,
  base,

  // Sitemap (VitePress 1.x built-in): generates dist/sitemap.xml at build
  // time. host=GitHub Pages URL with the repo path included.
  sitemap: {
    hostname: 'https://veawho.github.io/via54Larkbotgo/',
  },

  ignoreDeadLinks: true,

  // ------------------------------------------------------------------------
  // head: extra HTML injected into every page's <head>.
  // 1. Open Graph + Twitter Card meta — link previews
  // 2. Web App Manifest — PWA installability
  // 3. JSON-LD — Google Rich Results
  // 4. Service worker registrar — inlined, registers /via54Larkbotgo/sw.js
  // ------------------------------------------------------------------------
  head: [
    // Open Graph
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:site_name', content: 'via54Larkbotgo' }],
    ['meta', { property: 'og:title', content: 'via54Larkbotgo' }],
    ['meta', {
      property: 'og:description',
      content: 'Feishu/Lark bot cross-OS integration for AI agents and AI tools',
    }],
    ['meta', {
      property: 'og:image',
      content: 'https://veawho.github.io/via54Larkbotgo/og-image.png',
    }],
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],
    ['meta', { property: 'og:locale', content: 'zh_CN' }],
    ['meta', { property: 'og:locale:alternate', content: 'en_US' }],
    ['meta', { property: 'og:url', content: 'https://veawho.github.io/via54Larkbotgo/' }],

    // Twitter Card
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title', content: 'via54Larkbotgo' }],
    ['meta', {
      name: 'twitter:description',
      content: 'Feishu/Lark bot cross-OS integration for AI agents and AI tools',
    }],
    ['meta', {
      name: 'twitter:image',
      content: 'https://veawho.github.io/via54Larkbotgo/og-image.png',
    }],
    ['meta', { name: 'twitter:creator', content: '@veawho' }],

    // Web App Manifest
    ['link', { rel: 'manifest', href: '/via54Larkbotgo/manifest.webmanifest' }],
    ['meta', { name: 'theme-color', content: '#3b82f6' }],
    ['meta', { name: 'apple-mobile-web-app-capable', content: 'yes' }],
    ['meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' }],
    ['meta', { name: 'apple-mobile-web-app-title', content: 'via54Larkbotgo' }],

    // JSON-LD
    ['script', { type: 'application/ld+json' }, JSON_LD_SOFTWARE],

    // Service worker registrar
    ['script', {}, SW_REGISTRAR],
  ],

  locales: {
    'zh-CN': {
      label: '中文',
      lang: 'zh-CN',
      themeConfig: {
        nav: [
          { text: '首页', link: '/zh/' },
          { text: 'Skills', link: '/zh/skills/via54feishu' },
          { text: 'English', link: '/en/' },
        ],
        sidebar: {
          '/zh/': zhSidebar,
          '/zh/skills/': zhSidebar,
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
          { text: 'Skills', link: '/en/skills/via54feishu' },
          { text: '中文', link: '/zh/' },
        ],
        sidebar: {
          '/en/': enSidebar,
          '/en/skills/': enSidebar,
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

  // vite-plugin: RSS feed generator (sitemap.xml is handled by the
  // VitePress-built-in sitemap config above).
  vite: {
    plugins: [
      RssPlugin({
        title: 'via54Larkbotgo',
        baseUrl: 'https://veawho.github.io',
        copyright: 'Copyright (c) 2026 veawho',
      }),
    ],
  },
})