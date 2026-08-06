---
title: "11 个 Agent Benchmark 深度研究：General Task 进展与瓶颈分析"
public: true
description: "系统拆解 11 个 Agent Benchmark 的数据、任务、环境、评分与 SOTA，理解 General Task Agent 的进展与瓶颈。"
type: agent-evaluation
date: 2026-08-05
reading_surface: true
kicker: "AGENT BENCHMARK · GENERAL TASK FRONTIER"
---

# 11 个 Agent Benchmark 深度研究：General Task 进展与瓶颈分析

## 研究概述

本文依据[Feishu 原始整理][feishu-doc]，对当前主流的 11 个 Agent Benchmark 进行系统性深度拆解，覆盖数据规模、任务类型、环境设计、评分机制与 SOTA 表现等维度，旨在建立对 General Task Agent 领域当前进展与核心瓶颈的整体认知。

这里的核心判断是：

> **Agent benchmark 本质上是系统 benchmark。**

它测到的从来不只是模型，而是下面这些因素的乘积：

```text
模型 × Harness × 工具协议 × 环境镜像
    × 任务数据 × 评分器 × 运行策略
```

因此，在比较 leaderboard 分数之前，至少要先回答四个问题：

1. 初始状态一样吗？
2. Agent 看见的东西一样吗？
3. grader 是同一个版本吗？
4. 失败与恢复被记成同一种状态吗？

本文保留 Feishu 文档中的 SOTA 口径，并在表格标题中标明版本、Harness 或评测设置。不同 Benchmark 的任务、环境和评分方式不同，分数不可直接横向比较；`—` 表示当前没有公开数据，而不是模型一定失败。

## 11 个 Benchmark 总览

|Benchmark|任务数|工具/环境数|状态权威|评分主路径|SOTA 分数|
|---|---|---|---|---|---|
|[Agents Last Exam（ALE）][ale-lifecycle]|147 public / 1500+ total|55 个子行业|VM 文件与应用状态|任务级 evaluator|GPT-5.6：29.6% / Kimi K3：28.3% / Claude Fable 5：25.7%|
|[AutomationBench][automation-world]|606 scored + 200 simple|47 SaaS tools|内存 `WorldState`|最终状态 assertions|Kimi K3：30.8% / GPT-5.6：29.7% / Claude Fable 5：29.1%|
|[Claw-Eval][claw-scoring]|300|9 类别|Docker mock services|Completion × Safety × Robustness|暂无三大模型公开数据|
|[JobBench][job-runner]|65 main + 63 easy|35 个职业|最终交付物|LLM rubric judge|Claude Fable 5：57.4% / Kimi K3：54.3% / GPT-5.6：45.4%|
|[MCP-Atlas][atlas-loop]|1000，公开 500|36 MCP servers / 307 tools|共享 MCP sandbox|Claim coverage LLM judge|Claude Fable 5：84.7% / Kimi K3：84.2% / GPT-5.6：83.6%|
|[MCPMark][mcpmark-evaluator]|177，含 127 standard + 50 easy|5+ 服务类型|服务终态|`verify.py` 程序化检查|Kimi K3：94.5%（Verified） / GPT-5.6：92.9% / Claude Fable 5：87.4%|
|[OfficeQA][officeqa-reward]|133 Pro / 246 Full|89k 页文档|最终文本答案|数值容差 / 文本匹配|Claude Fable 5：69.9%（Pro） / Kimi K3：63.3% / GPT-5.6：63.2%|
|[SpreadsheetBench 2][spreadsheet-eval]|321|4 大类任务|最终 `.xlsx` 文件|Cell diff + VLM checklist|Kimi K3：34.8% / Claude Fable 5：34.7% / GPT-5.6：32.4%|
|[Toolathlon][toolathlon-guard]|108|32 apps / 604 tools|本地 workspace + 远程状态|任务私有 evaluator|Claude Fable 5：77.9%（Verified） / Kimi K3：76.5% / GPT-5.6：74.9%|

## 分类视角

从“结果状态在哪里”看，这 11 个 benchmark 大致分成三类：

### 1. 交付物中心

代表项目是 JobBench、OfficeQA 和 SpreadsheetBench 2。它们以最终产出文件或文本作为评分对象，关键问题是：参考答案是否可见、等价输出能否通过、解析器是否真的读到了文件。

### 2. 轨迹中心

代表项目是 MCP-Atlas，以及 Claw-Eval 的部分维度。它们关注工具调用序列和中间过程，需要判断工具调用是否是任务所需，最终 claim 能否追溯到证据。

### 3. 环境状态中心

代表项目是 ALE、AutomationBench、MCPMark 和 Toolathlon。它们以环境终态作为真相源，核心问题是：谁拥有状态、怎样 reset、并发是否串扰、cleanup 失败后会发生什么。

这三类不是互斥的实现标签，而是阅读分数时的第一层视角。一个看起来很高的 claim coverage，和一个严格的服务终态通过率，回答的不是同一个问题。

## 逐 Benchmark 深度拆解

### 1. Agents Last Exam（ALE）——职业任务系统

#### 数据规模与类型

ALE 是目前覆盖范围最广的 Agent 评测基准之一，目标是构建 5000 个任务的完整语料库。ALE-V1 当前公开发布 147 个参考任务，覆盖 55 个子行业，参考美国 O*NET / SOC 2018 联邦职业分类体系定义非物理行业。许多任务需要私有数据或许可软件，因此保留在私有池中。

ALE 采用滚动评测机制：大约每 6 个月发布一批新的公开任务实例，同时让私有任务轮换进出，已退役的公开任务也会轮换出去，以限制基准泄露。

#### 任务设计

ALE 的核心设计理念不是统一任务格式，而是统一生命周期。每个职业任务都被做成一个小型系统，包含完整的输入、处理和输出流程。任务类型覆盖临床数据映射（如 `CRF → SDTM`）以及各类专业工作流，强调长周期、经济价值高的专业任务。

每个任务有独立 evaluator，既可以使用确定性评分，也可以使用混合评分。统一的是任务生命周期，不是每个职业任务的输出格式。

#### 环境设计

ALE 的环境以 VM 文件和应用状态为核心，Agent 通过桌面、Shell 以及 task-specific 软件进行交互。每个任务有独立的 provider VM，reference 在 Agent 执行结束后才注入环境，实现强时间隔离；实验级和任务级持久化支持 resume 身份验证。

#### SOTA 表现

|排名|Harness|模型|Pass Rate|Score|估算成本|运行时间|
|---:|---|---|---:|---:|---:|---:|
|1|Codex|GPT-5.6 Sol|30.6%|53.6%|$762|94h 39m|
|2|Codex|GPT-5.6 Luna|29.6%|48.3%|$235|66h 7m|

即使是最强模型，在 ALE 上的通过率也只有约 30%，同时需要近百小时运行时间和数百美元成本。这说明长周期专业任务仍是 Agent 面临的巨大挑战。

### 2. AutomationBench——WorldState 为唯一真相

#### 数据规模与类型

AutomationBench 包含 606 个 scored task 和 200 个 simple task，README 的口径是 600 + 200。它模拟 47 个 SaaS 工具，覆盖 Gmail、Salesforce、Google Calendar、Slack 等主流办公场景，任务分布在多个业务领域，每个领域约 100 个任务。

#### 任务设计

AutomationBench 看起来像 Agent 在操作各种 SaaS，实际上没有外部 SaaS。每个任务把完整业务世界反序列化成 Pydantic `WorldState` 对象，所有工具都查询或修改这个对象，grader 也读取同一个对象。

核心流程是：

```text
task prompt + initial_state
→ construct WorldState
→ model/tool loop
→ evaluate assertions against final WorldState
→ task_completed_correctly = all assertions pass
```

这种结构的优势非常直接：没有网络抖动、OAuth、页面改版和 eventual consistency；同一个初始状态加同一串 tool calls，应得到同一个终态。它还把 task prompt、initial state、tools 和 assertions 规范化后计算 task contract SHA-256，确保任务身份可验证。

#### 环境设计

AutomationBench 的环境是纯内存的 `WorldState` 对象，每个 task 新建状态对象，实现强进程内隔离。assertions 留在 host task object 中，Agent 无法看到。

#### SOTA 表现

三大前沿模型在 max effort 设置下的统一评测数据：

- Kimi K3：30.8%
- GPT-5.6 Sol：29.7%
- Claude Fable 5：29.1%

注：Claude Fable 5 与 Claude Mythos 5 是同一底层模型的不同配置。Fable 5 内置安全分类器，会将高风险请求 reroute 到 Opus；Mythos 5 是没有安全过滤的原始模型。

### 3. Claw-Eval——三维可信评测

#### 数据规模与类型

Claw-Eval 包含 300 个人工验证任务，跨越 9 个细粒度类别，组织成三大组：

- **通用服务编排（General）**：从单服务查询到跨服务协调和多系统工作流，反映部署相关的操作场景。
- **多模态感知与交互（Multimodal）**：视频、文档、图像、代码生成视觉产物等丰富媒体的主动感知和生成。
- **多轮专业对话（Multi-turn Dialogue）**：STEM、社会科学、商业等领域的专业咨询，包含隐藏意图用户场景，需要主动澄清和信息收集。

#### 任务设计

Claw-Eval 的核心创新是轨迹感知评分。每次运行通过三个独立证据通道记录执行轨迹、审计日志和环境快照，产生 2159 个细粒度 rubric 项。

评分协议评估三个维度：

- **Completion（完成度）**：任务目标是否达成。
- **Safety（安全性）**：是否违反安全约束、是否调用了禁止工具。
- **Robustness（鲁棒性）**：在错误注入和扰动下是否稳定。

它使用 Average Score、`Pass@k` 和 `Pass^k` 三种指标，通过三次试验区分真实能力和幸运结果。

#### 环境设计

Claw-Eval 的 Agent loop 在 host，任务服务和文件 sandbox 在 Docker 中。Agent 通过 HTTP tools 与 sandbox 交互，grader 在 host 侧读取 trace 并注入 grader-only 文件。grader-only 文件在 loop 结束后才注入，实现强时间隔离。

#### 关键发现

对 14 个前沿模型的实验显示：

1. 轨迹不透明的评测系统性不可靠，遗漏了 44% 的安全违规和 13% 的鲁棒性失败。
2. 能力不等于一致性：错误注入下，`Pass@3` 可以保持稳定，而 `Pass^3` 最多下降 24 个百分点。
3. Agent 能力是强多维的，模型排名会在不同任务组和指标之间发生很大变化。

### 4. JobBench——专业交付物 LLM 评审

#### 数据规模与类型

JobBench 面向 35 个白领职业的多源预处理工作，main split 有 65 个完整任务，easy split 有 63 个简化任务。正式数据由 setup 脚本从 Hugging Face 拉取，覆盖商业金融、行政管理、计算数学、建筑工程、管理、艺术等多个领域。

#### 任务设计

JobBench 的任务通常同时要求：

- `reconcile conflicting records`：调和冲突记录；
- `cross-reference`：交叉引用；
- `trace citations`：追踪引用；
- 制作专业交付物。

runner 的主路径是：

```text
TASK_INSTRUCTIONS + reference files
→ CLI agent 写入临时输出
→ 移回 model_output
→ 从多种文件类型提取文本 / 图像
→ 每个加权 rubric 调用一次 LLM
→ 聚合通过的权重
```

这种设计比让一个 agent-as-judge 自己打开所有文件便宜得多，但也把“文件解析器看见了什么”变成评分的一部分。

#### 环境设计

JobBench 使用 CLI agent 和临时工作目录，每个 task 复制到独立 `/tmp` 目录。`RUBRICS.json` 留在原数据树，临时 Agent workspace 不含它，实现目录隔离；但隔离强度仍取决于 CLI 实际文件权限。

#### SOTA 表现

|模型|Overall|Bus. Fin.|Admin|Comp. Math.|Arch. Eng.|Mgmt|Arts|
|---|---:|---:|---:|---:|---:|---:|---:|
|Claude Code Opus-4.7|45.9%|46.1%|47.8%|39.2%|46.6%|38.8%|64.2%|
|GPT-5.5（Codex CLI）|42.7%|47.7%|42.6%|39.4%|40.9%|30.5%|50.2%|
|Claude Code Sonnet-4.6|36.9%|36.7%|38.4%|31.9%|41.1%|30.7%|54.9%|

最强模型在 JobBench 上的整体通过率约 46%。艺术类任务相对容易，达到 64%；管理类和建筑工程类任务难度较大。

### 5. MCP-Atlas——大规模工具覆盖评测

#### 数据规模与类型

MCP-Atlas 是目前规模最大的 MCP 工具评测基准之一，包含 36 个真实 MCP server 和 307 个工具，论文口径为 220 tools；共有 1000 个任务，其中公开发布 500 个任务子集。

任务用于评估真实多步工作流中的工具使用能力，使用自然语言 prompt，不指定具体工具或服务器，要求 Agent 自行识别并编排 3–6 次跨多个服务器的工具调用。

#### 任务设计

MCP-Atlas 的任务数据包含 `TASK`、`PROMPT`、`ENABLED_TOOLS` 和 `GTFA_CLAIMS`。评分采用基于 claims 的 rubric，根据模型最终答案中满足的事实声明给予部分分数，并报告 0.50 / 0.75 两个 coverage threshold。

它主要测的是“能否用工具找到并表述所需事实”，而不是应用终态。

架构分三层：

```text
Python agent-environment sandbox
    ← HTTP → TypeScript multi-turn harness
    ← HTTP → Python CSV runner / HF task dataset
```

#### 环境设计与问题

MCP-Atlas 存在一个根因级风险：默认并发共享 sandbox。TypeScript client 实现了 `resetState()`，但实际 agent loop 明确将它禁用，因为 Python image 没有 `/reset-state` endpoint。

这意味着 Task B 观察到的可能是 `E₀ + S₁`（前一个任务的残留状态），而不是它声明的 `E₀`。有状态工具会跨 task 污染，trial 也因此不独立。

#### SOTA 表现

在 1000 个任务的完整集合上，表现最好的模型 Claude Opus 4.5 达到 62.3% 的成功率。前沿模型的通过率超过 50%，主要失败原因是工具使用不足和任务理解不够。

### 6. MCPMark——服务状态测试

#### 数据规模与类型

MCPMark 包含 177 个任务，其中 127 个 standard、50 个 easy。每个任务由三份文件构成：

- `description.md`：Agent 可见任务；
- `meta.json`：task id、category、difficulty、初始 state locator；
- `verify.py`：对服务终态的程序化检查。

它覆盖 Filesystem、GitHub、Notion、Playwright、Postgres 等多种服务类型，每个环境有 20–30 个任务。

#### 任务设计

MCPMark 的核心不是比较最终回复，而是验证服务终态：

```text
setup target service state
→ run task
→ verify.py against service
→ cleanup seeded state
```

Agent 可以使用任意合理调用序列，只要最终服务状态正确。这种结构特别适合 Notion、GitHub、Postgres、filesystem 和浏览器任务。

MCPMark Verified 版本进一步将每个服务器固定到精确版本，每个验证脚本都经过审查和收紧，确保正确解决方案通过、错误解决方案失败，并尽量跨运行和随时间保持一致。

#### 环境设计

MCPMark 采用 `setup → agent → verify → cleanup` 的服务状态测试流程。`src/services.py` 是服务名称、setup 与连接方式的单一真源。

隔离方式是 setup/cleanup 加服务级状态，但 cleanup 失败、重复对象、全局搜索命中其他 task 等问题仍然存在。

#### SOTA 表现

|模型|`Pass@1`|`Pass^4`|平均轮数|
|---|---:|---:|---:|
|GPT-5-medium|52.56%|33.86%|约 16.2|
|Claude Sonnet 4|< 30%|< 15%|—|
|O3|< 30%|< 15%|—|

平均每个任务需要 16.2 次执行轮和 17.4 次工具调用。MCPMark 的难度显著高于更早的 MCP 基准，如 MCPEval 和 LiveMCPBench。

### 7. OfficeQA——企业级文档推理

#### 数据规模与类型

OfficeQA 是一个基于美国财政部公报（U.S. Treasury Bulletin）的财务问答基准，覆盖 1939–2025 年近 100 年的历史数据。语料库包含 89,000 页、超过 2600 万个数值；OfficeQA Pro 包含 133 个问题，OfficeQA Full 包含 246 个问题。

自 2026 年 5 月起，benchmark CSV、PDF、parsed JSON/TXT 都移到门控 Hugging Face 数据集。

#### 任务设计

OfficeQA 评估 AI Agent 在大型异构文档语料上的 grounded multi-document reasoning，即基于事实的多文档推理。问题需要精确的文档解析、检索，以及跨非结构化文本与表格数据的分析推理。

仓库本身不规定 Agent loop、工具、context budget、并发、resume 或 sandbox。这意味着：如果两个论文都说“跑 OfficeQA”，一个给 Agent oracle pages，另一个让 Agent 在 86 年文档中检索，它们测的并不是同一件事。

#### 评分机制

评分使用 `score_answer(ground_truth, prediction, tolerance)`，基于数值容差或文本匹配。单位缺失是 wildcard，也就是说“回答是否携带必要单位”不在 reward 保证范围内。

#### SOTA 表现

|设置|前沿模型表现|
|---|---:|
|仅参数知识|< 5% accuracy|
|加网络访问|< 12% accuracy|
|直接提供文档语料|约 34.1% average|
|结构化文档表示（`ai_parse_document`）|约 39.6% average，提升 16.1% relative|

Agent 的难点是长时间跨度、密集表格、跨页表头、单位和历史口径变化。即使提供完整文档语料，前沿 Agent 也只能答对约三分之一的问题。

### 10. SpreadsheetBench 2——端到端电子表格工作流

#### 数据规模与类型

SpreadsheetBench 2 包含 321 个任务，分为四大类：

- **Debugging**：公式调试和错误修正；
- **Financial Model**：财务建模和计算；
- **Template**：模板化电子表格操作；
- **Visualization**：图表生成和数据可视化。

每个实例平均 11.8 个工作表，需要 593.5 个单元格修改，反映具有跨表依赖的复杂多工作表工作簿。数据来源于真实商业数据，包括财务报告和公司文件，由领域专家注释和验证，专家投入超过 1500 小时。

#### 任务设计

它评估的是工作流级别的任务，而不是孤立操作。任务要求：

1. 通过多步协调操作完成工作流目标；
2. 在复杂多工作表工作簿中进行跨表推理；
3. 产生交付物级别的成果，包括结构化模型、修复的电子表格和准确的可视化。

#### 评分机制

Financial Modeling、Template 和 Debugging 使用确定性的单元格比较。先根据 golden 与 input 的差异，把 answer range 中的 cells 分成：

- `modification cells`：任务要求改变的格子；
- `regression cells`：不应改变、需要保留的格子。

最终只有两类 ratio 都为 1，`accuracy` 才为 1。为容忍少量电子表格引擎差异，regression ratio 达到 99.8% 会提升为 1；modification 没有同样豁免。

Visualization 任务使用 VLM checklist 评估。每个任务有参考答案和断言清单，VLM（GLM-4.6V）评估生成的图表图像，分数是 `Passed Assertions / Total Assertions`，70 分以上视为正确。

#### 环境设计

SpreadsheetBench 2 使用 SWE-agent 作为 Agent scaffold，通过 `bash`、`view_xlsx` 和 `submit` 三个工具与电子表格交互。运行在 Docker 容器中，挂载前按名称剔除 golden 文件，防止 Agent 直接打开标准答案。

#### SOTA 表现

|模型|Overall Acc.|Financial Modif.|Debugging Acc.|Visualization|
|---|---:|---:|---:|---:|
|Claude Opus 4.6|34.89%|89.69% / 34.0% Acc|50.38% / 12.0% Acc|—|
|GPT-5.2|约 25–30%|—|—|—|
|GLM-5|约 17%|—|—|—|

最佳模型整体准确率仅 34.89%，debugging 准确率低至 12%。失败主要原因是电子表格检查不足和目标单元格选择错误。Modification 分数 89.69% 远高于 Accuracy 34%，说明模型能改对大部分目标单元格，但很难做到“所有该改的都改对、所有不该改的都没改坏”。

### 11. Toolathlon——长链工具任务

#### 数据规模与类型

Toolathlon-Verified 包含 108 个任务、604 个工具，跨越 32 个软件应用，从 Google Calendar、Notion 等日常平台到 WooCommerce、Kubernetes、BigQuery 等专业应用。每个任务平均需要约 20 次交互轮次，要求与多个应用交互。

#### 任务设计

每个任务目录可以包含可见 task prompt 与 initial workspace、preprocessing 脚本、token/key session、groundtruth workspace、task-specific evaluation command，以及需要的 MCP servers 与 local tools。

Toolathlon 是 11 个项目中对“Agent 会主动找 grader 或改 grader”威胁建模最完整的一类。标准 containerized 模式把每个 task 放进独立容器；decoupled 模式让环境留在容器、Agent loop 跑在 host，便于替换 Agent framework。

#### 环境设计

Toolathlon 采用 hardened runner stash/restore grader 与 ground truth，并校验 hash，实现强 artifact 隔离。containerized hardened 和 decoupled 两种模式支持不同测试需求；checkpoint、artifact hash 与宿主状态支持 resume 身份验证。

#### SOTA 表现

|模型|`Pass@1`|`Pass@3`|`Pass^3`|平均轮数|工具调用数|
|---|---:|---:|---:|---:|---:|
|Kimi K3（max）|76.5%|83.3%|68.5%|22.8|39.1|
|Claude Opus 4.8（max）|76.2%|84.3%|66.7%|19.9|36.3|

Toolathlon 是所有 benchmark 中 SOTA 分数最高的之一，`Pass@1` 达到 76% 以上。但 `Pass^3` 比 `Pass@3` 低约 15–17 个百分点，说明一致性仍然是问题：三次独立试验全部通过的概率显著低于至少通过一次的概率。

DeepSeek-V4-Flash 在 Toolathlon-Verified 上达到 70.3%，也验证了开源模型在工具使用任务上的快速进步。

## 横向对比与深度分析

### 一、四种评分机制对比

这 11 个 benchmark 的评分机制可以归纳为四类，每类测量的其实是不同东西：

|评分类型|代表 Benchmark|优点|缺点|
|---|---|---|---|
|Exact outcome grader（精确结果比对）|AutomationBench、ALE（部分）、OfficeQA、SpreadsheetBench 2|便宜、稳定、可调试|reference 必须完整，等价解容易被格式误杀|
|Programmatic service verifier（程序化服务验证）|MCPMark、Toolathlon|接近真实 outcome，不要求固定轨迹|verifier 自己会遇到 API 权限、pagination、索引延迟和 duplicate object|
|LLM / VLM rubric judge（大模型评审）|JobBench、MCP-Atlas、Claw-Eval（部分）、SpreadsheetBench 2（可视化）|能处理报告质量、claim coverage 和视觉美学|引入第二个模型，judge 自身的一致性和校准存疑|
|Trajectory / safety grader（轨迹/安全评分）|Claw-Eval、Toolathlon|适合验证安全边界和 proof-of-work|不应代替 outcome，可能奖励形式主义|

**关键洞察：**最稳妥的优先级是：

```text
outcome → safety → efficiency
```

效率最好作为诊断维度，不要让少调用一步抵消结果错误。同样，trajectory 评分不能替代终态验证：Agent 可能调用了正确工具却写错值，也可能通过另一条合法路径得到正确结果。

### 二、环境隔离机制对比

|状态类型|代表项目|正确 reset 方式|主要风险|
|---|---|---|---|
|单服务状态|MCPMark|每 task setup + cleanup 或 namespace|cleanup 失败、重复对象、全局搜索命中别的 task|
|共享 MCP sandbox|MCP-Atlas|task namespace 或 ephemeral sandbox|并发 task 互相看到 filesystem、memory、git|
|远程公共状态|Toolathlon（Cloud/Gmail 等）|task-specific prefix + 时间窗 + cleanup|eventual consistency、旧对象、共享配额|
|内存对象|AutomationBench|每 task 新建状态对象|几乎无，确定性最高|

一个好的 task 定义应明确写出：

```text
state_owner
reset_scope
cleanup_verification
```

只写“容器化”不够：容器名称如果没有 lease，仍然不是隔离；只写“共享 sandbox 性能足够”也不够，因为容量隔离与状态隔离是两个问题。

### 三、SOTA 分数全景与难度梯度

|Benchmark|SOTA 分数|分数含义|难度等级|
|---|---:|---|---:|
|MCPMark（Verified）|94.5% `pass@1`|服务终态验证通过率|⭐⭐|
|MCP-Atlas|84.7% pass rate|Claim coverage 通过率|⭐⭐⭐|
|Toolathlon（Verified）|77.9% `Pass@1`|端到端任务通过率|⭐⭐⭐|
|OfficeQA Pro|69.9%|问答准确率|⭐⭐⭐⭐|
|JobBench|57.4%|加权 rubric 通过率|⭐⭐⭐⭐|
|SpreadsheetBench 2|34.8%|所有单元格全对率|⭐⭐⭐⭐|
|AutomationBench|30.8%|`WorldState` assertion 全过率|⭐⭐⭐⭐|
|ALE|29.6% pass rate|任务通过率|⭐⭐⭐⭐⭐|

这些分数不可直接横向比较。每个 benchmark 的任务难度、评分严格度和环境复杂度不同，分数不代表难度的线性比例；比较只能在同一个 benchmark、同一个设置和同一个版本下进行。

### 四、已发现的根因级风险

基于对 11 个 benchmark 的静态源码审计，以下问题会改变实验语义：

|严重度|Benchmark|问题|影响|
|---:|---|---|---|
|P0|MCP-Atlas|默认并发共享 sandbox，`/reset-state` 未实现且调用被禁用|有状态工具跨 task 污染，trial 不独立|
|P1|JobBench|失败后仍回收半成品，目录非空即 resume complete|timeout/失败被永久跳过|
|P1|MCP-Atlas|把 `ERROR:` 行的 task_id 也视为 done|临时 HTTP/timeout 错误永久固化|
|P1|MCPMark|itinerary 在核心数据库核验异常时返回 success|服务故障可能变成假阳性|
|P1|Toolathlon|CSV “accuracy” 实际只算 precision|可漏掉 25%–45% 的应预警学生|
|P1|JobBench|信任 `rubric_passed`，不重算 criterion invariant|judge 自相矛盾时整项误得分|
|P2|AutomationBench、ALE|README 数量与当前源码目录漂移|“跑全量”的集合可能含义不同|
|P2|OfficeQA|单位缺失是 wildcard|无单位答案可能通过|

这些问题不等于所有公开分数都无效；它们说明的是：如果基础设施故障、状态污染和 grader 异常没有从模型失败中分离，结果就无法回答“模型到底做得好不好”。

## General Task Agent 当前进展与核心瓶颈

### 一、当前进展：我们站在哪里

#### 1. 单工具 / 单服务任务已相当成熟

在工具使用的基础层，前沿模型已经表现出相当强的能力：

- Toolathlon-Verified 上 `Pass@1` 达到 76.5%（Kimi K3），大部分单应用任务可以稳定完成；
- MCP-Atlas 上 Claude Opus 4.5 达到 62.3%，在 300+ 工具的大规模工具集中仍能找到并使用正确工具；
- MCPMark 上 GPT-5-medium 达到 52.6% `pass@1`，在真实服务状态验证下仍有过半任务一次通过。

这说明工具发现、基本参数填充、单步操作已经不是主要瓶颈。模型能理解工具描述、找到正确工具、填对参数并处理基本错误。

#### 2. 工具编排能力显著提升

多步工具编排也有明显进步：

- MCPMark 平均 16.2 轮执行、17.4 次工具调用，最强模型仍能保持过半通过率；
- Toolathlon 平均 20+ 轮交互、39 次工具调用，`Pass@1` 仍能到 76%；
- SpreadsheetBench 2 平均 593.5 个单元格修改，Financial Modeling 的 Modification 分数达到 89.69%。

模型已经能规划并执行相当长的工具调用序列，不再是“调用一两次工具就卡住”的阶段。

#### 3. 闭源 vs 开源：差距在缩小但仍显著

从多个 benchmark 看，闭源模型整体优于开源模型，但差距在快速缩小：

- SpreadsheetBench 2：闭源 23.68%–34.89%，开源 7.17%–17.14%；
- Toolathlon：DeepSeek-V4-Flash 达到 70.3%，与闭源 SOTA 76.5% 的差距已缩小到 6 个百分点；
- AutomationBench：DeepSeek-V4-Flash 达到 25.1%（公开设置）。

开源模型在工具使用类任务上的进步速度很快，尤其是在工具接口明确、环境确定性的场景中。

#### 4. Agent scaffold 对结果影响巨大

SpreadsheetBench 2 的实验清楚地展示了这一点：固定 GLM-5 模型时，SWE-agent-based scaffold 显著优于三个通用 coding agent scaffold（Claude Code、Kilo Code、Cline）。Modification 分数可能相近，但 task-level accuracy 差距很大；通用 coding scaffold 在端到端正确性上弱得多。

这说明 Agent 框架设计本身就是能力的一部分。工具接口设计、观察—推理—行动循环的结构和错误处理机制，都会显著影响最终表现。

### 二、核心瓶颈：为什么端到端通过率这么低

#### 瓶颈 1：长程任务的错误累积效应

这是最根本的瓶颈。几乎所有 benchmark 都显示同一个模式：任务越长，通过率越低。

|Benchmark|证据|
|---|---|
|SpreadsheetBench 2|Financial Modification 89.69% → Accuracy 仅 34%|
|Toolathlon|`Pass@1` 76.5% → `Pass^3` 68.5%，一致性下降|

数学上很直观：如果每步有 95% 的成功率，12 步后只剩 54%，20 步后只剩 36%，50 步后只剩 7.7%。长任务的端到端通过率会随着步数增加呈指数级下降。

**核心矛盾：**Agent 的每一步都有小概率出错，而任务越长，累积错误的概率越高。当前 Agent 缺乏有效的自我验证和错误恢复机制，做错了往往不知道自己错了，继续往下做，最后越走越偏。

#### 瓶颈 2：状态管理与环境隔离的脆弱性

从 benchmark 设计本身的问题，可以反推 Agent 在真实环境中会遇到的问题：

- **并发串扰**：MCP-Atlas 的共享 sandbox 问题，本质上反映“多任务共享状态时如何保证隔离”的困难；
- **Reset 不彻底**：cleanup 失败、残留对象、索引延迟，在 benchmark 中是评分问题，在生产中就是数据污染；
- **状态漂移**：Toolathlon 的远程公共状态问题，反映环境版本不一致导致结果不可复现的普遍挑战。

Agent 在真实环境中工作时，状态管理是比工具调用更底层的能力。能不能正确理解当前状态、能不能从异常状态恢复、能不能保证操作的原子性，都是当前薄弱环节。

#### 瓶颈 3：多应用 / 跨系统协调能力弱

长任务的错误累积效应非常显著：

- 单应用任务平均分约 53%；
- 双应用任务平均分约 40%；
- 三应用任务平均分约 30%；
- 四应用任务平均分约 20%。

每多一个应用，分数就掉一截。这不是简单的“步骤更多所以更难”，而是跨系统协调本身就是一个独立难点：

- 需要理解不同系统的数据模型和操作语义；
- 需要在系统之间映射数据，包括格式转换和字段对应；
- 需要处理跨系统一致性：A 系统改了，B 系统要不要同步；
- 需要处理部分失败：A 成功了、B 失败了怎么办。

当前 Agent 更多是在“一个系统里做一系列操作”，而不是“在多个系统之间协调完成一个业务流程”。

#### 瓶颈 4：鲁棒性与一致性不足

`Pass@k` 和 `Pass^k` 的差距是衡量一致性的关键指标：

|Benchmark|`Pass@k`|`Pass^k`|差距|
|---|---:|---:|---:|
|MCPMark（`k=4`）|52.6%|33.9%|约 18.7 pp|
|Toolathlon（`k=3`）|83.3%|68.5%|约 14.8 pp|
|Claw-Eval（`k=3`，错误注入）|—|—|下降最多 24 pp|

“三次里至少过一次”和“三次全都过”之间有巨大差距。这意味着：

- Agent 的成功有相当大的运气成分；
- 同样的任务，有时候能做对，有时候做不对；
- 在错误注入或环境扰动下，成功率会大幅下降。

对于生产环境，一致性可能比单次成功率更重要。用户需要的是“每次都能可靠完成”，而不是“试三次可能有一次能成”。

#### 瓶颈 5：安全与越界行为

Claw-Eval 的发现很关键：轨迹不透明评测遗漏了 44% 的安全违规。也就是说，只看最终结果，将近一半的安全问题都发现不了。

当前 Agent 在完成任务过程中经常会“走捷径”：调用不该调用的工具、访问不该访问的数据、修改不该修改的状态。如果只看最终结果对不对，这些问题都会被掩盖。

在真实场景中，安全违规的代价可能远高于任务没完成。但当前 benchmark 设计和 Agent 训练还没有把安全放在与正确性同等重要的位置。

#### 瓶颈 6：评分器可靠性本身就是问题

这是一个元问题：我们用什么来判断 Agent 做得对不对？

- **LLM judge 不一致**：JobBench 信任 `rubric_passed` 但不重算 criterion invariant，judge 自相矛盾时整项误得分；
- **Verifier fail-open**：MCPMark itinerary 在核心数据库核验异常时返回 success，服务故障变成假阳性；
- **单位 / 格式误判**：OfficeQA 单位缺失是 wildcard，无单位答案可能通过；
- **等价解被误杀**：精确匹配的 grader 经常把格式不同但语义等价的答案判错。

如果评分器本身不可靠，leaderboard 上的分数就更不可靠。这是整个领域的基础设施问题。

### 三、各维度难度梯度

综合 11 个 benchmark，可以大致画出 General Task Agent 的难度梯度：

|难度层级|任务特征|代表 Benchmark|SOTA 水平|
|---|---|---|---:|
|L1：入门|单服务 CRUD 操作，步骤少，确定性高|MCPMark 简单任务、MCP-Atlas 简单任务|70%+|
|L2：基础|单应用多步操作，基本工具编排|Toolathlon 大部分任务、OfficeQA Pro|60–75%|
|L3：中等|多工具编排、专业交付物，需要一定领域知识|JobBench、SpreadsheetBench 2、MCPMark|35–55%|
|L4：困难|跨应用工作流、长周期任务、复杂状态管理|ALE、AutomationBench|25–35%|

当前前沿 Agent 大致位于 L2–L3；在 L4 上能取得部分进展但很少完全成功，L5 基本还处于“能做但经常做不完”的阶段。

### 四、未来方向：瓶颈在哪里突破

#### 1. 自我验证与错误恢复

如果 Agent 能在每一步之后验证自己做对了没有，发现错了就回退或修正，错误累积效应会大大减弱。这需要：

- 更好的状态理解能力，知道“正确的状态应该是什么样”；
- 内置的验证机制，做完一步自动检查结果；
- 回退和重试能力，发现错了能回到上一个正确状态。

#### 2. 更可靠的状态管理

把状态管理从“隐式假设”变成“显式工程”：

- 操作的原子性和事务性；
- 状态快照和回滚；
- 并发安全和隔离。

#### 3. 跨系统协调框架

从“单系统操作”升级到“多系统编排”需要：

- 统一的数据模型和映射层；
- 跨系统的事务和一致性保证；
- 部分失败的处理策略，包括补偿事务和重试队列。

#### 4. 一致性优先的训练

从“追求单次最高准确率”转向“追求多次稳定成功率”：

- `Pass^k` 比 `Pass@k` 更重要；
- 鲁棒性训练，包括错误注入和环境扰动；
- 不确定性估计，知道自己什么时候不确定。

#### 5. 安全与合规内置

安全不是事后检查，而是设计时就内置：

- 工具权限的最小化原则；
- 操作的可审计性；
- 安全边界的主动学习。

## 总结

General Task Agent 领域正处于一个关键转折点：

- 基础能力已经相当成熟，单工具、单服务、短任务的表现已经很好；
- 端到端长任务仍然很弱，一旦任务变长、变复杂、跨系统，成功率就急剧下降；
- 核心瓶颈不是“会不会用工具”，而是错误累积、状态管理、跨系统协调、一致性和安全；
- Benchmark 本身也在快速进化，从简单的工具调用测试走向更真实、更复杂、更严格的系统级评测。

下一阶段的突破，可能不只在于模型本身变得更聪明，也在于 Agent 系统变得更可靠：更好的自我验证、更好的状态管理、更好的错误恢复和更好的一致性保证。

用户需要的不是“有时候能做对”的 Agent，而是“每次都能可靠完成”的 Agent。

> **一句话总结：General Task Agent 已经从“会不会用工具”进入“能不能可靠地做完一整件事”的阶段。工具使用不是问题，长程可靠性才是。**

## 附录：四大前沿模型 SOTA 对比（官方数据）

本章节对比 Kimi K3、Claude Opus 5、Claude Fable 5、GPT-5.6 Sol 四大前沿模型在纯工具 / 文本类 Agent Benchmark 上的表现。数据截止 2026 年 8 月 5 日。

“—”表示该模型暂无此 Benchmark 的官方公开数据。不同 Benchmark 的评测设置、Harness 和评分机制不同，分数不可直接横向比较；Toolathlon / Toolathlon-Verified、OfficeQA / OfficeQA Pro 也不是同一版本。

### 一、四大模型 SOTA 分数总览

|Benchmark|GPT-5.6 Sol|Claude Opus 5|Kimi K3|Claude Fable 5|数据来源|
|---|---:|---:|---:|---:|---|
|ALE（Pass Rate / Score）|30.6% / 53.6%|—|28.3% / 51.6%|25.7% / 48.7%|Snorkel AI 官方|
|AutomationBench|—|—|30.8%|17.4%（private held-out）|各厂商官方|
|Claw-Eval|—|—|—|—|暂无公开数据|
|JobBench|—|—|52.9%|—|Moonshot 官方|
|MCP-Atlas|—|85.8%|84.2%|83.3%|各厂商官方|
|MCPMark|—|—|—|—|暂无公开数据|
|OfficeQA Pro|—|—|63.3%|57.9%（Databricks 评测）|各厂商官方|
|SpreadsheetBench 2|—|—|34.8%|—|Moonshot 官方|
|Toolathlon（Pass@1）|58%（非 Verified）|—|76.5%（Verified）|61.7%（内部 Harness）|各厂商官方|

### 二、各模型已公开的 Agent Benchmark 数据

#### GPT-5.6 Sol（OpenAI 官方）

- ALE：30.6% Pass Rate / 53.6% Score（Codex harness，XHigh）；
- Toolathlon：58%（非 Verified 版本）；
- Terminal-Bench 2.0：91.9%；
- BrowseComp：92.2%。

#### Claude Opus 5（Anthropic 官方 System Card）

- MCP-Atlas：85.8% pass rate / 89.1% mean claim coverage；
- Toolathlon-Verified：80.6% `Pass@1` / 87.0% `Pass@3` / 73.1% `Pass^3` / 23.5 平均轮次；
- AutomationBench：26.0%；
- OfficeQA Pro：66.9%；
- OfficeQA：78.1%（标准版）；
- BrowseComp：90.8%；
- DeepSearchQA：95.0%。

#### Kimi K3（Moonshot AI 官方发布博客）

- ALE：28.3% Pass Rate / 51.6% Score（Kimi Code harness，Max）；
- MCP-Atlas：84.2%；
- Toolathlon-Verified：73.2%（benchlm.ai）/ 76.5%（Toolathlon 官方）；
- AutomationBench：30.8%；
- JobBench：52.9%；
- SpreadsheetBench 2：34.8%；
- OfficeQA Pro：63.3%；
- Terminal-Bench 2.0：88.3%；
- BrowseComp：91.2%；
- DeepSearchQA：95.0%。

#### Claude Fable 5（Anthropic 官方 + Snorkel AI）

- ALE：25.7% Pass Rate / 48.7% Score（Claude Code harness，XHigh）；
- Toolathlon：61.7% `Pass@1` / 68.5% `Pass@3` / 55.6% `Pass^3`（非 Verified 版本，非官方来源）。

### 三、数据来源

|来源|类型|覆盖模型|覆盖 Benchmark|更新时间|
|---|---|---|---|---|
|Moonshot AI Kimi K3 发布博客|官方|Kimi K3|AutomationBench、MCP-Atlas、JobBench、SpreadsheetBench 2、OfficeQA Pro、Toolathlon-Verified 等 10 项|2026 年 7–8 月|
|Anthropic Claude Opus 5 System Card|官方|Claude Opus 5|MCP-Atlas、Toolathlon-Verified、AutomationBench、OfficeQA Pro 等 18 项|2026 年 7–8 月|
|OpenAI GPT-5.6 官方发布|官方|GPT-5.6 Sol|Toolathlon、Terminal-Bench 2.0、BrowseComp 等 6 项|2026 年 7–8 月|
|Snorkel AI Leaderboard|官方|全部|ALE|2026 年 7–8 月|
|Toolathlon 官方 Leaderboard|官方|全部|Toolathlon-Verified|2026 年 7 月|

第三方聚合排行榜的数据来源和评测设置可能与官方不一致，分数仅供参考。不同 Benchmark、不同设置下的分数不可直接比较。

## 附录 B：9 大纯工具 / 文本类 Benchmark 速览

本附录聚焦 9 个纯工具调用 / 文本推理类 Benchmark，移除 OSWorld V2 和 SaaS-Bench 两个以视觉 / GUI 操作为核心的 benchmark，以便更直观地对比 General Task Agent 在工具使用、任务规划和状态管理上的核心能力。

### 一、速览总表：任务 / 工具 / 难点

|Benchmark|典型任务示例|核心工具 / 环境|核心难点|
|---|---|---|---|
|ALE|为初创公司制作季度财务报表；起草商业租赁合同；分析市场调研数据并撰写报告|VM 完整文件系统；办公应用套件；55 个子行业专业工具|长周期任务（小时级）；跨领域专业知识；强时间隔离；经济价值导向|
|AutomationBench|从 CRM 同步新客户到邮件营销列表；根据支持工单创建日历事件并分配工程师；跨系统对账|47 个 SaaS 工具 REST API；Sales / Marketing / Ops / Support / Finance / HR 六大领域；内存 `WorldState`|自主 API 发现；跨应用协调；策略文档遵循；无关或误导性记录|
|Claw-Eval|编排多个微服务完成订单处理；多轮法律 / 医疗专业咨询；错误注入下的鲁棒性测试|Docker mock services；Host agent + HTTP tools；9 类别 / 3 大组|完成度 × 安全 × 鲁棒性；轨迹透明评分；44% 安全违规被传统评测遗漏；`Pass@k` 与 `Pass^k` 差距|
|JobBench|产品经理撰写 PRD；数据分析师构建销售仪表盘；人力资源设计招聘流程方案|CLI agent + 临时工作目录；35 个白领职业；加权 rubric|专业交付物质量；LLM judge 一致性；失败后半成品回收；目录隔离与 resume|
|MCP-Atlas|从数据库查询数据并生成图表报告；跨多个 MCP 服务编排工作流；处理 API 调用失败|36 个真实 MCP 服务器；论文口径 220 个工具；Python sandbox + TypeScript harness|工具发现与选择；3–6 步多工具编排；参数化正确性；P0 并发共享 sandbox 状态污染|
|MCPMark|用 Playwright 完成网页认证；在 Notion 创建项目跟踪数据库；从 GitHub 提取数据存入 PostgreSQL|5+ MCP 服务类型；Filesystem / Notion / GitHub / PostgreSQL / Playwright；setup → agent → verify → cleanup|服务状态验证；长链工具调用（平均 16.2 轮）；`Pass@k` 与 `Pass^k` 差距；核心数据库核验异常时 fail-open|
|OfficeQA|查找 1975 年第三季度美国国债收益率；计算 1990–2000 年财政赤字年均增长率；对比两个时期的税收结构|89k 页 / 2600 万数值文档；美国财政部公报 1939–2025；文档检索 + 数值推理|大规模文档定位；跨文档多步推理；数值计算精度；数据漂移与格式变化|
|SpreadsheetBench 2|调试财务模型公式；从零构建三表联动模型；根据模板填充数据并生成图表|SWE-agent + shell / 表格环境；Docker 隔离；Debugging / Financial / Template / Visualization|端到端工作流；Cell diff（修改 + 回归）；财务模型 debugging 极难；可视化需要 VLM 验证|
|Toolathlon|从 Canvas LMS 导出并分析成绩；跨 WooCommerce、邮件和 Google Sheets 处理订单；在 Notion 创建项目看板|32 个 MCP 服务器 / 604 个工具；Canvas、Email、WooCommerce、GitHub、Notion、Google、Snowflake、BigQuery、arXiv、文档工具；容器化 hardened runner|长链工具任务；多应用状态协调；确定性评分；Containerized 与 Decoupled 模式选择|

### 二、按难度梯度分类

#### L1–L2 入门级：70%+ SOTA

单服务 CRUD、简单工具调用、确定性任务。代表是 MCPMark 简单任务和 Toolathlon 基础任务。

#### L3 中等：35–60% SOTA

多工具编排、专业交付物、需要一定领域知识。代表是 MCP-Atlas（62.3%）、JobBench（45.9%）和 SpreadsheetBench 2（34.9%）。

#### L4–L5 困难：< 30% SOTA

长周期任务、跨系统协调、复杂状态管理和端到端完成。代表是 ALE（30.6% pass rate）、AutomationBench（< 10%）以及 Claw-Eval 的安全鲁棒性维度。

### 三、核心洞察

#### 洞察 1：工具数量 ≠ 难度

Toolathlon 有 604 个工具但 SOTA 达到 76.5%，而 ALE 工具数量更少但 SOTA 只有 30.6%。难度的关键不在工具多少，而在任务长度、状态管理复杂度和专业知识要求。

#### 洞察 2：评分机制决定分数天花板

- 精确结果匹配（cell diff / 程序验证）：分数最可靠，但天花板低；
- LLM judge / rubric：分数较高，但一致性存疑；
- 轨迹透明评分（Claw-Eval）：发现 44% 的安全违规被传统评测遗漏。

不同评分机制下的分数不可直接比较。

#### 洞察 3：环境隔离是被低估的维度

从内存对象（AutomationBench）到单容器（MCPMark）、共享 sandbox（MCP-Atlas）再到完整 VM（ALE），隔离强度递增，评测可信度也递增。MCP-Atlas 的并发共享 sandbox 问题可能导致分数虚高。

#### 洞察 4：一致性比单次通过率更重要

`Pass@k` 表示 k 次中至少 1 次通过，`Pass^k` 表示 k 次全部通过。MCPMark `k=4` 时，`Pass@4` 为 52.6%，`Pass^4` 为 33.9%，差距接近 20 个百分点。生产环境需要的是 `Pass^k`，而不是 `Pass@k`。

[feishu-doc]: https://feishu.doubao.com/docx/RpYXddP8To2VYixbxhxcAUn3ncf?enter_from=public_link
[ale-lifecycle]: https://github.com/rdi-berkeley/agents-last-exam/blob/2d4d2205c255/ale_run/orchestration/lifecycle.py
[automation-world]: https://github.com/zapier/AutomationBench/blob/4a8e10612540/automationbench/schema/world.py
[claw-scoring]: https://github.com/claw-eval/claw-eval/blob/5680b8b11ff2/src/claw_eval/models/scoring.py
[job-runner]: https://github.com/Job-Bench/job-bench-eval/blob/bbeae9de5d2f/eval/run_benchmark_claude_code_cli.sh
[atlas-loop]: https://github.com/scaleapi/mcp-atlas/blob/f24ba3fb0bfa/services/agent-harness/src/mcp-agent/agent-evals/agent-eval.ts
[mcpmark-evaluator]: https://github.com/eval-sys/mcpmark/blob/cd45b7f57923/src/evaluator.py
[officeqa-reward]: https://github.com/databricks/officeqa/blob/e155e210fcb5/reward.py
[spreadsheet-eval]: https://github.com/RUCKBReasoning/SpreadsheetBench-2/blob/599b24aa4792/evaluation/evaluation.py
[toolathlon-guard]: https://github.com/hkust-nlp/Toolathlon/blob/2aed2468858f/scripts/containerized/task_artifact_guard.py
