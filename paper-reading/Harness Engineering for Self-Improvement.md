---
title: "Harness Engineering for Self-Improvement"
public: true
description: "Lilian Weng 这篇 blog 把 recursive self-improvement 的近路放在 harness engineering：workflow、文件系统记忆、sub-agent、context/workflow/harness-code 优化、evolutionary search 和人类监督边界。"
type: paper-reading
date: 2026-07-08
paper_title: "Harness Engineering for Self-Improvement"
venue: "Lil'Log"
year: "2026"
status: "reading"
source_url: "https://lilianweng.github.io/posts/2026-07-04-harness/"
---

# Harness Engineering for Self-Improvement：近端 RSI 可能先发生在 harness 层

- **Source**: [Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness/)
- **Author**: Lilian Weng
- **Published**: 2026-07-04
- **类型**: 技术博客 / 研究综述 / agent harness 读书笔记
- **关键词**: recursive self-improvement, harness engineering, context engineering, self-improving agents, evolutionary search, auto-research

## 一句话判断

这篇不是一篇实验论文，而是一张很好的研究地图：它把 recursive self-improvement 的短期可行路径从“模型直接改自己权重”转移到“模型改进围绕自己的 harness”，也就是 workflow、上下文、工具、文件系统记忆、评测和权限边界。

## 先看我整理的结构图

![Harness engineering RSI loop](assets/paper-reading/harness-engineering-self-improvement/harness-rsi-loop.svg)

图里的核心读法是：base model 提供推理和工具能力，harness 把它接到 workflow、文件系统、sub-agent、评测和权限系统里；当 harness 本身成为优化对象时，自我改进不必从权重更新开始，而可以先从上下文、流程、代码和优化器代码开始。

## 1. What are you trying to do?

这篇文章想说明：AI 自我改进的近期入口，很可能不是模型直接重写自己的参数，而是模型改进“让自己工作的那套系统”。

更具体地说，Weng 把 **harness** 定义为围绕 base model 的执行系统：它决定模型如何计划、调用工具、管理上下文、写入文件、保存工件、评估结果以及和用户/环境交互。文章的目标是把 auto-research、self-improving agents、evolutionary program search 这些方向统一到一个问题下：我们能否优化 agent 的运行时机制，让它变成模型能力增长的放大器。

## 2. What is the problem, how is it done today, and what are the limits?

问题是 long-horizon agent 要做的事越来越像真实软件工程和科研，而不是单轮问答；只靠 prompt 或长上下文很快会失控。

今天常见的做法有三类：

- **Prompt / instruction engineering**：把行为规则写进提示词，但随着任务变长，规则和历史都会膨胀。
- **Agent framework**：把 LLM、memory、tools、planning、action 接起来，但很多设计仍停留在模板和固定流程。
- **专用产品 harness**：例如 coding agent，用文件系统、shell、git、浏览器、MCP、sub-agent 和后台任务把模型接到真实环境。

这篇的判断是，harness 已经更接近 runtime/software system design，而不只是 prompt template。它要解决的是 agent 如何观察、行动、记忆、检查自己并持续改进。

## 3. What is new in the approach, including core idea, math, and method?

核心新意不是单个算法，而是一种组织框架：把 harness 视为可设计、可评估、可搜索、可进化的对象。

### 三个基础设计模式

1. **Workflow automation**
   典型循环是 plan → execute → observe/test → improve → execute again。关键不是让模型“想更久”，而是给它一个能行动、测试、修复和请求澄清的运行回路。

2. **File system as persistent memory**
   文章强调，不应该把所有日志、工具输出和历史轨迹都塞进上下文。长期 rollout 里的实验日志、代码 diff、论文摘要、error trace、过去失败轨迹，应该落在文件系统里，让模型通过 `bash`、`grep`、`cat`、编辑器等工具按需读取。

3. **Sub-agent and backend jobs**
   harness 可以显式启动多个 sub-agent 或后台任务，用于并行搜索假设、跑实验、委托隔离子任务。重要的是让并行过程可检查：日志、状态、结果都要成为持久工件，而不是消失在 transient chat context 里。

### 优化对象的层级

Weng 给出的 harness optimization ladder 很有用：

| 优化对象 | 含义 | 代表方向 |
|---|---|---|
| Instruction prompts | 写更好的指令 | prompt engineering |
| Structured context | 组织上下文和记忆 | ACE |
| Workflow | 生成或选择 agent 流程 | AFlow, AI Scientist |
| Harness code | 直接修改运行时实现 | Meta-Harness, Self-Harness, DGM |
| Optimizer code | 让优化器本身也被改进 | evolutionary/self-referential systems |

### Context engineering 的数学框架

文章用 MCE 的形式化说明“优化上下文”和“优化管理上下文的方法”可以分层。

一个 skill \(s \in \mathcal{S}\) 定义 context function \(c_s = \left(\rho_s, F_s\right)\)，并把输入 \(x\) 映射到上下文：

$$
c = F_s\left(x;\rho_s\right)
$$

其中：

- \(\rho_s\) 是静态组件，例如 prompts、knowledge bases、code libraries；
- \(F_s\) 是动态算子，例如 search、selection、filtering、formatting；
- 内层优化找给定 skill 下最好的上下文；
- 外层优化搜索能在 validation set 上表现更好的 skill。

对应的双层目标是：

$$
\text{Inner: } c_s^* = \arg\max_{c_s} J_\text{train}\left(c_s;s\right)
$$

$$
\text{Outer: } s^* = \arg\max_{s \in \mathcal{S}} J_\text{val}\left(c_s^*\right)
$$

机械上看，ACE 还是比较手工的“playbook 更新”；MCE 进一步把 context 管理机制也变成可进化对象；Meta-Harness 和 Self-Harness 则把 harness code 本身也纳入搜索。

## 4. Who cares? If successful, what difference does it make?

这篇对做 coding agent、auto-research、RL sandbox、个人知识库 agent 的人都很有价值，因为它讲的是“模型外的工程层怎么变成能力的一部分”。

My read is，最重要的影响有三个：

- **Agent 产品**：Claude Code、Codex、Cursor 这类系统的差异，不只是 base model 分数，而是 harness 对文件、工具、权限、测试和上下文的管理。
- **自动科研**：AI Scientist、ScientistOne、Autodata 这类系统说明，科研流程可以被部分 harness 化，但“写论文”和“发现科学”不是一回事。
- **个人 workflow**：对个人 wiki/paper-reading pipeline 来说，这篇直接解释了为什么文件系统、日志、构建检查、版本控制、可回滚状态比单次聊天上下文更重要。

My analysis is that，这篇文章的价值不是给出一个全新 benchmark，而是把 2025 到 2026 年很多自改进 agent 工作放进同一张地图里，读完后更容易判断一个系统到底是在优化 prompt、context、workflow、harness code，还是已经碰到 evaluator 和安全边界问题。

## 5. What are the risks?

风险集中在一个事实：一旦 harness 能自我修改，系统就在优化自己的操作系统。

My read is，最关键的风险是：

- **Evaluator 太弱**：很多科研质量、长期可维护性、taste、novelty 没有快速且精确的 verifier。
- **Reward hacking**：如果 reward 来自 unit tests，agent 可能过拟合测试；如果 reward 来自 judge model，agent 可能学会骗 judge；如果 reward 来自 benchmark，agent 可能利用 benchmark artifact。
- **Implementation drift**：任务复杂时，模型可能从原始想法滑向更常见、更简单但不忠实的实现。
- **Memory degradation**：长任务如果不把日志、失败、假设和决策写成持久工件，关键细节会在上下文压缩和中断中丢失。
- **Diversity collapse**：evolutionary/RL loop 容易收敛到当前 evaluator 喜欢的高分模式，而不是保留真正新颖的路线。
- **权限边界破坏**：Self-Harness 类型系统如果允许程序改“OS 层”，editable surface 和 permission control 必须在 loop 外部定义。

My analysis is that，文章最应该被记住的安全原则是：评测、权限、trace audit、held-out tests 和人类 review 不能完全放进被优化的 loop 里，否则系统会同时学习任务和学习绕过任务。

## 6. How much will it cost?

这里的 cost 不是 Weng 自己训练了一个模型的成本，而是复现这些 harness/self-improvement 路线需要的工程成本、评测成本和运行成本。

按文章线索拆开看：

| 方向 | 主要成本 |
|---|---|
| Workflow automation | 设计可执行 loop、工具接口、状态机、失败恢复 |
| File memory | 文件布局、日志规范、artifact schema、上下文检索策略 |
| Sub-agent/backend jobs | 并发调度、日志收集、取消/重试、结果合并 |
| Context engineering | rollout 数据、reflect/curate 机制、context eval |
| Harness code optimization | 可编辑代码面、候选生成、回归测试、held-out 验证 |
| Evolutionary search | 大量候选执行和评分，适合 fast verifier，不适合慢而模糊的科研判断 |

文章附录给出的 benchmark 也能反映 cost：

- **PaperBench**：20 篇 ICML 2024 Spotlight/Oral 论文复现任务，8,316 个 rubric，作者协同标注，最强模型约 21%。
- **CORE-Bench**：270 个任务，来自 90 篇论文，覆盖计算机科学、社会科学、医学；最难设置下 GPT-4o / GPT-4o-mini 约 21%。
- **ScienceAgentBench**：102 个任务，来自 44 篇 peer-reviewed publications，覆盖数学、化学、生物、地理。
- **RE-Bench**：7 个开放式 ML research-engineering 环境，每个环境最多 8 张 H100；包含 61 位专家的 71 次 8 小时尝试。
- **MLE-bench**：75 个 Kaggle 离线竞赛；o1-preview + AIDE scaffolding 在 16.9% 比赛达到 Kaggle bronze-medal level。
- **KernelBench**：250 个 PyTorch 任务，关注生成 GPU kernel 的正确性和速度。

My read is，个人或小团队最现实的复现路径不是做端到端 self-improving harness，而是先做可审计的 workflow harness：任务目录、日志、测试、build、失败归档、可回滚分支，再逐步让模型优化其中某一层。

## 7. What are the experiments and results?

这篇 blog 本身没有新实验，证据来自它综述的论文和系统。

几个值得记的结果和案例：

- **ACE**：把 context 作为可演化 playbook，通过 generator、reflector、curator 从成功和失败轨迹中提炼条目，避免无限增长的 prompt blob。
- **MCE**：把 context artifact 和 context-management skill 分开，做 meta-level skill evolution 和 base-level context optimization。
- **Meta-Harness**：让 coding agent 生成 harness candidates，并保留 Pareto frontier；TerminalBench-2 实验从强 harness 初始化，说明不是从零变魔法，而是在强起点上继续搜索。
- **Self-Harness**：通过 weakness mining、bounded proposal、held-in/held-out validation 更新 harness；在 Terminal-Bench-2 上为 MiniMax M2.5、Qwen3.5-35B-A3B、GLM-5 学到模型特异的 harness instruction。
- **DGM**：固定 base model，让 agent 修改自己的 harness code；文章记录其在 SWE-bench Verified 从 20% 到 50%，Polyglot 从 14.2% 到 30.7%。
- **SIA**：尝试在同一 loop 里选择更新 harness 或 model weights，但文章认为实验有混杂因素，例如 task-specific agent 和 Meta/Feedback agent 的模型强度不一致，证据仍是 provisional。

My analysis is that，这些结果共同支持一个较弱但重要的 claim：harness 是可优化的，而且能显著影响 agent 表现。它们还不能证明完整 RSI 已经可行，因为科研 taste、长期 repo health、负结果保留、人类监督和模糊 evaluator 仍然没有解决。

## 对我的价值

这篇和个人 wiki/paper-reading pipeline 很贴合。它提醒我，真正可持续的 agent 工作流应该落在文件系统和版本控制里，而不是一段长聊天里。

可以直接借鉴的设计：

1. **任务目录化**：每篇 paper/blog 的来源、草稿、图、引用、build log、最终 md 都应该有稳定位置。
2. **失败也保存**：下载失败、OCR 错误、图表解释失败、build error 都应该进入日志，而不是只留下成功笔记。
3. **上下文不是全塞进去**：让模型按需读文件、读 diff、读前一次 note，而不是把整个 wiki 打进 prompt。
4. **评测留在外层**：Jekyll build、链接检查、图片路径检查、git diff review、Pages deploy 状态，应该是 harness 的外部 gate。
5. **人类 taste 在高层介入**：比如哪些 paper 值得读、哪些图需要重画、哪些结论太浮，这些应该由人设方向，agent 做执行和整理。

## 一句话收束

这篇文章最有用的判断是：近期的 recursive self-improvement 可能不是“模型自己改权重”的科幻场景，而是“模型逐步改进自己的工作环境、记忆系统、工具流程和评测回路”的工程现实；但 evaluator、权限边界和人类 taste 决定了它能不能真的走向可靠科研。
