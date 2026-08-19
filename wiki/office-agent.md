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
| PDF | ReportLab、HTML + Paged.js、`pdf-lib` | `pypdf`、`pikepdf`、`qpdf`、`pdf-lib` | 文本/结构：`pypdf`、`pdfplumber`、`pdf.js`；页面渲染：Poppler、PyMuPDF、`pdf.js` → PNG → VLM/OCR |

`pandas` 主要负责表格数据处理，不是完整的 XLSX serializer；LibreOffice 负责重算/渲染，Poppler 负责页面渲染，PyMuPDF 同时能抽取内容和 rasterize 页面。

### 0.2 PDF 怎么 read

```text
PDF
├─ 有 text layer → pypdf / pdfplumber / pdf.js
│                → 文本、坐标、表格、metadata、form fields
├─ 需要看版面   → Poppler / PyMuPDF / pdf.js
│                → 每页 PNG → 多模态模型
└─ 扫描件       → 每页 PNG → OCR / 多模态模型
```

稳妥的 PDF Skill 会同时做 **text extraction + page render**：前者便于搜索、引用和表格抽取，后者用于看图表、版面、扫描页以及检查文字是否截断。可填写表单还要额外读取 AcroForm field tree、page widgets 和 appearance stream。

- [`pypdf`](https://pypdf.readthedocs.io/)：文本、metadata、页面、加密、AcroForm。
- [`pdfplumber`](https://github.com/jsvine/pdfplumber)：字符坐标、行、表格和布局抽取。
- [`pdf.js`](https://mozilla.github.io/pdf.js/)：浏览器端解析与页面渲染。
- [PyMuPDF](https://pymupdf.readthedocs.io/)：文本/图片抽取与页面 rasterize。
- [Poppler](https://poppler.freedesktop.org/)：把 PDF 页面渲染为 PNG，常用入口是 `pdftoppm`。

### 0.3 成体系的 skill / CLI / MCP

- [Anthropic document-skills](https://github.com/anthropics/skills)：`pptx`、`xlsx`、`docx`、`pdf` 四个 skill。
- [OpenAI skills](https://github.com/openai/skills)：Slides、Documents、PDF、Spreadsheet artifact workflows。
- [Lark CLI](https://github.com/larksuite/cli)：[`lark-slides`](https://github.com/larksuite/cli/tree/main/skills/lark-slides)、[`lark-sheets`](https://github.com/larksuite/cli/tree/main/skills/lark-sheets)、[`lark-doc`](https://github.com/larksuite/cli/tree/main/skills/lark-doc)。
- [Kimi CLI Skills](https://moonshotai.github.io/kimi-cli/en/customization/skills.html)；产品 skill 的第三方提取见 [`kimi-skills`](https://github.com/thvroyal/kimi-skills)（非 Moonshot 官方）。
- [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI)：统一 `get/query/set/add/remove/batch/validate`，也可通过 `officecli mcp` 暴露 MCP。
- [DSH Office plugin](https://github.com/rong-coder/dsh-office-tool)：把 OfficeCLI 接入 DSH。

## 1. 总览

### 1.1 一张表看完

| 产品 / harness | PPTX | XLSX | DOCX | PDF | 核心范式 |
| --- | --- | --- | --- | --- | --- |
| 豆包 / Super Doubao | `lark-slides` → SML 2.0 → `lark-cli slides` | `lark-sheets` → Lark Sheets API | `lark-doc` → Lark Docs API | 读：PyMuPDF → 页面图像/视觉检查；写：HTML/Markdown/ReportLab（待确认） | 云端 Office IR / API |
| WorkBuddy | `PptxGenJS`、`python-pptx`、HTML → PPTX | `openpyxl` / `pandas` | `python-docx` | 读：`pypdf`/`pdfplumber`/PyMuPDF；写：WeasyPrint/ReportLab | Skill 驱动的通用代码执行 |
| Kimi Code / Web | 官方示例 `python-pptx` | `openpyxl` + `pandas` + KimiXlsx CLI / OpenXML（待确认） | 新建 C# OpenXML SDK；编辑 `lxml` + raw OOXML（待确认） | 读：`pdfplumber`；改：`pikepdf`；写：HTML + Paged.js + Playwright（待确认） | Skill-heavy + OpenXML/validator |
| Qwen Code | skill-dependent | skill-dependent | skill-dependent | 读：内置多模态 PDF bridge（待确认）；写：skill-dependent | Office-unaware harness |
| QwenWork | HTML 1280×720 工作台 → 导出 PPTX/PDF/HTML | `pandas` + `openpyxl` + recalc（待确认） | 在线 Word 可编辑；本地 serializer 未公开 | 读：产品支持，backend 未公开；写：Markdown → PDF | Workbench / code / GUI 混合 |
| GPT / ChatGPT artifact runtime | 当前 runtime 用 `@oai/artifact-tool`；公开 Slides Skill 用 PptxGenJS | 结构化 Workbook API / `@oai/artifact-tool` | `python-docx` + OOXML helpers | 读：`pypdf`/`pdfplumber` + Poppler → PNG/VLM；写：ReportLab | Structured artifact runtime |
| Claude Code + `document-skills` | 新建 `PptxGenJS`；已有 deck raw OOXML | `openpyxl` + `pandas` + LibreOffice 重算 | 新建 `docx-js`；已有文档 raw OOXML | 读：`pypdf`/`pdfplumber` + Poppler → PNG/VLM；写：ReportLab | Library codegen + OOXML escape hatch |
| Manus | PowerPoint Mode 原生 `.pptx`；内部 engine 未公开 | `openpyxl`（待确认）；Google Workspace 另走 CLI | 本地 backend 未公开；Google Docs 走 Workspace CLI | 产品支持读取 PDF；具体 backend 未公开 | Native PPT + sandbox / connector |
| Genspark / GenOffice | 自研 parse/render/edit engine；typed slide tools | Univer + Rust sidecar（calamine / IronCalc） | block tree + dirty OOXML splice | 读/渲染：`pdf.js`；编辑：`pdf-lib` | Native Office engine |
| MuleRun | `PptxGenJS` 动态安装（待确认）；Office Sync | backend 未公开；Office Sync 可回写 | backend 未公开 | backend 未公开 | VM + dynamic Skill + Office Sync |
| OfficeCLI / `dsh-office-tool` | OfficeCLI → OpenXML | OfficeCLI → OpenXML | OfficeCLI → OpenXML | PDF 不在核心 read/write scope | Agent-native DOM DSL |

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

**待确认**：当前产品轨迹看起来是：

```text
读取/验收：PyMuPDF → 提取文本/页信息 + 页面 rasterize → 视觉检查
新建：Markdown / HTML / ReportLab → PDF
```

公开的 Lark CLI 中没有与 Slides/Sheets/Docs 同等级的 PDF object model。

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
文本/结构 → pypdf / pdfplumber
页面视觉 → PyMuPDF rasterize → page images → 多模态模型
新建/排版 → WeasyPrint / ReportLab
```

这里的“读”不是单一步骤：`pypdf`/`pdfplumber` 负责文本、表格和 metadata，PyMuPDF 负责把页面转成图像保留版面信息。

#### 另一条通道：腾讯文档

```text
WorkBuddy → Tencent Docs connector → 云端文档/表格/幻灯片对象
```

- [Skills 机制](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)
- [腾讯文档连接器](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Knowledge-Base/Tencent-Doc)

### 2.3 Kimi Code / Kimi Web

[Kimi CLI 官方文档](https://moonshotai.github.io/kimi-cli/en/customization/skills.html)只规定 Skills、Plugins、shell、MCP；官方 PPT 示例是 `python-pptx`。

**待确认**：下面的 XLSX/DOCX/PDF 细节来自 [第三方提取的 Kimi Skills](https://github.com/thvroyal/kimi-skills)，不是 Moonshot 官方仓库。

#### PPTX

```text
Kimi Skill → Python → python-pptx → PPTX
```

这是官方 CLI 示例，不等于所有 Kimi 产品都固定使用它。

#### XLSX

```text
常规表格 → openpyxl / pandas
复杂结构 → KimiXlsx CLI → OpenXML SDK
校验     → recheck / reference-check / inspect / pivot / chart-verify / validate
```

因此 Kimi XLSX 是 `openpyxl + pandas + 专用 validator/CLI`，不是只有 `openpyxl`。

- [kimi-xlsx/SKILL.md](https://github.com/thvroyal/kimi-skills/blob/main/skills/kimi-xlsx/SKILL.md)

#### DOCX / Word

```text
新建：Program.cs → C# OpenXML SDK → fix_element_order → validators → DOCX
编辑：DOCX unzip → Python + lxml / raw OOXML → validators → DOCX
```

该 Skill 明确不建议用 `python-docx` 或 `docx-js` 作为 fallback。

- [kimi-docx/SKILL.md](https://github.com/thvroyal/kimi-skills/blob/main/skills/kimi-docx/SKILL.md)

#### PDF

```text
读取：pdfplumber → 文本 / 坐标 / 表格
页面对象操作：pikepdf
新建：HTML/CSS → Paged.js → Playwright/Chromium → PDF
显式 LaTeX：Tectonic → PDF
```

- [kimi-pdf/SKILL.md](https://github.com/thvroyal/kimi-skills/blob/main/skills/kimi-pdf/SKILL.md)

### 2.4 Qwen

必须拆成 **Qwen Code** 和 **QwenWork**。

#### Qwen Code

```text
Qwen Code → filesystem / run_shell_command / Skills / MCP
         → 由安装的 Skill 决定 Python、JS、CLI 或自研 backend
```

四种格式都没有 core 固定 serializer。

**待确认**：PDF 读取通过内置 bridge 把 PDF 交给多模态模型；具体是直接传 PDF、先提取 text layer，还是先 rasterize 页面，公开文档没有写清楚。

- [Tools](https://qwenlm.github.io/qwen-code-docs/en/developers/tools/introduction/)
- [Skills](https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/)
- [MCP](https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/)

#### QwenWork

- **PPTX**：`outline → HTML 1280×720 canvas → export PPTX/PDF/HTML`；converter 未公开。
- **XLSX**：社区实跑为 `xlsx Skill → pandas/openpyxl → recalc`，不是官方 serializer 承诺。
- **DOCX**：支持在线 Word/文件编辑；本地 DOCX serializer 未公开。写作工作台以 Markdown 为源。
- **PDF**：支持上传并理解 PDF，底层 text extraction / page render backend 未公开；写作工作台的输出路径是 `Markdown → PDF export`。
- **GUI**：Computer Use 可直接操作桌面 Office/Numbers，是独立于文件 serializer 的第四条路线。

- [QwenWork](https://help.aliyun.com/zh/qwenwork/qwenwork-intro)
- [Slides 工作台](https://help.aliyun.com/zh/qwenwork/qw-workbench-slides)
- [Writing 工作台](https://help.aliyun.com/zh/qwenwork/qw-workbench-writing)
- [Computer Use](https://help.aliyun.com/zh/qwenwork/qw-computer-use)

### 2.5 GPT / ChatGPT artifact runtime

这里描述当前 OpenAI artifact runtime；live Excel 是另一条 connector 路线。

#### PPTX

```text
Slides Skill → @oai/artifact-tool（JavaScript）
             → presentation → master/layout → slide → element
             → export PPTX
             → render every slide → overflow / font / visual QA
```

`@oai/artifact-tool` 是 OpenAI artifact runtime 内置的结构化文档库，不是 Microsoft Office API，也不是通用标准。它让 Agent 操作内存中的 presentation object model，再序列化为 PPTX；公开仓库中的 [Slides Skill](https://github.com/openai/skills/tree/main/skills/.curated/slides) 则使用 PptxGenJS，是另一条 runtime 路线。

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
文本/结构：pypdf / pdfplumber
页面视觉：Poppler → PNG → 多模态模型
表单：pypdf → AcroForm fields + widgets + appearance streams
创建：ReportLab
JS 编辑：pdf-lib / pdf.js
```

复杂长文档通常先做 DOCX，slide-like PDF 通常先做 PPTX，再导出 PDF。

- [OpenAI skills](https://github.com/openai/skills)
- [ChatGPT Work](https://help.openai.com/en/articles/20001278)
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
文本/结构：pypdf / pdfplumber
页面视觉：Poppler → PNG → 多模态模型
创建：ReportLab
结构/压缩/合并：qpdf / pdf-lib
```

- [PDF Skill](https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md)
- [Anthropic Skills](https://github.com/anthropics/skills)

### 2.7 Manus

- **PPTX**：PowerPoint Mode 从第一步就生成 native `.pptx`；真实 charts、tables、slide masters 都是对象。内部 serializer 未公开，不能写成 PptxGenJS。
- **XLSX（待确认）**：本地 sandbox 轨迹为 `openpyxl → XLSX`；Google Sheets 则走 Google Workspace CLI。
- **DOCX**：本地默认 serializer 未公开；Google Docs 走 Workspace connector/CLI。
- **PDF**：能读取 PDF；底层是 text extraction、page render 还是原生多模态 PDF input 未公开，本地默认 authoring backend 也未公开。

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
读取/渲染：pdf.js → PDF state
编辑/写回：pdf-lib → annotations/forms/outlines/page ops
```

- [GenOffice](https://github.com/genspark-ai/genoffice)

### 2.9 MuleRun

MuleRun 提供完整云 VM、shell、浏览器、Skills 和动态依赖安装，不规定单一 Office serializer。

- **PPTX（待确认）**：`install pptxgenjs + icon deps → JS codegen → PPTX`。
- **XLSX / DOCX / PDF**：没有公开默认 backend；PDF 的 text extraction、page render 与 authoring 路径均未公开。
- **Office Sync**：上传 Excel/PPT 后可让 Agent 双向回写源文件；内部 diff/serializer 未公开。

- [MuleRun Chat / Skills](https://blog.mulerun.com/p/meet-mulerun-chat-one-agent-everything-done/)
- [Office Sync](https://help.mulerun.com/features/super-agent)

### 2.10 OfficeCLI / `dsh-office-tool`

`dsh-office-tool` 只是把 OfficeCLI 暴露给 DSH；真正处理 Office 文件的是 OfficeCLI：

```text
DSH tool → officecli get/query/set/add/remove/batch/validate
         → DOM-like address
         → OfficeCLI → OpenXML → DOCX/XLSX/PPTX
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
- [DSH Office plugin](https://github.com/rong-coder/dsh-office-tool)

## 3. 横向结论

1. **新建和已有文件编辑必须分开看。** 新建适合 `PptxGenJS`、`docx-js`、HTML/Paged.js；模板保真和局部修改通常退回 raw OOXML 或 native document state。
2. **XLSX 最能暴露 verifier 差异。** 写入只是第一步；公式重算、引用检查、图表范围、格式和渲染结果都要单独验证。
3. **PDF 经常是输出格式，不是编辑格式。** 长文档先 DOCX，slide-like 内容先 PPTX，最后再导出 PDF；直接改 PDF 只适合局部 patch、表单和页面操作。
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
