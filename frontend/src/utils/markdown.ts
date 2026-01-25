import { marked } from "marked"
import hljs from "highlight.js"

// Custom renderer for enhanced markdown
const renderer = {
  // Code blocks with syntax highlighting
  code(code: string, language: string | undefined): string {
    const lang = language || ""
    const escapedCode = code.replace(/</g, "&lt;").replace(/>/g, "&gt;")
    const copyButton = `<button class="code-copy-btn" data-code="${encodeURIComponent(code)}" title="Copy code"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg><span class="copy-label">Copy</span></button>`

    // Handle mermaid diagrams
    if (lang === "mermaid") {
      return `<div class="mermaid-container"><pre class="mermaid">${code}</pre></div>`
    }

    // Syntax highlighting for code blocks
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
        return `<div class="code-block-wrapper"><pre class="code-block" data-lang="${lang}"><code class="hljs language-${lang}">${highlighted}</code></pre>${copyButton}</div>`
      } catch {
        // Fall through to default
      }
    }

    // Auto-detect language or plain text
    try {
      const result = hljs.highlightAuto(code)
      const detectedLang = result.language || "plaintext"
      return `<div class="code-block-wrapper"><pre class="code-block" data-lang="${detectedLang}"><code class="hljs language-${detectedLang}">${result.value}</code></pre>${copyButton}</div>`
    } catch {
      return `<div class="code-block-wrapper"><pre class="code-block"><code>${escapedCode}</code></pre>${copyButton}</div>`
    }
  },

  // Inline code
  codespan(text: string): string {
    return `<code class="inline-code">${text}</code>`
  },

  // Images with lazy loading and figure wrapper
  image(href: string, title: string | null | undefined, text: string): string {
    const titleAttr = title ? ` title="${title}"` : ""
    const caption = text ? `<figcaption>${text}</figcaption>` : ""
    return `<figure class="md-image"><img src="${href}" alt="${text || ""}" loading="lazy"${titleAttr} />${caption}</figure>`
  },

  // Links with external detection
  link(href: string, title: string | null | undefined, text: string): string {
    const titleAttr = title ? ` title="${title}"` : ""

    // Check if external link (different origin or starts with http)
    const isExternal =
      href.startsWith("http://") ||
      href.startsWith("https://") ||
      href.startsWith("//")

    if (isExternal) {
      return `<a href="${href}" class="external-link" target="_blank" rel="noopener noreferrer"${titleAttr}>${text}<svg class="external-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a>`
    }

    return `<a href="${href}"${titleAttr}>${text}</a>`
  },

  // Tables with wrapper for horizontal scroll
  table(header: string, body: string): string {
    return `<div class="table-wrapper"><table><thead>${header}</thead><tbody>${body}</tbody></table></div>`
  },
}

marked.setOptions({
  gfm: true,
  breaks: true,
})

marked.use({ renderer })

export function renderMarkdown(text: string): string {
  return marked.parse(text ?? "") as string
}

// Initialize mermaid diagrams after content is rendered
export async function initMermaid() {
  const mermaid = await import("mermaid")
  mermaid.default.initialize({
    startOnLoad: false,
    theme: "neutral",
    securityLevel: "loose",
    fontFamily: "var(--font-sans)",
  })
  return mermaid.default
}

export async function renderMermaidDiagrams(container: HTMLElement) {
  const mermaidElements = container.querySelectorAll<HTMLPreElement>("pre.mermaid")
  if (mermaidElements.length === 0) return

  const mermaid = await initMermaid()

  for (const el of mermaidElements) {
    const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    try {
      const { svg } = await mermaid.render(id, el.textContent || "")
      const wrapper = el.closest(".mermaid-container")
      if (wrapper) {
        wrapper.innerHTML = svg
        wrapper.classList.add("mermaid-rendered")
      }
    } catch (e) {
      console.warn("Mermaid render error:", e)
      el.classList.add("mermaid-error")
    }
  }
}
