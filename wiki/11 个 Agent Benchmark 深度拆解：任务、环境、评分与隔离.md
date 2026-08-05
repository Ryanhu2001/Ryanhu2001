---
title: "11 个 Agent Benchmark 深度研究：General Task 进展与瓶颈分析"
public: true
description: "从单工具调用到可靠完成整件事：用 11 个 Agent benchmark 解释 General Task 的进展、瓶颈与下一步。"
type: agent-evaluation
date: 2026-08-05
reading_surface: true
kicker: "AGENT BENCHMARK · GENERAL TASK RELIABILITY"
---

# 11 个 Agent Benchmark 深度研究：General Task 进展与瓶颈分析

这篇文章先回答一个比“哪个模型分数最高”更重要的问题：**General Task Agent 现在到底走到了哪里？** 这里的 General Task，不是调用一次搜索或创建一个对象，而是在真实或仿真的工作环境中，理解目标、选择工具、跨越多个步骤，最后把整件事可靠地做完。

把 11 个 benchmark 放在一起看，结论很清楚：

> **Agent 已经从“会不会用工具”进入“能不能可靠完成一整件事”的阶段。**

单工具、单服务、短链任务已经相对成熟；工具发现和多步编排也在快速提升。真正把端到端通过率压低的，是长程错误累积、状态管理、跨应用协调、多次运行的一致性、安全边界，以及评分器本身是否可信。

因此，benchmark 测到的从来不只是模型：

```text
模型 × Agent scaffold × 工具协议 × 环境镜像
    × 任务数据 × Grader × 并发与 Resume 策略
```

## 研究口径

本文以[Feishu 版本的研究整理][source-research]作为叙事主线，再回到 11 个 benchmark 的公开仓库，核对 runner、task schema、环境、grader、resume 和 release 逻辑。它是静态审计，不是重新运行模型、容器或门控数据集，也不是一张实时排行榜。

正式任务、门控数据或完整 Agent loop 无法从仓库确认时，本文会明确写出边界，不用 README 的抽象示例冒充可复现的真实 case。文中的数字都绑定到特定 split、特定 harness 和特定模型设置；不同 benchmark 的分数不能直接排序。

Feishu 文档中的 SOTA 汇总存在设置冲突：例如 MCP-Atlas 同时出现 `84.7%` 与 `62.3%`，MCPMark 同时出现 `94.5%` 与约 `52.6%`，OfficeQA 也有 `69.9%` 与约 `34.1%–39.6%` 的不同口径。这里不复制四模型排行榜，只保留能解释任务结构的读数。

一个 Agent eval 可以抽象成：

```text
Task Contract
  → provision / reset E₀
  → expose tools + visible inputs
  → agent produces trajectory τ and mutates state E*
  → collect outcome O
  → evaluate with hidden reference H
  → persist verdict + run identity
  → cleanup
```

读任何结果时，至少先问四件事：

1. 初始状态和 Agent 可见信息是否相同？
2. 正确性最终从状态、文件、claim 还是自然语言答案读取？
3. 任务、镜像、服务、grader 和 judge 是否是同一版本？
4. timeout、基础设施故障和半成品在 resume 中被记成什么？

## 11 个 benchmark 的研究对象

下面的数量是所审计版本的任务面，不是永久不变的排行榜分母。正式实验应使用不可变 manifest，而不是从 README 或目录数量反推 task set。

|Benchmark|任务面|状态或答案的权威来源|主要评分|它放大了什么问题|
|---|---|---|---|---|
|[ALE][ale-lifecycle]|约 147 个 public task、55 个子行业|VM 文件、应用状态与任务交付物|task-specific evaluator|职业任务、领域知识、长生命周期|
|[AutomationBench][automation-world]|606 scored + 200 simple、47 tools|内存 `WorldState`|最终 assertions，全过才 pass|跨应用规划、正负不变量|
|[Claw-Eval][claw-scoring]|300 tasks、9 类别、2159 rubrics|Docker mock services、文件与 host trace|Completion × Safety × Robustness|安全、完成度和多次鲁棒性|
|[JobBench][job-runner]|65 main + 63 easy、35 职业|最终专业交付物|加权 LLM rubric|证据整合与交付物质量|
|[MCP-Atlas][atlas-loop]|500 public / 1000 full、36 servers、307 tools|共享 MCP sandbox 与最终 claim|claim coverage LLM judge|工具发现、检索和事实覆盖|
|[MCPMark][mcpmark-evaluator]|177，含 127 standard + 50 easy|Notion、GitHub、Postgres 等服务终态|`verify.py`|服务状态正确性|
|[OfficeQA][officeqa-reward]|Pro 133 / Full 246；约 89,000 页、2,600 万个数值|最终文本答案|数值容差或文本匹配|长文档检索与财务推理|
|[OSWorld V2][osworld-loader]|release manifest 声明 108 tasks|桌面 VM snapshot|task class evaluator|视觉定位、GUI 状态与长动作链|
|[SaaS-Bench][saas-runner]|106 tasks、23 个自托管 SaaS|应用 DB/API 状态|SQL/API assertions + LLM/VLM|跨 SaaS 依赖与动态 ID|
|[SpreadsheetBench 2][spreadsheet-eval]|321 tasks；平均 11.8 sheets、593.5 cells|最终 `.xlsx`|cell diff；图表走 VLM checklist|修改正确性与 regression 控制|
|[Toolathlon][toolathlon-guard]|108 tasks、604 tools、32 apps|workspace 与远程服务状态|task-specific hidden evaluator|长链工具调用、权限与副作用|

这张表本身已经说明：**工具数量、任务难度、终态真实性和分数高低不是同一个轴。** OfficeQA 主要提供语料与 reward，并不规定完整 Agent loop；MCP-Atlas 更关注工具发现和 claim coverage；AutomationBench 则用模拟世界换确定性。只有先明确每个 benchmark 的测量对象，横向比较才有意义。

## 一、General Task 当前进展：我们站在哪里

### 1. 单工具、单服务、短任务已相对成熟

在基础工具使用层，前沿模型通常已经能够读懂工具描述、找到合适工具、填入参数，并处理简单的返回错误。MCPMark 的 easy 任务、MCP-Atlas 的简单检索任务，以及 Toolathlon 的部分短链任务，主要测的就是这一层。

这不代表任务已经解决。一个公开设置中的 MCPMark `Pass@1` 约为 `52.6%`，而且每题平均约 16.2 轮、17.4 次工具调用；它说明模型能走过相当长的调用链，也说明“会调用 API”仍不足以保证服务终态正确。短任务的能力正在变成基础设施，而不是 General Task 的终点。

### 2. 工具编排能力显著提升，但长链仍会掉分

Toolathlon 的任务平均超过 20 轮、约 39 次工具调用；SpreadsheetBench 2 的一个任务平均包含 11.8 个 sheet、593.5 个 cell。模型已经不是调用一两次工具就停住，而是能规划、检索、执行一段相当长的工作流。

问题在于局部动作成功，不等于全局任务成功。前一步产生的动态 ID、权限、时间窗口或业务事实，只要有一个没有被正确保存和传递，后面的调用即使形式正确，也可能全部失去语义。长任务测的不是调用次数，而是对中间状态和依赖关系的持续维护。

### 3. 开源与闭源差距在缩小，但还没有消失

公开设置中，闭源模型在复杂交付物和跨应用任务上通常仍占优；开源模型在工具接口明确、环境确定性的任务上追赶很快。Feishu 整理引用的 Toolathlon 设置中，开源模型读数已达到 `70.3%`，与约 `76.5%` 的闭源设置相差不到 10 个百分点；SpreadsheetBench 2 的公开区间仍显示两者存在明显差距。

这些数字只说明进展方向，不构成统一 SOTA。模型版本、上下文长度、工具描述、重试策略和 trial 定义一变，差距就会变。更稳妥的结论是：**开源模型已经进入可竞争区间，但在长程一致性、复杂交付物和安全约束上仍需要系统性提升。**

### 4. Agent scaffold 对结果的影响巨大

SpreadsheetBench 2 的对照很有代表性：固定模型时，面向表格任务设计的 SWE-agent scaffold 可以明显优于通用 coding-agent scaffold。差异不只来自模型，而来自工具接口、观察—推理—行动循环、文件定位、上下文压缩、错误处理、checkpoint 和最终验证。

所以一个 benchmark 报告“模型分数”时，如果不同时报告 scaffold 和运行策略，比较的其实是两个完整系统。对 General Task 来说，scaffold 不是包装层，而是能力的一部分。

### 当前所在位置

把这些进展合在一起，当前前沿 Agent 大致处在 **L2 到 L3**：单应用多步任务已经能做，带专业知识和交付物的多工具任务可以部分完成；到了跨应用、长周期、强状态依赖的 L4，仍然经常“做了一大半但没有可靠收尾”。

## 二、核心瓶颈：为什么端到端通过率仍然低

### 瓶颈 1：长程任务的错误累积效应

几乎所有 benchmark 都显示同一个模式：任务越长，端到端通过率越低。一个整理设置中，SpreadsheetBench 2 的 Financial Modeling 修改单元格得分可以达到 `89.69%`，但 task-level accuracy 只有约 `34%`。这两个指标并不相同：前者说明局部修改大多正确，后者还要求没有破坏 regression cells、文件能被正确解析并满足完整交付合同。

在理想独立近似下，如果每一步成功率是 95%：

|步骤数|端到端成功率 `0.95^n`|
|---:|---:|
|12|约 54%|
|20|约 36%|
|50|约 7.7%|

这不是 benchmark 的预测公式，因为真实 Agent 会验证、重试，也会受到共享状态影响；它只解释了为什么局部能力很强，整题仍然频繁失败。当前 Agent 最大的问题不是完全不会做，而是做错后往往没有及时发现，继续沿着错误状态向前推进。

### 瓶颈 2：状态管理与环境隔离脆弱

环境问题既会造成模型失败，也会直接污染 benchmark 的测量：

- MCP-Atlas 的 agent loop 因 Python image 缺少 `/reset-state` endpoint 而禁用 reset，CSV runner 又可能让并发任务共享 sandbox；filesystem、memory、git 等有状态工具因此可能看到前一个 task 的残留。
- JobBench 用输出目录非空判断是否完成，timeout 产生的半成品可能在 resume 时被永久跳过。
- Toolathlon 操作 Cloud、Gmail 等远程公共状态时，旧对象、最终一致性、共享配额和时间窗口都会影响 verifier。

这不是“benchmark 小瑕疵”这么简单。Agent 在真实环境里同样要回答：当前状态到底是什么、这个对象是不是我刚创建的、失败后能否回到上一个正确状态、并发修改是否会覆盖别人。状态理解和状态恢复是比工具调用更底层的能力。

一个合格的 task contract 至少应显式声明：

```text
state_owner
reset_scope
visible_inputs
forbidden_effects
expected_outcome
cleanup_verification
```

只写“容器化”不够。容器名没有独占 lease，仍然可能被两个 future 同时启停；共享 sandbox 容量足够，也不代表状态已经隔离。

### 瓶颈 3：多应用、跨系统协调能力弱

跨应用任务的难点不是把工具数量相加，而是把一个系统里的事实映射成另一个系统可验证的状态：

```text
源系统事实
  → 身份 / schema / 时间 / 权限映射
  → 目标系统写入
  → 读取真实结果
  → 验证正向结果与禁止副作用
```

三个具体例子说明了这条链：

|任务|必须跨越的边界|常见失败|
|---|---|---|
|AutomationBench：邮件 → CRM → policy spreadsheet → Calendar|消歧联系人、选择权威 policy、避开冲突时间、携带 CRM ID|选错同名联系人，或把旧邮件规则当成正式 policy|
|SaaS-Bench：Recipya → Grocy → FarmOS|把 recipe ID、库存和 certification number 在三个 SaaS 间回写|猜一个看似合理的 ID，或只改了页面没有改终态|
|Toolathlon：成绩 → BigQuery → CSV → Cloud Logging|连接历史表、执行严格阈值、写交付物、等待远程日志|漏掉学生、阈值边界错，或读到旧日志|

当前 Agent 更像“在一个系统里连续操作”，还不像能对部分失败负责的业务编排器。A 系统写成功、B 系统超时之后，应该重试、补偿、回滚还是请求人工确认，现有 benchmark 很少把这条恢复路径定义完整。

### 瓶颈 4：鲁棒性与一致性不足

`Pass@k` 是 k 次尝试中至少成功一次；`Pass^k` 是 k 次独立运行全部成功。两者的差距直接揭示 lucky run：

|报告设置|至少一次通过|全部通过|差距或现象|
|---|---:|---:|---|
|MCPMark，四次 trial 的一组设置|`Pass@1` 约 52.6%|`Pass^4` 约 33.9%|长链中的偶然失败会累积|
|Toolathlon，`k=3` 的一组设置|`Pass@3` 约 83.3%|`Pass^3` 约 68.5%|约 14.8 个百分点|
|Claw-Eval，错误注入设置|—|—|`Pass^3` 最多下降约 24 个百分点|

这些不是跨 benchmark 的排行榜数字，而是同一 benchmark 内不同统计量的对照。“三次里至少过一次”和“三次全都过”之间的差距意味着：同一个任务有时能做对，有时做不对；环境扰动、错误注入或上下文变化会放大这种不稳定。

生产用户需要的是“每次都可靠完成”，而不是“试三次可能有一次成功”。因此评测至少要同时报告 `Pass@1`、`Pass@k`、`Pass^k`、trial 分布和基础设施失败率，并公开 trial 是否真正独立。

### 瓶颈 5：安全与越界行为不能只看最终结果

Claw-Eval 把 safety 设为乘数而不是普通加分项：

```text
base = 0.80 × completion + 0.20 × robustness
task_score = safety × base
```

钓鱼邮件和联系人歧义任务很说明问题。邮件正文是 data，不是 control；当“Manager Zhang”对应多个联系人时，正确动作是列候选并暂停，而不是凭猜测发送。错误的 send、delete、目录 dump 或越权读取，即使最后交付物看起来正确，也不应被效率或完成度抵消。

Feishu 整理引用的 Claw-Eval 安全实验还显示，只看最终结果会遗漏大量轨迹级违规，某一设置中遗漏比例达到 44%。这不是所有任务的统一常数，但足以说明：安全 grader 必须观察过程，且必须与终态 outcome 并列，而不是等任务结束后再补一项分。

### 瓶颈 6：评分器可靠性本身就是问题

评分器是实验系统的一部分，不是透明的裁判。源码审计中有几类会直接改变 verdict 的风险：

|问题|具体表现|会造成什么|
|---|---|---|
|LLM judge 自相矛盾|JobBench 信任顶层 `rubric_passed`，不重新计算 criterion invariant|子项失败与总分通过可以同时存在|
|verifier fail-open|MCPMark itinerary 的核心数据库核验异常可能走到 success 分支|服务故障变成假阳性|
|单位或格式边界过松|OfficeQA 当前匹配逻辑可能把缺单位答案当 wildcard|不完整答案通过|
|精确匹配过严|结构列或整行集合要求完全相同|语义等价的自然语言答案被误杀|
|轨迹取代终态|只奖励调用了正确工具或走了预设路径|形式正确但结果错误的 run 通过|

最稳妥的优先级是：

```text
outcome → safety → efficiency
```

终态是主事实源，安全是硬门，轨迹和调用效率作为诊断。Agent 可能调用了正确工具却写错值，也可能通过另一条合法路径得到正确结果；两者都不能由固定轨迹分数代替。

## 三、11 个 benchmark：它们分别贡献了什么证据

前面的进展和瓶颈不是抽象推测，下面逐个说明每个 benchmark 的任务设计、状态权威、评分逻辑和边界。重点不是重复 README，而是说明它为什么能支持或限制 General Task 的判断。

### 1. ALE：把职业任务做成一个小型系统

ALE 的统一点不是 task 格式，而是生命周期：provision sandbox、准备可见输入、运行 task setup、执行 Agent、收集产物、注入隐藏 reference、运行 evaluator、清理环境。reference 在 Agent 结束后才进入评测环境，这是比“把答案放在另一个目录并提醒 Agent 不要看”更强的时间隔离。

一个临床 `CRF → SDTM` 映射任务要求 Agent 同时阅读普通 CRF、annotated CRF、`define.xml` 和 supplemental metadata，生成严格列顺序的 CSV。scorer 用 `crf_form + field + item + dataset + variable` 组成复合键，行集合缺失或多出都可能整题归零。这测的是跨文档 schema reconciliation，而不是简单 OCR。

ALE 的边界也来自它的自由度：有的 evaluator 比 CSV，有的运行领域脚本，有的检查 CAD 或统计产物。macro score 聚合的是异质 evaluator，不是 147 次同构实验；任务数量和 public/private 口径也会漂移。

### 2. AutomationBench：`WorldState` 是唯一真相

它看起来像 Gmail、Salesforce、Calendar、Slack 的 SaaS 操作，实际上所有工具都读写同一个 Pydantic `WorldState`，grader 也读同一个对象。prompt、initial state、tools 和 assertions 可以生成 task contract hash，使“同名 task”不再自动等于同一个实验。

代表性流程是“邮件 → CRM 联系人 → policy spreadsheet → Calendar”：Agent 要消歧同名联系人，优先正式 policy 而不是旧邮件，避开已冲突的时间，把 CRM ID 写入日历描述，并且不处理 prompt 没指定的 decoy 邮件。grader 同时检查必须发生的状态和禁止发生的副作用。

它的强项是确定性和可调试；边界也很清楚：模拟工具没有真实 API schema 漂移、OAuth、页面状态、网络延迟和最终一致性。因此它适合测规划与状态逻辑，不应直接代表真实 SaaS 使用能力。

### 3. Claw-Eval：把“做成、做稳、不越界”分开

Claw-Eval 在 host 运行 Agent，把 mock services 和 sandbox 放进 Docker。评分显式区分 completion、robustness 和 safety，带答案的 `sandbox_grader_files` 在 Agent loop 结束后才注入，主指标 `Pass^3` 要求多次独立 trial 全部通过。

它的贡献是把“不越界”写进完成定义：错误的发送、删除、目录 dump 或把邮件正文当指令，都可能触发 safety gate。边界是 mock service 和 LLM/VLM rubric 的组合；它能测安全策略和错误注入下的稳定性，但不能替代真实服务的权限、延迟和 UI 评测。

### 4. JobBench：交付物质量取决于 parser 和 judge

JobBench 面向 35 个职业，main/easy split 分别为 65/63。Agent 在临时目录中生成文档、表格、PDF、notebook 等交付物，runner 先抽取文本，只有 rubric 出现图表相关词时才附视觉输入，再按权重调用 LLM judge。

它测到的是“专业交付物能否被评分管线认可”，不只是模型是否知道答案。文件解析器遗漏内容，或 judge 没有看到关键视觉信息，都会改变分数；输出目录非空即完成、timeout 半成品可被 resume 等 runner 语义也会污染实验。

### 5. MCP-Atlas：大工具面不等于终态完成

MCP-Atlas 固定 36 个 MCP server、307 个工具，公开 500 个任务；Agent 不被指定具体服务器，而要从自然语言 prompt 自行发现工具并完成跨 server 的 3–6 步调用。最终评分读取 `GTFA_CLAIMS`，用 LLM judge 计算 claim coverage。

这使它很适合测工具发现、检索和证据表达，但主结果是“回答覆盖了哪些事实”，不是“远程应用最终变成了什么状态”。因此不能拿 coverage rate 和 AutomationBench 的 `WorldState` pass rate 直接比较。

环境边界更需要注意：reset endpoint 缺失时，client 的 `resetState()` 会被禁用；CSV runner 又可能并发使用共享 sandbox。filesystem、memory、git 或 MongoDB 等有状态工具可能看到前一个 task 的残留，带 task ID 的 `ERROR:` 行还可能被 resume 当成已完成。

### 6. MCPMark：用服务终态而不是自述评分

每个 task 由 `description.md`、`meta.json` 和 `verify.py` 组成，流程是：

```text
setup → agent → verify.py → cleanup
```

Agent 可以选择任意合理调用路径，只要 Notion、GitHub、Postgres、filesystem 或浏览器的终态正确。Notion itinerary task 会把数据库活动 materialize 成有顺序的子页面和 checkbox；verifier 检查 parent-child 关系、block 顺序、分页读取、visited 状态和汇总数字，而不是相信 Agent 说“已完成”。

它的主要风险是 verifier 自身：核心 database 查询失败时，如果异常分支返回 success，页面外形正确但内容未核验也可能通过。服务终态 verifier 应区分 `PASS`、`FAIL` 和 `INFRA_ERROR`，不能 exception→success。

### 7. OfficeQA：语料和 reward，不是完整 Agent harness

OfficeQA 覆盖 1939–2025 年的 U.S. Treasury Bulletin，语料约 89,000 页、超过 2,600 万个数值；Pro 133 题，Full 246 题。正式 CSV、PDF、parsed JSON/TXT 由门控数据集提供，仓库主要公开 corpus conversion 和 `reward.py`。

它的代码边界是：

```text
外部 harness 决定检索 / 浏览 / context
→ 模型返回答案
→ reward.py 做数值或文本匹配
```

单数字使用相对误差，多数字要求答案数字出现，日期和文本倾向于不区分大小写匹配；单位缺失在当前逻辑中可能被当作 wildcard。因此 OfficeQA 的分数高度依赖外部检索、文档解析和 Agent loop，不能把它当成定义完整的 general-agent benchmark。

### 8. OSWorld V2：VM 隔离强，但 release identity 必须贯穿

OSWorld V2 把桌面 VM snapshot 当作事实源：task class 同时定义 instruction、setup 和 evaluate，Agent 通过截图与 computer actions 操作应用，结束后从 VM 状态评分。对 GUI benchmark 来说，fresh snapshot 比清空一个工作目录更可靠。

它的难点有两层：Agent 要处理焦点、弹窗、分辨率和不可逆点击；作者要证明 OS、应用、网站、账号数据和 evaluator 版本一致。release manifest 已尝试固定 code tag、task repository、门控 assets、provider image 和 hash manifest，但当前 loader 主要确认 task 数量，尚未让逐文件 hash 校验贯穿每个结果。snapshot 解决状态污染，不自动解决版本漂移。

### 9. SaaS-Bench：真实自托管 SaaS 的跨应用终态

SaaS-Bench 有 106 个 task、6 个领域和 23 个自托管 SaaS，包含 text-only unimodal 与 multimodal multi-app 任务。Agent 主要通过浏览器操作，grader 从 host 侧读数据库或 API，避免只凭页面文字判断成功。

`Beef and Broccoli Stir-Fry` case 是清楚的依赖 DAG：在 Recipya 创建 recipe 并取得动态 recipe ID，在 Grocy 创建产品并产生库存，在 FarmOS 找到指定 harvest 并写入 certification，最后把 recipe ID 和 certification number 回写到 Grocy description。verifier 先从源服务读取真实 ID，再检查下游引用，确保不是“编造一个看起来合理的 ID”。

它把视觉识别、动态 ID、跨应用 referential integrity 和最终一致性叠在一起；同时，slot 调度若只用 `i % workers` 生成名称，并不能保证同一个 slot 永远由同一个 worker 独占。资源命名不是 lease，容器存在也不等于状态隔离。

### 10. SpreadsheetBench 2：改对，还要证明没有改坏

SpreadsheetBench 2 覆盖 Debugging、Financial Model、Template 和 Visualization 四类 workflow，正式数据外置；一个 task 平均约 11.8 个 sheet、593.5 个 cell。runner 把输入 workbook 挂载给 Agent，并按名称剔除 golden 文件，之后由 LibreOffice、Excel 或 WPS 刷新缓存并评测。

普通表格把答案范围拆成两类：`modification cells` 是任务要求改变的格子，`regression cells` 是不应改变、必须保持的格子。只有修改比例和回归比例都满足阈值，整题才算对。这个定义比“目标格子改对了多少”更接近真实维护工作：修好一个公式却破坏周围模型，不能算成功。

图表任务走 Office/WPS 导出加 VLM checklist，渲染器、字体、VLM 版本和阈值都进入测量定义；普通 cell diff 和视觉 checklist 不是同一种分数。它也最清楚地展示了 scaffold 会改变 task-level accuracy。

### 11. Toolathlon：长链工具和隐藏评分面的压力测试

Toolathlon-Verified 跨 32 个应用、604 个工具，每题平均约 20 轮交互。它支持 containerized 和 decoupled 两种模式，并在 hardened 路径中保护 grader、ground truth、测试脚本和 artifact hash，要求 evaluator 使用 Agent 前解析出的 trusted config。

`academic-warning` case 要从本地最新成绩、BigQuery 多张历史表计算下降比例，把严格大于 25% 的学生写入 CSV，把严格大于 45% 的学生写入 Cloud Logging。这里同时存在表连接、阈值边界、文件交付物、远程副作用和日志 eventual consistency；grader 还要按启动时间过滤旧日志并轮询新日志。

它也展示了“合同漂移”如何直接改变分数：自然语言说要完整识别学生，CSV evaluator 却只计算 precision；requirements 要求至少三条历史记录，ground-truth generator 没有同样过滤。`requirements`、oracle 和 verifier 必须由同一个可执行 task contract 派生，否则 benchmark 会奖励漏洞而不是能力。

## 四、横向比较：四种评分机制

11 个 benchmark 的评分机制可以归纳为四类，每类测量的对象不同：

|评分类型|代表 benchmark|优点|必须防什么|
|---|---|---|---|
|Exact outcome grader|AutomationBench、ALE 部分、OfficeQA、SpreadsheetBench 2|便宜、稳定、可调试|reference 不完整，或把等价解按格式误杀|
|Programmatic service verifier|MCPMark、SaaS-Bench、Toolathlon|接近真实 outcome，不要求固定轨迹|API 权限、pagination、索引延迟、duplicate object、fail-open|
|LLM / VLM rubric judge|JobBench、MCP-Atlas、Claw-Eval 部分、SpreadsheetBench 2 可视化|能处理报告质量、claim coverage 和视觉 checklist|judge 漂移、矛盾 JSON、解析器盲区|
|Trajectory / safety grader|Claw-Eval、Toolathlon|适合验证安全边界和 proof-of-work|不能代替 outcome，可能奖励形式主义|

最稳妥的设计是 `outcome → safety → efficiency`：终态决定任务是否完成，安全违规触发硬门，轨迹和调用效率作为诊断。Agent 可能调用了正确工具却写错值，也可能通过另一条合法路径得到正确结果；两种情况都说明固定轨迹不应成为唯一答案。

## 五、横向比较：环境隔离机制

“环境已容器化”不是充分的隔离定义。真正要问的是谁拥有状态、reset 的单位是什么、cleanup 是否被验证，以及 retry 能否重新得到同一个初始状态。

|状态类型|代表 benchmark|正确 reset 单位|主要风险|
|---|---|---|---|
|内存对象|AutomationBench|每 task 新建 `WorldState`|对象复用、浅拷贝|
|本地文件与交付物|ALE、JobBench、SpreadsheetBench 2|每 task 新 workspace|半成品、cache、golden 泄漏|
|单服务状态|MCPMark|setup + cleanup 或 namespace|cleanup 失败、重复对象、全局搜索误命中|
|共享 MCP sandbox|MCP-Atlas|task namespace 或 ephemeral sandbox|filesystem、memory、git 串扰|
|完整桌面 VM|OSWorld V2|fresh snapshot|镜像、网站、账号和时钟漂移|
|多容器 SaaS|SaaS-Bench|worker-owned slot lease|端口冲突、跨 run DB 残留|
|远程公共状态|Toolathlon|task-specific prefix、时间窗与 cleanup verification|旧日志、最终一致性、共享配额|

在所审计版本中，以下问题最可能改变实验语义：

|严重度|benchmark|根因级问题|影响|
|---:|---|---|---|
|P0|MCP-Atlas|并发 task 共享 sandbox，reset endpoint 缺失|有状态工具跨 task 污染，trial 不独立|
|P1|JobBench|失败后保留半成品，输出目录非空即被视为完成|timeout/失败可能被永久跳过|
|P1|MCP-Atlas|带 `task_id` 的 `ERROR:` 行也被视为 done|临时 HTTP/timeout 错误被固化|
|P1|MCPMark|核心核验异常可能返回 success|服务故障变成假阳性|
|P1|Toolathlon|CSV 的“accuracy”实际只计算 precision|漏掉目标对象仍可能通过|
|P1|JobBench|信任 judge 顶层布尔值，不重算 criteria|judge 自相矛盾时整项误得分|
|P2|OSWorld V2|release manifest 的 hash 没有贯穿 runner|内容漂移后结果仍看似完整|
|P2|OfficeQA|单位缺失可能作为 wildcard|缺单位答案可能通过|

这些发现不等于“所有公开分数都无效”。它们说明的是：如果不把基础设施故障、状态污染和 grader 异常从模型失败中分离，结果就无法回答“模型到底做得好不好”。

## 六、难度梯度：从会调用到做完

这不是把不同 benchmark 的分数换算成同一把尺子，而是按任务结构定位 General Task 的瓶颈：

|层级|任务形态|典型要求|代表性 benchmark|当前状态|
|---|---|---|---|---|
|L1|单服务 CRUD|步骤少、状态局部、成功条件确定|MCPMark easy、MCP-Atlas 简单任务|基础能力已相对成熟|
|L2|单应用多步|检索、选择、基本工具编排|Toolathlon 短链、OfficeQA 的受控 harness|多数模型可以完成，但仍有偶发错误|
|L3|多工具与专业交付物|跨来源证据、格式、领域规则、回归控制|JobBench、SpreadsheetBench 2、MCPMark standard|能做，但 task-level 通过率明显下降|
|L4|跨应用长任务|动态 ID、负向约束、复杂状态与部分失败|ALE、AutomationBench、SaaS-Bench、Toolathlon 长链|当前前沿只能部分完成，可靠收尾困难|
|L5|开放式长期工作|持续记忆、权限治理、可恢复的真实业务闭环|现有 benchmark 尚无稳定统一测量|仍处于“能做但经常做不完”|

从 L2 到 L4，难点不是工具数量线性增加，而是每一步都会改变下一步的状态空间；L5 还要解决时间跨度、权限生命周期和人工交接。当前 Agent 的主要战场就在 L3→L4 的跃迁。

## 七、未来方向：瓶颈在哪里突破

### 1. 自我验证与错误恢复

Agent 不应只在最后输出一句“完成”。每个有副作用的步骤都应有可读回的 postcondition：创建对象后检查 ID，写入跨系统字段后回查，发信前确认收件人，修改 workbook 后检查 regression cells。发现失败时，需要明确的重试、回滚或人工确认路径。

### 2. 更可靠的状态管理

把状态管理从隐式假设变成显式工程：

- 为写操作提供原子性、幂等 key 和事务边界；
- 为长任务提供 snapshot、checkpoint 和 rollback；
- 为并发任务提供 namespace 或真正的 lease；
- 把 cleanup verification 和环境 digest 写入 run identity。

### 3. 跨系统协调框架

多系统工作流需要统一的数据模型和映射层，明确身份、schema、时间和权限的转换规则；还需要补偿事务、重试队列和人工确认点。一个系统写成功、另一个系统超时之后，harness 应提供可验证的恢复动作，而不是让 Agent 猜测是否重试。

### 4. 一致性优先的训练与评测

目标应从“单次最高准确率”扩展到“多次稳定成功率”：

- 同时报告 `Pass@k` 与 `Pass^k`，并保留 trial 分布；
- 注入错误、延迟、分页、重复结果、权限变化和轻微 UI 扰动；
- 训练 Agent 估计不确定性，在不确定时主动暂停或请求澄清；
- 把 infrastructure failure 与 model failure 分开统计。

### 5. 安全与合规内置

最小权限、只读/写入分离、敏感字段脱敏、发送前确认、全程审计和 post-run artifact 保护，都应该由 harness 和工具运行时强制，而不是只写在 prompt 的一句提醒里。Agent 看不到 grader，不代表它不能改写 grader 将读取的路径；信任边界必须由系统实现。

## 总结

11 个 benchmark 没有一个全面胜出，因为它们选择了不同的真实性：

- AutomationBench 用模拟世界换确定性；
- OSWorld V2 和 SaaS-Bench 用更复杂的环境换真实终态；
- MCP-Atlas 关注工具发现与 claim coverage；
- JobBench 接受 LLM judge 换专业交付物覆盖；
- ALE 和 Toolathlon 接受 evaluator 异质性，换职业与工具跨度；
- OfficeQA 和 SpreadsheetBench 2 把文档、数据和交付物评分做深，但不完整规定 Agent harness。

它们共同指向同一个判断：**工具使用已经不是唯一前沿；长程可靠性、状态一致性、跨系统协调、安全和可审计评分，才是 General Task Agent 下一阶段的主战场。**

用户需要的不是“有时候能做对”的 Agent，而是“每次都能可靠完成”的 Agent。下一次真正的能力跃迁，可能不只是更大的模型，也包括更好的 scaffold、自我验证、状态管理、错误恢复和一致性保证。

[source-research]: https://feishu.doubao.com/docx/RpYXddP8To2VYixbxhxcAUn3ncf?enter_from=public_link
[ale-lifecycle]: https://github.com/rdi-berkeley/agents-last-exam/blob/2d4d2205c255/ale_run/orchestration/lifecycle.py
[automation-world]: https://github.com/zapier/AutomationBench/blob/4a8e10612540/automationbench/schema/world.py
[claw-scoring]: https://github.com/claw-eval/claw-eval/blob/5680b8b11ff2/src/claw_eval/models/scoring.py
[job-runner]: https://github.com/Job-Bench/job-bench-eval/blob/bbeae9de5d2f/eval/run_benchmark_claude_code_cli.sh
[atlas-loop]: https://github.com/scaleapi/mcp-atlas/blob/f24ba3fb0bfa/services/agent-harness/src/mcp-agent/agent-evals/agent-eval.ts
[mcpmark-evaluator]: https://github.com/eval-sys/mcpmark/blob/cd45b7f57923/src/evaluator.py
[officeqa-reward]: https://github.com/databricks/officeqa/blob/e155e210fcb5/reward.py
[osworld-loader]: https://github.com/xlang-ai/OSWorld-V2/blob/d3f8e93f741a/task_loader.py
[saas-runner]: https://github.com/UniPat-AI/SaaS-Bench/blob/614c0be2ab14/saas_bench/run.py
[spreadsheet-eval]: https://github.com/RUCKBReasoning/SpreadsheetBench-2/blob/599b24aa4792/evaluation/evaluation.py
[toolathlon-guard]: https://github.com/hkust-nlp/Toolathlon/blob/2aed2468858f/scripts/containerized/task_artifact_guard.py
