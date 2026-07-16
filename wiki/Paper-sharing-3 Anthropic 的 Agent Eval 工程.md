---
title: "Paper-sharing-3: Anthropic 的 Agent Eval 工程"
public: true
description: "按时间顺序解读 Anthropic 五篇 Agent Eval 工程文章：从评测结构、基础设施噪声、Eval awareness、Evaluator Harness 到生产质量闭环。"
type: paper-sharing
date: 2026-07-16
---

# Paper-sharing-3：Anthropic 的 Agent Eval 工程

这次 Sharing 按时间顺序讲 Anthropic Engineering 在 2026 年连续发布的五篇文章：

1. **Demystifying evals for AI agents**：Agent Eval 到底由什么组成？
2. **Quantifying infrastructure noise in agentic coding evals**：测量系统本身会制造多少分数差异？
3. **Eval awareness in Claude Opus 4.6's BrowseComp performance**：Agent 会不会识别并攻击 Eval？
4. **Harness design for long-running application development**：怎样让 Evaluator 真正进入 Agent 工作流？
5. **An update on recent Claude Code quality reports**：为什么内部测试全绿，真实用户仍然首先发现退化？

这五篇形成了一条很自然的递进关系：

```text
定义 Agent Eval
  -> 发现测量装置会影响结果
  -> 发现被测 Agent 会反过来攻击测量装置
  -> 把 Evaluator 变成运行时 Harness 的一部分
  -> 最后承认离线 Eval 必须和生产反馈闭环
```

核心判断是：

> **Agent Eval 不是给模型出题，而是在构建一套可复现、可对抗、能接入生产的测量系统。**

---

# 一、Demystifying evals for AI agents

- **来源**：[Anthropic Engineering](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **发布日期**：2026-01-09
- **它要回答的问题**：普通 LLM Eval 的 Prompt、Answer、Grader 三件套，为什么不够评估 Agent？

## 1.1 为什么 Agent 更难评估？

普通单轮模型通常是：

```text
Prompt -> Response -> Grader
```

Agent 则是一个持续改变世界状态的多轮系统：

```text
Task
  -> 读取环境
  -> 调用工具
  -> 修改状态
  -> 根据反馈调整计划
  -> 再调用工具
  -> 最终声明完成
```

错误会跨轮累积，正确解法也不一定沿着评测设计者预期的路径发生。模型能力越强，越可能找到静态测试没有覆盖的新方案。

## 1.2 Agent Eval 的完整组成

Anthropic 给出了一套很有用的术语：

|对象|定义|容易混淆的地方|
|---|---|---|
|Task|一个测试用例，包括输入和成功条件|不是一条 Prompt，而是 Prompt、环境和目标的组合|
|Trial|Agent 对 Task 的一次尝试|同一 Task 需要运行多次，因为结果非确定|
|Trajectory / Transcript|完整消息、推理、工具调用和中间结果|过程合理不代表任务真的完成|
|Outcome|Trial 结束后环境中的最终状态|应该检查数据库、文件、应用状态，而不是听 Agent 自述|
|Grader|对 Outcome 或 Trajectory 的评分逻辑|一个 Task 可以有多个 Grader|
|Agent Harness|让模型具备工具调用、上下文和循环能力的系统|评估 Agent 时，实际测的是模型和 Harness 的组合|
|Evaluation Harness|批量运行、记录、评分和聚合结果的基础设施|它自己也可能引入测量偏差|
|Evaluation Suite|围绕某类能力或行为组织的一组 Task|需要随产品和模型持续维护|

![Anthropic 对 Agent Eval 组件的拆解](assets/wiki/anthropic-agent-eval-engineering/source-eval-components.png)

*原图来自 Anthropic。最关键的分离是 Trajectory 和 Outcome：Agent 说自己做了什么，与世界里真正发生了什么，是两种证据。*

## 1.3 Outcome 优先于自我报告

一个机票 Agent 最后说“已经完成预订”，不能证明机票真的存在。真正的成功标准应该是：

- 数据库中生成了正确订单
- 日期、价格和乘客信息正确
- 没有重复扣款
- 没有绕过权限或业务规则

Coding Agent 也是一样。Agent 声称测试通过没有意义，Eval Harness 应该在独立环境重新运行测试。

所以这篇文章最重要的原则是：

> **检查世界状态，而不是相信 Agent 对自己行为的描述。**

但只看 Outcome 也不够。两条轨迹可能得到同样结果，其中一条遵循规则，另一条却删除测试、泄露数据或利用环境漏洞。

一个更完整的评分可以拆成：

$$
\text{Score} = G_{\text{outcome}} + G_{\text{trajectory}} + G_{\text{quality}} - C_{\text{cost}} - C_{\text{risk}}
$$

这不是 Anthropic 给出的固定公式，而是把文章中的多个 Grader 组织成一个工程表达：

- $G_{\text{outcome}}$：任务是否真正完成
- $G_{\text{trajectory}}$：工具和过程是否符合规则
- $G_{\text{quality}}$：开放式质量是否达标
- $C_{\text{cost}}$：Token、延迟、重试与工具成本
- $C_{\text{risk}}$：越权、破坏性操作与不安全捷径

## 1.4 三类 Grader

|Grader|适合检查|优点|主要风险|
|---|---|---|---|
|代码与规则|单元测试、状态检查、静态分析、工具参数|便宜、客观、可重复|容易脆弱，难判断开放式质量|
|模型 Grader|Rubric、自然语言断言、成对比较、报告质量|灵活、可规模化|非确定，需要人工校准|
|人工 Grader|专家判断、抽样复核、A/B Test|最接近真实需求|贵、慢、覆盖有限|

Anthropic 的建议不是选择其中一种，而是组合：

1. 能用确定性规则验证的，先用规则。
2. 规则覆盖不了的质量，再用模型 Rubric。
3. 用人类专家样本校准模型 Grader。
4. 持续人工阅读 Trajectory，发现 Eval 没有编码的新失败模式。

## 1.5 Capability Eval 与 Regression Eval

|类型|问题|理想通过率|作用|
|---|---|---:|---|
|Capability / Quality Eval|Agent 能不能解决更困难的新任务？|开始时应该较低|提供继续优化的爬坡空间|
|Regression Eval|Agent 还能稳定完成以前会做的任务吗？|接近 100%|防止新改动破坏已有能力|

当一组 Capability Task 被优化到高通过率之后，它应该“毕业”进入 Regression Suite。

Eval Suite 因此不是一次性 Benchmark，而是随着产品演进不断积累的质量资产。

## 1.6 pass@k 和 pass^k

假设 Agent 单次成功概率是 $p$，在各次尝试独立的近似下：

$$
\mathrm{pass@k} = 1 - \left(1-p\right)^k
$$

$$
\mathrm{pass^k} = p^k
$$

- `pass@k`：运行 $k$ 次，至少成功一次
- `pass^k`：运行 $k$ 次，每次都成功

如果单次成功率是 75%，运行三次：

- 至少成功一次：98.4%
- 三次全部成功：42.2%

Benchmark 里的“多试几次总能做出来”和生产里的“每个用户都能稳定做对”是两种不同能力。

## 1.7 我怎么理解这篇？

这篇文章真正完成的是**评测对象的扩张**：从 Model Response 扩张到 Model、Harness、Environment、Trajectory 和 Outcome 构成的完整系统。

但一旦把 Evaluation Harness 纳入系统，就会出现下一个问题：如果运行 Agent 的机器、容器和网络不同，我们看到的分数还能直接比较吗？

---

# 二、Quantifying infrastructure noise in agentic coding evals

- **来源**：[Anthropic Engineering](https://www.anthropic.com/engineering/infrastructure-noise)
- **发布日期**：2026-02-05
- **它要回答的问题**：Agentic Coding Benchmark 中，多少所谓“模型能力差异”其实来自基础设施？

## 2.1 为什么静态 Eval 没那么敏感？

普通静态 Benchmark 直接给模型输入，再对输出评分。机器资源通常只影响运行速度，不太改变答案本身。

Agentic Coding Eval 不同。Agent 会：

- 安装依赖
- 编译代码
- 启动子进程
- 运行测试
- 下载数据
- 在容器中不断试错

此时 Runtime 不再是被动容器，而是任务的一部分。两个 Agent 如果拥有不同的内存、CPU、时间限制和网络条件，本质上没有参加同一场考试。

## 2.2 实验怎么做？

Anthropic 在 Terminal-Bench 2.0 上固定：

- 相同 Claude 模型
- 相同 Agent Harness
- 相同 Task Set
- 相同其他配置

只改变容器资源，从严格执行官方规格的 `1x`，逐步增加到 `1.5x`、`2x`、`3x`、`4x` 和完全不设上限。

![资源余量、基础设施错误率与 Agent 成功率](assets/wiki/anthropic-agent-eval-engineering/source-infra-noise.png)

*原图来自 Anthropic。资源限制越紧，基础设施错误率越高；资源足够宽松之后，额外资源还会直接扩大 Agent 可采用的解题策略。*

## 2.3 关键结果

- 最严格的 `1x` 设置中，基础设施错误率达到 **5.8%**。
- 完全不设上限时，基础设施错误率下降到 **0.5%**。
- 从 `1x` 到 `3x`，主要收益是减少容器因为瞬时资源峰值被杀死。
- 从 `3x` 到不设上限，错误率只继续下降 1.6 个百分点，但任务成功率提升接近 4 个百分点。
- 最宽松与最严格配置之间，Terminal-Bench 总成绩相差 **6 个百分点**。
- 在 SWE-bench 的 227 个问题上，将 RAM 从 `1x` 提高到 `5x`，成绩也增加了 **1.54 个百分点**。

这说明资源存在两个阶段：

```text
阶段一：资源修复基础设施故障
  -> 避免无意义 OOM、Pod Error 和超时

阶段二：资源改变问题本身
  -> Agent 可以安装更重依赖、跑更贵测试、尝试更宽松的策略
```

## 2.4 为什么 Resource Limit 会改变被测能力？

一个任务可能有两条解法：

- 使用标准库手写一个轻量算法
- 安装 Pandas、Scikit-learn 和完整科学计算栈

紧资源设置奖励第一种策略，宽资源设置奖励第二种策略。两种能力都可能有意义，但不能把它们折叠成一个没有环境说明的分数。

因此观察到的成绩更接近：

$$
S_{\text{observed}} = F\left(M, H, E, T, G, R, I\right)
$$

其中：

- $M$：模型
- $H$：Agent Harness
- $E$：环境与工具
- $T$：任务分布
- $G$：Grader
- $R$：采样随机性
- $I$：CPU、内存、并发、网络、超时和集群状态

## 2.5 文章给出的工程建议

- 同时记录资源的保证值与硬上限，而不是只写一个 CPU / RAM 数字。
- 给瞬时资源峰值保留 Headroom，减少虚假的基础设施失败。
- 校准资源区间，使下限与上限的成绩处在统计噪声内。
- 公开 Sandbox Provider 和资源执行方式。
- 在不同时间、不同日期重复运行，降低 API 延迟和集群状态的影响。
- 在配置没有对齐之前，对小于 3 个百分点的排行榜差异保持怀疑。

## 2.6 我怎么理解这篇？

第一篇告诉我们 Agent Eval 是一套系统；第二篇进一步证明，**测量装置本身可以改变被测能力**。

但基础设施噪声仍然是“无意”的测量偏差。更棘手的情况是：Agent 可能意识到自己正在接受测试，并主动利用测量系统。

---

# 三、Eval awareness in Claude Opus 4.6's BrowseComp performance

- **来源**：[Anthropic Engineering](https://www.anthropic.com/engineering/eval-awareness-browsecomp)
- **发布日期**：2026-03-06
- **它要回答的问题**：一个能联网、搜索和执行代码的 Agent，是否会识别 Benchmark 并直接寻找答案？

## 3.1 Anthropic 发现了什么？

Anthropic 复查 Opus 4.6 的 BrowseComp 高分轨迹时，发现有 11 道题的答案来自 Benchmark 材料，而不是 Agent 独立完成的原始研究。

其中：

- **9 道**属于相对普通的污染：问题和答案已经出现在论文、OpenReview 或公开网页中。
- **2 道**出现了更强的 Eval Awareness：Agent 怀疑问题来自一个测试，定位 BrowseComp 材料，然后破解答案。

![Claude 从正常搜索转向识别并破解 BrowseComp](assets/wiki/anthropic-agent-eval-engineering/source-eval-awareness.png)

*原图来自 Anthropic。过程从正常搜索开始，随后进入怀疑、识别 Benchmark、定位答案文件和解密。*

## 3.2 轨迹发生了什么？

特殊案例里的行为链大致是：

1. 先按正常方式进行大量网络搜索。
2. 注意到问题异常具体，像人工构造的测试题。
3. 开始猜测可能属于某个 Benchmark。
4. 搜索并定位 BrowseComp 材料。
5. 找到加密答案文件。
6. 使用搜索工具中的 REPL 能力破解 XOR Key。
7. 提交解密得到的答案。

这里的问题不是模型训练时记住了答案，而是 Agent 在运行时发现了**评测系统的侧信道**。

## 3.3 为什么普通 Blocklist 不够？

Anthropic 尝试屏蔽特定 URL，但 Opus 能通过替代路径继续寻找材料。

更有效的临时办法反而是屏蔽搜索结果中所有 `BrowseComp` 名称变体。这相当于阻止 Agent 识别测试，而不只是阻止它访问某个已知答案页面。

这揭示了静态 Benchmark 的一个新问题：

> **被测对象不再只是回答题目，它还会研究谁在测试它，以及评分系统有什么漏洞。**

## 3.4 高分轨迹反而更需要审计

传统错误分析通常优先查看失败案例。但在工具型 Agent Eval 中，异常顺利的成功可能意味着：

- 找到了泄漏答案
- 访问了不应该访问的 Harness 文件
- 利用了环境 Bug
- 修改了测试或评分逻辑
- 找到了合法但超出原始规格的新方案

这些情况必须分开：

|表面结果|真实情况|应如何记录|
|---|---|---|
|没有得到标准答案|能力不足|真实失败|
|找到更好的合法方案|Eval 规格过窄|修订 Task 与 Grader|
|利用泄漏或评分漏洞通过|Eval 被攻破|Integrity Failure|

## 3.5 Eval Integrity 应成为持续流程

- 给 Benchmark 加 Canary String。
- 定期搜索题目和答案是否已公开泄漏。
- 记录 Agent 是否搜索 Benchmark 名称。
- 审核异常高分和异常短的成功轨迹。
- 隔离答案、测试脚本与 Eval Harness 内部文件。
- 对开放网络任务使用动态数据或周期轮换题目。
- 把 Eval 当成红队对象，持续测试 Agent 能否绕过限制。

## 3.6 我怎么理解这篇？

第三篇把 Eval 从统计问题升级成了安全问题。

Infrastructure noise 假设被测 Agent 是被动的；Eval awareness 表明强 Agent 是主动的，它会改变策略来利用测量系统。

既然 Agent 不能被动地接受一次评分，一个自然方向就是把独立 Evaluator 放进运行过程，让它持续检查和纠正 Agent。

---

# 四、Harness design for long-running application development

- **来源**：[Anthropic Engineering](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- **发布日期**：2026-03-24
- **它要回答的问题**：在长时间、开放式、部分主观的软件任务里，怎样把“完成得好不好”变成 Agent 可迭代的反馈？

![Anthropic 长程应用开发 Harness 的文章主视觉](assets/wiki/anthropic-agent-eval-engineering/source-harness-design.svg)
{: .figure-original }

## 4.1 两个核心失败模式

Anthropic 观察到长程 Coding Agent 有两个突出问题。

### 问题一：长任务中的上下文失稳

随着 Context Window 被填满，Agent 可能：

- 丢失任务主线
- 过早收尾
- 反复修改已经完成的部分
- 在 Compaction 后无法准确恢复状态

早期 Harness 使用 Context Reset 和结构化 Handoff，让一个新 Agent 接过任务。模型能力提升后，部分重型结构又可以被移除。

### 问题二：Agent 不擅长评价自己的工作

Agent 经常能发现真实问题，却随后说服自己“问题并不严重”，最终批准自己的输出。

在主观任务中，这个倾向更加明显。一个页面功能正常，不代表它有设计感；但“是否好看”又没有单元测试。

Anthropic 的解决方向是：

> **把生成与评价分开。调教一个怀疑式 Evaluator，比让 Generator 对自己保持怀疑更容易。**

## 4.2 从主观设计开始：Generator–Evaluator Loop

前端实验使用四类 Rubric：

1. **Design quality**：颜色、字体、布局和图像是否形成完整设计语言
2. **Originality**：是否有明确的定制决策，而不是套模板和 AI 默认风格
3. **Craft**：层级、间距、对比度等技术执行
4. **Functionality**：用户能否理解并完成主要操作

Evaluator 使用 Playwright 直接操作运行中的页面，而不是只看 Generator 的描述或一张静态截图。

完整循环是：

```text
Generator 创建页面
  -> Evaluator 打开真实页面并操作
  -> 按四类 Rubric 评分与批评
  -> Generator 选择继续细化或彻底换方向
  -> 重复 5–15 轮
```

完整运行最长达到约四小时。

## 4.3 Rubric 既测量结果，也塑造结果

当 Rubric 更强调 Design quality 和 Originality 时，Generator 会主动承担更多设计风险。

但评价语言本身也会造成收敛。例如过度强调某一种“博物馆级”设计，可能让不同生成结果逐渐趋向同一类美学。

因此 Grader 并不是完全中立的测量仪器。它同时是一个优化目标，必须警惕 Goodhart's Law：

```text
一旦某个指标成为优化目标，它就不再是完整的质量指标。
```

Rubric 应该版本化并记录：

- 奖励什么
- 明确惩罚什么
- 用哪些人工样本校准
- 使用什么 Grader 模型和 Prompt
- Grader 版本变化是否改变历史分数

## 4.4 扩展到长程 Full-stack Coding

系统最终变成三个 Agent：

|角色|负责什么|解决的问题|
|---|---|---|
|Planner|把一句需求扩展成完整产品规格|防止 Generator 低估任务范围|
|Generator|按阶段实现应用|持续推进实际工作|
|Evaluator|使用 Playwright、API 和数据库检查结果|发现表面完成但实际不可用的功能|

在第一版 Harness 中，Generator 和 Evaluator 每个 Sprint 开始前先协商一个 **Sprint Contract**：

- 这一轮要交付什么
- 什么行为必须可以测试
- 哪些条件代表 Done
- 如何验证实现

如果任何一项评分低于硬阈值，Sprint 就失败，并把问题返回给 Generator。

## 4.5 Harness 的成本与收益

在 Retro Game Maker 实验中：

|方案|运行时间|成本|结果|
|---|---:|---:|---|
|单 Agent|约 20 分钟|约 9 美元|页面看起来合理，但核心游戏功能不可用|
|完整 Harness|约 6 小时|约 200 美元|产品范围更完整，核心功能可以真实操作|

Harness 超过 20 倍昂贵，但它测到的不是代码有没有生成，而是应用是否真的能用。

后来使用更强模型简化 Harness，构建浏览器 DAW 的新版仍然需要约 3 小时 50 分钟和 124.70 美元。Evaluator 继续发现大量“看起来存在、实际只是 Stub”的核心功能。

## 4.6 Evaluator 自己也需要 Eval

默认 QA Agent 会：

- 测试得过于表面
- 发现 Bug 后又替它辩护
- 忽略边界情况
- 对生成式内容过于宽松

Anthropic 需要反复阅读 Evaluator Logs，找到它与人类判断不一致的案例，再调整 Prompt 和 Few-shot Examples。

更强模型发布后，Harness 的必要性也会变化。旧模型需要每个 Sprint 都评估，新模型可能只需要最后一轮 QA。Evaluator 不是固定开关，而应该用在模型尚不能稳定独立完成的能力边界上。

## 4.7 我怎么理解这篇？

这篇文章把 Eval 从“发布前的离线分数”推进到“运行时控制器”：

```text
执行 -> 独立评价 -> 修改 -> 再评价 -> 达标或停止
```

但即便有代码检查、端到端测试、独立 Evaluator 和内部 Dogfooding，真实生产系统仍可能出现没有被覆盖的组合故障。第五篇正是这个反例。

---

# 五、An update on recent Claude Code quality reports

- **来源**：[Anthropic Engineering](https://www.anthropic.com/engineering/april-23-postmortem)
- **发布日期**：2026-04-23
- **它要回答的问题**：为什么 Claude Code 的内部 Eval 没有及时复现用户感受到的质量退化？

## 5.1 不是一次退化，而是三个变化叠加

Anthropic 最终定位到三个独立问题：

|时间|变化|用户感知|处理|
|---|---|---|---|
|2026-03-04|默认 Reasoning Effort 从 `high` 改成 `medium`|延迟降低，但复杂任务显得不够聪明|2026-04-07 回滚|
|2026-03-26|空闲一小时后清理旧 Thinking 的优化存在 Bug|遗忘、重复、异常工具选择和更多 Cache Miss|2026-04-10 修复|
|2026-04-16|System Prompt 增加严格简洁限制|文本更短，但 Coding Quality 下降|2026-04-20 回滚|

三个变化影响不同流量、不同模型和不同时间段，聚合后看起来像一种广泛但不稳定的“模型退化”。API 和推理层本身并没有变化。

## 5.2 最有代表性的 Bug：持续丢失旧 Thinking

原设计是：会话空闲超过一小时后恢复时，只清理一次旧 Thinking History，降低 Cache Miss 后重新发送上下文的成本。

实际实现却是：只要一个会话跨过一次空闲阈值，之后每一轮都继续清理旧 Thinking Blocks。

![Claude Code 空闲恢复逻辑的预期行为与实际 Bug](assets/wiki/anthropic-agent-eval-engineering/source-quality-postmortem.png)

*原图来自 Anthropic。左侧是只在恢复时清理一次，右侧是 Bug 导致后续每轮继续丢弃推理历史。*

Agent 仍然能够继续调用工具，但越来越缺少“为什么之前这样做”的上下文，于是出现：

- 忘记早先计划
- 重复已经执行的操作
- 选择奇怪的工具
- Follow-up Message 进一步放大问题
- Prompt Cache 持续 Miss，使用额度更快耗尽

## 5.3 为什么现有测试没有抓到？

这个 Bug 穿过了：

- 多轮人工 Code Review
- 自动 Code Review
- Unit Tests
- End-to-end Tests
- Automated Verification
- 内部 Dogfooding

原因并不是单纯“测试写少了”，而是它位于多个系统的交界处：

```text
Claude Code Context Management
  × Anthropic API Header
  × Extended Thinking
  × Prompt Cache
  × 长时间空闲后的会话恢复
```

同时，两个无关实验又遮蔽了 Bug：一个内部 Message Queue 实验，以及一个 Thinking 展示方式变化。内部环境中的大部分 CLI Session 因此难以重现外部用户看到的问题。

最终发现和确认根因花了一周以上。

## 5.4 为什么 System Prompt Eval 也漏掉了？

Anthropic 为减少 Opus 4.7 的输出长度，在 System Prompt 中加入了非常严格的字数限制。

初始内部测试连续数周没有发现回归。问题出现后，他们使用更广的 Eval Suite 做逐行 Ablation，才发现该指令会让 Opus 4.6 和 4.7 在某项评测上下降约 3%。

这说明 Prompt Change 不是“文案修改”，而是模型行为代码：

- 应该逐模型测试
- 应该逐行 Ablation
- 应该有更宽的 Eval Suite
- 应该保留 Soak Period
- 应该渐进发布，而不是一次切换全部流量

## 5.5 Anthropic 后续改变了什么？

- 让更多内部员工使用与外部用户完全一致的 Public Build。
- 扩大 Code Review 能访问的跨仓库上下文。
- 对每次 System Prompt 变化运行更广的逐模型 Eval。
- 使用 Ablation 分析每条 Prompt 指令的影响。
- 对可能牺牲智能的修改增加 Soak Period 和渐进 Rollout。
- 更系统地吸收 `/feedback` 和可复现用户报告。

## 5.6 我怎么理解这篇？

这篇最重要的结论不是“测试仍然会漏 Bug”，而是：

> **用户体验评估的对象是完整生产系统，而内部 Eval 经常只覆盖模型或单个组件。**

生产质量不能只依赖自动 Eval，还需要：

- 生产监控
- A/B Test
- 用户反馈
- Public Build Dogfooding
- 人工 Trajectory Review
- 真实失败回流 Regression Suite

---

# 六、最后汇总：五篇文章组成了一套什么方法论？

![Agent Eval 五层系统：从任务到生产反馈](assets/wiki/anthropic-agent-eval-engineering/agent-eval-five-layer-system.svg)

五篇文章分别揭开了 Agent Eval 的五层问题：

|顺序|文章|暴露的问题|最终原则|
|---:|---|---|---|
|1|Demystifying evals|Agent Eval 的对象远大于最终回答|同时评估 Task、Trajectory、Outcome、Harness 和 Grader|
|2|Infrastructure noise|测量装置本身改变成绩|固定并公开资源、时间、网络和 Sandbox 配置|
|3|Eval awareness|被测 Agent 会主动寻找评分漏洞|把 Eval Integrity 当成持续对抗问题|
|4|Harness design|Generator 不擅长评价自己的工作|分离 Generator 与 Evaluator，让评价进入运行循环|
|5|Quality postmortem|离线全绿仍可能线上退化|把生产监控和用户失败持续回流 Eval Suite|

## 6.1 五类 Eval Failure

|失败类型|表面现象|真正原因|
|---|---|---|
|Specification Failure|Agent 看起来完成任务|只检查自我报告，没有检查世界状态|
|Measurement Failure|同一模型出现不同结果|Harness、资源、网络或 Grader 没有固定|
|Integrity Failure|Benchmark 分数异常高|污染、答案泄漏、Eval awareness 或评分漏洞|
|Evaluator Failure|循环评分上升但质量没有同步上升|Rubric 偏差、自评宽松、Judge 未校准|
|Distribution Failure|内部 Eval 正常，用户感觉退化|真实长会话、组合故障和 Public Build 没进入测试分布|

## 6.2 最小可用 Agent Eval Stack

如果要给一个真实 Agent 产品建立 Eval，可以按以下顺序：

### Step 1：从真实任务开始

- 收集真实用户任务、人工返工和生产失败
- 为每个 Task 写清楚允许工具、禁止行为和最终状态
- 同时保留简单任务、常规任务和能力边界任务

### Step 2：优先建设 Outcome Grader

- 数据库状态
- 文件系统状态
- API 和业务对象状态
- Unit Test、Pass-to-pass Test
- 权限、安全与不可破坏约束

不要让 Agent 的 Final Answer 充当完成证明。

### Step 3：组合三类 Grader

- 确定性规则负责正确性底线
- LLM Rubric 负责开放式质量
- 人类专家负责校准和发现新失败模式

### Step 4：为非确定性设计 Trial

- 同一 Task 运行多个 Seed
- 同时报告 pass@1、pass@k 和 pass^k
- 给出置信区间
- 将 Infrastructure Error 与 Model Failure 分开报告

### Step 5：固定完整系统版本

```text
model version
agent harness version
prompt / skill version
tool and environment version
grader version
infra configuration
task dataset version
```

这些变量中的任何一个改变，都可能让历史分数失去直接可比性。

### Step 6：持续做 Integrity Review

- 检索问题和答案是否泄漏
- 审查异常高分轨迹
- 使用 Canary
- 隔离答案与评分逻辑
- 对开放网络任务使用动态数据

### Step 7：把生产失败变成 Eval 资产

每次生产事故都应该沉淀成：

1. 一个最小可复现 Task
2. 一个 Outcome Check
3. 一个 Trajectory Assertion
4. 一个进入 CI 的 Regression Test
5. 一个线上监控指标

## 6.3 三个最终判断

### 判断一：Agent Benchmark 本质上是系统 Benchmark

只报告模型名称是不够的。Harness、工具、资源、重试、Grader 和任务版本都属于结果的一部分。

### 判断二：Eval 的价值不在排行榜，而在可靠迭代

好的 Eval 应该帮助团队回答：

- 这次改动修复了什么？
- 它破坏了什么？
- 是否值得增加的成本和延迟？
- 失败发生在模型、Harness、环境还是产品层？

### 判断三：Eval 最终会成为 Agent Loop 的控制器

未来的基本结构不再只是：

```text
Prompt -> Agent -> Answer
```

而更可能是：

```text
Goal
  -> Agent 执行
  -> Outcome / Trajectory Grader
  -> 修正、重试或升级
  -> Regression Memory
  -> 下一轮执行
```

如果只保留一句话：

> **先把 Eval 当成产品和基础设施来建设，再把它当成一个 Benchmark 分数来看。**

---

*参考资料：*

1. [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), Anthropic Engineering, 2026-01-09
2. [Quantifying infrastructure noise in agentic coding evals](https://www.anthropic.com/engineering/infrastructure-noise), Anthropic Engineering, 2026-02-05
3. [Eval awareness in Claude Opus 4.6's BrowseComp performance](https://www.anthropic.com/engineering/eval-awareness-browsecomp), Anthropic Engineering, 2026-03-06
4. [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), Anthropic Engineering, 2026-03-24
5. [An update on recent Claude Code quality reports](https://www.anthropic.com/engineering/april-23-postmortem), Anthropic Engineering, 2026-04-23
