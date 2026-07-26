---
title: "Demystifying Evals for AI Agents"
public: true
description: "Anthropic 的 agent eval 工程手册：好评测不是一个分数，而是把任务、轨迹、环境状态、grader、人工校准和生产信号串成能持续修系统的闭环。"
type: paper-reading
date: 2026-07-26
created_at: 2026-07-26T21:30:00+08:00
paper_title: "Demystifying evals for AI agents"
authors: "Mikaela Grace, Jeremy Hadfield, Rodrigo Olivares, Jiri De Jonghe"
venue: "Anthropic Engineering"
year: "2026"
status: "digested"
category: "Agent Evaluation"
tags:
  - agent-evaluation
  - evals
  - llm-as-judge
  - regression-testing
  - agent-harness
  - anthropic
source_url: "https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents"
---

# Anthropic：agent eval 的产出不是分数，而是能修系统的失败信号

- **Source**: [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **Authors**: Mikaela Grace, Jeremy Hadfield, Rodrigo Olivares, Jiri De Jonghe
- **Published**: 2026-01-09, Anthropic Engineering
- **关键词**: agent eval, evaluation harness, task / trial / grader / trajectory / outcome, code-based grader, LLM-as-judge, human calibration, pass@k, pass^k, eval-driven development, transcript review
- **相关分享**: [Paper-sharing-3：Anthropic 的 Agent Eval 工程]({{ '/wiki/Paper-sharing-3%20Anthropic%20%E7%9A%84%20Agent%20Eval%20%E5%B7%A5%E7%A8%8B.html' | relative_url }})——本文与其余四篇 Anthropic Eval 文章的按时间线串讲

## 读法：给人和 agent 的路标

不要按 benchmark paper 读——它没有新数据集、没有实验，是一篇 **agent eval 工程手册**。它想讲清楚的是：agent 会调用工具、修改环境、积累中间状态，所以评测不能只看最后一句回答；一个可用的 eval 要同时管住 **任务定义、环境隔离、轨迹证据、最终状态、grader 公平性、生产信号回流** 六件事。最省力的读法是三段式：先记住第二节那组 vocabulary（task/trial/grader/trajectory/outcome/harness），再按自己的 agent 类型跳到对应小节挑 grader 组合，最后把 Step 0-8 路线图当 checklist 逐条对照。

给以后做 wiki/paper-reading pipeline 的 agent 检索，关键词是：`task bank`、`trajectory`、`outcome`、`evaluation harness`、`agent harness`、`reference solution`、`balanced positive negative cases`、`read transcripts`、`capability eval saturation`、`pass@k pass^k`、`Swiss cheese model`。

## 一句话判断

这篇最有价值的判断是：**agent eval 不是"给模型排个榜"，而是一个持续把失败样本、环境状态、轨迹证据、自动 grader 和人工判断连接起来的产品系统**。分数只是表层输出，真正重要的是它能不能回答：这次失败公平吗、该修 agent 还是修任务还是修 grader、改动有没有回归、模型升级值不值得切、生产里的新问题怎样进入下一轮测试集。文章用 CORE-Bench 的 **42% → 78% → 95%** 三级跳证明了这一点：同一个模型，换 scaffold 就差 36 个百分点，再修 grader 又差 17 个百分点——不读细节的分数几乎没有信息量。

## 图表优先读法

| 先看 | 图 / 表 | 读完应该抓住什么 |
|---|---|---|
| 1 | 自制 eval flywheel | 全文骨架：失败进任务库，transcript review 决定修什么，生产信号回流 |
| 2 | single-turn vs agent eval 原图 | agent eval 的对象多了 tools、environment、agent loop 和最终状态 |
| 3 | components 原图 | task、trial、trajectory、outcome、grader、两种 harness 是不同层次 |
| 4 | pass@k vs pass^k 原图 | "多试几次能成功"和"每次都可靠"是两种产品承诺 |
| 5 | roadmap 原图 + CORE-Bench 数字 | 低分先查 scaffold 和 grader，再怪模型 |
| 6 | Swiss cheese 原图 + 六方法对照表 | 自动 eval 只是第一层防线，每层都有洞 |

## 先看我画的闭环图

![Self-made agent eval flywheel](assets/paper-reading/anthropic-agent-evals/agent-eval-flywheel.svg)

*自制图解：把全文重组成一个 flywheel——task bank 吸收真实失败（正负例平衡），isolated trials 复刻生产 harness，同时收集 trajectory 和 outcome 两种证据，hybrid graders（code/model/human）打分后由 transcript review 判断失败是否公平、该修 agent/task/harness/grader 里的哪一个，过关的 capability eval 沉淀为 regression suite，底部虚线是生产信号（monitoring、A/B、feedback、human studies）回流进任务库。后文每一节对应图里一个节点。*

## Agent eval 和 single-turn eval 差在哪

文章对 eval 的定义很朴素："给 AI 一个输入，对输出应用 grading logic 来度量成功"。single-turn eval 就是 prompt → response → 打分。agent eval 的复杂度来自三个变化：

- **工具调用会改变世界状态**：agent 可能改文件、下单、更新数据库；最后一句"我完成了"不等于事情真的完成，grader 必须去环境里验证。
- **错误沿轨迹传播**：早期一次错误搜索或错误工具参数，会让后面每一步看似合理但整体跑偏。
- **好答案可能突破静态 rubric**：Opus 4.5 在 τ2-Bench 航班预订任务里发现了 policy loophole，按原评测算失败，但从用户目标看反而是更好的解法——静态 grader 天然会漏掉这类"超纲的对"。

![Anthropic official comparison between single-turn and agent evaluations](assets/paper-reading/anthropic-agent-evals/official-eval-structure.png)

*原图来自 Anthropic：左边 single-turn eval 的输入/输出边界很窄（prompt 进、response 出、grading logic 查文本）；右边 agent eval 多了 tools、environment、task、agent loop 和 environment update，grading logic 也从"检查文本"变成"检查环境里是否真的出现了可验证结果"。*

## 一组必须钉死的 vocabulary

搭 eval 系统之前，先把这组词的层次分开——很多"分数看不懂"的问题都源于把它们混在一起：

| 概念 | 白话解释 | 为什么不能省 |
|---|---|---|
| Task / problem / test case | 一个带输入和成功标准的测试题 | 任务不清楚，后面所有分数都是噪声 |
| Trial | 同一 task 的一次运行 | agent 非确定性强，同题要跑多次才知道稳定性 |
| Grader | 给某个方面打分的逻辑 | 一个 task 可以挂多个 grader、多个 assertion |
| Transcript / trace / trajectory | 一次 trial 的完整记录：输出、工具调用、推理、中间结果、环境交互 | 不读轨迹就不知道失败是 agent 错、grader 错还是 task 错 |
| Outcome | trial 结束时的最终环境状态 | 用户真正关心的是数据库、文件、订单、PR 是否正确 |
| Evaluation harness | 跑 eval 的基础设施：发任务、并发跑 trial、记录轨迹、执行 grader、汇总分数 | 决定 eval 是否可复现、可扩展 |
| Agent harness / scaffold | 让模型像 agent 一样行动的系统：工具编排、上下文管理、执行循环 | 评测对象是 model + harness，不是裸模型 |
| Evaluation suite | 一组测某类能力或行为的 tasks | 支撑 capability eval 和 regression eval 的长期维护 |

![Anthropic official components of agent evaluations](assets/paper-reading/anthropic-agent-evals/official-components.png)

*原图来自 Anthropic：一次 eval 里 task、trial、trajectory、outcome、grader 的嵌套关系。两个容易忽略的点：trajectory 和 outcome 是两种证据——前者解释"它怎么做"，后者证明"世界最后对不对"，只看 outcome 会漏掉危险行为，只看 trajectory 又可能惩罚合理的替代路径；agent harness 和 evaluation harness 要分开想，很多"模型能力差"其实是 harness 限制或 grader bug。*

## 为什么要早建 eval：三个公司的时间线

没有 eval 的团队会进入 reactive debugging：用户说变差 → 手工复现 → 修一个 bug → 不知道有没有引入回归 → 等下一批抱怨。文章给了三条真实时间线：

- **Claude Code**：早期靠内部 dogfooding 和用户反馈快速迭代，后来先给 concision、file edits 这类窄行为加 eval，再扩展到 over-engineering 这种复杂行为。
- **Descript**：video editing agent 把成功拆成三维——**不破坏东西、按要求做、做得好**；从人工评分演进到产品团队定义 criteria 的 LLM graders，并定期做人工校准。
- **Bolt**：agent 已大规模使用后补 eval，**3 个月**内搭出能运行 agent、做 static analysis、用 browser agents 实测 app、再用 LLM judge 看 instruction following 的系统。

我的理解：**eval 是产品、工程、研究之间带宽最高的接口**。产品团队用它明确"什么叫好"，工程团队用它防回归，研究团队用它 hill-climb；模型升级时，有 eval 的团队几小时就能判断是否值得切换，没有的团队要靠几周的感觉测试。eval 的成本在前期可见，收益在整个生命周期复利。

## Grader 三件套：确定性优先，LLM 必须校准，人类是金标准

| Grader 类型 | 典型手段 | 优点 | 风险 |
|---|---|---|---|
| Code-based / deterministic | 单元测试、状态断言、static analysis、工具调用验证、transcript 指标 | 快、便宜、客观、可复现、好 debug | 对合法变体过于刚性，缺乏 nuance |
| Model-based / LLM judge | rubric 打分、自然语言 assertion、pairwise 比较、多 judge 共识 | 灵活、可扩展，能处理开放式输出 | 非确定性、成本高、必须人工校准 |
| Human | 专家 review、spot-check、A/B test、inter-annotator agreement | 最接近真实用户和专家判断 | 慢、贵，不适合每次提交都跑 |

实际系统几乎都是组合拳：coding agent 用 unit tests 保 correctness、LLM rubric 看代码质量；support agent 用 state check 验证退款真的处理了、LLM rubric 看同理心。文章特别警告 **不要过度检查路径**：硬性规定工具调用顺序，会把模型自己找到的有效路径打成失败——更稳的方式是检查产物和最终状态，用 transcript review 观察危险策略。

另一组要分开的概念：**capability eval** 问"这个 agent 能做好什么"，应该从低通过率起步，给团队一座可以爬的山；**regression eval** 问"它还能做好过去会做的事吗"，应该维持接近 **100%** 的通过率，一掉就是回归警报。成熟后，打满分的 capability eval 会毕业进 regression suite。

## 按 agent 类型选尺子

- **Coding agents**：主 grader 天然是确定性的——测试能不能过、是否修了 failing tests 且不破坏 passing tests。SWE-bench Verified（GitHub issues + 测试套件）和 Terminal-Bench（Linux kernel 编译、ML 训练这类端到端任务）都是这个路线。好的套件还会叠 static analysis、state check、transcript 指标（turns/tool calls/tokens/latency）和 LLM rubric（是否过度设计、是否尊重现有风格）。
- **Conversational agents**：难点在任务完成和交流质量都算数——退款处理了但态度糟糕，和态度很好但没改后端状态，都是失败。做法是 **verifiable end-state + rubric**，常需要第二个 LLM 模拟用户；τ-Bench / τ2-Bench 就是这种多轮 benchmark 的代表。一个任务可以同时挂 state check（ticket resolved）、transcript 约束（10 turns 内）、LLM rubric（语气得体、不编造政策）。
- **Research agents**：输出主观、专家会互相不同意、ground truth 随网页漂移。组合 **groundedness**（关键 claim 有 source 支撑）、**coverage**（覆盖任务要求的事实）、**source quality**（用权威来源）、客观题用 exact match，开放式质量频繁对齐专家判断。BrowseComp 是这类"验证容易、求解难"的代表。
- **Computer-use agents**：通过截图、点击、键盘操作真实 GUI，必须在真实或 sandboxed 环境跑并检查最终状态。WebArena 用 URL/page state/backend 检查浏览器任务，OSWorld 用脚本检查文件系统、配置、数据库和 UI 属性。一个实用 tradeoff：总结 Wikipedia 时从 DOM 抽文本更高效，在 Amazon 找 laptop case 时截图更高效——Claude for Chrome 的 eval 就专门检查 agent 会不会按场景选对工具。

## 非确定性：pass@k 和 pass^k 是两种产品承诺

![Anthropic official pass@k and pass^k comparison](assets/paper-reading/anthropic-agent-evals/official-pass-metrics.png)

*原图来自 Anthropic：横轴是尝试次数 k。k=1 时两条曲线都等于单次成功率；k 增大后 pass@k（k 次里至少一次成功）逼近 100%，pass^k（k 次全部成功）跌向 0%。同一个 agent，两个指标讲的是完全不同的故事。*

| 指标 | 含义 | 适合什么产品语义 |
|---|---|---|
| `pass@k` | k 次里至少一次成功 | 只要有一个可用结果就有价值的任务 |
| `pass^k` | k 次必须全部成功 | 客服、交易、生产操作——用户期待每次都稳 |

文章的例子：单次成功率 75% 的 agent 跑 3 次，"3 次都成功"的概率只有 **(0.75)^3 ≈ 42%**。这就是 demo 和上线的落差：demo 展示的是 pass@k 的乐观面，用户体验要求的是 pass^k 的一致性。面向用户的可靠性承诺，必须盯 pass^k。

## 从 0 到 1 的九步路线图

![Anthropic official roadmap to excellent evals](assets/paper-reading/anthropic-agent-evals/official-eval-creation.png)

*原图来自 Anthropic：从 start early 到 long-term maintenance 的建设流程图。核心不是步骤数量，而是顺序——先有真实失败构成的任务库和无歧义的成功标准，再谈 harness 和 grader 的工程化。*

**Step 0-3：把任务库搭起来。** 不用等几百个任务，**20-50 个来自真实失败的简单任务**就够开工——早期每次改动影响明显，小样本信号足够。把上线前的手测清单、bug tracker、support queue 转成 task，按用户影响排优先级。好 task 的标准：两个领域专家独立判断能给出相同 pass/fail；任务描述包含 grader 检查所需的全部信息（audit Terminal-Bench 时发现过：任务没说文件路径、测试却假设了特定路径，agent 无辜失败）；有 **reference solution** 证明可解、顺便验证 grader 没写错——frontier model 出现 **0% pass@100** 时，多半是任务坏了而不是模型不行。正负例要平衡：Claude.ai 的 web search eval 同时覆盖"查天气"这类该搜的 query 和 "who founded Apple?" 这类该直接回答的 query——**单边 eval 会训练出单边行为**。

**Step 4-5：harness 稳定，grader 不脆。** eval 里的 agent 要尽量像生产环境的 agent；trial 之间必须隔离，清掉 leftover files、cached data、资源耗尽这些相关失败源——Anthropic 内部就出过 Claude 通过查看前面 trial 留下的 git history 拿到不公平优势的事故。grader 设计的几个坑：能确定性就确定性，但别把合法变体写死；多组件任务给 partial credit（"找对了问题但没退成款"和"完全没做"要区分开）；LLM judge 要有 Unknown 退出选项，减少信息不足时的幻觉评分；一个维度一个 judge，别让单个 judge 一口气判所有复杂维度；grader 要抗作弊，通过 eval 必须真的需要完成任务。

最有警示性的两个案例都在这里。**CORE-Bench**：Opus 4.5 用原 CORE-Agent scaffold 只有 **42%**；换成 Claude Code、模型不变，直接到 **78%**——scaffold 本身在锁死模型；再修掉刚性数值匹配（期望 `96.124991…` 却惩罚 `96.12`）、任务歧义、随机任务不可复现这些 grader/task 问题，才到约 **95%**。**METR** 的 time horizon benchmark 则出过阈值 bug：任务文字要求"达到"某分数，grader 却要求"超过"，遵守指令的模型反而吃亏。原则只有一条：**低分不一定 agent 差，高分不一定 agent 好；先读 transcript，再信数字。**

**Step 6-8：读轨迹、防饱和、有人养。** 定期读大量 trial 的 transcript 和评分，确认失败看起来公平、grader 真的在测重要的东西——这是 agent 开发的核心技能。capability eval 会饱和：SWE-bench Verified 一年内从 **40% 到超过 80%**，接近饱和时进步会显得虚假地小；Qodo 起初觉得 Opus 4.5 提升不明显，后来发现是自己的 one-shot coding eval 没覆盖更长的 agentic 任务，换成 agentic eval framework 才看到真实进步。长期维护上，核心 infrastructure 交给专门 eval team，但 task 应该由最接近用户的人贡献——现在 PM、客户成功、销售都能用 Claude Code 把 eval task 提成 PR，"let them"。更进一步是 eval-driven development：先写 eval 再做能力，像 TDD 一样迭代。

## 自动 eval 不是全部：Swiss cheese 才是现实

![Anthropic official Swiss cheese model for AI agent quality](assets/paper-reading/anthropic-agent-evals/official-swiss-cheese.png)

*原图来自 Anthropic：Swiss cheese 模型——每一层评测方法都有洞（automated evals 可能和真实使用脱节、监控是事后的、人工 review 不可规模化），但错位叠放的多层能挡住单层漏掉的失败。*

| 方法 | 它抓什么 | 主要短板 |
|---|---|---|
| Automated evals | 快速迭代、回归、每次提交都能跑、无用户影响 | 前期投入大，可能和真实使用脱节造成虚假信心 |
| Production monitoring | 真实用户行为、真实错误和分布漂移 | 事后反应，问题已经影响用户，信号噪 |
| A/B testing | 真实结果指标：retention、task completion | 慢（数天到数周）、需要流量、不解释为什么 |
| User feedback | 没预料到的问题、自带真实例子 | 稀疏、自选择、偏向严重问题 |
| Manual transcript review | subtle failure、质量直觉、judge 校准 | 不可规模化，reviewer 会疲劳 |
| Systematic human studies | 主观任务金标准、校准 LLM grader | 贵、慢，复杂领域需要专家 |

落地节奏：automated evals 管 pre-launch 和 CI/CD；上线后开 production monitoring；大改动用 A/B 验证；feedback 持续 triage、每周抽样读 transcript；human studies 定期校准 LLM grader。

## 附录：框架是加速器，质量在任务里

文章附录盘点了几个 eval 框架，值得存档备查：

- **Harbor**：容器化 agent 环境，支持跨云大规模跑 trial，task/grader 有标准化格式；Terminal-Bench 2.0 就通过它的 registry 分发。
- **Braintrust**：离线评测 + 生产可观测 + 实验追踪，附带 `autoevals` 预置 scorer 库。
- **LangSmith**：tracing、离线/在线 eval、数据集管理，深度绑定 LangChain 生态。
- **Langfuse**：功能类似的 self-hosted 开源替代，适合有数据驻留要求的团队。
- **Arize**：开源的 Phoenix（tracing/debug/评测）加商业的 AX（规模化与监控）。

文章的态度很清醒：很多团队混用多个工具或干脆自己写脚本，**框架只是加速器，eval 的质量永远在高质量 task 和 grader 的迭代里**。

## 我怎么看

### 可信之处

- **案例有名有姓有数字**：CORE-Bench 42→78→95、Bolt 3 个月、SWE-bench 40→80、(0.75)^3≈42%，都是可核对的具体证据，不是空泛原则。
- **诚实暴露自家事故**：git history 污染、CORE-Bench grader bug 都是 Anthropic 自己踩的坑，这类自曝比"最佳实践清单"可信得多。
- **对 LLM judge 的态度克制**：反复强调人工校准、Unknown 选项、维度拆分，没有把 LLM-as-judge 当银弹卖。
- **"先读 transcript 再信数字"贯穿全文**：这是一条能直接改变工作习惯的原则，而且给了 42→78 这种量级的理由。

### 需要警惕

- **不是可复现研究**：没有新数据集和系统实验，案例来自 Anthropic 和合作客户的一面之词，方向可信但数字不可外推。
- **LLM judge 校准只有原则没有协议**：说要 human calibration，但没给误差曲线、标注一致性指标或具体流程。
- **安全攻防点到为止**：grader bypass、prompt injection 只作为"要抗作弊"的原则出现，没有 threat model。
- **有推广自家生态的成分**：CORE-Bench 案例同时是"scaffold 很重要"的论据和 Claude Code 的广告；附录里 Harbor 也是自家关联项目。
- **多 agent 与长任务评测是承认的空白**：文章自己说这个领域 nascent，结论会随 agent 形态演化。

## 对我的价值

这套框架可以直接落到我的 wiki/paper-reading agent pipeline 上，映射成一个轻量 eval harness：

| 文章概念 | 对应到 paper-reading pipeline |
|---|---|
| Task | 给定 URL / arXiv / local markdown，产出一篇可发布精读 |
| Outcome | markdown 存在、frontmatter 完整、source link 可点、Jekyll build 通过 |
| Deterministic grader | `check_paper_reading_figures.py`：≥3 原图 + 1 自制图、路径存在、caption 齐全 |
| LLM rubric | 主线是否清楚、关键数字是否可回溯、是否区分原图和自制图、是否避免空泛总结 |
| Human calibration | 我读完觉得"有重点、有细节、有味道"，把不满意处变成新 checklist 项 |
| Regression suite | 已定稿的高质量 note 作为风格样本，防止新 note 退化成短摘要 |
| pass^k | 一篇成功不算数：连续多篇稳定过全部 gate 才说明 pipeline 可靠 |

三条直接可执行的迁移：**正负例平衡**——eval 里不只测"该配图时配了"，也要测"不该硬凑图时没凑"；**partial credit**——"图齐了但 caption 敷衍"和"完全没图"要区分；**读 transcript**——agent 写砸一篇时，先看它的轨迹判断是 prompt 歧义、工具限制还是能力问题，再决定修哪层。

## 一句话收束

把 eval 当作 agent 系统本身的一部分而不是外挂的记分牌——失败变成任务，任务变成回归护栏，分数低时先审 scaffold 和 grader 再怪模型，这就是整篇文章值得带走的姿势。
