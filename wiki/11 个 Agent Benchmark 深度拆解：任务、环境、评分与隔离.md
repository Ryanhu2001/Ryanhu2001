---
title: "11 个 Agent Benchmark 深度研究：General Task 进展与瓶颈分析"
public: true
description: "从工具调用到整件事可靠完成：比较 11 个 Agent benchmark 的任务链、状态权威、评分器与失败边界。"
type: agent-evaluation
date: 2026-08-05
reading_surface: true
kicker: "AGENT BENCHMARK · WHOLE-TASK RELIABILITY"
---

# 11 个 Agent Benchmark 深度研究：General Task 进展与瓶颈分析

这篇文章基于[最新研究整理][source-research]，并回到 11 个 benchmark 的 runner、task schema、环境、grader、resume 与 release 代码核对。主线不再是“哪个模型的分数最高”，而是一个更有用的问题：

> **General Task Agent 已经从“会不会调用工具”，进入“能不能可靠做完一整件事”的阶段。**

短任务、单服务、常见工具的能力已经不再是主要瓶颈。真正把端到端通过率拉低的，是长链中的错误累积、跨系统状态传递、负向约束、环境隔离、多次运行的一致性，以及评分器本身是否可信。

因此，benchmark 测到的不是裸模型，而是：

```text
模型 × Agent scaffold × 工具协议 × 环境镜像
    × 任务数据 × Grader × 并发与 Resume 策略
```

看任何 leaderboard 前，先回答四个问题：

1. 初始状态和可见信息是否相同？
2. 正确性最终从哪个状态或交付物读取？
3. grader、judge、镜像和数据是否是同一版本？
4. timeout、基础设施错误和半成品在 resume 中被记成什么？

## 研究口径

这是源码和公开文档的静态审计，不是重新运行 11 个 benchmark，也不是一张实时排行榜。门控数据集、正式任务或模型报告无法在仓库中核验的地方，我会明确写出边界，不用 README 的抽象示例冒充真实 case。

本文保留能解释系统行为的数字，删除无法确认设置、模型版本或评分定义的 SOTA 汇总。文中出现的分数都应理解为**特定 split、特定 harness 和特定模型配置下的读数**，不能跨 benchmark 排序。

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

![Agent benchmark 的五层评测栈](assets/wiki/agent-benchmarks/evaluation-stack.svg)

图中最重要的不是流程箭头，而是三个边界：

- **可见性边界**：reference、grader 和答案何时进入 Agent 的能力范围。
- **状态边界**：一次 task 的副作用能否进入下一次 task、并发 worker 或 retry。
- **判定边界**：最终分数读的是终态、文件、claim、轨迹，还是另一个模型的意见。

## 一、General Task 已经走到哪里

### 1. 单工具、单服务、短任务已经相对成熟

当任务只要求在一个稳定服务上完成少量 CRUD，工具 schema、输入输出和成功条件都比较局部。MCPMark 的 easy 任务、MCP-Atlas 的简单检索任务，以及 Toolathlon 的部分短链任务，都落在这一层。

但“能调用工具”不等于“能完成工作”。一旦任务要求把一个服务中的动态 ID、权限、时间约束或业务事实带到另一个服务，问题就从 API 记忆变成状态和依赖管理。

### 2. 工具编排已经从单步调用走向工作流

AutomationBench 用 47 个模拟 SaaS 工具和 `WorldState` assertions 把邮件、CRM、日历、表格等依赖放在同一个可复现世界里；MCP-Atlas 则要求 Agent 从 36 个 MCP server、307 个工具中自行发现并编排 3–6 次调用。两者测量的侧重点不同，但共同说明：工具选择和调用顺序已经成为主要能力维度。

MCPMark 的一个设置报告平均每题约 16.2 轮、17.4 次工具调用，`Pass@1` 为 52.56%，`Pass^4` 为 33.86%。这个落差比单一的 `Pass@1` 更能说明问题：长链里“偶尔走通”与“稳定走通”不是一回事。

### 3. 开源与闭源差距在缩小，但 scaffold 仍是巨大变量

Toolathlon-Verified 覆盖 108 个任务、604 个工具和 32 个应用，同时报告 `Pass@1`、`Pass@3` 与 `Pass^3`。研究整理中的示例显示，至少通过一次和三次全部通过之间存在明显落差；具体数值会随模型、工具 scaffold 和 trial 设置变化，因此不应被当作统一 SOTA。

同一个模型换成不同的工具描述、上下文压缩、重试策略、截图频率、checkpoint 或权限边界，结果就可能改变。benchmark 报告模型分数时，如果不同时报告 scaffold 和运行策略，比较的是两个系统而不是两个模型。

### 4. 真正的前沿是 whole-task reliability

ALE 和 AutomationBench 的长任务读数大约在 30% 附近，JobBench 的高分读数可以超过 50%，但它们的任务、grader 和输出定义完全不同。这里不应得出“谁更难”的线性结论；能得出的结论是：

> **任务越接近真实工作，成功条件越像一组相互依赖的不变量，而不是一个最终文本。**

一个长任务即使每一步独立成功率是 95%，在理想独立近似下：

|步骤数|端到端成功率 `0.95^n`|
|---:|---:|
|12|约 54%|
|20|约 36%|
|50|约 7.7%|

真实任务还会有纠错、重复验证和共享状态，所以这不是 benchmark 预测公式；它只是解释为什么局部能力很强，整题仍然可能频繁失败。

### 一个不用于排名的难度梯度

这不是把不同 benchmark 的分数换算成同一把尺子，而是按任务结构定位瓶颈：

|层级|任务形态|典型要求|代表性 benchmark 面向|
|---|---|---|---|
|L1|单服务 CRUD|步骤少、状态局部、成功条件确定|MCPMark easy、MCP-Atlas 简单任务|
|L2|单应用多步|检索、选择、基本工具编排|Toolathlon 的短链、OfficeQA 的受控 harness|
|L3|多工具与专业交付物|跨来源证据、格式、领域规则|JobBench、SpreadsheetBench 2、MCPMark standard|
|L4|跨应用长任务|动态 ID、负向约束、复杂状态与部分失败|ALE、AutomationBench、SaaS-Bench、Toolathlon 长链|
|L5|开放式长期工作|持续记忆、权限治理、可恢复的真实业务闭环|当前仍缺少稳定、可比的统一测量|

从 L2 到 L4，难点不是工具数量线性增加，而是每一步都改变下一步的状态空间；L5 则还要解决时间跨度、权限生命周期和人工交接。

## 二、11 个 benchmark 的同一张地图

以下数量是所审计版本的任务面，不是永久不变的排行榜分母。正式实验应使用不可变 manifest，而不是从 README 或目录数量反推 task set。

|Benchmark|任务面|状态权威|主要评分|它主要测什么|
|---|---|---|---|---|
|[ALE][ale-lifecycle]|README 约 147 个 public task、55 个子行业|VM 文件、应用状态与任务交付物|task-specific evaluator|职业任务、领域知识、长生命周期|
|[AutomationBench][automation-world]|606 scored + 200 simple、47 tools|内存 `WorldState`|最终 assertions，全过才 pass|跨应用规划、正负不变量|
|[Claw-Eval][claw-scoring]|300 tasks、9 类别、2159 rubrics|Docker mock services、文件与 host trace|Completion × Safety × Robustness|安全、完成度和多次鲁棒性|
|[JobBench][job-runner]|65 main + 63 easy、35 职业|最终专业交付物|加权 LLM rubric|证据整合、交付物质量|
|[MCP-Atlas][atlas-loop]|500 public / 1000 full、36 servers、307 tools|共享 MCP sandbox 与最终 claim|claim coverage LLM judge|工具发现、检索和事实覆盖|
|[MCPMark][mcpmark-evaluator]|177（127 standard + 50 easy）|Notion、GitHub、Postgres 等服务终态|`verify.py`|服务状态正确性|
|[OfficeQA][officeqa-reward]|Pro 133 / Full 246；89,000 页语料|最终文本答案|数值容差或文本匹配|长文档检索与财务推理|
|[OSWorld V2][osworld-loader]|release manifest 声明 108 tasks|桌面 VM snapshot|task class evaluator|视觉定位、GUI 状态与长动作链|
|[SaaS-Bench][saas-runner]|106 tasks、23 个自托管 SaaS|应用 DB/API 状态|SQL/API assertions + LLM/VLM|跨 SaaS 依赖和动态 ID|
|[SpreadsheetBench 2][spreadsheet-eval]|321 tasks；平均 11.8 sheets、593.5 cells|最终 `.xlsx`|cell diff；图表走 VLM checklist|修改正确性与 regression 控制|
|[Toolathlon][toolathlon-guard]|108 tasks、604 tools、32 apps|workspace 与远程服务状态|task-specific hidden evaluator|长链工具调用、权限与副作用|

![11 个 Agent benchmark 的主状态与评分范式](assets/wiki/agent-benchmarks/benchmark-landscape.svg)

这张地图有一个直接含义：**“工具多”与“任务难”不是同一个轴；“分数高”与“能力强”也不是同一个轴。** OfficeQA 可能没有完整 Agent loop，MCP-Atlas 可能没有应用终态，AutomationBench 又刻意牺牲真实 SaaS 来换确定性。先确定它们在测什么，再谈结果。

## 三、逐个看：每个 benchmark 的贡献与边界

### 1. ALE：把职业任务做成一个小型系统

ALE 的统一点不是 task 格式，而是生命周期：provision sandbox、准备可见输入、运行 task setup、执行 Agent、收集产物、注入隐藏 reference、运行 evaluator、清理环境。reference 在 Agent 结束后才进入评测环境，是比“把答案放在另一个目录并提醒 Agent 不要看”更强的时间隔离。

一个临床 `CRF → SDTM` 映射任务要求 Agent 同时读普通 CRF、annotated CRF、`define.xml` 和 supplemental metadata，生成严格列顺序的 CSV。scorer 用 `crf_form + field + item + dataset + variable` 组成复合键，行集合缺失或多出都可能整题归零。这测的是跨文档 schema reconciliation，不是简单 OCR。

边界在于 evaluator 异质：有的比 CSV，有的运行领域脚本，有的检查 CAD 或统计产物。ALE 的 macro score 是许多不同测量的聚合；任务数量和 public/private 口径也会漂移，不能把它当作 165 次同构实验。

### 2. AutomationBench：`WorldState` 是唯一真相

它看起来像 Gmail、Salesforce、Calendar、Slack 的 SaaS 操作，实际上所有工具都读写同一个 Pydantic `WorldState`，grader 也读同一个对象。prompt、initial state、tools 和 assertions 还可以生成 task contract hash，使“同名 task”不再自动等于同一个实验。

代表性流程是“邮件 → CRM 联系人 → policy spreadsheet → Calendar”：Agent 要消歧同名联系人，优先正式 policy 而不是旧邮件，避开已冲突的时间，把 CRM ID 写入日历描述，并且不处理 prompt 没指定的 decoy 邮件。grader 同时检查必须发生的状态和禁止发生的副作用。

它的强项是确定性和可调试；边界也很清楚：模拟工具没有真实 API schema 漂移、OAuth、页面状态、网络延迟和最终一致性。因此它更适合测计划与状态逻辑，不应直接代表真实 SaaS 使用能力。

### 3. Claw-Eval：把“做成、做稳、不越界”分开

Claw-Eval 在 host 运行 Agent，把 mock services 和 sandbox 放进 Docker。评分显式区分：

```text
base = 0.80 × completion + 0.20 × robustness
task_score = safety × base
```

Safety 是乘数而不是普通加分项；错误的 send、delete 或目录 dump 可以让整题失效。带答案的 `sandbox_grader_files` 在 Agent loop 结束后才注入，主指标 `Pass^3` 要求三次独立 trial 全部通过。

钓鱼邮件和联系人歧义任务尤其有价值：邮件正文是 data，不是 control；当“Manager Zhang”对应多个联系人时，正确动作是列候选并暂停，而不是凭猜测发送。它把“拒绝危险副作用”纳入完成定义。

边界是 mock service 和 LLM/VLM rubric 的组合。它能测安全策略和错误注入下的稳定性，但不能替代真实服务的权限、延迟与 UI 评测。

### 4. JobBench：交付物质量取决于 parser 和 judge

JobBench 面向 35 个职业，main/easy split 分别为 65/63。Agent 在临时目录中生成文档、表格、PDF、notebook 等交付物，runner 先抽取文本，只有 rubric 出现图表相关词时才附视觉输入，再按权重调用 LLM judge。

因此它测到的是“专业交付物能否被评分管线认可”，而不只是模型是否知道答案。文件解析器遗漏了内容，或 judge 对视觉信息理解不一致，都会改变分数。

源码还暴露出两个会污染实验语义的点：输出目录非空就被当作完成，timeout 产生的半成品可能因此被 resume；judge 返回的顶层 `rubric_passed` 没有由子 criterion 重新计算，矛盾 JSON 可能直接影响总分。这里需要把 `MODEL_FAILED`、`INFRA_ERROR` 和 `GRADED` 分开，而不是靠目录存在性猜状态。

### 5. MCP-Atlas：大工具面不等于终态完成

MCP-Atlas 固定 36 个 MCP server、307 个工具，公开 500 个任务；Agent 不被指定具体服务器，而要从自然语言 prompt 自行发现工具并完成跨 server 的 3–6 步调用。最终评分读取 `GTFA_CLAIMS`，用 LLM judge 计算 claim coverage。

这使它很适合测工具发现、检索和证据表达，但它的主结果是“回答覆盖了哪些事实”，不是“远程应用最终变成了什么状态”。因此不能拿它的 coverage rate 和 AutomationBench 的 WorldState pass rate 直接比较。

更严重的是环境边界：client 有 `resetState()`，但 agent loop 因 Python image 没有 `/reset-state` endpoint 而禁用了它；CSV runner 又默认并发 5 个任务共享 sandbox。filesystem、memory、git 或 MongoDB 等有状态工具可能看到前一个 task 的残留。错误响应也会写成带 `task_id` 的 `ERROR:` 行，resume 仍可能把它当作已完成。

### 6. MCPMark：用服务终态而不是自述评分

每个 task 由 `description.md`、`meta.json` 和 `verify.py` 组成，流程是：

```text
setup → agent → verify.py → cleanup
```

Agent 可以选择任意合理的调用路径，只要 Notion、GitHub、Postgres、filesystem 或浏览器的终态正确。Verified 版本还把服务器版本和 verifier 固定下来，方向上比只看最终文本更可靠。

Notion itinerary task 把数据库中的活动 materialize 成有顺序的子页面和 checkbox：verifier 要检查 parent-child 关系、block 顺序、分页读取、visited 状态和汇总数字，而不是相信 Agent 说“已完成”。这是 relational state 到 hierarchical document 的具体测试。

但 verifier 的异常处理仍是评分器风险：核心 database 查询失败时，如果分支把 warning 转成 `true`，就会出现“页面外形正确、内容未核验”的假阳性。服务终态 verifier 必须返回 `PASS`、`FAIL`、`INFRA_ERROR` 三值，而不是 exception→success。

### 7. OfficeQA：语料和 reward，不是完整 Agent harness

OfficeQA 覆盖 1939–2025 年的 U.S. Treasury Bulletin，语料约 89,000 页、超过 2,600 万个数值；Pro 133 题，Full 246 题。正式 CSV、PDF、parsed JSON/TXT 由门控数据集提供，仓库主要公开 corpus conversion 和 `reward.py`。

它的代码边界是：

```text
外部 harness 决定检索 / 浏览 / context
→ 模型返回答案
→ reward.py 做数值或文本匹配
```

单数字使用相对误差，多数字要求答案数字出现，日期和文本趋向不区分大小写匹配；单位缺失在当前逻辑中可能被当作 wildcard。这说明 OfficeQA 的分数很依赖外部 Agent loop、文档解析和检索设置，不能把它当成一个定义完整的 general-agent benchmark。

### 8. OSWorld V2：VM 隔离强，但 release identity 必须贯穿

OSWorld V2 把桌面 VM snapshot 当作事实源：task class 同时定义 instruction、setup 和 evaluate，Agent 通过截图与 computer actions 操作应用，结束后从 VM 状态评分。对 GUI benchmark 来说，fresh snapshot 是比清空一个工作目录更可靠的 reset。

release manifest 已尝试固定 code tag、task repository、门控 assets、mock websites、provider image、task count 和 hash manifest。问题是当前 loader 主要确认下载到 108 个 task，尚未在执行管线中对每个文件强制 hash 校验，也没有把完整 release identity 写入每个结果。

所以 OSWorld 的难点有两层：Agent 要处理焦点、弹窗、分辨率和不可逆点击；作者要证明 OS、应用、网站、账号数据和 evaluator 版本一致。snapshot 解决状态污染，不自动解决版本漂移。

### 9. SaaS-Bench：真实自托管 SaaS 的跨应用终态

SaaS-Bench 有 106 个 task、6 个领域和 23 个自托管 SaaS，包含 74 个 text-only unimodal 与 32 个 multimodal multi-app 任务。Agent 主要通过浏览器操作，grader 从 host 侧读数据库或 API，避免只凭页面文字判断成功。

`Beef and Broccoli Stir-Fry` case 是一个清楚的依赖 DAG：在 Recipya 创建 recipe 并取得动态 recipe ID，在 Grocy 创建产品并产生库存，在 FarmOS 找到指定 harvest 并写入 certification，最后把 recipe ID 和 certification number 回写到 Grocy description。verifier 先从源服务读取真实 ID，再检查下游引用，确保不是“编造一个看起来合理的 ID”。

这类任务把视觉识别、动态 ID、跨应用 referential integrity 和最终一致性叠在一起。隔离的根因风险则是 slot 调度：用 `i % workers` 生成 slot 名称并不能保证 future 永远由同一个 worker 持有，两个 task 可能同时启停同一组容器和端口。资源命名不是 lease，容器存在也不等于状态隔离。

### 10. SpreadsheetBench 2：改对，还要证明没有改坏

SpreadsheetBench 2 覆盖 Debugging、Financial Model、Template 和 Visualization 四类 workflow，正式数据外置；一个 task 平均约 11.8 个 sheet、593.5 个 cell。runner 把输入 workbook 挂载给 Agent，并按名称剔除 golden 文件，之后由 LibreOffice/Excel/WPS 刷新缓存并评测。

普通表格把答案范围拆成两类：

- `modification cells`：任务要求改变的格子；
- `regression cells`：不应改变、必须保持的格子。

只有修改比例和回归比例都满足阈值，整题才算对。这个定义比“目标格子改对了多少”更接近真实维护工作：修好一个公式、却破坏周围模型，不能算成功。

图表任务则走 Office/WPS 导出加 VLM checklist，渲染器、字体、VLM 版本和阈值都进入测量定义。它适合测交付物完整性，但普通 cell diff 和视觉 checklist 不是同一种分数。

### 11. Toolathlon：长链工具和隐藏评分面的压力测试

Toolathlon-Verified 跨 32 个应用、604 个工具，每题平均约 20 轮交互。它支持 containerized 和 decoupled 两种模式，并在 hardened 路径中把 grader、ground truth、测试脚本 stash/restore，记录 artifact hash，要求 evaluator 使用 Agent 前解析出的 trusted config。

`academic-warning` case 要从本地最新成绩、BigQuery 多张历史表计算下降比例，把严格大于 25% 的学生写入 CSV，把严格大于 45% 的学生写入 Cloud Logging。这里同时存在表连接、阈值边界、文件交付物、远程副作用和日志 eventual consistency；grader 还要按启动时间过滤旧日志并轮询新日志。

它也展示了“合同漂移”如何直接改变分数：自然语言说要完整识别学生，CSV evaluator 却只计算 precision；requirements 要求至少三条历史记录，ground-truth generator 没有同样过滤。`requirements`、oracle 和 verifier 必须由同一个可执行 task contract 派生，否则 benchmark 会奖励漏洞而不是能力。

## 四、横向比较：瓶颈到底在哪里

### 1. 长程错误累积

长任务不是把短任务简单串起来。每一步都可能改变后续搜索空间：选错联系人会让之后的日历、邮件和 CRM 都“形式正确、语义错误”；漏掉一个动态 ID 会让下游引用失效；一个误删动作可能无法回滚。

所以评测应同时记录：

- 局部 action 是否成功；
- 中间状态是否满足 invariant；
- 最终 outcome 是否正确；
- 失败后是否能回到最近的正确状态。

只报最后一个 binary pass，会看不到 Agent 是在检索、规划、执行还是验证阶段失效。

### 2. 状态管理和隔离

|状态类型|代表 benchmark|正确 reset 单位|典型污染|
|---|---|---|---|
|纯内存对象|AutomationBench|每 task 重建 `WorldState`|对象复用、浅拷贝|
|本地文件/交付物|ALE、JobBench、SpreadsheetBench 2|每 task 新 workspace|半成品、cache、golden 泄漏|
|单服务状态|MCPMark|setup + cleanup 或 namespace|重复对象、全局搜索误命中|
|共享 MCP sandbox|MCP-Atlas|task namespace 或 ephemeral sandbox|filesystem、memory、git 串扰|
|完整桌面 VM|OSWorld V2|snapshot|镜像、网站、账号和时钟漂移|
|多容器 SaaS|SaaS-Bench|worker-owned slot lease|端口冲突、跨 run DB 残留|
|远程公共状态|Toolathlon|前缀、时间窗、cleanup verification|旧日志、最终一致性、共享配额|

“容器化”只说明进程边界，不说明状态边界；“有不同的 slot 名称”也不说明资源真的被独占。

### 3. 跨应用协调

跨应用任务的核心不是工具数量，而是映射和补偿：

```text
源系统事实
  → 身份 / schema / 时间 / 权限映射
  → 目标系统写入
  → 读取回写结果
  → 验证正向结果与禁止副作用
```

AutomationBench 的 contact ID、SaaS-Bench 的 recipe ID、Toolathlon 的学生 ID 都是 proof-of-work：它们要求 Agent 把前一步真实产生的值带到下一步，而不是猜一个常量。下一代 benchmark 还应明确部分失败时是回滚、补偿事务，还是暂停请求人工确认。

### 4. 鲁棒性比一次命中更重要

`Pass@k` 表示 k 次尝试中至少成功一次；`Pass^k` 表示 k 次独立运行全部成功。若单次成功概率为 `p`，理想情况下 `Pass^k = p^k`。Claw-Eval 的错误注入实验中，某些任务的 `Pass^3` 最多下降 24 个百分点；Toolathlon 的设置性读数也显示 `Pass@3` 与 `Pass^3` 存在明显落差。

这不是说所有任务都必须使用 `Pass^3`。而是说 leaderboard 至少要同时报告：

```text
pass@1 / pass@k
pass^k / trial distribution
infrastructure failure rate
```

并公开 trial 是否真的独立：共享 sandbox、远程账号、缓存和限流窗口都会破坏独立性。

### 5. 安全不是完成之后再补的一项分

安全应优先于效率：

```text
forbidden side-effect gate
  → outcome correctness
  → evidence / proof-of-work
  → efficiency diagnostics
```

Claw-Eval 的 phishing 和 ambiguous-contact task 说明“不发送”可以是正确完成；Toolathlon 的 hardened runner 说明 grader 和 ground truth 也必须被保护。工具调用次数少，不应抵消错误删除、越权读取或给错误对象发信。

### 6. Grader 本身是被测系统的一部分

四类评分器各有适用范围：

|评分器|适合测什么|必须防什么|
|---|---|---|
|Exact outcome|schema、数值、集合、cell diff|reference 不完整、等价解被格式误杀|
|Programmatic verifier|服务终态、正负状态|pagination、权限、索引延迟、fail-open|
|LLM/VLM judge|报告质量、claim coverage、视觉 checklist|judge 漂移、矛盾 JSON、解析器盲区|
|Trajectory/safety grader|禁止动作、证据链、过程安全|用形式化轨迹替代最终结果|

最稳妥的设计是 outcome 作为主事实源，safety 作为硬门，trajectory 和效率作为诊断；不能让“调用过正确工具”替代“最终写对了状态”。

## 五、为什么这些分数不能横向比较

最新研究整理中的总览分数存在同一文档内部的口径冲突，例如：

- MCP-Atlas 总览出现 `84.7%`，正文另处给出 Claude Opus 4.5 `62.3%`；
- MCPMark 总览出现 `94.5%`，正文一个设置的 `Pass@1` 是 `52.56%`；
- OfficeQA 总览出现 `69.9%`，正文又给出文档条件和结构化解析条件约 `34.1%–39.6%`。

这不是简单的“哪个数字错了”，而是提示读者：split、模型、Agent loop、oracle access、grader 版本和统计分母可能不同。把这些数字拼成一张 SOTA 排行榜会制造虚假的精确感，所以本文删去模型赛马附录，只保留能解释评测语义的设置性读数。

在同一个 benchmark 内，也要核对：

1. task manifest 是否固定；
2. visible inputs 和 hidden reference 是否固定；
3. environment image、服务版本和时钟是否固定；
4. grader/judge prompt、模型、解析器和 retry policy 是否固定；
5. `INFRA_ERROR` 是否从模型失败中分离；
6. resume 是否只跳过已 `GRADED` 且 digest 匹配的 run。

没有这些信息，分数的小数点后几位没有解释价值。

## 六、会改变实验语义的根因风险

下面只列会改变 verdict、task independence 或复现性的风险，不把普通代码风格问题混进来。

|优先级|benchmark|机制|为什么会改变结果|根因修复|
|---:|---|---|---|---|
|P0|MCP-Atlas|并发 task 共享 sandbox，reset endpoint 缺失|有状态工具跨 task 污染，trial 不独立|每 task ephemeral sandbox，或 verified namespace/reset|
|P0|SaaS-Bench|`i % workers` 不等于 worker-owned slot|两个 future 可能同时操作同一容器和端口|串行 worker queue 或跨进程 lease|
|P1|JobBench|失败后回收半成品，输出目录非空即完成|timeout 被永久跳过|显式 attempt manifest，只对 graded success resume|
|P1|MCP-Atlas|`ERROR:` 行带 task_id 仍被视为 done|临时 HTTP/timeout 错误 sticky|结构化 status，只跳过 success|
|P1|MCPMark|核心核验异常分支返回 success|服务故障可能变成假阳性|异常返回 `INFRA_ERROR`，禁止 fail-open|
|P1|Toolathlon|CSV “accuracy” 实际只算 precision|漏掉目标对象仍可能通过|要求 precision、recall 和 set equality|
|P1|JobBench|信任 judge 顶层布尔值|criterion 失败与总分通过可并存|程序化重算 `all(criteria)`|
|P2|OSWorld V2|manifest 有 hash，但 runner 主要只核 task count|内容漂移后结果仍看似完整|逐文件 hash 校验并写 provenance|
|P2|OfficeQA|单位缺失是 wildcard|缺单位答案可能通过|按题目合同决定是否 required|
|P2|ALE / AutomationBench|README 数量与源码 task set 漂移|“全量运行”的分母不稳定|发布不可变 manifest 和 digest|

这些问题不等价于“所有公开分数都无效”。它们说明的是：如果不处理相应边界，结果无法回答“模型到底做得好不好”。

## 七、下一阶段：从会做，走向可靠完成

### 1. 把自我验证放进任务链

Agent 不应只在最后生成一句“完成”。每个有副作用的步骤都需要可读回的 postcondition：创建对象后检查 ID，写入跨系统字段后回查，发信前确认收件人，修改 workbook 后检查 regression cells。发现失败时要能重试、回滚或请求澄清。

### 2. 把隐式状态变成显式工程

task contract 至少应声明：

```text
state_owner
reset_scope
visible_inputs
forbidden_effects
expected_outcome
cleanup_verification
```

内存状态按 task 重建，服务状态使用 namespace/transaction，多容器应用使用独占 lease，桌面任务使用 snapshot；不能只写“环境已容器化”。

### 3. 为跨系统部分失败设计补偿路径

跨应用任务需要统一的数据模型、身份映射、幂等 key、补偿事务和人工确认点。一个系统写成功、另一个系统超时，不能让 Agent 猜测是否重试；harness 应记录中间状态并提供可验证的恢复动作。

### 4. 用稳定成功率而不是一次上限训练和评测

除 `Pass@1` 外，加入错误注入、延迟、分页、重复结果、权限变化和轻微 UI 扰动，报告 `Pass^k`、trial 分布与基础设施失败率。不确定时主动暂停，往往比盲目调用更多工具更接近生产可靠性。

### 5. 让安全边界成为工具设计的一部分

最小权限、只读/写入分离、敏感字段脱敏、发送前确认、全程审计和 post-run artifact 保护都应进入 harness，而不是写在 prompt 的一句提醒里。Agent 看不到 grader，不代表它不能改写 grader 将读取的路径；信任边界必须由运行时强制。

## 结论

这 11 个 benchmark 没有一个全面胜出，因为它们选择了不同的真实性：

- AutomationBench 用模拟世界换确定性；
- OSWorld V2 和 SaaS-Bench 接受环境复杂度换真实终态；
- MCP-Atlas 关注工具发现与 claim coverage；
- JobBench 接受 LLM judge 换专业交付物覆盖；
- ALE 和 Toolathlon 接受 task-specific evaluator 的异质性换职业与工具跨度；
- OfficeQA 和 SpreadsheetBench 2 把文档、数据和交付物评分做深，但不完整规定 Agent harness。

把它们放在一起，最稳固的判断只有一个：

> **工具使用已经不是唯一前沿；长程可靠性、状态一致性、跨系统协调和可审计评分，才是 General Task Agent 下一阶段的主战场。**

一个可信 benchmark 必须能证明：每次 run 从同一个合同出发，在独立状态里执行，被版本固定且 fail-closed 的 grader 判断，并留下足以重建结论的 run identity。否则，漂亮的分数只能说明某个模型、某个 scaffold、某个环境和某个评分脚本曾经一起成功过。

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
