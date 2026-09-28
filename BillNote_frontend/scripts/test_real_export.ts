// 用用户真实导出文件验证
import { embedImagesAsBase64 } from '../src/utils/embedImages.ts'
import { readFileSync, writeFileSync } from 'node:fs'

if (typeof (globalThis as any).FileReader === 'undefined') {
  ;(globalThis as any).FileReader = class {
    onload: any; onerror: any; result: any
    readAsDataURL(blob: Blob) {
      blob.arrayBuffer().then(buf => {
        this.result = `data:${blob.type || 'application/octet-stream'};base64,${Buffer.from(buf).toString('base64')}`
        this.onload && this.onload()
      }).catch((e: any) => this.onerror && this.onerror(e))
    }
  }
}

const f = process.argv[2]
const md = readFileSync(f, 'utf-8')
const before = (md.match(/!\[[^\]]*\]\([^)]*\)/g) || []).length
const res = await embedImagesAsBase64(md, 'http://127.0.0.1:8483')
const after = (res.content.match(/!\[[^\]]*\]\([^)]*\)/g) || []).length
const dataUris = (res.content.match(/!\[[^\]]*\]\(data:image/g) || []).length
const dosLeft = (res.content.match(/!\[[^\]]*\]\(D:/g) || []).length
const relLeft = (res.content.match(/!\[[^\]]*\]\(\/static\//g) || []).length
console.log(JSON.stringify({ before, after, dataUris, dosLeft, relLeft, ...{embedded: res.embedded, fallback: res.fallback, skipped: res.skipped} }, null, 1))
writeFileSync(process.argv[3], res.content)
console.log('md size:', md.length, '->', res.content.length, `(+${((res.content.length-md.length)/1024).toFixed(0)}KB)`)
