---
title: "Anthropic RSI, Loops, and Managed Agents"
public: true
description: "三篇 Anthropic/Claude 文章串起来看：近端 RSI 更像 AI R&D 被 loops、persistent sessions、sandbox、vault、eval 和人类 judgment 共同加速，而不是模型神秘地直接重写自己。"
type: paper-reading
date: 2026-07-08
paper_title: "When AI builds itself / Getting started with loops / The evolution of agentic surfaces"
venue: "Anthropic Institute / Claude Blog"
year: "2026"
status: "reading"
source_url: "https://www.anthropic.com/institute/recursive-self-improvement"
source_urls:
  - "https://www.anthropic.com/institute/recursive-self-improvement"
  - "https://claude.com/blog/getting-started-with-loops"
  - "https://claude.com/blog/building-with-claude-managed-agents"
---

# Anthropic 的 RSI 三件套：自我改进、循环和托管 agent

- **Source 1**: [When AI builds itself](https://www.anthropic.com/institute/recursive-self-improvement), Anthropic Institute, 2026。页面未显式标注发布日期；文中核心证据集中在 2026.04-2026.05。
- **Source 2**: [Getting started with loops](https://claude.com/blog/getting-started-with-loops), Claude Blog, 2026-06-30。
- **Source 3**: [The evolution of agentic surfaces: building with Claude Managed Agents](https://claude.com/blog/building-with-claude-managed-agents), Claude Blog, 2026-06-10。
- **原文体量**: 三篇合计约 **9300 words**。RSI 文章约 **5500 words**，loops 约 **1300 words**，Managed Agents 约 **2500 words**。
- **关键词**: recursive self-improvement, AI-driven AI R&D, loops, Claude Code, `/goal`, `/loop`, `/schedule`, Managed Agents, session log, vault, sandbox, Dreaming, Amdahl's law。

## 读法：给人和 agent 的路标

这三篇最好不要分开读。RSI 那篇回答 **为什么这件事重要**：AI 已经在加速 AI 研发本身，未来可能把人类从执行者压缩成目标设定者、审查者和瓶颈修复者。Loops 那篇回答 **怎样把 agent 的行动变成可控循环**：触发、执行、验证、停止，每个环节都要显式设计。Managed Agents 那篇回答 **怎样把循环放进生产环境**：有隔离的 sandbox，有不暴露给代码的 credentials，有可恢复的 session log，有 observability，有随模型演进的 harness。

所以这篇笔记的主线是：

```text
RSI 压力：AI 开始加速 AI R&D
  -> loop 原语：把一次次行动变成可停止、可验证的循环
  -> managed runtime：把循环放到持久、隔离、可审计的生产环境
  -> 人类角色：taste、verification、bottleneck selection
```

如果只想快速 get 到重点，读 **一句话判断**、**结构图**、**关键数字表** 和 **对我的 wiki/paper-reading pipeline 的启发**。如果要真的拿去设计自己的 agent 系统，再读 loops 和 Managed Agents 两节。

## 一句话判断

Anthropic 这三篇合起来的判断是：近端 recursive self-improvement 不一定先表现为“模型直接改自己的权重”，更可能先表现为 **AI 把 AI R&D 里的执行部分自动化**，同时由 loops、评测、日志、sandbox、权限和人类 judgment 组成一个越来越强的工程闭环。

这里的关键不是神秘的“自我意识式自举”，而是很工程的东西：模型能写代码、跑实验、看日志、修 bug、复现实验、并行委托；系统能保存完整轨迹、隔离执行、控制凭证、自动审查；人类开始把时间从“亲手做”转到“选择什么值得做、怎样验证、哪里该停”。这就是短期更可信的 RSI 表面。

## 先看结构图

![Anthropic RSI, loops, and Managed Agents map]({{ '/assets/paper-reading/anthropic-rsi-loops-managed-agents/rsi-loops-managed-agents.svg' | relative_url }})

这张图的读法有三个锚点：

- **RSI 压力来自执行成本下降**：代码、实验、复现、debug 这些“做事”的部分变得越来越便宜，瓶颈就会往上游移动。
- **Loops 是控制原语**：一个 agent 不是“prompt 一下就完”，而是被 trigger、stop condition、verification 和 artifacts 约束住的循环。
- **Managed Agents 是生产底座**：真正上线时，agent 需要 sandbox、vault、session log、resume、observability，而不是一个随容器死亡的脚本进程。

## 1. RSI 文章到底在说什么

Anthropic Institute 的 RSI 文章不是说“完整 recursive self-improvement 已经发生了”。它的更强说法是：**AI 已经在加速 AI 系统的开发，并且这种加速可能比制度准备速度更快。**

文章把 AI 研发拆成两类工作：

- **Engineering**：写代码、改基础设施、跑训练、修工具、处理 incident。
- **Research**：决定跑什么实验、解释结果、判断下一步、知道哪个方向值得继续。

现在 Claude 已经很擅长第一类，也开始侵入第二类里的“执行一个明确实验”。但真正的缺口仍然在 **judgment**：选什么问题、怎么定义成功、看到结果后信不信、什么时候承认方向死了。也就是说，Claude 已经能接过很多“method”，但还没有完全接过“taste”。

这点很重要。很多 RSI 讨论会直接跳到“AI 自己训练下一代 AI”，但 Anthropic 文章实际给的是一条更连续的进化路径：

| 阶段 | 主要形态 | 人类的角色 |
|---|---|---|
| 2021-2023 | 人类写代码和文档，构建早期 Claude | 几乎全流程主导 |
| 2023-2025 | chatbot 帮忙生成短代码片段 | 人类复制、粘贴、整合 |
| 2025-2026 | coding agent 可以直接写和改文件 | 人类给目标、审查结果 |
| today | autonomous agents 能跑代码、委托数小时任务 | 人类管理方向、资源和验证 |
| future | agent 可能构建和训练下一代模型 | 人类转向 oversight、validation、verification |

我的理解是：**RSI 的近端问题不是模型会不会“突然自举”，而是组织会不会在不知不觉中把研发速度推到人类审查和治理跟不上的区间。**

## 2. 关键证据：哪些数字值得记

RSI 文章最有价值的部分是把外部 benchmark 和 Anthropic 内部数据放在一起。数字本身不能无脑当作通用结论，因为很多数据是内部场景、Claude judge 或挑选过的 session；但它们展示了一个方向：执行能力、长任务能力和研究 next-step 能力都在变强。

| 证据 | 数字 | 我会怎么读 |
|---|---:|---|
| autonomous task horizon | 可靠任务长度大约每 4 个月翻倍，早期趋势约每 7 个月翻倍 | 长任务能力在加速，但“可靠完成”取决于任务定义和评测方式 |
| Claude Opus 3, 2024.03 | 可完成约 4 分钟人类任务 | 还像短助手 |
| Claude Sonnet 3.7, 2025 | 可完成约 1.5 小时任务 | 开始像能接小工单的 coding agent |
| Claude Opus 4.6, 2026 | 可完成约 12 小时任务 | 开始触及半天级自主工作 |
| SWE-bench | 两年内从低个位数到接近饱和 | 单一 benchmark 会饱和，所以要持续换更难任务 |
| CORE-Bench | 2024 年约 20% 成功，15 个月后接近饱和 | 复现实验这种科研前置能力被快速自动化 |
| Anthropic 代码占比 | 2026.05 超过 80% merged code 由 Claude authored | 这说明“写代码”本身已经不是主要人力成本；但 LOC 不是质量 |
| Anthropic 工程输出 | 2026 Q2 典型工程师每日 merge 代码量约为 2024 的 8x | 方向可信，倍率要谨慎，因为代码量高估生产力 |
| Anthropic research poll | 130 名 research 员工，median 估计 Mythos Preview 带来约 4x output | 主观数据，但和工程输出方向一致 |
| API error cleanup | Claude ship 800+ fixes，把一类 API error 降低 1000x；人类估计要 4 年 | 最适合 AI 的任务：大量、分散、重复、上下文宽 |
| open-ended task success | 2026.05 达到 76%，6 个月增加 50 个百分点 | Claude judge 判定，仍需注意 judge bias |
| training job incident | 约 2 小时定位 obscure debug flag；平常约 2-3 天 | 很像真实研发里“读日志 + 缩小搜索空间 + 验证”的工作 |
| automated code review | retrospectively 可提前抓住 claude.ai 过去 incidents 中约三分之一 bug | 审查也被 agent 化，人的 review bottleneck 会被部分转移 |
| 小模型训练加速任务 | 2025.05 Opus 4 约 3x，2026.04 Mythos Preview 约 52x；强人类 4-8 小时到 4x | 明确目标 + 明确 correctness check 的实验优化，AI 特别强 |
| open-ended AI safety research | 人类约一周恢复 floor-ceiling gap 的 23%；agents 用 800 cumulative hours 和约 USD 18,000 compute 恢复 97% | 很强，但 humans 选择问题和评分 rubric，且未干净迁移到 production scale |
| research next-step | n=129；Opus 4.5 在 2025.11 胜过人类 detour 选择 51%，Mythos Preview 在 2026.04 达到 64% | 不是公平人机对比，而是“模型是否越来越会选下一步”的早期信号 |

这组数字背后的主线可以压成一句：**doing 在人类时间里变便宜了，judgment 和 verification 开始变贵。**

Anthropic 文章也很清楚地把风险放在这里：如果 Claude 生成代码、实验和 ideas 的速度远快于人类 review，那么组织会遇到 Amdahl's law。你加速了某个环节，整体速度马上被没加速的环节卡住。现在这个环节可能是代码审查、实验解释、优先级选择、安全验证、组织协调。

## 3. Loops：把“能做事”变成可控循环

Claude 的 loops 文章很短，但它是 RSI 文章的工程解释。它把 loop 定义成：**agent 重复执行工作循环，直到满足停止条件。**

这听起来简单，但它把 agent 设计从“怎么 prompt”换成了四个问题：

- **Trigger**：什么时候启动？
- **Work cycle**：每轮做什么？
- **Verification**：怎么知道这轮有没有变好？
- **Stop condition**：什么时候停，而不是一直烧 token？

Claude Code 文中把 loop 分成四类：

| Loop 类型 | 触发方式 | 停止方式 | 适合任务 | 你实际交给 agent 的东西 |
|---|---|---|---|---|
| Turn-based loop | 用户 prompt | Claude 判断完成或需要更多上下文 | 短任务、探索性任务、不固定流程 | 把 **check** 的一部分交给 agent |
| Goal-based loop `/goal` | 手动 prompt | 达成目标或达到最大 turn 数 | 有明确 exit criteria 的任务 | 把 **stop condition** 交给 evaluator |
| Time-based loop `/loop`, `/schedule` | 时间间隔 | 取消、PR merge、队列清空等 | 定时摘要、PR/CI 监控、周期性检查 | 把 **trigger** 交给系统 |
| Proactive loops | 事件或 schedule，无实时人类 | 每个任务达标退出，routine 持续运行 | bug report、issue triage、迁移、依赖升级 | 把 **prompt 和执行流程** 整体交出去 |

这里最值得偷到自己工作流里的不是命令本身，而是 stop criteria 的思想。一个 loop 的质量不取决于它看起来多自动，而取决于它有没有明确的可验证边界。

例如做 paper-reading，可以这样拆：

```text
turn-based:
  读一篇文章，生成初稿，人工看主线是否对

goal-based:
  反复修到满足 checklist：来源链接存在、关键数字可回溯、图表加载、公式渲染、build 通过

time-based:
  每天/每周检查候选 paper、blog、GitHub issues 或 deploy 状态

proactive:
  新 URL 进入 inbox 后自动抽取正文、建素材目录、起草笔记、跑 verifier、打开 PR 或 push
```

Loops 文章还强调了一个容易被忽略的点：**代码库本身的干净程度会影响 agent 输出质量**。Claude 会模仿已有 pattern。如果仓库里路径、命名、front matter、assets、构建方式都很乱，agent 也会跟着乱。这和个人 wiki 很贴：wiki 不是越自动越好，而是越要有稳定目录、清晰模板、可运行的 build check 和能复用的 verifier。

## 4. Managed Agents：把 loop 放进生产基础设施

Managed Agents 那篇可以看成 loops 的生产化版本。核心判断是：**prompt 不能把 agent 带进生产，基础设施才可以。**

一个真正能上线的 agent 至少需要：

- **运行环境**：代码写完在哪里执行？依赖怎么装？网络怎么限制？
- **凭证管理**：agent 怎么访问 GitHub、数据库、MCP、内部系统，又不把 token 暴露给它生成的代码？
- **session 状态**：长任务中断后能不能恢复？历史在哪里？
- **filesystem**：artifacts 放哪里？下次如何接着用？
- **execution isolation**：代码错了或被 prompt injection 诱导时，爆炸半径多大？
- **observability**：跑了一个小时后做出奇怪动作，能不能逐步复原？

文章里最核心的架构句子可以概括成：**decouple brain from hands**。也就是调用 Claude 的 harness 和执行代码的 sandbox 分开。

| 资源 | 它是什么 | 为什么重要 |
|---|---|---|
| Agent | model、prompt、tools、guardrails 的配置 | 定义 agent 是谁、能用什么、边界在哪里 |
| Environment | sandbox container、网络规则、预装包，可以在 Anthropic cloud 或用户自控 infra | 定义 agent 的手在哪里工作 |
| Session | 一次 run，把 agent 和 environment 配对，保存完整 event history、sandbox state 和 outputs | 定义 agent 的记忆、审计轨迹和恢复点 |
| Vault | 独立存 credentials，按需由 proxy 解密和调用 | 让 token 不和生成代码待在同一个容器里 |

为什么这会改变 agent 体验？因为传统做法经常是 harness 和 filesystem 放在同一个 container 里：container 不起来，Claude 不能开始；credentials 离可执行代码太近；container 死了，run 也死了。Managed Agents 则让 Claude 可以先思考，环境并行启动；没有 tool call 的 session 可以不启动容器；完整事件流保存在进程之外。

文章给了几个产品侧数字和例子：

- time-to-first-token 在测试中 p50 降低约 **60%**，p95 降低超过 **90%**。
- Notion early prototype 把约 **12 小时**工作压到 **20 分钟**。
- Rakuten 的 specialist agents 在 product、sales、marketing、finance 等方向，每个约 **一周**上线。
- Sentry 用 Seer debugging agent 加 Claude patch/PR agent，单个工程师在数周内构建。

这些更像产品 case，不是严谨 benchmark；但它们说明了一个现实：当 agent 从 demo 到 production，难点会从“模型会不会回答”转移到“状态、权限、隔离、可观测性、恢复、成本和用户体验”。

还有一个细节我很喜欢：harness 必须跟着模型变。文章举例说 Sonnet 4.5 临近上下文末尾有 “context anxiety”，harness 加了 context reset；到了 Opus 4.5 这个行为消失，reset 反而变成 overhead。这说明 harness engineering 不是一次写死的脚手架，而是随模型行为不断调参的 runtime。

## 5. 三篇连起来的真正主线

把三篇合在一起，Anthropic 其实在讲一个完整 stack：

```text
model capability
  -> agentic loop
  -> verifier / evaluator
  -> persistent session
  -> sandboxed environment
  -> credential vault
  -> observability and memory
  -> human taste and governance
```

RSI 文章说明 capability 进步正在压缩研发周期。Loops 文章说明怎么把 capability 包成可控制的循环。Managed Agents 说明怎么把循环放进可恢复、可隔离、可审计的生产环境。三篇共同指向一个结论：**未来的 AI 研发加速不只是模型参数问题，而是 model + harness + infra + org process 的复合系统问题。**

这也解释了为什么我觉得 “AI 会不会 self-improve” 这个问题最好拆开问：

- **会不会自己写更多研发代码？** 已经在发生。
- **会不会自己跑明确目标的实验？** 已经很强，尤其有 correctness check 的任务。
- **会不会自己提出研究方向？** 有早期信号，但远未闭环。
- **会不会自己训练下一代并验证对齐？** 这是 full RSI，风险最大、证据最少、治理最困难。
- **组织会不会因为 agent 速度太快而 review 不过来？** 这是短期就会发生的问题。

所以我会把 Anthropic 的论证看成：**full RSI 未到，但 RSI 的工程前奏已经到场。**

## 6. 风险和我不完全买账的地方

这三篇都值得读，但也不能照单全收。

第一，RSI 文章大量依赖 Anthropic 内部数据。内部数据很珍贵，但也很容易带有组织、工具链、模型、任务选择和文化偏差。Anthropic 工程师和研究员可能比一般组织更擅长把 Claude 用到极致。

第二，LOC 和 authored code share 不能直接等于生产力。Claude 写了 80% merged code 很震撼，但真正难的可能是需求判断、架构边界、review、rollout、incident response、长期维护成本。

第三，Claude judge 和 evaluator 会带来测量风险。open-ended task success、research next-step 这些指标都很有意义，但如果评审者也是 Claude，就要特别注意偏差、过拟合和“看起来合理”的幻觉。

第四，open-ended AI safety research 的 97% gap recovery 很强，但 caveat 也很关键：问题和 rubric 由人类选择，结果没有干净迁移到 production-scale models。这说明 agent 可以在定义好的小世界里很强，但把小世界的成功搬到真实前沿研发里，还要过很多层验证。

第五，Managed Agents 是产品文章，不是中立系统论文。它讲的 vault、session、sandbox、latency、Dreaming 都是非常关键的生产要素，但案例更多是 adoption 和 product fit，不是公开可复现实验。

最后，RSI 治理难度被文章说得很真实：pause 或 slowdown 只有在多家 frontier lab、多国、同条件、可验证时才有意义；训练 run 又比导弹井更难发现，defect incentive 很强。也就是说，技术上越像软件，治理上反而越不像传统军控。

## 7. 对我的 wiki / paper-reading pipeline 的启发

这三篇对我自己的 paper-reading 和个人 wiki 最大的启发是：不要把“自动化阅读”理解成一次性生成 Markdown，而要把它做成一个有状态、有验证、有审计的 loop。

一个更合理的 personal wiki loop 是：

```text
source URL / PDF / local markdown
  -> extract text, metadata, figures
  -> draft reading note
  -> verify checklist
       - source links exist
       - publication date / venue not hallucinated
       - key numbers trace back to source
       - figures load
       - formulas render
       - Jekyll build passes
  -> human taste pass
       - 主线是否清楚
       - 细节是否够用
       - 有没有我自己的判断
  -> publish
  -> save failures and lessons into future skill / checklist
```

这里有三个设计原则：

- **Artifacts 要落盘**：原文 HTML/TXT、图片、笔记、构建日志、git diff、失败记录都应该能恢复。否则 agent 做过什么很快会消失在聊天上下文里。
- **Verifier 要外置**：公式、链接、图片、front matter、Jekyll build、GitHub Pages deploy 都可以脚本化，不要靠“看起来没问题”。
- **Taste 不能完全交出去**：agent 可以写很长，也可以画图，但哪条主线最值得保存、哪些细节该删、哪种表述像自己，这些仍然应该由我来定。

如果把 Anthropic 的 Managed Agents 换成个人版，就是一个 “managed-agent-lite”：

| Managed Agents 资源 | 个人 wiki 对应物 |
|---|---|
| Agent | paper-reading skill、写作偏好、图文规范、review checklist |
| Environment | 本地 repo、Jekyll、Ruby bundle、图片处理脚本、浏览器验证 |
| Session | 每次阅读的素材目录、草稿、git diff、构建日志、失败记录 |
| Vault | GitHub token、API keys、发布权限，尽量不进正文和仓库 |
| Dreaming / memory | 从每次失败里更新 checklist 和 skill，让下一篇少犯同样错 |

这就是为什么之前的 [Harness Engineering for Self-Improvement]({{ '/paper-reading/Harness%20Engineering%20for%20Self-Improvement.html' | relative_url }}) 和这三篇应该放在一起看。Harness 讲的是 agent 自我改进的近端入口；Anthropic RSI 讲的是为什么这件事在 AI R&D 上变得危险又重要；Loops 和 Managed Agents 讲的是把入口变成工程系统需要哪些基本件。

## 8. 一句话收束

RSI 的短期现实版本不是一个模型在黑箱里神秘地“进化自己”，而是一套越来越强的研发机器：模型负责执行，loops 负责迭代，managed runtime 负责隔离和记忆，verifier 负责约束，人类负责 taste、边界和最终判断。真正要维护的不是一篇笔记，而是这套循环本身。
