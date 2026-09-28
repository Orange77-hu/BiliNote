// 验证 embedImages：路径解析 + 对真实后端取图内嵌
// Node 24 原生跑 TS（type stripping）
import { embedImagesAsBase64, extractStaticPath } from '../src/utils/embedImages.ts'

// --- 1. extractStaticPath 两种 bug 形态 + 正常形态 ---
const cases: [string, string | null][] = [
  ['/static/screenshots/a.jpg', '/static/screenshots/a.jpg'],
  ['D:\\ToolBOX\\BiliNote\\static\\screenshots\\b.jpg', '/static/screenshots/b.jpg'],
  ['D:\\\\ToolBOX\\\\BiliNote\\\\static\\\\screenshots\\\\c.jpg', '/static/screenshots/c.jpg'],
  ['D:/ToolBOX/BiliNote/static/screenshots/d.jpg', '/static/screenshots/d.jpg'],
  ['http://127.0.0.1:8483/static/screenshots/e.jpg', '/static/screenshots/e.jpg'],
  ['/static/screenshots/f.jpg?x=1', '/static/screenshots/f.jpg'],
  ['data:image/png;base64,xxx', null],
  ['https://i0.hdslb.com/g.jpg', null],
  ['', null],
]
let fail = 0
for (const [input, want] of cases) {
  const got = extractStaticPath(input)
  const ok = got === want
  if (!ok) fail++
  console.log(`${ok ? 'PASS' : 'FAIL'} extract(${JSON.stringify(input)}) = ${JSON.stringify(got)} want ${JSON.stringify(want)}`)
}

// --- 2. 对真实后端端到端内嵌 ---
const md = [
  '# 测试笔记',
  '',
  '![](D:\\ToolBOX\\BiliNote\\static\\screenshots\\screenshot_000_44a03650-6560-4697-914c-0da72a01fbd6.jpg)',
  '',
  '![](/static/screenshots/screenshot_001_1f5fa909-12fc-4821-bc96-8de969ed4640.jpg)',
  '',
  '![远程图](https://i0.hdslb.com/cover.jpg)',
].join('\n')

// FileReader polyfill（Node 没有）
if (typeof (globalThis as any).FileReader === 'undefined') {
  ;(globalThis as any).FileReader = class {
    onload: any; onerror: any; result: any
    readAsDataURL(blob: Blob) {
      blob.arrayBuffer().then(buf => {
        const b64 = Buffer.from(buf).toString('base64')
        this.result = `data:${blob.type || 'application/octet-stream'};base64,${b64}`
        this.onload && this.onload()
      }).catch((e: any) => this.onerror && this.onerror(e))
    }
  }
}

const res = await embedImagesAsBase64(md, 'http://127.0.0.1:8483', (d, t) => process.stdout.write(`\rprogress ${d}/${t}`))
console.log('\nstats:', res)
const okEmbedded = res.embedded === 2 && res.skipped === 1 && res.fallback === 0
if (!okEmbedded) fail++
const hasData1 = res.content.includes('data:image/jpeg;base64,')
const noDosPath = !res.content.includes('D:\\ToolBOX')
const remoteKept = res.content.includes('https://i0.hdslb.com/cover.jpg')
console.log(`${hasData1 ? 'PASS' : 'FAIL'} base64 内嵌存在`)
console.log(`${noDosPath ? 'PASS' : 'FAIL'} 反斜杠路径已消失`)
console.log(`${remoteKept ? 'PASS' : 'FAIL'} 远程图保留原样`)
if (!hasData1 || !noDosPath || !remoteKept) fail++
console.log(fail === 0 ? '\nALL PASS' : `\n${fail} FAILURES`)
process.exit(fail === 0 ? 0 : 1)
