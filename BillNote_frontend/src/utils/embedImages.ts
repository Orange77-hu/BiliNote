/**
 * 导出 Markdown 时把本地图片嵌入为 base64 data URI。
 *
 * 背景：笔记 markdown 里的图片引用存在两种错误形态：
 *  1. `/static/screenshots/x.jpg` —— 相对路径，无主机地址（地址不全）
 *  2. `D:\ToolBOX\BiliNote\static\screenshots\x.jpg` —— Windows 绝对路径且斜杠反了
 * 本模块统一解析两种形态，从后端取回图片字节转 data URI 内嵌，
 * 使导出的 md 自包含、可移植。取图失败时回退为完整的正斜杠 http URL。
 */

/** 从任意形态的本地图片引用提取 `/static/...` 相对部分；无法识别返回 null */
export function extractStaticPath(raw: string): string | null {
  if (!raw) return null
  // 统一斜杠并折叠连续分隔符：D:\\a\\\\b -> D:/a/b（反斜杠可能被 JSON 转义成两连）
  const norm = raw.replace(/\\/g, '/').replace(/\/{2,}/g, '/')
  const idx = norm.toLowerCase().indexOf('/static/')
  if (idx < 0) return null
  // 去掉查询串/锚点
  const path = norm.slice(idx)
  const cut = path.search(/[?#]/)
  return cut >= 0 ? path.slice(0, cut) : path
}

/** 该引用是否是本笔记后端托管的本地图（可被 embed 处理） */
function isLocalStaticRef(raw: string): boolean {
  if (raw.startsWith('data:')) return false
  if (raw.startsWith('#')) return false
  return extractStaticPath(raw) !== null
}

/** 收集 markdown 中所有图片引用（![](src) 与 <img src="...">） */
function collectImageRefs(md: string): string[] {
  const refs = new Set<string>()
  const mdRe = /!\[[^\]]*\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)/g
  const htmlRe = /<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["'][^>]*>/gi
  let m: RegExpExecArray | null
  while ((m = mdRe.exec(md)) !== null) refs.add(m[1])
  while ((m = htmlRe.exec(md)) !== null) refs.add(m[1])
  return [...refs]
}

/** 取图片字节并转 data URI；失败返回 null */
async function fetchDataUri(url: string): Promise<string | null> {
  try {
    // no-store：WebView 的 HTTP 缓存里可能存着旧的无 CORS 头响应，
    // 浏览器读缓存时发现缺 Access-Control-Allow-Origin 会直接 reject。
    const resp = await fetch(url, { cache: 'no-store' })
    if (!resp.ok) return null
    const blob = await resp.blob()
    if (!blob.size) return null
    return await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(blob)
    })
  } catch {
    return null
  }
}

/**
 * 把 markdown 中的本地图引用替换为 base64 data URI。
 * @param md 源 markdown
 * @param baseURL 后端地址（如 http://127.0.0.1:8483，无尾斜杠）
 * @param onProgress (done, total) 导出进度回调
 * @returns 内嵌后的 markdown 与统计信息
 */
export async function embedImagesAsBase64(
  md: string,
  baseURL: string,
  onProgress?: (done: number, total: number) => void
): Promise<{ content: string; embedded: number; fallback: number; skipped: number }> {
  const refs = collectImageRefs(md)
  const targets = refs.filter(r => isLocalStaticRef(r))
  const skipped = refs.length - targets.length

  const resolved = new Map<string, string>()
  let embedded = 0
  let fallback = 0
  let done = 0

  // 小并发（6 路）取图，避免一次性压满后端
  const CONCURRENCY = 6
  let cursor = 0
  async function worker() {
    while (cursor < targets.length) {
      const i = cursor++
      const ref = targets[i]
      const staticPath = extractStaticPath(ref)!
      const url = baseURL + staticPath
      const dataUri = await fetchDataUri(url)
      if (dataUri) {
        resolved.set(ref, dataUri)
        embedded++
      } else {
        // 取图失败：回退成完整正斜杠 http URL（地址全 + 斜杠正）
        resolved.set(ref, url)
        fallback++
      }
      done++
      onProgress?.(done, targets.length)
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, targets.length) }, () => worker())
  )

  let content = md
  for (const [ref, replacement] of resolved) {
    // 引用里可能含反斜杠/特殊字符，用 split-join 做字面替换
    content = content.split(ref).join(replacement)
  }

  return { content, embedded, fallback, skipped }
}
