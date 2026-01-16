/**
 * @param text 原始文本
 * @param terms 需要高亮的关键词数组 (通常是 scope)
 * @returns 包含 HTML <mark> 标签的字符串
 */
export function highlightTerms(text: string, terms: string[]): string {
  if (!terms || terms.length === 0 || !text) return text
  
  const validTerms = terms
    .filter(t => t.trim().length > 0)
    .map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    
  if (validTerms.length === 0) return text
  const regex = new RegExp(`(${validTerms.join("|")})`, "gi")
  return text.replace(regex, '<mark style="background-color: #f3c969; color: #0f2a1d; padding: 0 2px; border-radius: 2px;">$1</mark>')
}

export function getFileName(path: string): string {
  if (!path) return ""
  const normalized = path.replace(/\\/g, "/")
  const parts = normalized.split("/")
  return parts[parts.length - 1] || path
}
