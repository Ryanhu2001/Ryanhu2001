---
title: "Office-Agent：PPTX、XLSX、DOCX、PDF 的实现路径"
public: true
description: "按 skill、CLI、Office engine 与 QA 链路拆解主流 Agent 如何读写四类 Office 文件。"
type: agent-harness
date: 2026-08-19
reading_surface: true
kicker: "OFFICE AGENT · SKILL / BACKEND / QA"
---

# Office-Agent

## 0. 组件

### 0.1 四种文件常见的 backend

| 格式 | 新建 | 已有文件编辑 | 读取 / QA |
| --- | --- | --- | --- |
| PPTX | `PptxGenJS`、`python-pptx`、`@oai/artifact-tool`、自研 engine | raw OOXML、`python-pptx`、native slide state | XML/package validator、LibreOffice、缩略图/PNG、视觉 QA |
| XLSX | `openpyxl`、`pandas`、`rust_xlsxwriter`、`@oai/artifact-tool`、自研 engine | OOXML、Excel/云端 workbook API | 公式重算、`inspect`、错误扫描、渲染 |
| DOCX | `docx-js`、`python-docx`、OpenXML SDK | `lxml`/raw OOXML、native block tree | LibreOffice → PDF/PNG、结构审计 |
| PDF | ReportLab、`md2pdf`（MDX → React SSR → Chromium）、HTML + Paged.js、`pdf-lib` | `pypdf`、`pikepdf`、`qpdf`、`pdf-lib` | 文本/结构：`pypdf`、`pdfplumber`、`pdf.js`；页面渲染：Poppler、PyMuPDF、`pdf.js` → PNG → VLM/OCR |

`pandas` 主要负责表格数据处理，不是完整的 XLSX serializer；LibreOffice 负责重算/渲染，Poppler 负责页面渲染，PyMuPDF 同时能抽取内容和 rasterize 页面。

### 0.2 成体系的 skill / CLI / MCP

- [Anthropic document-skills](https://github.com/anthropics/skills)：`pptx`、`xlsx`、`docx`、`pdf` 四个 skill。
- [OpenAI Work with files](https://learn.chatgpt.com/docs/artifacts-viewer)：Documents、Presentations、Spreadsheets、PDF artifact workflows；旧的 `openai/skills` 仓库已 deprecated。
- [Lark CLI](https://github.com/larksuite/cli)：[`lark-slides`](https://github.com/larksuite/cli/tree/main/skills/lark-slides)、[`lark-sheets`](https://github.com/larksuite/cli/tree/main/skills/lark-sheets)、[`lark-doc`](https://github.com/larksuite/cli/tree/main/skills/lark-doc)。
- [Kimi CLI Skills](https://moonshotai.github.io/kimi-cli/en/customization/skills.html)说明 CLI 的 Skill 机制；Kimi 第一方 `kimi-slides` / `xlsx`、辅助 Skills 与官方推荐的社区 PPT Skills 在 2.3 分开列出。
- [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI)：统一 `get/query/set/add/remove/batch/validate`，也可通过 `officecli mcp` 暴露 MCP。

## 1. 总览

### 1.1 一张表看完

| 产品 / harness                    | PPTX                                                                                               | XLSX                                                                                                                          | DOCX                               | PDF                                                                                                  |
| ------------------------------- | -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 豆包 / Super Doubao               | `lark-slides` → SML 2.0 → `lark-cli slides`                                                        | `lark-sheets` → Lark Sheets API                                                                                               | `lark-doc` → Lark Docs API         | 读入口：CDN URL → `curl -L` → local PDF；解析：`\`；生成入口：Python script；serializer：`\`                   |
| WorkBuddy                       | `PptxGenJS`、`python-pptx`、HTML → PPTX                                                              | `openpyxl` / `pandas`                                                                                                         | `python-docx`                      | 读：`pypdf`/`pdfplumber`/PyMuPDF；写：WeasyPrint/ReportLab                                                |
| Kimi Web / CLI                  | 第一方 `kimi-slides`：`.pptd` YAML DSL ↔ PPTX；`check` / `screenshot`                                   | 第一方 `xlsx`：`openpyxl` / `pandas` → formulas/styles → `recheck` / `reference-check` / `chart-verify` / `validate` → OpenXML 校验 | Kimi Web：无 DOCX Skill；不能生成可下载 `.docx` | Kimi Web 读：system `<document>` → XML-tagged content → context；写：`\`                                  |
| QwenWork                        | 读：MarkItDown / thumbnail / raw OOXML；新建：`python-pptx`；编辑：unpack/edit/pack；QA：LibreOffice + Poppler | `openpyxl` / `pandas` → formulas/styles → `recalc.py` → LibreOffice 重算与错误扫描                                                   | `\`                                | 读：`pdftotext` + `pdftoppm` → `media-read` / Qwen3-Omni；写：MDX → `md2pdf` → React SSR → Chromium → PDF |
| ChatGPT Work / artifact skills  | `@oai/artifact-tool` presentation object model                                                     | `@oai/artifact-tool` Workbook API                                                                                             | `python-docx` + OOXML helpers      | API 输入：抽 text + page images；本地 Skill：text extraction + Poppler render；写：ReportLab                    |
| Claude Code + `document-skills` | 新建 `PptxGenJS`；已有 deck raw OOXML                                                                   | `openpyxl` + `pandas` + LibreOffice 重算                                                                                        | 新建 `docx-js`；已有文档 raw OOXML        | API 输入：每页 text + image；Skill：`pypdf`/`pdfplumber` + Poppler；写：ReportLab                              |
| Manus                           | PowerPoint Mode → native `.pptx`                                                                   | `\`；Google Sheets → Workspace CLI                                                                                             | 本地：`\`；Google Docs → Workspace CLI | `pdftotext`                                                                                          |
| Genspark / GenOffice            | 自研 parse/render/edit engine；typed slide tools                                                      | Univer + Rust sidecar（calamine / IronCalc）                                                                                    | block tree + dirty OOXML splice    | 读/渲染：`pdf.js`；编辑：`pdf-lib`                                                                           |
| MuleRun                         | `\`                                                                                                | `\`                                                                                                                           | `\`                                | `\`                                                                                                  |

`\` 表示目前没有足够证据，不代表产品不支持。

### 1.2 技术路线

```text
通用代码生成：LLM → Python/JS → Office library → 文件
Skill + OOXML：高层 library → 复杂处 unzip/lxml/XML → repack
云端 IR：LLM → Office-specific XML/blocks → cloud API → 在线文档
原生引擎：LLM → typed document state → 自研 parser/render/export
CLI DSL：LLM → get/query/set/... → deterministic OpenXML executor
```

## 2. 详情

### 2.1 豆包 / Super Doubao

入口是 [Lark CLI](https://github.com/larksuite/cli) 的三个 Office skill，不是 `python-pptx`。

#### PPTX

```text
需求 → slide_plan → 单页 SML 2.0 XML
     → xml_lint.py / SXSD / overlap lint
     → lark-cli slides +create / +add-slide
     → Lark Slides object model
     → +xml-get 回读 → +screenshot → 视觉 QA
```

- 新建用 `<slide>` XML；素材引用由 CLI 上传并替换 token。
- 小改动用 `+replace-slide`；整页重写用 `+update-slide`。
- 这套 XML 是 LLM-friendly IR，不是本地 PPTX 的 OOXML。
- [lark-slides/SKILL.md](https://github.com/larksuite/cli/blob/main/skills/lark-slides/SKILL.md) · [CLI](https://github.com/larksuite/cli)。

#### XLSX

```text
lark-sheets Skill → lark-cli sheets → Lark Sheets API / cloud workbook
                  → 读取、写入、公式/格式操作 → 云端对象或导出文件
```

不是本地 `openpyxl` pipeline；backend 是飞书 Sheets 的云端对象模型。

- [lark-sheets/SKILL.md](https://github.com/larksuite/cli/blob/main/skills/lark-sheets/SKILL.md)

#### DOCX / Word

```text
lark-doc Skill → lark-cli docs → Lark Docs block model
               → 读写 / 导入 / 导出 DOCX
```

Word 文件是交换格式，主要编辑面是云端 Docs block，而不是直接改 DOCX ZIP。

- [lark-doc/SKILL.md](https://github.com/larksuite/cli/blob/main/skills/lark-doc/SKILL.md)

#### PDF

```text
读入口：CDN URL → curl -L → workspace/local PDF
内容解析 / OCR / page rendering：\

生成入口：Agent → generate_hkd_invoice.py → Python
PDF serializer / final PDF：\
```

读取轨迹只证明 PDF 被下载到本地，没有展示 text extraction、OCR 或逐页渲染；生成轨迹只证明 Agent 写出了 Python 脚本，没有展示脚本内容、所用 PDF library、执行命令或最终 PDF。

### 2.2 WorkBuddy

官方确认有 [PDF / DOCX / PPTX / XLSX Office Skills](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/WorkBuddy-Zero-Cost-Skill-Top-10/Office-Document-Suite)，但 Skill 最终调用本地 shell、Python、Node；因此不存在一个固定 Office engine。

#### PPTX

```text
PPTX Skill → JS → PptxGenJS → PPTX
PPTX Skill → Python → python-pptx → PPTX
PPTX Skill → HTML/CSS → Playwright → html2pptx → PptxGenJS/PPTX
```

三条路线都已在公开案例或运行轨迹中出现；Skill 决定走哪条。

- [PptxGenJS 案例](https://cloud.tencent.com/developer/article/2666814)
- [python-pptx / openpyxl / python-docx 案例](https://cloud.tencent.com/developer/article/2674970)
- [HTML → PPTX 案例](https://cloud.tencent.com/developer/article/2718258)

#### XLSX

```text
XLSX Skill → Python → openpyxl / pandas → XLSX
```

`openpyxl` 负责 workbook/style/chart，`pandas` 负责批量表格数据；不是 WorkBuddy core 的硬编码 backend。

#### DOCX

```text
DOCX Skill → Python → python-docx → DOCX
```

复杂结构是否追加 OOXML patch，取决于具体 Skill。

#### PDF

```text
输入 PDF（文本/表格/metadata）→ pypdf / pdfplumber
输入 PDF（版面/扫描页）      → PyMuPDF → page images → 多模态模型/OCR
生成 PDF                    → WeasyPrint / ReportLab
```

`pypdf`/`pdfplumber` 读 text layer，PyMuPDF 的页面图像补足图表、扫描件和版面信息。

### 2.3 Kimi Web / Kimi CLI

以下 PPTX / XLSX 实现来自 Moonshot AI 第一方 Skill；PDF / DOCX 描述 Kimi Web runtime 的系统能力，不是独立 Skill。[Kimi CLI 官方文档](https://moonshotai.github.io/kimi-cli/en/customization/skills.html)说明 Skill 的发现和调用机制。

#### PPTX：第一方 `kimi-slides`

```text
新建：内容 / 文档 / 大纲 → .pptd（YAML DSL）
                         → kimi-slides check / screenshot
                         → kimi_ref → Kimi 编辑器 → 用户导出 PPTX / images

编辑：PPTX → kimi-slides convert → .pptd → 修改 → check
复刻：图片 / PDF → 视觉分析 + 素材裁切 → .pptd
```

`.pptd` 是对 OOXML 的简化抽象：保留主题、布局、元素位置和定义，去掉复杂的 master 嵌套，每页自包含。配套 CLI 支持 `.pptd ↔ .pptx`、校验和截图；但 Kimi Web 的交付合同是 `.pptd + kimi_ref`，PPTX 由用户在编辑器中导出。

需要生成图片时，第一方 `image_generation` 只走素材旁路：

```text
prompt + optional reference URLs → agent-gw → JPG / PNG → media → .pptd
```

- [Kimi Slides](https://www.kimi.com/slides) · [Kimi Slides 帮助中心](https://www.kimi.com/zh-cn/help/slides)

#### XLSX：第一方 `xlsx`

```text
openpyxl / pandas → values + styles + Excel formulas → XLSX
                → 每个工作表 recheck + reference-check
                → 图表 chart-verify → validate → OpenXML 结构校验
```

Professional Finance 风格隐藏网格线，内容从 B2 开始，封面放标题、关键指标、报表导航和口径说明。派生指标保留为 Excel 公式；外部数据集中写入“数据来源”工作表，列出 Source Name 与 Source URL。任何公式错误都必须修复后再交付。

- [`openpyxl`](https://openpyxl.readthedocs.io/) · [`pandas`](https://pandas.pydata.org/docs/)

#### DOCX / Word

该 Kimi Web runtime 没有 DOCX Skill，不能生成或交付可下载的 `.docx`；只能输出纯文本供用户自行粘贴进 Word。

#### PDF

```text
输入 PDF → system <document> parser
         → XML-tagged content → conversation context

生成 PDF → \
```

PDF 读取由系统级 `<document>` 工具完成，没有可复述的 PDF Skill；这条回答也没有给出逐页图像或视觉读取链。

#### 其他第一方 Skills：不属于 Office backend

- `kimi-widget`：在会话内的 sandboxed iframe 渲染 HTML/SVG/CSS/JS，使用预载的 Kimi design system；不读写 Office 文件。
- [`kimi-help-center`](https://www.kimi.com/zh-cn/help)：把产品问题路由到对应帮助中心文章；不参与文件生成或解析。

#### PPTX：Kimi 推荐的社区 Skills

推荐关系来自 Kimi；以下仓库都是第三方社区实现，不是 Moonshot 官方代码。

| Skill | 关键链路 / 输出 |
| --- | --- |
| [`knowledge-cat-ppt-skill`](https://github.com/gnipbao/knowledge-cat-ppt-skill) | story plan → 按任务选择 `@oai/artifact-tool` native PPTX、HTML deck 或 image-first PPTX |
| [`guizang-ppt-skill`](https://github.com/op7418/guizang-ppt-skill) | 内容 → 单文件 HTML；瑞士/电子杂志风格 + WebGL，主输出不是 native PPTX |
| [`starry-slides`](https://github.com/StarryKit/starrykit-plugin) | Agent → hosted MCP → StarryKit editable design state → PPTX/PDF/SVG/PNG/JPEG/HTML/Google Slides |
| [`agentbuff-presentation-skills`](https://github.com/nugrahalabib/AgentBuff-Presentation-Skills) | HTML-first → browser render → PDF/PNG/JPG/PPTX；PPTX 可选 image 或 editable mode |
| [`frontend-slides`](https://github.com/zarazhangrui/frontend-slides) | 内容 → 零依赖单文件 HTML；已有 PPTX 先抽文本/图片/备注，再重建为 Web deck |
| [`slide-skill`](https://github.com/icgma/slide-skill) | PDF/Markdown/DOCX/URL → Markdown → SVG → DrawingML/OOXML → fully editable PPTX → LibreOffice render/QA |
| [`slide-maestro`](https://github.com/BFLabsAI/Slide-maestro_agents-skill) | PAS/AIDA/SCQA → HTML + Chart.js；已有 PPTX 用 `python-pptx` 抽取后转 HTML |
| [`html2pptx`](https://github.com/GX-Alex/html2pptx) | HTML/WebDeck → Chromium 提取 DOM/CSS/SVG → SVG → DrawingML → editable PPTX |
| [`image-to-editable-ppt-skill`](https://github.com/ningzimu/image-to-editable-ppt-skill) | 图片/PDF/图片版 PPT → 逐页 raster → OCR/VLM → 重建文本框、形状和图片 → editable PPTX |
| [`slide-writer`](https://github.com/FeeiCN/slide-writer) | idea/outline/document/speech → standalone HTML deck；不以 PPTX 为主输出 |
| [`powerpoint-fancy-design`](https://github.com/Phlegonlabs/Powerpoint-fancy-design) | Markdown → 1600×900 HTML → PNG → image-based PPTX；视觉一致，但页面元素不可编辑 |
| [`slide-creator`](https://github.com/kaisersong/slide-creator) | prompt → `BRIEF.json` → HTML → validate/eval → `kai-html-export` → PPTX/PNG；支持像素保真与 native editable mode |

### 2.4 QwenWork

#### PPTX

```text
读内容：PPTX → MarkItDown → text
看全局：PPTX → thumbnail.py → slide overview
看结构：PPTX → unpack.py → raw OOXML

新建：blank Presentation() → theme / layouts / components.py
                           → python-pptx → editable PPTX
编辑：template QA → unpack → edit / clean / pack → PPTX

QA：MarkItDown + view_issues.py
  → LibreOffice → PDF → pdftoppm → per-slide JPG
  → visual review → fix → re-verify
```

`view_issues.py` 先查 broken relationships、overflow、越界、重复 slide ID、未引用 media、对比度、字体层级和 palette；页面 JPG 才是最终视觉判断。需要真实图片时走素材旁路：

```text
prompt / reference → media-generate → qwenwork-router → image → PPTX
```

- [MarkItDown](https://github.com/microsoft/markitdown) · [`python-pptx`](https://python-pptx.readthedocs.io/) · [LibreOffice](https://www.libreoffice.org/discover/libreoffice/) · [Poppler](https://poppler.freedesktop.org/)

#### XLSX

```text
openpyxl / pandas → values + styles + Excel formulas → XLSX
                → scripts/recalc.py → LibreOffice 重算
                → 扫描 #REF! / #DIV/0! / #VALUE! / #NAME? / #N/A
```

公式必须留在 workbook 中，不能由 Python 算完后硬编码；财务模型用蓝色硬编码输入、黑色公式、绿色跨表链接，假设放在独立单元格并标注来源。

#### DOCX / Word

`\`

#### PDF

```text
读 text layer：PDF → pdftotext → text
读页面视觉：PDF → pdftoppm → page images
                    → media-read → Qwen3-Omni → text / objects / layout

生成：MDX + built-in components → md2pdf → React SSR
                                → Chromium / Playwright → PDF
```

`media-read` 适合提取页面里的文字、对象、数量和布局；美学判断仍直接看页面图像。生成链里的 KaTeX、Shiki 和 server-side SVG charts 随 MDX 做组件渲染，Mermaid 在浏览器 capture 前渲染，输出后逐页检查。

- [QwenWork](https://help.aliyun.com/zh/qwenwork/qwenwork-intro) · [Slides 工作台](https://help.aliyun.com/zh/qwenwork/qw-workbench-slides) · [Writing 工作台](https://help.aliyun.com/zh/qwenwork/qw-workbench-writing)

### 2.5 ChatGPT Work / artifact skills

这里描述文件 artifact skills；live Excel 是另一条 connector 路线。

#### PPTX

```text
Presentation Skill → @oai/artifact-tool（JavaScript）
                   → presentation → master/layout → slide → element
                   → export PPTX → 逐页 render / overflow / font / visual QA
```

`@oai/artifact-tool` 是当前 artifact runtime 给 Skill 使用的 JS package，不是 Microsoft Office API。Agent 构造 presentation object model，再导出 PPTX。

#### XLSX

```text
Spreadsheet Skill → @oai/artifact-tool Workbook API
                  → inspect(values, formulas)
                  → formula-error scan → render → export XLSX
```

当前 Workbook skill 不把 `openpyxl`、`xlsxwriter` 当 authoring backend。

#### DOCX

```text
python-docx → 必要时 OOXML helpers
            → LibreOffice → PDF/PNG
            → 逐页视觉检查
```

#### PDF

```text
模型直接读：Responses API input_file → 抽取 text + page images → 一起送入视觉模型
本地 Skill 读：pypdf / pdfplumber → 文本/表格/结构
             + Poppler → page PNG → 多模态模型/OCR
表单读取：pypdf → AcroForm fields + widgets + appearance streams
直接生成：ReportLab
间接导出：DOCX / PPTX → PDF
```

官方 [File inputs](https://developers.openai.com/api/docs/guides/file-inputs) 明确说明：视觉模型收到 PDF 的抽取文本和每页图像；这不是只把 PDF 当下载附件。复杂长文档通常先做 DOCX，slide-like PDF 通常先做 PPTX，再导出。

- [Work with files](https://learn.chatgpt.com/docs/artifacts-viewer)
- [ChatGPT for Excel](https://help.openai.com/en/articles/20001063)

### 2.6 Claude Code + Anthropic `document-skills`

官方 repo 的四个目录会被打包为 `document-skills` plugin；不是 Claude Code core 自带的硬编码 Office engine。

#### PPTX

```text
Prompt / content
      ↓
layout planning
      ├─ new deck       → PptxGenJS
      └─ existing deck  → unzip → raw OOXML / rels → repack
                              ↓
                           PPTX
                              ├─ package validator
                              └─ LibreOffice render → thumbnails/PNG → vision QA → fix
```

- `add_slide.py` 负责复制 slide registration、relationships、content types；不要手工复制 slide XML。
- 读取路径是 MarkItDown/缩略图/raw XML；`python-pptx` 只做有限辅助，不是主生成 backend。
- [PPTX Skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md)

#### XLSX

```text
XLSX Skill → openpyxl / pandas → workbook/style/formula
           → LibreOffice recalc → inspect / error scan → XLSX
```

复杂格式仍可退回 OOXML；LibreOffice 负责重算和渲染，不是主要 authoring API。

- [XLSX Skill](https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md)

#### DOCX / Word

```text
新建：docx-js → DOCX
已有：unzip → raw OOXML surgery → repack
QA：LibreOffice → PDF/PNG → visual review
```

- [DOCX Skill](https://github.com/anthropics/skills/blob/main/skills/docx/SKILL.md)

#### PDF

```text
模型直接读：Messages API document block → 每页 text + image → Claude vision
Skill 本地读：pypdf / pdfplumber → 文本/表格/结构
             + Poppler/pdf2image → page images → vision/OCR
直接生成：ReportLab
结构/压缩/合并：qpdf / pdf-lib
```

- [Claude PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support)：官方说明每页同时按 text 和 image 处理。
- [PDF Skill](https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md)
- [Anthropic Skills](https://github.com/anthropics/skills)

### 2.7 Manus

- **PPTX**：PowerPoint Mode 从第一步就生成 native `.pptx`；charts、tables、slide masters 都是对象。内部 serializer：`\`。
- **XLSX**：本地：`\`；Google Sheets 走 Google Workspace CLI。
- **DOCX**：本地：`\`；Google Docs 走 Workspace connector/CLI。
- **输入 PDF**：`pdftotext → text`。
- **生成 PDF**：`\`。

- [Native PowerPoint Mode](https://manus.im/blog/manus-ppt-slides)
- [Skills](https://manus.im/docs/features/skills)
- [Google Workspace CLI](https://manus.im/blog/manus-google-drive-connector-update-cli)

### 2.8 Genspark / GenOffice

#### PPTX

```text
typed tools（read_slide / set_element_* / execute_slide_script）
→ native slide state
→ 自研 pptx parse/render/edit engine
→ PPTX
```

新建整套 deck 可以 `HTML → editable slide elements`；精确修改走 native shape/state，不是 PptxGenJS。

#### XLSX

```text
Univer UI/state → Rust sidecar → calamine（parse）+ IronCalc（formula）→ XLSX
```

#### DOCX

```text
DOCX ZIP → block tree → 只重写 dirty paragraph OOXML
         → splice 回原包 → 未修改部分 byte-preserving
```

#### PDF

```text
输入 PDF：pdf.js → parse + page render → PDF state
编辑/写回：pdf-lib → annotations/forms/outlines/page ops → PDF
```

- [GenOffice](https://github.com/genspark-ai/genoffice)

### 2.9 MuleRun

MuleRun 提供完整云 VM、shell、浏览器、Skills 和动态依赖安装，不规定单一 Office serializer。

- **PPTX / XLSX / DOCX**：`\`。
- **输入 / 生成 PDF**：`\`。
- **Office Sync**：上传 Excel/PPT 后可让 Agent 双向回写源文件；内部 diff/serializer：`\`。

- [MuleRun Chat / Skills](https://blog.mulerun.com/p/meet-mulerun-chat-one-agent-everything-done/)
- [Office Sync](https://help.mulerun.com/features/super-agent)

### 2.10 OfficeCLI

```text
officecli get/query/set/add/remove/batch/validate
→ DOM-like address → OpenXML → DOCX/XLSX/PPTX
```

模型操作的是：

```text
/slide[3]/shape[1]
/body/p[3]/r[1]
/Sheet1/A10
```

而不是 `openpyxl.Workbook` 或 `pptx.shapes`。PDF 不在 OfficeCLI 的核心 read/write scope。

```bash
officecli set deck.pptx /slide[3]/shape[1] --prop text="2027 Roadmap"
officecli validate deck.pptx
officecli mcp
```

- [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI)
- [Command reference](https://github.com/iOfficeAI/OfficeCLI/wiki/command-reference)

## 3. 横向结论

1. **新建和已有文件编辑必须分开看。** 新建适合 `PptxGenJS`、`docx-js`、HTML/Paged.js；模板保真和局部修改通常退回 raw OOXML 或 native document state。
2. **XLSX 最能暴露 verifier 差异。** 写入只是第一步；公式重算、引用检查、图表范围、格式和渲染结果都要单独验证。
3. **PDF 要拆成输入读取、直接生成和格式导出。** 输入读取通常同时抽 text layer 和渲染页面；输出可以由 ReportLab/HTML 直接生成，也可以从 DOCX/PPTX 导出；`pdf-lib`/qpdf 主要处理局部编辑和页面操作。
4. **Office-Agent benchmark 的最小 metadata 不应只有 model/harness：**

```yaml
model: ...
harness: ...
skill: ...
office_stack:
  pptx: { interface: ..., backend: ..., verifier: ... }
  xlsx: { interface: ..., backend: ..., verifier: ... }
  docx: { interface: ..., backend: ..., verifier: ... }
  pdf:  { interface: ..., backend: ..., verifier: ... }
runtime:
  python: ...
  node: ...
  libreoffice: ...
  fonts: ...
```

最终分数更接近：

```text
Model × Harness × Skill × Office substrate × Runtime × Verifier
```
