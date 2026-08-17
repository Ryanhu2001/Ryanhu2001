---
layout: dsh_runtime_wiki
title: "DeepSeek Harness：从 Agent Loop 到 Composable Agent Runtime"
public: true
description: "从 AgentLoop、多 Session 和 Plugin Composition 出发，分析 DeepSeek Harness 如何记录会话、组织模型输入、执行工具并管理长期任务。"
lead: "AgentLoop 只描述执行怎样向前推进；DSH 还要决定 Session 使用哪套 Composition、组件怎样注册、模型看见什么，以及运行事实如何进入 Session Log。"
duration: "技术分享讲稿 · 约 56 分钟正文 + Q&A"
source_revision: "47f943859bef60e4160492346772ded9b24f765a"
type: agent-harness
date: 2026-08-17
permalink: /wiki/DSH/
---

<!--
维护说明：
1. 本文件是正文唯一来源，最终 HTML 由 Jekyll 直接渲染，不要手改 _site。
2. ## 是五个 Part；Part 1 有 2 个小节，其他 Part 各有 5 个。保留显式 id，目录会自动生成。
3. 图通过 dsh/diagram.html include 声明。
4. 源码说明放在 <details class="source-note" markdown="1"> 中。
5. 每个 Part 标题前的 talk-route 注释只服务演讲取舍，不会显示在页面中。
-->

一个 Coding Agent 最初看起来只有一条很短的执行路径：用户提出要求，模型决定下一步，系统执行工具，再把结果交回模型。只运行一个会话、只提供一组固定工具时，用 AgentLoop 描述它完全够用。

真实使用很快会出现一个更具体的场景：同一个 Host 同时运行多个 Session；它们可以加入同一份 Agent Preset，却使用不同 Workspace、Session Log 和 Agent 状态。仅仅这个场景，就要求系统说明哪些组件可以共享，哪些数据必须按 Session 分开。

这场分享不会从 Cordis 的术语开始，也不会把 DSH 介绍成一张功能列表。叙述从 AgentLoop 的职责边界开始，然后依次回答：不同 Agent 的能力从哪里来，Plugin 怎样协作，会话怎样保存，模型实际看到什么，工具和长期任务怎样执行。标题中的 Agent Runtime 留到最后再解释；它是这些具体机制运行起来后的整体，不是一个预设结论，也不是源码里的某个单独 Class。

| Part | 建议时长 | 讨论内容 |
|---|---:|---|
| Part 1 · Overview | 6 min | 跨 Session 的 Preset 场景与一条完整 Session 时序 |
| Part 2 · Everything Is a Plugin | 15 min | AgentLoop 与其他能力如何被组合到一起 |
| Part 3 · Core Designs | 20 min | Session、模型输入、压缩、工具与长期任务 |
| Part 4 · Four Agent Presets | 8 min | Standard、Code、Minimal、Cordis 分别改变了什么 |
| Part 5 · Conclusion | 7 min | 怎样比较这套设计，它的代价是什么，Runtime 又指什么 |

页面中的实现判断固定到 front matter 标出的 DSH revision。每个小节末尾都有一组可以展开的源码依据：先概括文档或代码能证明什么，再给短原文、结构摘录或忠实伪代码。五张交互图只处理不适合线性文字的关系；不打开任何图，正文仍然可以独立阅读和修改。

<!-- talk-route: Part 1 | 6 min | full: 1.1→1.2 | short: 1.1→1.2 -->
## Part 1｜Overview：AgentLoop 之外还要管理什么 {#part-introduction}

Overview 只看一个场景和一条时序：同一份 Standard Preset 同时服务两个 Workspace 中的 Session，然后选择其中一个 Session，从创建与 Composition 绑定一直跟到一次 Turn 结束。

后文会反复使用下面这些名词。这里先统一它们在本文中的含义；`Realm`、`SurfaceOp` 等只影响具体实现核对的名字，仍留在对应源码依据中解释。

| 名词 | 本文中的含义 | 层次 |
|---|---|---|
| `Host` | 一次 DSH 启动后的常驻后台进程，持有跨 Session 共用的基础设施 | 运行对象 |
| `Agent` | 当前进程中推进一个普通 Session 的 live runtime object；顶层 Session 的运行对象通常就叫 Agent，不叫 Activation | 运行对象 |
| `Inbox` | Agent 当前进程中的 FIFO 输入队列；用户消息、Follow-up 或注入 Context 被领取后才进入 Turn 与 Session Log | 运行对象 |
| `Session` | 稳定身份及其 append-only 事件日志；不是浏览器 Tab，也不是当前 live Agent | 运行对象 |
| `SessionEvent` | 写入 Session Log 的 typed fact，例如消息、Turn/Step 边界和 Tool Call/Result | 运行对象 |
| `Child Session` | Subagent 相对 Parent 独立创建的 SessionId 与 Session Log；它不是 Parent Session 中的一段临时状态 | 运行对象 |
| `Activation` | Continuable Child Session 可选的进程内运行实例；只属于 Subagent 语境，不是 Plugin，也不会再拥有第二份 Session | 运行对象 |
| `Plugin` | 由 Cordis 挂载并参与依赖、注册和卸载生命周期的组件；Session、Activation 等运行实例本身不是 Plugin | 组件组织 |
| `Service` | Plugin 通过 `ctx.<key>` 提供或消费的稳定能力接口 | 组件组织 |
| `Context` | Plugin 解析 Service、Event、Scope 与生命周期的当前环境 | 组件组织 |
| `Composition` | 已经挂载在一起的 Plugin、Service 与 Registration 关系；它组织 Runtime，但不等于 Runtime | 组件组织 |
| `Agent Preset` | 一个包含 `agent.cordis.yml` 的 Agent-side Composition，例如 standard、code、minimal、cordis | 组件组织 |
| `Preset generation` | 某次实际挂载的 Preset 快照；已有 Session 保持原 generation，新 Session 可以进入新 generation | 组件组织 |
| `Host / Agent plane` | Host plane 放跨 Session 共用的基础设施；Agent plane 放当前 Agent 获得的 model-facing contributions | 组件组织 |
| `Registration` | Plugin 加入的 Tool、Prompt Section、Listener、Provider 等条目；通常会返回或由 Helper 持有对应 Disposer | 组件组织 |
| `Scope` | Registration 对谁可见；本文常见查找顺序是 `agent → preset → global` | 组件组织 |
| `Event` | Plugin 参与某个执行时点的扩展接口；Cordis Event 是 live 调用机制，写入日志的 `SessionEvent` 是另一类持久事实 | 组件组织 |
| `Fiber` | 某个 Plugin 的一次实际挂载；它拥有这次挂载产生的 Effect，并在卸载时触发清理 | 组件组织 |
| `Effect` | 执行一项可撤销的安装动作，并把返回的 Disposer 绑定到当前 Fiber；不是 Plugin 配置字段 | 组件组织 |
| `Disposer` | Effect 或 Registration 返回的清理函数；手动释放或 Plugin 卸载时执行，多个 Disposer 按注册的相反顺序清理 | 组件组织 |
| `Waterfall` | 可包裹一次调用的 middleware 链；Listener 调用 `next()` 才继续下一层，不调用即可拒绝或替换最终结果 | 组件组织 |
| `Service Definition / Provider / Consumer` | 分别定义稳定接口、实现接口、使用接口；三者共同形成一项可替换能力 | 组件组织 |
| `Dependency Inversion` | Consumer 依赖 Service Definition，不依赖具体 Provider；Composition 负责选择 Provider | 组件组织 |
| `Capability Seam` | 由 Service Definition、Provider 与 Consumer 构成的一项可替换能力 | 组件组织 |
| `Execution World` | Filesystem 与 Subprocess Provider 共同指向的文件和进程环境；两者必须描述同一个本地或远端世界 | 组件组织 |
| `Persistence` | Session Log 的落盘、加载、批量写入与 Flush 子系统；由 Coordinator、Persistence Seam 和 JSONL/SQLite Backend Plugins 共同完成 | 核心子系统 |
| `Compaction` | 保留原始 SessionEvent，同时通过 Summary 与 Projection replacement 缩短后续 Model Surface 的子系统；不是删除历史，也不是单个 Plugin | 核心子系统 |
| `Subagent` | 委派 Child Session 的子系统，由 `ctx.subagents` Registry、Provider Plugins、model-facing Tools、Child Session 与可选 Activation 共同组成 | 核心子系统 |
| `AgentLoop` | 推进 Inbox、Turn、Step、模型请求与 continuation 判断的 driver；它本身也是 Plugin | 执行 |
| `Turn` | 从 `turn/start` 到 `turn/end` 的一次完整处理，可以包含零个、一个或多个 Step | 执行 |
| `Step` | 一次 Model Request，加上该请求触发的 Tool Executions | 执行 |
| `Projection` | 从完整 Session Log 派生出的某种读取结果，例如模型消息或 UI 视图 | 模型输入 |
| `Model Surface` | 某次请求中模型实际看到的 System Prompt、Tools、Context、History 等内容 | 模型输入 |
| `Tool Presentation` | 底层 Tool 以 native、code 或 both 哪种接口呈现给模型 | 模型输入 |
| `Agent Runtime` | Composition 生效后，连同 Agent、Session、模型请求、工具执行和资源所有权一起运行的系统 | 整体 |

后文涉及实现时，可以直接从下面这些入口继续读；每个入口只负责一个问题，不需要从 Package 目录开始猜。

| 想查什么 | 文档入口 | 主要内容 |
|---|---|---|
| DSH 全局结构 | [Architecture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md) | Plugin tree、Turn flow、Session Log、Capability Seam，以及新行为应该进入哪里 |
| Cordis 的基本概念 | [Cordis Primer ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md) · [Services Tutorial ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-tutorial/03-services.md) | Context、Service、`inject`、Effect、Event、Waterfall，以及依赖变化时的 Plugin 生命周期 |
| Preset 怎样跨 Session 工作 | [Agent Presets README ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md) | standing mount、scope parent、generation、blank-session recompose 与 child composition |
| Session 与事件日志 | [Session ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md) | SessionEvent vocabulary、模型历史派生和 Turn/Step 边界 |
| Prompt 与模型输入组装 | [System Prompt ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/system-prompt.md) | Prompt Sections、Prompt Context、Tool providers 与 assembly |
| Tool 注册与执行 | [Tools ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/tools.md) · [Execution Pipeline ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/tool-execution-pipeline.md) | Tool Definition、scoped schemas、Approval、hooks 与结果收尾 |
| 可替换能力怎样设计 | [Capability Seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/capability-seams.md) | Definition、Provider、Consumer 及其依赖图 |
| 添加新的 Plugin 或 Tool | [Adding a Package ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cookbook/adding-a-package.md) · [Adding a Tool ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cookbook/adding-a-tool.md) | 新 Package 的 Service/Event/Effect 接入，以及 model-facing Tool 的完整路径 |
| 添加新的模型 Adapter | [Adding an LLM Adapter ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cookbook/adding-an-llm-adapter.md) | Provider 注册、stream contract 与模型请求适配 |
| 长期子任务 | [Subagent ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/subagent.md) | Child Session、Activation、Follow-up、Interrupt 与 Resume |
| 历史如何缩短为模型输入 | [Compaction ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/compaction.md) | Compaction Events、Surface replacement 与恢复路径 |

### 1.1 同一个 Host 上的两个 Session {#section-1-1}

Host 是一次 DSH 启动后常驻的后台进程，持有跨 Session 共用的 AgentLoop、Session Store、LLM 和 Tool Registry。Agent Preset 是一份 `agent.cordis.yml`；其中列出的 Plugin 被挂载以后形成 Preset Composition，决定 Agent 获得哪些 Persona、Prompt、Tools、Plan 与 Compaction 能力。
{: .section-lead}

现在创建两个 Session：Session A 与 Session B 加入同一份 Standard Preset，A 工作在 repo-A，B 工作在 repo-B。DSH 不为每个 Session 重新挂载一棵 Standard Plugin tree；它先保证 Standard 已经挂载，再把 A、B 各自的 Agent scope 绑定到这份 Preset Composition。

```text
DSH Host
└── Standard Preset（挂载一次）
    ├── Agent A scope → Session A → repo-A / Session Log A
    └── Agent B scope → Session B → repo-B / Session Log B
```

这不是唯一可行的实现：系统也可以为每个 Session 单独挂载一棵 Preset Plugin tree。当前 DSH 选择 standing mount，同一 generation 的 Prompt Section、Tool Definition、Listener 和 Plugin 生命周期只建立一次；README 也因此把它的常驻成本描述为“per generation rather than per session”。代价是共享 Plugin 不能把某个 Session 的可变状态只存在一个实例字段里，而要从 Session Log 读取，或者按 SessionId / AgentId 分开保存。

所以这里共享的是 Preset 定义及其 Registration，不是 Workspace 和历史。Agent A 与 B 都沿 `agent → preset → global` 读取 Standard 的注册，但各自拥有 Session Log、Inbox、Cancellation 和 Workspace。下一节选择 Session A，把 Composition 绑定、Registration 生效以及一次 Turn 的执行顺序放到同一条时序里。

<details class="source-note" markdown="1">
<summary>源码依据：Preset 怎样挂载并绑定 Agent</summary>

**Preset 实现结论：**`mount()` 先通过 `ensureStanding()` 取得该 Preset 的 standing mount，再把当前 Agent 的 scope parent 绑定到 `standing.key`。同一 standing mount 可以服务多个 Agent；每个 Agent 保留自己的 binding。
{: .evidence-summary}

**源码批注版（中文注释为后加）：**

```ts
async mount(agentCtx: Context, id?: string): Promise<AgentPreset> {
  // 取得当前 Agent 的 ScopeKey；没有 Scope 就无法加入任何 Preset
  const agentKey = scopeOf(agentCtx)
  if (agentKey === undefined) {
    throw new Error('agent-presets: refusing to compose an unscoped context; the scope key is what joins an agent to its preset')
  }

  // 根据 PresetId 解析并验证 Preset
  const preset = await this.resolveMountable(id)

  // 已经存在的 generation 直接复用，否则先创建 standing mount
  const standing = await this.ensureStanding(preset)

  // 把 Agent Scope 的 parent 指向 Preset Scope；Prompt、Tool 等注册由此可见
  this.bindings.set(agentKey, bindScopeParent(agentKey, standing.key))

  // 返回实际选中的 Preset，供调用方记录 Session 使用的 Preset
  return preset
}
```

[packages/preset/agent-presets/src/index.ts：mount() ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/src/index.ts#L275-L287){: data-source-evidence=""}

[packages/preset/agent-presets/README.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}
</details>

### 1.2 一个 Session 从创建到 Turn 结束 {#section-1-2}

创建 Session A 时，Agent Factory 先准备 Session 与 Header，再在 Agent 发布以前执行 Preset setup。组件依赖满足以后，Preset 中的 Plugin 才建立 Prompt、Tool 等 Registration；注册进入 Preset 的作用范围，Agent 通过 parent binding 读取它们。完成这一步以后，AgentLoop 才开始接收消息并推进 Turn。
{: .section-lead}

| 名称 | 在这条时序中的含义 |
|---|---|
| Session | append-only `SessionEvent` log，保存已经发生的交互事实 |
| Component dependency | Plugin 通过 `inject` 等待所需 Service 可用 |
| Registration | Plugin 注册的 Prompt、Tool 或 Listener；跟随作用范围和生命周期 |
| Turn | 从 `turn/start` 到 `turn/end`；可以包含零个、一个或多个 Step |
| Step | 一次 Model Request，加上这次请求触发的 Tool Executions |

用户消息进入 AgentLoop 后，Loop 先写入 `turn/start`。每个 Step 都按当前 Agent scope 组装 Prompt 与 Tool Schemas，从 Session Log 派生模型历史，然后请求模型。图中的 Step 1 产生 Tool Calls，工具结果写回 Session，因此还需要 Step 2；Step 2 直接得到最终回答，随后写入 `step/end` 与 `turn/end`。

这张图把两种关系放在同一条时间线上：上半段是 Session 如何取得 Composition 与 Registrations，下半段是这些注册怎样参与一次 Turn。虚线写入 Session Log 的是可持久事实；模型请求、Tool Runtime 和组件 setup 是当前运行过程。

{% include dsh/diagram.html number="1" title="一个 Session 从 Composition 到 Turn 结束" src="/assets/wiki/deepseek-harness/diagrams/13-session-composition-turn.html" description="展开 Session 创建、Preset 注册以及两个 Step 的完整时序" note="查看依赖满足、Registration、Session Log、Turn 与 Step 如何连接" %}

Overview 到这里结束。Part 2 再分别解释 AgentLoop、Preset 与其他 Plugin 为什么能够用同一套 Composition 机制安装和协作。

<details class="source-note" markdown="1">
<summary>源码依据：Composition setup 与 Turn flow</summary>

**Preset、Cordis 与 Architecture 文档结论：**Agent Factory 在发布 Agent 前执行 Preset setup；Plugin 等待声明的依赖并建立可撤销注册。进入 Turn 后，每个 Step 读取当前注册、请求模型、执行 Tool Calls，并把模型可见事实写入 Session Log。
{: .evidence-summary}

**流程图摘录：**

```text
turn/start
  claim next-step input plus one queued message
  assemble prompt sections + tool schemas
  -> agent/pre-step                   reject | enter(messages)
     reject, or a first enter rewritten empty -> close the turn with no step
     step/start
     append entered messages as user/message
     derive model history from the log
     agent/request -> llm/stream -> assistant/chunk* -> assistant/message
     tool/call* -> tools/pre-execute -> tools/execute -> tools/post-execute -> tool/result*
     step/end
     tools owe another request, or next-step input arrived -> claim -> next step
  -> agent/turn-stopping
turn/end
```

[packages/preset/agent-presets/README.md：Where to call mount ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#where-to-call-mount){: data-source-evidence=""}

[docs/cordis-primer.md：Cordis in five ideas ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-in-five-ideas){: data-source-evidence=""}

[docs/architecture.md：Turn flow ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#turn-flow){: data-source-evidence=""}

[packages/core/agent-loop/src/agent.ts：turn() ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent-loop/src/agent.ts#L245-L329){: data-source-evidence=""}
</details>

<!-- talk-route: Part 2 | 15 min | full: 2.1→2.2→2.3→2.4→2.5 | short: 2.1→2.4→2.5 -->
## Part 2｜Everything Is a Plugin：DSH 如何组织这些能力 {#part-composition}

Part 1 把一个 Session 从 Composition 绑定到 Turn 结束串了起来。现在拆开这条时序背后的组件关系：AgentLoop 为什么也是 Plugin，Plugin 怎样取得依赖、参与调用和撤销注册，具体实现又怎样在不修改 Consumer 的情况下被替换。最后再回到同一个 Host 上的多个 Agent。

### 2.1 AgentLoop 为什么也是一个 Plugin {#section-2-1}

DSH 把 AgentLoop 与 Model Adapter、Tool Registry、Session Service 一起装进 Cordis Plugin tree。AgentLoop 仍然负责推进执行；“也是 Plugin”改变的是它与其他组件的关系，而不是取消它对 Turn 和 Step 的控制职责。
{: .section-lead}

这里的 “Everything” 指组成产品的能力模块，不是说每条 SessionEvent、每个 Agent 或每次 Tool Call 都是 Plugin。源码中的 `AgentLoop` 继承 `Service`，声明自己需要 `agents`、`sessions`、`llm`、`tools` 和 `systemPrompt`；构造时把自己发布成 `ctx.agentLoop`。因此它由 Composition 安装，也只能在依赖已经可用的环境中工作。

AgentLoop 的职责仍然明确：从 Inbox 认领输入，写入 Turn/Step 边界，组装请求，调用模型，安排 Tool Calls，并判断是否还欠下一个 Step。它不是空壳，也不是只负责调用一串 Callback。

同时，Plan、Compaction、Subagent 和权限审批没有全部写成 AgentLoop 内部的分支。Compaction 在 `agent/pre-step` 与 `agent/request-error` 参与，Plan 通过 SessionEvent、Prompt Section 和 Tool 改变协作状态，权限检查进入 Tool Execution Pipeline，Subagent 由独立 Registry、Provider 和 Tool 组成。AgentLoop 驱动主流程，这些组件通过稳定的 Service 或 Event 接入。

Plugin 也不等于 Feature。一个 Feature 往往横跨多个 Plugin 和数据结构：Plan Mode 包含 Service、Session Event、Prompt Section、Tool 与 Command；Subagent 包含 Service Definition、多个 Provider、model-facing Tools、Child Session 和 Activation Manager。`Everything Is a Plugin` 描述的是组件如何进入系统，不是说每个功能只对应一个文件。

<details class="source-note" markdown="1">
<summary>源码依据：AgentLoop 怎样作为 Service 进入 Composition</summary>

**AgentLoop 源码结论：**`AgentLoop` 本身是一个 Cordis `Service`，依赖其他核心 Service，并把工厂能力发布到 `ctx.agentLoop`。Architecture 同时要求新增行为优先进入已有 Service、Event 或 Capability Seam。
{: .evidence-summary}

**源码批注版（中文注释为后加）：**

```ts
// AgentLoop 也是一个由 Cordis 管理的 Service
export class AgentLoop extends Service implements AgentFactory {
  // 这些 Service 全部可用以后，AgentLoop 才能进入工作状态
  static inject = ['agents', 'sessions', 'llm', 'tools', 'systemPrompt']

  constructor(ctx: Context, config: Config) {
    // 运行时把这个实例注册成 ctx.agentLoop
    super(ctx, 'agentLoop')
    // ...
  }
}
```

[packages/core/agent-loop/src/index.ts：AgentLoop Service ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent-loop/src/index.ts#L295-L320){: data-source-evidence=""}

[docs/architecture.md：Where new behavior goes ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#where-new-behavior-goes){: data-source-evidence=""}
</details>

### 2.2 Context、Service 与 inject 怎样建立依赖 {#section-2-2}

Plugin 之间不靠 YAML 行序或直接导入具体实现来决定谁先启动。Provider 把能力注册为稳定的 `ctx.<key>`，Consumer 用 `inject` 声明自己必须取得哪些 Service；Cordis 在依赖满足以后才让这个 Plugin 生效。
{: .section-lead}

以文件工具为例，`tool-fs` 需要 Tool Registry、Filesystem 和 System Prompt。源码中的依赖声明只有一行：

**源码摘录：**

```ts
export const inject = ['tools', 'fs', 'systemPrompt']
```

这行没有选择 Local Filesystem 或 E2B Filesystem，只说明 `tool-fs` 离开 `ctx.fs` 就无法工作。Loader 会等 `fs` Service 存在再执行 `apply()`；如果依赖消失，这次 Plugin 挂载也会退出。配置文件可以为了阅读把相关行放在一起，但启动关系来自依赖图，不来自肉眼看到的上下顺序。

Context 是这次解析发生的环境。读取 `ctx.fs` 不是读取一个在应用启动时固定写死的普通字段，而是解析当前 Context 可以看到的 `fs` Service。后面讲 Preset 时，同一个 Service key 可以因为 Scope 与 Composition 不同而落在不同的可见范围中。

这里还要分清 TypeScript 声明与运行时事实：给 `Context` interface 增加 `fs: FileSystem`，只让编译器接受 `ctx.fs`；真正让运行时拥有这项能力的是某个 `FileSystem` Provider 构造并通过 `super(ctx, 'fs')` 注册 Service。`inject = ['fs']` 再让 Consumer 等待这项运行时能力。三者分别解决类型、提供能力和声明依赖，不能互相代替。

Service method 与 Event 也从这里分开：当调用方知道自己要使用哪项能力时，直接调用 `ctx.fs.readText()` 等方法；当系统希望未知数量的 Plugin 在某个时点参与时，才发布 Event。下一节专门看 Event 如何参与调用，以及这些注册怎样在卸载时清理。

<details class="source-note" markdown="1">
<summary>源码依据：Filesystem Service 与 tool-fs 怎样通过 key 连接</summary>

**Filesystem 源码结论：**Service Definition 把实现注册为 `ctx.fs`；`tool-fs` 只声明自己需要 `fs`，没有选择具体 Provider。依赖是否可用决定 Consumer Plugin 何时激活。
{: .evidence-summary}

**源码批注版（中文注释为后加）：**

```ts
// Service Definition：任何具体 Filesystem Provider 都通过这个稳定 key 发布能力
export abstract class FileSystem extends Service {
  constructor(ctx: Context) {
    super(ctx, 'fs')
  }
}

// Consumer：只声明需要 fs，不导入或选择 fs-local / fs-e2b
export const inject = ['tools', 'fs', 'systemPrompt']
```

[packages/fs/fs/src/index.ts：FileSystem Service Definition ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/fs/fs/src/index.ts#L66-L70){: data-source-evidence=""}

[packages/fs/tool-fs/src/index.ts：inject ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/fs/tool-fs/src/index.ts#L18-L23){: data-source-evidence=""}

[docs/cordis-primer.md：Context 与 inject ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-in-five-ideas){: data-source-evidence=""}

[Cordis Tutorial：Dependencies are tracked after load ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-tutorial/03-services.md#dependencies-are-tracked-after-load){: data-source-evidence=""}
</details>

### 2.3 Event 怎样扩展调用，Effect 怎样清理注册 {#section-2-3}

Plugin 通常会做两类贡献：在某个执行时点参与一次调用，或者向 Registry 安装 Tool、Prompt Section、Listener 等 Registration。Cordis 分别用 Event 和 Effect 管理这两件事。
{: .section-lead}

Event 的 Dispatch Mode 是公共契约，不同模式处理不同协作关系：

| 模式 | 调用关系 | 典型用途 |
|---|---|---|
| `emit` | 同步通知所有 Listener，不收集返回值 | 广播已经发生的 live 变化 |
| `parallel` | 并发等待所有 Listener | 多个互不依赖的异步参与者 |
| `serial` | 按注册顺序逐个等待 | 顺序执行的 checkpoint |
| `waterfall` | Listener 包裹下一层，可改写或短路 | 请求、模型流、工具执行与策略 |

Waterfall 最容易和普通通知混淆。Listener 调用 `next()`，控制才进入下一层；`next()` 的返回值再回到外层，外层可以继续修改。如果某个拥有决定权的 Listener 不调用 `next()`，后续 Listener 和默认实现都不会执行。`agent/pre-step`、`agent/request`、`llm/stream`、`system-prompt/assemble` 以及三段 Tool Execution hooks 都使用这种关系。

**关系整理（非仓库原文）：**

```text
Listener A
  → next()
    → Listener B
      → next()
        → 默认实现
      ← 结果
    ← B 可以修改结果
  ← A 得到最终结果
```

Effect 处理另一件事。Persona Plugin 调用 `ctx.systemPrompt.section()` 以后，Registry 中多出一个 Prompt Section；这个注册动作改变了 Plugin 外部的状态，所以它是一项副作用。`section()` 返回删除该 Section 的 Disposer，`ctx.effect()` 把 Disposer 交给当前 Fiber。Fiber 是这一次实际挂载的 Plugin 实例；它卸载时，持有的 Disposer 按相反顺序执行。

**关系整理（非仓库原文）：**

```text
ctx.effect(setup)
  → 立即执行 setup
  → setup 安装 Registration，并返回 Disposer
  → 当前 Fiber 保存 Disposer
  → Fiber 卸载时执行 Disposer
```

Effect 不是每个 Plugin 都要在 YAML 中声明的字段，也不负责回滚所有已经发生的事情。`ctx.on()` 等 Cordis Helper 已经把 Listener 注册接入对应生命周期；而已经提交的 `session.append(...)` 代表持久事实，持久 SessionEvent 不由 Effect 撤销。

Scope 与 Effect 仍是两件事：Scope 决定谁能看见 Registration，Effect 决定它存在到什么时候。一个 Tool 可以只对 Standard Preset 下的 Agent 可见，同时跟随这一代 Preset Fiber 卸载；可见范围正确但 Disposer 丢失，仍然会产生残留。

Cordis 不负责决定模型下一步做什么，也不保存 Conversation。它提供的是依赖解析、调用扩展点和可撤销生命周期；AgentLoop 仍负责推进 Turn 与 Step，Session 仍负责记录持久事实。

<details class="source-note" markdown="1">
<summary>源码依据：Persona Plugin 怎样声明依赖与 Effect</summary>

**Persona 与 Cordis 结论：**Persona Plugin 等待 `systemPrompt` Service，在自己的 Scope 中注册 Prompt Section，并让 Effect 持有 Section 的 Disposer。Cordis Fiber 卸载时反向执行收集到的 Disposer。
{: .evidence-summary}

**源码批注版（中文注释为后加）：**

```ts
// Plugin 名称，以及必须等待的 Service
export const name = 'persona'
export const inject = ['systemPrompt']

export function apply(ctx: Context, config: Config): void {
  // section() 注册 Prompt Section 并返回 Disposer；
  // effect() 把这个 Disposer 绑定到当前 Plugin Fiber
  ctx.effect(() => ctx.systemPrompt.section({
    name: PERSONA_SECTION,
    order: PERSONA_ORDER,
    text: config.text,
    ...(config.complete ? { complete: true } : {}),
  }), 'persona.section()')

  if (!(config.includeRuntimeContext ?? true)) ctx.systemPrompt.suppressRuntimeContext()
}
```

[packages/preset/persona/src/index.ts ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/persona/src/index.ts#L27-L68){: data-source-evidence=""}

[docs/cordis-primer.md：Cordis in five ideas ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-in-five-ideas){: data-source-evidence=""}

[docs/cordis-primer.md：Waterfall semantics ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-waterfall-semantics){: data-source-evidence=""}
</details>

### 2.4 依赖倒置怎样形成 Capability Seam {#section-2-4}

Context 与 `inject` 解决运行时怎样找到依赖，依赖倒置解决源码应该依赖谁：Consumer 只依赖稳定的 Service Definition，不依赖 Local、Sandbox 或 E2B 等具体 Provider；Composition 是选择并安装 Provider 的地方。
{: .section-lead}

Filesystem 可以把这条关系完整展开：

| 角色 | 当前实现中的例子 | 负责什么 |
|---|---|---|
| Service Definition | `FileSystem` / `ctx.fs` | 文件身份、读取、写入、错误等稳定语义 |
| Provider | `fs-local`、`fs-sandbox`、`fs-e2b` | 把接口连接到本机、受限本机或远端环境 |
| Consumer | `tool-fs` | Tool Schema、参数验证、读取窗口和结果呈现 |
| Policy | `fs-observation-policy` | 通过 `fs/*` Event 加入 read-before-write 等决策 |

`tool-fs` 的源码只通过 `ctx.fs` 读写文件，没有导入 `fs-local` 或 `fs-e2b`。因此替换 Provider 不要求在 Consumer 中增加 `remote` 分支。反过来，Provider 也不拥有模型看到的 Schema 和说明；这些内容留在 Consumer，换 Provider 时模型接口可以保持一致。

一项完整 Capability Seam 需要 Definition、Provider 和 Consumer 三个角色。单独写一个接口、一个实现或一个 Tool，都还没有形成可替换能力。角色可以位于不同 Package，也可以在简单场景中合并；判断标准是依赖方向和替换边界，而不是目录数量。

Filesystem 与 Subprocess 还必须共同描述同一个 Execution World。`tool-fs-search` 通过 `ctx.subprocess` 启动 ripgrep，`lsp-stdio` 同时通过 `ctx.fs` 读取源码、通过 `ctx.subprocess` 启动 Language Server。若两项 Provider 指向不同机器，它们就会看到不同文件和进程；因此 Local 组合使用 `fs-local + subprocess-local`，E2B 组合则同时替换为 `fs-e2b + subprocess-e2b`。

替换以后，Bash、PTY、LSP 和文件工具继续消费原来的接口。变化的是文件和进程实际存在的位置，不是每个 Consumer 的实现。Architecture 文档强调的正是这种传播关系：Provider 的选择可以通过稳定 Service 同时影响多个 Consumer。

这里的边界也必须一起保留：当前 E2B 是 ephemeral POC。Cordis Service、AgentLoop、Session Log、LLM 请求和 Skills 仍在 Host 进程；E2B 只提供远端 Filesystem 与 Subprocess 世界。它没有完整 reconnect、workspace synchronization 或 durable remote handle，也不是 hard multi-tenant boundary。

<details class="source-note" markdown="1">
<summary>源码依据：Consumer 为什么不依赖 Local 或 E2B Provider</summary>

**Filesystem、LSP 与 E2B 源码结论：**`tool-fs` 只要求 `fs`，`lsp-stdio` 只要求 `fs` 与 `subprocess`；E2B 通过同一个 sandbox owner 提供这两个 Service 的实现。Consumer 不导入 E2B 实现，Composition 才选择 Provider。
{: .evidence-summary}

**源码批注版（中文注释为后加）：**

```ts
// 文件 Tool 只依赖抽象的 fs Service
export const inject = ['tools', 'fs', 'systemPrompt']

// LSP Provider 同时使用抽象的 fs 与 subprocess，保证源码和进程处于同一 Execution World
export const inject = ['fs', 'lsp', 'subprocess']
```

[packages/fs/tool-fs/src/index.ts：Consumer inject ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/fs/tool-fs/src/index.ts#L18-L23){: data-source-evidence=""}

[packages/lsp/lsp-stdio/src/index.ts：Execution World inject ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/lsp/lsp-stdio/src/index.ts#L41-L48){: data-source-evidence=""}

[packages/e2b/e2b/README.md：共享 Sandbox Owner ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/e2b/e2b/README.md){: data-source-evidence=""}

[docs/architecture.md：Capability seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#capability-seams){: data-source-evidence=""}
</details>

### 2.5 Composition 怎样连接 Host、Preset 与多个 Agent {#section-2-5}

Capability Seam 说明具体实现怎样替换，Agent Preset 说明某类 Agent 最终取得哪些能力。当前 DSH 把长期存在的 Host Composition 与 Agent-side Composition 分开，再由 standing Preset 把后者提供给多个 Agent。
{: .section-lead}

Host plane 与 Agent plane 是当前 Preset 设计使用的职责名称，不是两台机器或两个进程。Standard 的配置文件明确把 Registries、Persistence、Sandbox、Approval、Model Route 和跨 Session Providers 留在 Host；Preset 主要贡献 Persona、Prompt Section、Tools、Skills，以及是否启用 Plan、Compaction、Delegation、Workflow 和某种 Tool Presentation。

| Host Composition 持有 | Standard Preset 贡献或选择 |
|---|---|
| AgentLoop、Agent/Session Registry、Persistence | Persona 与 Prompt Sections |
| Tool、System Prompt、Skill 等 Registry | 向该 Preset 注册的 Tools 与 Skill roots |
| Sandbox、Approval、Credentials、Model Route | 是否向模型提供 Plan、Compaction 与 Delegation |
| Subagent Registry 与具体 Providers | model-facing Subagent Tools 与 Workflow |
| Filesystem、Subprocess 等底层 Provider | Tool Presentation 等模型侧选择 |

这个划分不是根据 Feature 名字决定。例如 `subagents` Registry 和具体 Providers 需要被 Host API 与多个 Session 使用，所以留在 Host；Standard 决定是否给自己的 Agent 注册 model-facing delegation Tools。Plan Service 没有相同的 Host 消费者，Standard 在自己的隔离组里拥有它。具体判断来自消费者、作用范围和生命周期，而不是“它听起来是否属于 Agent”。

在 Agent plane 内，当前实现也没有为每个 Session 重复挂载 Standard。Roster 第一次使用某个 generation 时建立 standing composition；之后 Agent A、B 把各自 ScopeKey 的 parent 指向该 Preset ScopeKey，读取顺序是 `agent → preset → global`。

```text
Host / Global registrations
            ↑
Standard standing composition
       ↑               ↑
    Agent A          Agent B
       │               │
  Session A data   Session B data
```

| 共享到 Preset generation | 仍按 Session / Agent 分开 |
|---|---|
| Plugin objects 与 Effect lifetime | Workspace、Session Log |
| Prompt Sections、Tool Definitions、Skills roots | Agent、Inbox、Cancellation |
| Scoped Listeners 与 Preset-owned Service instances | 以 SessionId/AgentId 为 key 的 mutable state |

这项选择不是 Cordis 强制要求。每个 Session 单独挂载 Preset 也能工作，但会按 Session 重复建立 Plugin、Listener、Watcher 和 Registration；standing mount 把这部分成本改成 per generation。相应代价是共享 Plugin 必须把 Session 状态放进 Session Log、按 identity 建索引，或者使用明确的 per-agent structure，不能只用一个实例字段保存“当前 Session”。

事件监听也沿相同 Parent Chain 过滤。Standing Preset 中注册的 scoped listener 会收到加入这一 Preset 的 Agent Event，却不会接收 Sibling Preset 的 Agent Event。Host 在没有 live Agent 时读取 cold transcript，也可以根据 durable PresetId 取得对应 standing key，用同一套 Prompt 与 Presentation Registration 解释历史。

{% include dsh/diagram.html number="2" title="Host、Preset 与 Agent 的真实关系" src="/assets/wiki/deepseek-harness/diagrams/14-host-preset-agent.html" description="展开 Host 共享能力、Preset standing composition 与两个独立 Session" note="重点查看挂载一次、父级查找和会话数据分离" %}

Preset 文件变化时，下一次新建 Session 可以进入新的 generation；已经运行的 Session 继续绑定原来的 generation。这样不会在一段已有历史中途突然改变 Tool Schema 或 Prompt。代价是旧 generation 仍要存活，直到整个 tree 被释放；当前实现也把 generation 回收列为未完成问题。

<details class="source-note" markdown="1">
<summary>源码依据：Host 与 standing Preset 分别持有什么</summary>

**Standard 配置与 Preset README 结论：**Standard 是 Agent-plane composition，Host 保留 Registries、Persistence、Sandbox、Approval 与 Model Route；一个 Preset generation 只挂载一次，多个 Agent 通过 parent binding 读取它的 Registration，Session 状态仍按 identity 分开。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
Host Composition
  ├── registries / persistence / sandbox / approval / providers
  └── AgentLoop

Standard standing composition（one per generation）
  ├── persona / prompt / tools / skills
  ├── plan / compaction / workflow choices
  ├── Agent A parent binding → Session A state
  └── Agent B parent binding → Session B state
```

[Standard Preset 的 Host / Agent 注释 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}

[Agent Presets README：standing mount ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}
</details>

<!-- talk-route: Part 3 | 20 min | full: 3.1→3.2→3.3→3.4→3.5 | short: 3.1→3.3→3.4→3.5 -->
## Part 3｜Core Designs：会话、模型输入、工具和长期任务 {#part-core-designs}

Composition 解释一个 Agent 拿到哪些组件。接下来沿一次真实执行继续向下：Session 保存什么，模型每次请求收到什么，历史过长后怎样压缩，工具如何执行，以及一次 Turn 不够时任务怎样继续。

### 3.1 Session 如何记录执行过程并支持恢复 {#section-3-1}

DSH 把 Session 定义为按顺序追加的 typed SessionEvent log。它记录一段 Agent interaction 中已经发生的事实；模型消息、网页展示和恢复判断都从这份记录重新生成，而不是各自维护另一份历史。
{: .section-lead}

这种组织通常称为 Event Sourcing：系统保存发生过的 Event，再从 Event 计算当前需要的视图。DSH 并不是完全不使用 Messages；它不把 Messages 维护成第二份独立历史，而是在请求模型时通过 `deriveMessages()` 从 Session Log 生成。

Agent 负责当前执行，Session 记录持久事实。Agent 拥有 Inbox、Cancellation 与当前 Status；Session 拥有可重放的 Event Log。进程内 Agent 可以释放和重建，但已经提交的 SessionEvent 不因此消失。Part 2 讨论 Plugin 安装在哪里，这一节讨论运行数据能否跨过进程生命周期，两者不是同一项分类。

只保存 user/assistant messages 不够。一次工具调用是否执行成功、模型当时拿到了哪些 Tool Schemas、使用哪个 Provider 和 Model、Turn 是否在中途崩溃，都会影响后续恢复与调试。DSH 因此记录 Turn、Step、消息、Tool Call、Tool Result 和 Request Header 等不同事件。

```text
SessionEvent log
├── turn/start · turn/end
├── step/start · step/end
├── user/message · assistant/chunk · assistant/message
├── tool/call · tool/result
├── request/header
└── request/context
```

`request/header` 保存 Call Config、最终 System Prompt 和已经组装的 Tool Schemas，它是重建 Request Envelope 的依据。`request/context` 另外保存 Provider、Model 与 Context Window，用于记录 Route 与容量变化，但不参与 Header Equality。两者都不生成聊天消息；`assistant/chunk` 保留流式回放，`assistant/message` 才进入模型历史。

| 内容 | 是否持久化 | 恢复时怎样处理 |
|---|---|---|
| SessionEvent | 是 | 从 Persistence 加载 |
| 模型 Messages | 不单独保存 | `deriveMessages()` 从 Event 重新生成 |
| UI Conversation | 不作为第二真源 | 从同一 Log Projection 得到 |
| live Agent / Inbox / Cancellation | 否 | 需要时重新创建 |
| Subagent Activation | 否 | 根据 durable child Session 冷恢复 |

Persistence 是独立接口，可以接 JSONL 或 SQLite。Cold Session 从存储加载时，如果日志里有 `turn/start` 却没有对应的 `turn/end`，恢复逻辑会保留已经持久化的中间事件，再追加 synthetic interrupted `turn/end`；它不会截掉整个 Turn。这个修复只适用于 cold load，仍在内存中执行的 live Session 不会被擅自补结束事件。遇到当前版本无法忠实理解的必需 Event 或旧格式时，DSH 选择明确拒绝，而不是静默跳过后继续执行。

持久化还有一个时间边界：`session.append()` 先提交内存中的事实并同步发出 `session/event`，Persistence Plugin 再把 Event 放进按 Session 管理的批次。`session/flush` 会取消等待并排空已有批次；调用方如果要在 `whenIdle()` 后立即读取存储，仍要显式等待 Flush。Turn 结束本身不会自动证明 Backend 已完成 durable write。

<details class="source-note" markdown="1">
<summary>源码依据：SessionEvent 如何成为唯一历史来源</summary>

**Session 与 Persistence 文档结论：**Session 是 append-only typed Event log；LLM history 通过 `deriveMessages()` 生成。Persistence 负责 Flush、恢复和 Header；开放 Turn 恢复为 interrupted，无法忠实读取的格式明确失败。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
const events = await persistence.loadCold(sessionId)

if (hasOpenTurn(events)) {
  // 保留 Turn 中已经持久化的 Event，只补充明确的中断结尾
  append({ type: 'turn/end', reason: { kind: 'interrupted' } })
}

const messages = deriveMessages(events)
```

[docs/subsystems/session.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md){: data-source-evidence=""}

[docs/subsystems/persistence.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/persistence.md){: data-source-evidence=""}
</details>

### 3.2 模型每次请求里到底有什么 {#section-3-2}

模型接收的不是整棵 Plugin tree，也不是完整 Session Log。每次请求都会从当前 Agent 的注册与 Session 记录中组装 System Prompt、Tool Schemas、动态上下文和一段经过 Projection 的消息历史。
{: .section-lead}

本文把模型在一次请求中实际接收的内容称为 **Model Surface**。这是一个讨论边界，不是新的持久化对象：

**关系整理（非仓库原文）：**

```text
Model Surface
= System Prompt Sections
+ Tool Schemas 或 Code SDK
+ 从 SessionEvent 生成的 Conversation Messages

Runtime Context、Skill Content、Plan Policy
最终会进入上述 Prompt、Tools 或 Messages 中的某一处
```

完整的模型请求还包括 Call Config，例如 Provider、Model、Reasoning Effort、Max Tokens 和 Sampling 参数。它们不一定作为文字被模型“阅读”，却会改变请求如何执行。为避免把 API 参数也叫成 Prompt，本文用 **Request Semantics** 指 Model Surface 加上这些调用参数。

Architecture 明确要求 **Model-visible means logged**：最终进入模型请求的语义必须能够从 Session Log 重建。不同内容落在不同 Event 中：

| 请求内容 | 日志中的来源 |
|---|---|
| Call Config、Adapter Defaults、最终 System Prompt、Tool Schemas | 最新的 `request/header` snapshot |
| Provider、Model 与 Context Window 等 Route metadata | 最新的 `request/context`，不参与 Header Equality |
| User、Assistant 与 Tool Result Messages | 当前 Session Surface 上的 message-producing Events |

`agent/pre-step` 可以在 live 调用中改写输入，但真正进入 Step 的消息会写成 `user/message`；Assistant Message、Tool Call 和 Tool Result 也各自落成 Event。

这不表示 Prompt 渲染、Waterfall Listener 或 Provider 内部的每个中间值都要持久化。需要被记录的是最终到达模型的 Request Semantics，以及影响后续 Projection 的 durable fact。否则 Resume、Fork、Transcript 和调试会从同一份 Log 推导出与真实请求不同的结果。

System Prompt Registry 支持全局与 scoped contribution。同名 Prompt Section 可以在更近的 Agent/Preset 层覆盖全局定义；Tool provider 只返回本次 assembly 可见的 schemas。频繁变化的 Runtime Context 不一定要改写高位 System Prompt，DSH 还可以把它物化成 durable user-role snapshot，减少稳定前缀被动态信息反复破坏。

Skills 也遵循类似边界：Host 可以拥有 Skill Registry，Preset 决定向自己的作用范围贡献哪些 Skill roots 和 model-facing Tool。系统“知道哪些 Skills”和这个 Agent“能发现并加载哪些 Skills”不是同一个问题。

Plan Mode 是一个更具体的例子。`plan/mode` 作为 Session Event 保存，当前状态由 Log fold 得到；启用后加入 `plan:policy` Prompt Section。`exit_plan_mode` 始终留在 Tool Catalog 中，所以进入和退出 Plan 只改变 Prompt，不改变工具目录。这样既能恢复协作状态，也避免 Mode switch 本身导致 Tool Schema 前缀变化。

| 关注点 | DSH 的处理 |
|---|---|
| Behavior | Plan Prompt 提供软性行为指导 |
| Authority | Sandbox 与 Approval 独立执行真实权限 |
| Cache | Plan 切换保持 Tool Catalog 不变 |
| Reconstruction | Request Header 记录最终 Prompt 与 Tools |

DSH 还要求 model-facing package 的 README 说明 “What the model sees”、Token Effect 和 KV Cache Effect。它不保证自动优化缓存，但要求包作者把模型输入变化当成架构影响，而不是只在 Prompt 调试时才发现。

这个 Contract 也约束模型邻近组件。一个 Package 即使不直接写 Prompt，只要会改变 Tool Schema、动态 Context、Messages Projection 或 Request Prefix，也应该说明影响。这样 Code Review 可以同时检查功能正确性和模型体验，而不是等到线上 TTFT、Cache Read 或行为漂移以后再反推是哪项注册改变了请求。

<details class="source-note" markdown="1">
<summary>源码依据：Prompt、Tools 与 Plan 怎样进入请求</summary>

**System Prompt 与 Plan 文档结论：**Assembly 按 scope 解析 Prompt Sections、Prompt Context 和 Tool providers；Plan state 从 Session Log 恢复，启用时添加 `plan:policy`，而 `exit_plan_mode` 在 inactive 状态仍保持注册，因此 Tool Catalog 不随 Plan 切换。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
assembly = await systemPrompt.assemble({ scope: agent.scope })
request = {
  system: render(assembly.sections),
  tools: assembly.tools,
  messages: deriveMessages(session.events),
}

if (foldPlanMode(session.events)) addSection('plan:policy')
// exit_plan_mode remains in the catalog in both states
```

[docs/subsystems/system-prompt.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/system-prompt.md){: data-source-evidence=""}

[docs/subsystems/plan.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/plan.md){: data-source-evidence=""}
</details>

### 3.3 历史变长以后，Compaction 改了什么 {#section-3-3}

压缩上下文不等于删除历史。DSH 保留原始 SessionEvent，并通过新的 Event 改变后续模型消息如何从 Log 中生成；审计和回放仍能看到被压缩前的内容。
{: .section-lead}

假设一段会话已经产生 A 到 G 七段模型可见内容，Context Window 即将用满。直接删除 A 到 E 会让原始记录永久消失，也会让恢复、Fork 和调试无法知道摘要从何而来。DSH 追加 Compaction 的开始、摘要和结束记录，再追加一条新的 model-visible message，声明它替换旧 Surface 上的一段范围。

```text
压缩前
Session Log： A B C D E F G
模型看到：   A B C D E F G

压缩后
Session Log： A B C D E F G + compaction events + summary message
模型看到：   [A-E 的摘要] F G
```

这张图把 Log、替换范围和最终请求分开：

{% include dsh/diagram.html number="3" title="完整历史如何变成较短的模型输入" src="/assets/wiki/deepseek-harness/diagrams/15-history-to-model-surface.html" description="展开原始事件、摘要替换与最终 Model Surface" note="观察历史保留与模型输入缩短如何同时成立" %}

`compaction/start` 与 `compaction/end` 形成 durable bracket。进程崩溃后，如果发现没有匹配结束的 live compaction，系统可以识别它没有完整完成。`compaction/summary` 本身是 Log-only；真正进入 Model Surface 的是带 replace 操作的新 user message。这样“发生了一次摘要”和“模型以后看到这段摘要”是两项分别记录的事实。

替换范围还必须保持消息结构有效。一个 Tool Call 与对应 Tool Result 不能被切到摘要边界两侧，否则派生出的模型历史会出现没有调用的结果，或没有结果的调用。Compaction Service 在提交前检查范围是否存在、顺序是否正确，以及边界前后是否保持 Tool Pairing 平衡。

在调用模型生成摘要以前，Tool Result Pruner 可以先处理特别长的工具结果：保留头尾文本和非文本块，用明确标记替换过长中间部分。若确定性裁剪已经释放足够空间，就不必额外花一次模型请求。Compaction 通常在 `agent/pre-step` 检查压力，也可以在 Provider 返回 context overflow 后进入恢复路径。

源码把生成当前消息视图的过程称为 Projection，把消息如何加入或替换视图的字段称为 `SurfaceOp`。正文需要记住的仍然只有一件事：Execution History 与下一次 Model Request 不是同一个数据结构。

<details class="source-note" markdown="1">
<summary>源码依据：摘要怎样替换 Model Surface 而不删除 Event</summary>

**Compaction 文档结论：**Compaction 过程使用 start/summary/end Event 记录；原始 Event 不删除。带 `SurfaceOp.replace(start, end)` 的新消息在 Projection 中遮蔽旧范围，`deriveMessages()` 因此返回 Summary 加 Recent Messages。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
append({ type: 'compaction/start', ... })
append({ type: 'compaction/summary', summary }) // log-only
append({
  type: 'user/message',
  content: summary,
  surfaceOp: replace(startSeq, endSeq),
})
append({ type: 'compaction/end', ... })
```

[docs/subsystems/compaction.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/compaction.md){: data-source-evidence=""}

[docs/subsystems/session.md：Surface types ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md#surface-types){: data-source-evidence=""}
</details>

### 3.4 一项 Tool Call 如何真正执行 {#section-3-4}

模型看见 Tool Schema 以后，并不是直接调用对应函数。DSH 先把 Tool Call 写入 Session，再经过解析、限制、审批、Sandbox 与可扩展执行管线，最后把规范化结果写回 Session。
{: .section-lead}

一个 `ToolDefinition` 不只有名称和 Input Schema，还可以包含 Output Schema、Execute 函数、调度元数据和 Presentation 元数据。真正发给模型的 Schema 使用显式 allowlist 生成；执行调度、审批状态和内部字段不会因为存在于 ToolDefinition 就自动暴露给模型。

```text
assistant Tool Call
  ↓
session tool/call
  ↓
resolve visible executable definition
  ↓
tools/pre-execute
  ↓
monotonic guards + approval + sandbox policy
  ↓
tools/execute waterfall → tool body
  ↓
tools/post-execute → normalize / finalize
  ↓
session tool/result
```

这条 Tool Execution Pipeline 是执行权限的共同入口。可见性过滤决定模型能否看见并命名一个 Tool；执行层仍会重新解析当前 Scope，并应用只能收紧、不能在后续阶段放宽的 Guard。Presentation、Visibility 和 Authority 因而是三件相关但不等价的事情。

工具的调度元数据还可以决定多个 Call 能否并行，结果 Finalizer 则负责把取消、解析失败、未知 Tool 和执行异常统一转成可记录的结果。无论失败发生在参数解析、Approval 还是 Tool Body，Session 都需要得到与原 `callId` 配对的终态，避免下一次 `deriveMessages()` 生成悬空 Tool Call。

Code Mode 改变的是模型组织工具调用的方式。Native 模式下，模型通常每得到一个 Tool Result 都要再次推理；Code 模式向模型提供 `run_code` 与生成的 SDK，让一段程序在一次 Runtime 执行中完成搜索、并发读取、分支、筛选和聚合，再把整理后的结果返回模型。

{% include dsh/diagram.html number="4" title="Native Tools 与 Code Mode 的调用差异" src="/assets/wiki/deepseek-harness/diagrams/16-native-vs-code.html" description="比较模型逐次编排与 Runtime 内程序化编排" note="Code Mode 改变调用接口，但不绕过工具权限管线" %}

Code Mode 的 SDK subcall 仍通过同一个 Tool Runtime，受到相同的 Tool Restriction、Approval 和执行 Hook 约束。默认 worker-thread backend 每次使用 fresh worker，并限制 Heap、Output、Compute Timeout 和 Wall Timeout；这些是故障控制与资源限制，不是恶意代码的硬安全边界。

因此不能直接声称 Code Mode 一定更快或一定节省 Token。它减少模型与工具之间的往返时，也会引入 SDK Token、程序生成、Worker 启动和结果整理成本。可以确定的架构变化是：一部分原本由模型逐轮完成的 orchestration，被移动到 Runtime 中执行。

<details class="source-note" markdown="1">
<summary>源码依据：Code subcall 为什么仍经过统一工具管线</summary>

**Tools 与 Code Mode 文档结论：**Native 调用和 Code SDK subcall 最终都由 ToolRuntime 解析并执行；Nested subcall 可以访问当前 Agent 可见的底层工具，但仍经过限制、Approval 和 `tools/*` hooks。Worker thread 只提供 containment。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
async function dispatch(call, { nested }) {
  const tool = resolveExecution(call.name, agentScope, nested)
  await runMonotonicGuards(tool, call)
  await approval.check(tool, call)
  return toolsWaterfall.execute(tool, call)
}

run_code(program) // SDK bindings call dispatch(..., { nested: true })
```

[docs/tool-execution-pipeline.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/tool-execution-pipeline.md){: data-source-evidence=""}

[Code Mode Agent Note ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-06-15-code-mode.md){: data-source-evidence=""}
</details>

### 3.5 一次 Turn 结束不了的工作如何继续 {#section-3-5}

Goal、Subagent 和 Workflow 都能让工作超出一次普通 Turn，但它们保存的身份和组织层次不同。把三者都理解成“后台任务”，会丢失恢复、取消与所有权上的关键差别。
{: .section-lead}

| 机制 | 身份 | 适合处理什么 |
|---|---|---|
| Goal | 仍在当前 Session | 同一个 Agent 持续维护的目标与 continuation |
| Subagent | 新的 child Session | 可独立运行、恢复和继续对话的委派工作 |
| Workflow / Ralph | 更高层 orchestration | 在现有 Agent、Goal、Subagent 与工具上组织重复执行 |

Subagent 不是 AgentLoop builtin。`ctx.subagents` 是 named Provider Registry；spawn-in-process、fork、ACP、Codex、Claude Code 和 DSH SDK 等实现可以共存。Model-facing delegation Tool 选择 Provider，Control Tools 负责 follow-up、interrupt 和列表查询。这样“由谁执行 child”与“主 Agent 如何委派”可以分别扩展。

Provider 还要声明自己支持哪些 Start-time Capability，例如 Persona、Tool Filter、Depth Limit 与 Structured Output。不支持的请求在启动前明确失败，不能接受以后静默忽略。Continuable Child 则由 `prepareContinuable` 的存在表示支持，因为它的 Session 与 Activation 由 Continuation Manager 统一建立，而不是交给每个 Provider 各写一套恢复协议。

Continuable Subagent 最关键的区分是 Session 与 Activation。Child Session 是持久身份；Activation 是这个 Child Agent 当前驻留在进程中的一段时间，内部持有 AgentHandle、Inbox 和 live descendants。Activation 不是另一种 Session，也不是一次请求或一个 Future。

```text
Durable child Session
        │
        └── optional live Activation
              ├── retained AgentHandle
              ├── Agent Inbox：唯一 FIFO
              └── owned child Activations
```

{% include dsh/diagram.html number="5" title="Child Session 与 Live Activation" src="/assets/wiki/deepseek-harness/diagrams/17-session-activation.html" description="展开 Subagent 的持久身份、当前驻留与 follow-up 路径" note="观察 running、waiting 与 cold resume 使用同一个 child Session" %}

`followup()` 遇到 running Activation 时进入同一 Inbox，waiting 时唤醒同一个 Activation，没有 Activation 时才 cold resume。一个 Session 同时至多有一个 live Activation。`interrupt()` 调用 `cancel(..., { keepInbox: true })`，停止当前 Turn，但不销毁 Child Session，也不删除尚未领取的后续消息。

父子权限依赖 durable direct-parent identity 与 live ancestry；清理按 child-first 顺序进行。进程内 Activation 被释放以后，durable child Session 仍可保留。由此可以看到，长期工作的难点不是“多启动一个 Loop”，而是身份、驻留、消息顺序、取消权和资源所有者必须一致。

<details class="source-note" markdown="1">
<summary>源码依据：Subagent Session 与 Activation 怎样分工</summary>

**Subagent 文档结论：**Continuable child 是一个 durable Session，最多对应一个 process-local Activation；Follow-up 按 residency 选择同一 Activation、Wake 或 Cold Resume。Goal 则明确是 same-session objective，不创建 child Session。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
function followup(childSessionId, message) {
  const activation = liveActivations.get(childSessionId)
  if (activation?.running) return activation.agent.followup(message)
  if (activation?.waiting) return activation.wake(message)
  return coldResume(childSessionId).then(a => a.agent.followup(message))
}
```

[docs/subsystems/subagent.md：Continuable children and activations ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/subagent.md#continuable-children-and-activations){: data-source-evidence=""}

[docs/subsystems/goal.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/goal.md){: data-source-evidence=""}
</details>

<!-- talk-route: Part 4 | 8 min | full: 4.1→4.2→4.3→4.4→4.5 | short: 4.2→4.5 -->
## Part 4｜Four Agent Presets：四种 Agent 分别改变了什么 {#part-presets}

Standard、Code、Minimal 和 Cordis 是四个 Agent Preset，不是四个互斥 Mode。Plan Mode 是 Session 当前的协作状态，Tool Presentation Mode 是 native、code 或 both；这三个维度需要分开。

| 名称 | 例子 | 它决定什么 |
|---|---|---|
| Agent Preset | standard / code / minimal / cordis | 参与 Agent-side composition 的 Plugin |
| Plan Mode | active / inactive | 当前 Session 是否加入 Plan Policy |
| Tool Presentation | native / code / both | 模型通过什么接口使用 Tool Universe |

### 4.1 Standard：完整的 Coding Agent {#section-4-1}

Standard 是日常完整 Coding Agent 的 Agent-side composition。它把 Persona、Shell、文件工具、Skills、Goal、Plan、Compaction、Delegation、Workflow 和其他工具组织到同一 Preset 中。
{: .section-lead}

这份文件也是理解前面所有抽象最直接的入口。没有一个 `standardAgent()` 函数一次性创建全部功能；YAML 按区域列出 Plugin，注释说明哪些 Registry 留在 Host、哪些行只向当前 Preset 贡献工具、哪些 Service 需要独立 isolate。

| Standard 区域 | 主要内容 |
|---|---|
| Identity | Persona、Agent Instructions |
| Shell / Filesystem | Bash 或 Pwsh、File Tools、File Search |
| Skills / Goals | Skill Discovery、Skill Tool、Goal Tool |
| Planning | Plan Mode 与 Exit Tool |
| Compaction | Basic Compaction、Tool Result Pruner |
| Delegation | Subagent Tools、Fork、Workflow、Ralph |
| Remaining Tools | Ask User、Todo、Web 等 |
| Presentation | Native Tool Presentation |

Standard 中的一些行只消费 Host Service。例如 Bash Tool 使用 Host 的 Shell、Sandbox 和 Background Jobs；Goal Tool 使用 Host 的 Goal Service；Delegation Tool 使用 Host 的 Subagent Registry。另一些 Service 确实由 Preset 拥有，例如 Plan Mode 和 Workflow，需要放在自己的 isolate group 中。

这种注释密度不是普通配置文件的常态，但在这里很有价值：每一组都解释为什么某个 Registry 必须留在 Host、为什么某个 Consumer 不能单独放进 isolate，以及哪部分只是决定模型能否调用。这些说明把抽象的 Plane Rule 落到真实依赖图，避免仅凭包名移动组件。

因此 Standard 不是“所有 package 全开”，而是一份经过所有权判断后的完整产品 Composition。某个功能是否存在，要看 Preset 是否贡献 model-facing 入口，以及 Host 是否提供它依赖的底层 Service。

<details class="source-note" markdown="1">
<summary>源码依据：Standard 文件怎样划分完整 Agent</summary>

**配置文件结论：**Standard 用命名区域组织 Identity、Shell、Filesystem、Jobs、Skills、Goals、Plan、Compaction、Delegation 与其他 Tools；每组注释明确它消费 Host Service 还是拥有 Preset-local Service。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
standard/agent.cordis.yml
├── identity
├── shell / filesystem / background jobs
├── skills / goals / plan mode
├── compaction
├── delegation and workflows
└── remaining tools + native presentation
```

[Standard Agent Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.2 Code：主要能力相近，工具接口发生变化 {#section-4-2}

Code Preset 保留 Standard 的大部分能力与结构，主要变化是把 Tool Presentation 设置为 `code`。模型不再直接看到整组 Native Tool Schemas，而是看到 `run_code` 与按当前可见工具生成的 SDK。
{: .section-lead}

这正好把“系统拥有什么能力”和“模型通过什么接口使用能力”分开。底层 File Search、Read、Web、Todo 或 Subagent Tool 仍然注册在 Tool Runtime 中；Presentation Layer 把它们变成 SDK Binding，模型写程序调用这些 Binding。

```text
Standard Preset
Tool Universe ──native presentation──> Tool A / Tool B / Tool C

Code Preset
Tool Universe ──code presentation────> run_code + generated SDK
```

Tool Universe 并没有因为 Schema 不再直接发送给模型而消失。Code Executor 仍要知道当前 Agent 可见哪些工具，并让 subcall 经过统一执行管线。直接伪造一个底层 Native Tool Call 在 Code-only 模式下会被拒绝；只有 `run_code` 内部标记为 nested 的 SDK 调用可以访问相应定义。

Generated SDK 也属于 Model Surface。Tool Name、Input Schema 与输出类型会变成程序接口文本，因此 Code Presentation 不等于“只发送一个很小的 run_code Schema”。它可能减少多轮模型编排，却会增加 SDK 描述；是否更省 Token 要按具体 Tool Universe、调用轮数与 Cache 行为测量。

因此 Code 是 Preset，Code Mode 也是 Tool Presentation 机制。Part 3 解释的是机制如何执行和隔离；这里强调产品配置如何选择它。两者不能写成“另一个 AgentLoop”。

<details class="source-note" markdown="1">
<summary>源码依据：Code Preset 实际改变了哪一行</summary>

**Code 配置结论：**文件保持 Standard 的完整结构，并加入 `tool-presentation: { mode: code }`。Tool Registry 仍在 Host；Preset 选择当前 Agent 的 model-facing presentation。
{: .evidence-summary}

**配置摘录：**

```yaml
- id: tool-presentation
  name: '@deepseek-ai/dsh-agent-tool-presentation'
  config:
    mode: code
```

[Code Agent Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/code/agent.cordis.yml){: data-source-evidence=""}

[Per-agent Tool Presentation Agent Note ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-08-05-per-agent-tool-presentation.md){: data-source-evidence=""}
</details>

### 4.3 Minimal：从更小的能力集合开始 {#section-4-3}

Minimal 不是从 Standard 临时关闭几个按钮，而是一份独立、刻意缩小的 Composition。它提供固定完整 Persona、Persistent Bash 和 `str_replace_editor`，不加载 Standard 的 Skills、Plan、Compaction、Subagent 与 Workflow。
{: .section-lead}

Minimal 的 Persona 标记为 `complete`，并关闭 Runtime Context 注入；这使它的 System Prompt 不再继承 Standard 那套分段说明。工具方面，它保留持久 Shell 和一个兼容特定 Agent Interface 的 Editor，而不是完整 File Tools 与 Search 组合。

```text
Minimal Model Surface
├── complete fixed persona
├── persistent bash
└── str_replace_editor

没有加载
├── Skills / Goal / Plan
├── Compaction
└── Subagent / Workflow
```

Minimal 还展示了 Composition 不只是“增加 Plugin”。它在自己的 isolate group 中提供 Local Filesystem，从而只在这个 Preset 内覆盖 Host 的 Filesystem Provider；同组的 Editor 使用这份实现，其他 Preset 继续解析 Host 默认 Provider。

`includeRuntimeContext: false` 只影响模型侧动态上下文，不会关闭 Host 的 Sandbox、Workspace 或 Session 机制。Minimal 仍运行在同一 Host，Tool 执行仍使用统一管线，历史仍写入同一 Session 模型。它缩小的是 Agent-side composition 与 Model Surface，不是绕开基础设施。

这类替换必须谨慎描述。Minimal 没有改变整个进程的 `ctx.fs`，也不是另起一个 Host；它只让属于这个 Preset group 的 consumer 解析到更近的 Service。正文使用“在 Minimal 内替换”即可，具体 `Realm` 和 shadow 规则留给源码依据。

<details class="source-note" markdown="1">
<summary>源码依据：Minimal 怎样缩小并替换 Agent Composition</summary>

**Minimal 配置结论：**Persona 使用 complete 固定文本并禁用 Runtime Context；Preset 只加载 Persistent Shell 与 Editor。Filesystem Provider 和 Consumer 放在同一个 `isolate: { fs: true }` group，因此替换不会发布成 Host 全局 Service。
{: .evidence-summary}

**配置摘录：**

```yaml
- id: filesystem
  name: cordis:group
  group: true
  isolate:
    fs: true
  config:
    - id: fs-local
      name: '@deepseek-ai/dsh-fs-local'
      config:
        cwd: !!js process.env.DSH_CWD ?? process.cwd()

    - id: str-replace-editor
      name: '@deepseek-ai/dsh-tool-str-replace-editor'
      config:
        maxOutputChars: 16000
```

[Minimal Agent Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/minimal/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.4 Cordis：Agent 可以修改 Composition {#section-4-4}

Cordis Preset 在 Standard 能力上增加 Cordis Toolset、Composition Authoring Skill 和专门 Persona，使 Agent 能读取当前 Composition、编写新的 Plugin，并把临时组件挂载到 live Host。
{: .section-lead}

它把前面的 Composition 从部署者维护的文件变成模型可以操作的对象。Agent 可以检查当前 Cordis tree，生成 JavaScript Plugin，调用 `cordis_mount` 安装，再在不需要时卸载。Authoring Skill 则指导它复制 shipped Preset、编辑用户目录中的 `agent.cordis.yml`，避免直接破坏安装内容。

```text
Cordis Preset
= Standard capabilities
+ Cordis inspection tools
+ cordis_mount / unmount
+ composition-authoring skill
+ dedicated persona
```

这并不表示 DSH 可以安全地让任意低信任输入“自我进化”。`cordis_mount` 会把模型写出的 JavaScript 放进当前 live runtime 执行；代码可以接触 Host 中已有的 Service 和能力。仓库明确要求把它视为接近 Shell access 的权限。

临时 Mount 还必须拥有明确 disposer。若 Agent 新增 Tool、Prompt 或 Listener 后不保存卸载句柄，这些注册会继续影响后续请求；若它改写 shipped Preset，升级又可能覆盖修改。Authoring Flow 因而要求先复制到 User Preset，再编辑文件，并把 live experiment 与长期配置分开管理。

Cordis Preset 的价值在于把 Composition 的表达力推到极端：Agent 不只使用一套组合，也可以参与编写组合。但是否允许这种能力，是 Trust Policy，而不是 Composition Framework 自动做出的决定。

<details class="source-note" markdown="1">
<summary>源码依据：Cordis Preset 能做什么以及信任边界</summary>

**Cordis 配置结论：**Preset 增加 `dsh-tool-cordis` 与本地 Composition Authoring Skill；Persona 明确区分 Host Composition 与 Agent Preset，并要求不要修改 shipped install。Model-written JavaScript 在 live runtime 中执行，应按 Shell 权限对待。
{: .evidence-summary}

**配置摘录：**

```yaml
- id: tool-cordis
  name: '@deepseek-ai/dsh-tool-cordis'

- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - !!js "process.getBuiltinModule('node:url').fileURLToPath(new URL('skills/', baseUrl))"
```

[Cordis Agent Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/cordis/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.5 四个 Preset 到底差在哪里 {#section-4-5}

四个 Preset 共用同一个 Host Composition 和 AgentLoop，但向 Agent 贡献不同的 Prompt、Tools、Services 与 Tool Presentation。它们的差异可以从 Model Surface、长期任务能力和信任范围三个方向检查。
{: .section-lead}

| 能力或选择 | Standard | Code | Minimal | Cordis |
|---|---|---|---|---|
| 主要定位 | 完整日常 Coding Agent | 程序化工具编排 | 小型独立 Agent | Composition Authoring |
| Persona / Instructions | 完整 | 与 Standard 相近 | Complete 固定文本 | Cordis 专用 |
| Shell / Filesystem | 完整 | 完整 | Persistent Shell + Editor | 完整 |
| Skills | 有 | 有 | 无 | 有，另加 Authoring Skill |
| Plan / Compaction | 有 | 有 | 无 | 有 |
| Subagent / Workflow | 有 | 有 | 无 | 有 |
| Tool Presentation | native | code | 简单 native | native |
| 修改 live Composition | 无 | 无 | 无 | 有 |
| 信任范围 | 常规 Coding Agent | 增加代码执行面 | 较小能力面 | 很高，接近 Shell |

Standard 与 Code 的主要能力范围相近，但模型接口不同；Minimal 是独立定义的小 Composition，不是 Standard 在运行中的临时状态；Cordis 把 Composition Authoring 暴露给模型。表里的“Tool Presentation”不能与“Preset”合并，否则无法解释 Standard 也可以理论上选择 another presentation，Plan Mode 又为什么能在所有这些 Preset 内单独切换。

Session 创建时会记录所选 Preset，因为它决定模型能看到的 Prompt 与 Tools。空白 Session 可以 recompose 到另一 Preset；一旦已经产生历史，切换会被拒绝。原因不是实现上不能改 parent binding，而是已有 Tool Calls 与 Prompt 语义属于原来的 Composition，贸然切换会让历史中出现当前 Agent 已无法理解或执行的工具。

“空白”在这里是产品语义，不只是 UI 有没有显示消息。切换完成后会追加 `agent-preset/selected` Event，让恢复与 cold transcript 使用实际运行的 Preset；创建 Header 仍保存最初选择，因为它是创建事实。读取方必须解析 Header 与后续 Selection Event，不能只取其中一个字段。

Subagent child 会加入 Parent 正在使用的同一 Preset generation，而不是按相同 PresetId 重新读取磁盘。这样父子在一次长期工作中使用一致的 Prompt 与 Tool Definitions，即使磁盘上的 Preset 文件已经更新或删除。

<details class="source-note" markdown="1">
<summary>源码依据：Preset 选择为何成为 Session 事实</summary>

**Agent Presets README 结论：**Preset 是包含 `agent.cordis.yml` 的目录；所选 id 进入 durable Session Header。只有尚未产生内容的 Agent 允许 recompose；Child Agent 通过 `composeFrom()` 加入 Parent 的同一 standing generation。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```text
session.create(agentPreset = "standard")
  → header records preset id
  → agent joins that standing generation

recompose(nextPreset)
  → allowed only while the session is blank
```

[Agent Presets README：Which preset a session runs ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#which-preset-a-session-runs){: data-source-evidence=""}

[Agent Presets README：Composing a child agent ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#composing-a-child-agent){: data-source-evidence=""}
</details>

<!-- talk-route: Part 5 | 7 min | full: 5.1→5.2→5.3→5.4→5.5 | short: 5.3→5.4→5.5 -->
## Part 5｜Conclusion：这套设计解决了什么，又付出了什么 {#part-comparison}

最后不做 Feature 勾选表。Claude Code、Codex、Kimi 与 DSH 都在处理现代 Harness 的共同问题；真正可比的是它们如何定义 Agent、Session、Tool Surface、Subagent 和恢复语义，以及这些选择带来什么成本。

### 5.1 比较不同 Harness 时，真正可比的是什么 {#section-5-1}

两个产品都提供 Plan、Compaction 或 Subagent，不代表它们采用了相同架构。比较时需要确认这些名称背后的身份、持久化、权限与生命周期，而不是只确认 UI 中是否有同名入口。
{: .section-lead}

例如，一个 Subagent 可能只是执行一次外部命令并返回文本，也可能拥有 durable child Session、continuation Inbox 和 cold resume。两者在 Feature 表里都可以打勾，但 Follow-up、Interrupt、父子权限和进程重启后的含义完全不同。

| 比较问题 | 需要确认的语义 |
|---|---|
| 一个 Agent 怎样定义？ | 固定 Application、普通配置，还是运行中组合的能力集合 |
| Capability 对谁有效？ | User、Project、Session、Agent、Preset 与 Global 如何区分 |
| 运行中变化怎样传播？ | 立即更新、仅新 Session 生效，还是必须 Restart |
| Durable State 的来源是什么？ | Messages、Typed Events，或其他模型 |
| 模型请求怎样构造？ | Prompt、Tools、Skills、Dynamic Context 与 History 怎样进入 |
| Compaction 修改什么？ | 删除历史，还是改变后续请求的 Projection |
| Subagent 是什么？ | One-shot Call、Child Loop、Durable Child Session 或外部产品 |
| 取消与恢复由谁负责？ | Identity、Authority、Ownership 和 Cleanup 怎样定义 |
| Tool Change 怎样影响 Cache？ | Schema、顺序与高位 Prefix 是否稳定 |

比较结论还要带版本与证据。公开文档没有说明已有 Session 是否接受 MCP Tool Update，就应保留 Unknown；不能因为产品看起来简单，就替它补一个最简单的内部实现。相同名称也不能推出相同语义：Plan UI 不代表一定使用 durable Event，支持 MCP 不代表 Tool Ordering 一定稳定。

同一产品内部也可能同时存在多种答案。Built-in Tools 可以固定，Project MCP 可以动态，Deferred Tool Search 又可能只改变模型侧展开方式；Subagent 既可能调用本产品 child，也可能委派给外部 Agent Product。比较表若只允许一个 Yes/No，会把这些路径压成错误结论。

DSH 的价值不需要建立在“其他 Harness 没有这些 Feature”上。Claude Code 有不同 MCP Config Scope 与动态 Tool Update，Codex 公开讨论 Prompt Cache 与 Tool Ordering，其他现代 Harness 也在解决长上下文与多 Agent。共同问题越真实，比较不同答案才越有意义。

<details class="source-note" markdown="1">
<summary>源码依据：比较结果如何保持可核对</summary>

**比较方法：**每个判断同时记录日期或版本、公开来源、可以确认的语义和仍未知的部分；未知项不由推测补齐。DSH 内部结论继续固定到本页 revision，其他产品优先引用官方公开材料。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
comparison = {
  question: '已有 Session 是否接收动态 Tool 变化？',
  product: 'example harness',
  versionOrDate: '2026-08',
  confirmed: ['supports provider tool updates'],
  unknown: ['propagation timing', 'cache invalidation details'],
  source: 'official documentation',
}
```

[Claude Code MCP docs ↗](https://code.claude.com/docs/en/mcp){: data-source-evidence=""}

[OpenAI：Unrolling the Codex agent loop ↗](https://openai.com/index/unrolling-the-codex-agent-loop/){: data-source-evidence=""}
</details>

### 5.2 工具变化为什么会影响模型输入和 KV Cache {#section-5-2}

Tool Definition 通常位于模型请求的高位部分。增加工具、删除工具、修改 Schema 或改变排序，都可能改变后续请求前缀；要求 exact prefix match 的缓存因此无法继续复用。
{: .section-lead}

假设上一轮模型看到 Tool A、B、C，下一轮 MCP Provider 增加 Tool D。即使 Conversation History 完全相同，请求前部已经变化。若工具集合相同、序列化顺序却从 A/B/C 变成 B/A/C，字节前缀同样不同。

```text
Request N：   system + [Tool A, Tool B, Tool C]         + history
Request N+1： system + [Tool A, Tool B, Tool C, Tool D] + history
                              ↑ prefix changed
```

不同 Harness 可以选择固定完整目录、动态目录、按需发现完整 Schema，或者用 Code/Programmatic Interface 表达一批 Tool。没有一种方案在所有任务上都最好：

| 策略 | 优点 | 代价 |
|---|---|---|
| 固定完整 Tool Catalog | Prefix 更稳定 | 首轮 Schema Token 较大 |
| 动态 Tool Catalog | 当前能力集合直接准确 | Tool Change 造成 Cache Miss |
| Deferred Discovery | 完整 Schema 按需出现 | 增加发现步骤与状态语义 |
| Code Presentation | Runtime 内批量调用与聚合 | SDK Token、Worker 与安全成本 |

DSH 的几个具体选择是：Tool Registry 按 Agent Scope 解析；Tool Presentation 可以 per-agent 选择；Plan Mode 保持 Tool Catalog 不变；`request/header` 记录最终 System Prompt 与 Schemas；model-facing package 要声明 Token 与 KV Cache Effect。这些措施让变化可追踪，但不会保证所有请求命中缓存。

Tool Schema 的位置也很重要。若高位 System 与 Tools 保持稳定，变化只追加在 Conversation 尾部，已有 Prefix 更容易复用；若每轮把时间、工作区状态或动态 Tool Description 写回高位 Prompt，哪怕正文对话没变也会不断失效。DSH 将动态 Prompt Context 单独物化，正是在结构上区分稳定说明与运行中事实。

真实评估不能只看一轮 Input Token。还要同时记录首轮与后续轮、Cache Read/Write、TTFT、额外 Tool Discovery Step、模型调用次数、Runtime 执行成本和任务成功率。权限或工作区真实变化时，正确 Model Surface 仍然优先，不能为了缓存保留已经失效的 Tool Schema。

<details class="source-note" markdown="1">
<summary>源码依据：为什么 Tool Ordering 也会造成 Cache Miss</summary>

**公开资料结论：**Codex 团队将 Prompt Caching 描述为 exact prefix match，并记录过 MCP Tool Ordering 不稳定导致 Cache Miss；Claude Code 也把 MCP Tool Definition 与 Prompt Cache 放在同一设计问题中。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
same set, different serialization:

[Tool A, Tool B, Tool C]
[Tool B, Tool A, Tool C]

engineering requirement:
stable ordering + stable serialization + explicit surface changes
```

[Claude Code prompt caching docs ↗](https://code.claude.com/docs/en/prompt-caching){: data-source-evidence=""}

[Codex Agent Loop：Prompt caching ↗](https://openai.com/index/unrolling-the-codex-agent-loop/){: data-source-evidence=""}
</details>

### 5.3 DSH 比较特别的地方是什么 {#section-5-3}

DSH 的特点不在某个独有 Feature，而在于多个 Feature 尽量复用同一套 Plugin 生命周期、Session 记录、Model Surface 生成和 Capability 接口，不必各自在 AgentLoop 中建立一套规则。
{: .section-lead}

第一，主要能力使用统一 Composition vocabulary。Tool、Prompt、Session、LLM、Compaction、Subagent 和 AgentLoop 都通过 Service、Event 与 Effect 接入。它们的业务语义不同，但依赖如何等待、注册如何撤销、作用范围如何选择，可以使用同一种机制表达。

第二，可替换能力遵守明确的依赖方向。Consumer 依赖 Service Definition，Composition 选择 Provider；Filesystem、Subprocess、Persistence、Compaction 与 Subagent 都可以用 Definition / Provider / Consumer 检查完整性。依赖注入让运行时找到实现，依赖倒置让 Consumer 不被某个实现锁死。

第三，Session Event Log 是 durable interaction history。恢复、Fork、UI、Telemetry 和模型 Messages 都从这份记录派生。已经发生的事实与 live Agent Object 分开以后，进程内对象可以释放，历史仍保持一致。

第四，Execution History 与 Model Surface 分离。Compaction 可以保留原始事件，只替换模型以后看到的 Projection；Plan 可以记录状态并改变 Prompt；Skills、Tools 和 Code SDK 都作为当前请求的一部分单独组装。

第五，模型侧影响进入 Package Contract。What the model sees、Token Effect 和 KV Cache Effect 不再只是 Prompt 作者的隐性知识，而需要在 model-facing package 中被说明和校验。

| 需要评审的内容 | DSH 中对应的检查 |
|---|---|
| Plugin 加入和退出 | 依赖、Registration、Disposer、Scope |
| 事实是否需要恢复 | 是否成为 SessionEvent |
| 模型实际看到什么 | Request Header、Prompt Assembly、Projection |
| 能力怎样替换 | Definition、Provider、Consumer 是否完整 |
| 长期任务由谁拥有 | Session、Activation、Parent Authority、Cleanup |

这些统一规则不能自动保证实现正确。它们的价值是让问题有稳定归属：新行为应该写到哪里，哪些测试必须覆盖，失败或卸载时由谁清理。框架名字本身仍不能替代并发、崩溃和权限测试。

反过来看，DSH 的 distinct 之处也不是“Cordis 比所有框架都强”。Dependency Injection、Event Log、Middleware 和 Scoped Registry 都有其他实现方式。这里值得研究的是它把这些机制用于同一组 Harness 边界，并要求 Tool、Prompt、Session 与 Subagent 在一套所有权规则下协作。

<details class="source-note" markdown="1">
<summary>源码依据：Architecture 怎样为不同变化指定归属</summary>

**Architecture 文档结论：**需要持久化的事实进入 Session Event；Live Coordination 使用 Agent Event；Policy 与 Adapter 进入 Capability Event 或 Service；可替换实现要形成 Definition、Provider、Consumer；单 Agent 注册使用 Agent scope。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
durable fact            → SessionEvent
live request/turn rule  → agent/* event
tool policy             → tools/* pipeline
swappable implementation→ capability seam
one-agent contribution  → scoped registration
cross-session facility  → Host service
```

[DeepSeek Harness Architecture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md){: data-source-evidence=""}

[Capability seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#capability-seams){: data-source-evidence=""}
</details>

### 5.4 这套设计的代价和当前边界 {#section-5-4}

DSH 没有消除复杂度，而是把它从一个中心控制器分解到作用范围、Service 归属、Event Schema、Projection、Generation、Authority 和 Cleanup 中。这有利于替换和局部测试，也提高了理解与实现成本。
{: .section-lead}

| 获得的能力 | 同时承担的成本 |
|---|---|
| Host 与 Agent-side Composition 分开 | 要判断 Service 的真实消费者与所有者 |
| Scoped Registration | 要理解 Parent Chain、Shadow 与 Registration Leakage |
| Reversible Plugin Lifecycle | 每项副作用都必须有可靠 Disposer |
| Event-sourced Session | 要维护 Event Schema、兼容性与 Crash Semantics |
| Model Surface Projection | 要证明 Replace、Tool Pairing 与 Header Reconstruction 正确 |
| Preset Generation | 新旧 Generation 可能同时常驻，需要回收策略 |
| Continuable Subagent | 要维护 Parent Authority、Activation 与 child-first disposal |

Preset Generation 是一个具体例子。文件变化后，新 Session 使用新 generation，已有 Session 保持原定义，这保证历史语义稳定；但 superseded generation 当前不会主动回收，重复编辑会增加 live watcher 和 Plugin subtree。要安全回收，需要知道最后一个 joined Agent 何时离开。

Agent 生命周期还有类似问题。当前设计记录指出 Host 某些路径会长期保留访问过的 live Agent；对象本身可以在 dispose 后回收，但缺少 idle eviction 时，进程内成本随曾经运行的 Session 增长。Durable Session 能恢复，不代表 live Agent 应永久常驻。

远程执行的限制也必须留在正文。当前 E2B 是 ephemeral POC，没有完整 reconnect、workspace sync 和 durable remote handles；AgentLoop 与 LLM 并没有整体运行在远端。Code worker thread 提供资源限制，却不是 hard multi-tenant boundary。Cloud deployment 仍需要 Container、Credential、Filesystem 与 Network Isolation。

最后，Event Sourcing 和 Projection 也有长期维护成本。新增 model-visible state 必须能从 Log 重建；Persistence Backend 要同步写入新的 durable field；遇到无法解释的 required Event 应 fail loud。任何一处遗漏都会让“类型上存在”与“重启后仍存在”产生差异。

所以这套设计是否值得，取决于产品是否真的需要多 Session、不同 Agent Composition、恢复、长期 Subagent、动态工具和远程执行。若只有单会话与固定 Tool，一个清楚的小 Loop 仍可能是更合适的实现。

<details class="source-note" markdown="1">
<summary>源码依据：Preset Generation 与远程执行有哪些已知限制</summary>

**当前 README 与设计记录结论：**运行中 Session 继续绑定原 Generation，Superseded Generation 尚不回收；Agent idle eviction 仍是 TODO。E2B 明确保留 ephemeral、reconnect 与 synchronization 限制；Code worker thread 不是多租户安全边界。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
onPresetFileChanged(nextGeneration) {
  generationForNewSessions = nextGeneration
  // existing sessions remain on their current generation
}

knownLimits = {
  generationReclamation: false,
  idleAgentEviction: false,
  e2bReconnect: false,
  e2bWorkspaceSync: false,
  workerThreadIsSecurityBoundary: false,
}
```

[Agent Presets README：Known limitations ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#known-limitations-and-deferred-work){: data-source-evidence=""}

[Portable Execution World：Consequences ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/architecture/2026-07-28-portable-execution-world-consumers.md#consequences){: data-source-evidence=""}
</details>

### 5.5 从 AgentLoop 到 Agent Runtime {#section-5-5}

现在可以回到标题中的 Runtime：它不是 Composition 的同义词，也不是 AgentLoop 的新名字。AgentLoop 是整体 Composition 中的一个 Plugin；Composition 说明组件怎样组织；Runtime 是这些组件生效后，连同具体 Session、Agent 和执行资源一起运行的整个系统。
{: .section-lead}

三者可以这样区分：

| 名称 | 它回答的问题 |
|---|---|
| AgentLoop | 一次 Turn 按什么顺序执行，何时继续或停止 |
| Composition | 安装哪些 Plugin，它们如何依赖、注册和退出 |
| Agent Runtime | 这些组件运行以后，系统怎样管理身份、历史、模型请求、工具、长期任务和资源 |

```text
Agent Runtime
├── 已经生效的 Composition
│   ├── Host Composition
│   │   └── AgentLoop 也是其中一个 Plugin
│   └── Agent-side Composition / Preset Contributions
├── Durable Session State
├── Live Agent / Inbox / Cancellation
├── Model Request Assembly
├── Tool Execution and Authority
├── Subagent Session / Activation Ownership
└── Filesystem / Process Execution World
```

所以 Runtime 不是 Composition。没有 Composition，DSH 不知道组件怎样进入系统；只有 Composition 文件，也还没有正在运行的 Agent、已经追加的 SessionEvent、执行中的 Tool Call 或需要清理的 Activation。更准确的关系是：DSH 用 Composition 组织 Runtime 的组件，Runtime 再承担这些组件运行时产生的身份、状态和资源。

同样，AgentLoop 虽然位于整体 Composition 内，也不能因此说 Runtime 等于 AgentLoop 加几个 Plugin。Runtime 还包括不在 Plugin 配置中静态列出的具体实体：某个 Session 的 Event Log、当前 Inbox 中的消息、一次正在等待 Approval 的 Tool Call、一个可被 cold resume 的 Child Session，以及 Provider 此刻持有的文件与进程资源。

这场分享最终留下五个边界：

1. 能力不仅要问“有没有”，还要问对谁有效、何时加载和撤销。
2. Durable Facts 不等于 Live Execution；Session 可以保留，Agent Object 可以重建。
3. Execution History 不等于 Model Surface；Compaction 因此可以保留历史而缩短请求。
4. Capability 不等于 Model Presentation；Code Mode 因此可以改变接口而复用底层 Tools。
5. Runtime 必须明确 Ownership；Session、Subagent、Process、Sandbox、Effect 和 Context 都要知道谁负责取消、恢复与释放。

> **A Harness starts as a Loop. At what point does it become a Runtime?**
{: .final-question}

答案不是代码达到多少行。当系统不得不同时管理多个身份、可恢复历史、不同 Agent 的能力、模型输入、长期执行与资源所有权时，仅用 Loop 已经无法准确描述它。DSH 的尝试，是让这些问题分别进入 Composition、Session、Projection 和 Capability，而不是继续扩张 AgentLoop。

<details class="source-note" markdown="1">
<summary>源码依据：继续阅读 DSH 的建议顺序</summary>

**阅读依据：**Architecture 先给出 Plugin Tree、Turn Flow、Session Log 与 Capability Seam 的总关系；随后按 Session、Model Surface、Compaction、Tools、Subagent 与 Preset 进入具体实现，比从 Cordis 类型或 Package 目录开始更容易保持层次。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
docs/architecture.md
  → docs/subsystems/session.md
  → docs/subsystems/system-prompt.md
  → docs/subsystems/compaction.md
  → docs/tool-execution-pipeline.md
  → docs/subsystems/subagent.md
  → packages/preset/agent-presets/README.md
  → apps/cli/config/agent-presets/*/agent.cordis.yml
```

[DeepSeek Harness Architecture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md){: data-source-evidence=""}

[Subsystem documentation ↗](https://github.com/deepseek-ai/deepseek-harness/tree/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems){: data-source-evidence=""}
</details>
