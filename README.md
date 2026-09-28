<div style="display: flex; justify-content: center; align-items: center; gap: 10px;
">
    <p align="center">
  <img src="./doc/icon.svg" alt="BiliNote Banner" width="50" height="50"  />
</p>
<h1 align="center" > BiliNote v2.4.6</h1>
</div>

<p align="center"><i>AI 视频笔记生成工具 让 AI 为你的视频做笔记</i></p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" />
  <img src="https://img.shields.io/badge/frontend-react%2019-blue" />
  <img src="https://img.shields.io/badge/backend-fastapi-green" />
  <img src="https://img.shields.io/badge/AI-hermes%20%7C%20xiaomi%20mimo-ff69b4" />
  <img src="https://img.shields.io/github/stars/Orange77-hu/BiliNote?style=social" />
</p>

## ✨ 项目简介

BiliNote 是一个开源的 AI 视频笔记助手，支持通过哔哩哔哩、YouTube、抖音等视频链接，自动提取内容并生成结构清晰、重点明确的 Markdown 格式笔记。支持插入截图、原片跳转、AI 问答、思维导图等功能。

**核心流程**：粘贴视频链接 → 下载并提取音频 → 语音转文字 → LLM 生成结构化笔记 → Markdown 预览 / 思维导图 / AI 问答。

**技术栈**：FastAPI 后端 + React 19 前端 + Tauri 桌面打包。完整功能文档见[上游文档](https://docs.bilinote.app/)，Windows 桌面安装包见 [Releases](https://github.com/Orange77-hu/BiliNote/releases)。

## 📌 我的改动

本仓库在上游基础上做了一处功能增强和一组配套修复，已随 **v2.4.6** 发布：

### 新增

- **导出 Markdown 时图片内嵌进文件**（base64）
  - 此前导出只写图片的本地引用地址，文件拷走、换台设备打开，图片全部丢失
  - 现在导出时把笔记引用的每张截图取回，以 `data:image/...;base64` 形式直接写进 md
  - 生成的单文件笔记自包含：复制到任何位置、任何设备打开，图片都不丢
  - 个别取图失败时自动回退为完整的 `/static/...` 引用，不丢整篇笔记

### 修复

- **图片地址不完整**：预览页存的是 `/static/screenshots/...` 相对路径，导出后脱离服务端就无从解析 → 导出时统一解析为完整地址，或直接内嵌
- **路径分隔符反了**：Windows 绝对路径 `D:\...` 形态混进 md，多数渲染器无法识别 → 统一使用正斜杠
- **预览截图不显示**：预览组件只认 `/` 开头的路径，Windows 绝对路径形态被漏掉导致裂图 → 预览同样走统一的路径解析

### 涉及文件

| 文件 | 作用 |
|---|---|
| `BillNote_frontend/src/utils/embedImages.ts` | 路径识别（相对路径 / Windows 绝对路径）+ 取图转 base64 核心逻辑 |
| `BillNote_frontend/src/pages/HomePage/components/MarkdownViewer.tsx` | 导出前执行图片内嵌（带进度提示）、预览图路径修复 |

## 📥 下载

Windows 桌面版：**[Releases · v2.4.6](https://github.com/Orange77-hu/BiliNote/releases/tag/v2.4.6)**

- `BiliNote_2.4.6_x64-setup.exe`（NSIS 安装包）
- `BiliNote_2.4.6_x64_en-US.msi`（MSI 安装包）

> ⚠️ 运行路径中不能有中文（上游已知限制）。

## 🙏 致谢

功能与架构基于上游开源项目 [JefferyHcool/BiliNote](https://github.com/JefferyHcool/BiliNote)，在此致谢。

## 📜 License

MIT License
