---
layout: dsh_runtime_wiki
title: "DeepSeek Harness：从 Agent Loop 到 Composable Agent Runtime"
public: true
description: "从 AgentLoop 和多 Session 出发，分析 DeepSeek Harness 如何分配能力、记录会话、组织模型输入、执行工具并管理长期任务。"
lead: "AgentLoop 只描述执行怎样向前推进；DSH 还要决定每个 Session 使用哪些 Prompt 和 Tools、模型看见什么，以及运行事实如何进入 Session Log。"
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

| Part | 建议时长 | 讨论内容 |
|---|---:|---|
| Part 1 · Overview | 6 min | 跨 Session 的 Preset 场景与一条完整 Session 时序 |
| Part 2 · Everything Is a Plugin | 15 min | AgentLoop 与其他能力如何被组合到一起 |
| Part 3 · Core Designs | 20 min | Session、模型输入、压缩、工具与长期任务 |
| Part 4 · Four Agent Presets | 8 min | Standard、Code、Minimal、Cordis 分别改变了什么 |
| Part 5 · Conclusion | 7 min | 用五个问题回收前文，并回答 Loop 何时变成 Runtime |

<!-- talk-route: Part 1 | 6 min | full: 1.1→1.2 | short: 1.1→1.2 -->
## Part 1｜Overview：AgentLoop 之外还要管理什么 {#part-introduction}

后面的场景和时序会用到八个名字：

| 名词 | 在 Overview 中具体指什么 |
|---|---|
| `Host` | 当前正在运行的 DSH 进程。它可以同时管理多个 Agent 与 Session，并持有它们共同使用的基础能力。 |
| `Agent` | 当前进程里真正执行工作的对象。它从 Inbox 取输入，启动 Turn，并负责取消和当前运行状态；同一个 Session 以后可以重新创建新的 Agent 来继续。 |
| `Inbox` | Agent 还没有处理的输入队列。用户消息、Follow-up 和注入的上下文先进入这里；被 AgentLoop 领取并通过 `agent/pre-step` 后，最终内容才写进 Session Log。 |
| `Session` | 一段会话的身份和按顺序追加的事件记录。当前没有 Agent 在运行时，这段记录仍然可以保存，之后再加载继续。 |
| `SessionEvent` | Session Log 中已经追加的一条记录，例如 `turn/start`、用户消息、模型消息、Tool Call 或 Tool Result。它记录已经发生的事情，不是等待执行的命令。 |
| `AgentLoop` | 推进一次执行的组件：领取 Inbox 输入，建立 Turn 和 Step，发起模型请求，把模型返回的 Tool Calls 交给 Tool Runtime，并判断是否还要继续下一 Step。 |
| `Turn` | 从 `turn/start` 到 `turn/end` 的一次完整处理；可以包含零个、一个或多个 Step。 |
| `Step` | 一次模型请求，以及这次响应所触发的全部 Tool Executions。 |
{: .overview-glossary}

### 1.1 两个 Session，为什么会拿到不同的能力 {#section-1-1}

同一个 DSH 进程里，Session A 在 repo-A 中使用 Standard，Session B 在 repo-B 中使用 Minimal。它们由同一种 AgentLoop 推进，但使用的 Prompt、Tools、Workspace 和 Session Log 都不相同。
{: .section-lead}

| | Session A | Session B |
|---|---|---|
| Workspace | repo-A | repo-B |
| Agent Preset | Standard | Minimal |
| 主要模型能力 | 文件工具、Skills、Plan、Compaction、Subagent 等 | Persistent Bash 与 Editor |
| 会话记录 | Session Log A | Session Log B |
{: .session-scenario}

Agent Preset 是创建 Session 时选择的一组 Agent 组件。Standard 和 Minimal 的具体差异留到 Part 4；这里需要看到的只是：两个 Session 即使运行在同一个 DSH 进程里，也可以得到不同的模型输入和工具集合。

AgentLoop 分别推进两个 Agent 各自的 Turn 与 Step，却不负责单独决定 A 为什么看到这些 Tools、B 为什么看到另一些 Tools，也不能把两边的 Workspace 与历史混在一起。这个问题才是 Part 2 要讨论的组件组织。下一节先选择 Session A，看一次 Turn 如何真正流转。

<details class="source-note" markdown="1">
<summary>源码依据：Workspace 与 Preset 为什么是 Session 自己的选择</summary>

**Session 与 Preset 源码结论：**Session Header 分别记录 `cwd` 与 `agentPreset`；Preset id 必须持久保存，因为它决定这个 Session 的 Prompt 与 Tools。Standard 和 Minimal 的配置文件则列出两套不同的 model-facing 组件。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
export interface SessionHeader {
  // version、id、createdAt 等字段省略

  // 这个 Session 创建时使用的工作目录
  readonly cwd?: string

  // parentSession、seedLength、origin、delegationDepth 等字段省略

  // 这个 Session 的 Agent 使用哪一套 Preset
  readonly agentPreset?: string
}
```

[packages/core/session/src/types.ts：SessionHeader ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/session/src/types.ts#L62-L99){: data-source-evidence=""}

[Standard Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}

[Minimal Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/minimal/agent.cordis.yml){: data-source-evidence=""}
</details>

### 1.2 一个 Session 从创建到 Turn 结束 {#section-1-2}

创建 Session A 时，DSH 先准备 Session 和负责执行它的 Agent。在 Agent 对外可用以前，创建流程会确认当前 Standard 版本的运行实例已经挂载，并把这个 Agent 关联到它；如果它已经存在，本次创建只建立关联，不会再安装一遍同样的 Plugin。
{: .section-lead}

图中的“Agent 创建流程”只是对这段创建代码的统称，不是另一种需要长期存在的运行对象。源码把创建接口命名为 `AgentFactory`：`ctx.agents` 接收创建请求，再交给 AgentLoop 提供的 Factory 准备 Session、执行 setup，最后发布 Agent。

Preset 中的一个 Plugin 可能依赖另一个 Plugin 在运行时注册的 Service。例如文件工具需要先取得 Filesystem 和 Tool Registry；依赖没有准备好时，它不会带着残缺能力开始运行。Plugin 第一次挂载时加入的 Prompt、Tool 或 Listener 才叫 Registration；后来使用同一 Preset 版本的 Session 只是读取这些已有 Registration，不会重复注册。依赖怎样声明、Registration 怎样在卸载时清理，留到 Part 2 再展开。

用户消息先进入 Inbox。AgentLoop 准备处理它时写入 `turn/start`，随后建立第一个 Step：读取当前 Agent 的 Prompt 与 Tool Schemas，从 Session Log 生成模型历史，然后请求模型。图中的 Step 1 产生 Tool Calls，工具结果写回 Session，因此还需要 Step 2；Step 2 得到最终回答，随后写入 `step/end` 与 `turn/end`。

源码把“从 Session Log 生成模型历史”这个动作命名为 `Session.deriveMessages()`。它只读取当前对模型可见的事件，把 `user/message`、`assistant/message` 和 `tool/result` 转成模型 API 需要的 `Message[]`；它不会调用模型、不会追加 SessionEvent，也不会修改原始日志。

这张图把两段过程放在同一条时间线上：上半段是 Agent 创建、确认 Preset 运行实例并建立关联，下半段是一个包含两个 Step 的 Turn。虚线写入 Session Log 的是可以在以后重新读取的 SessionEvent；Preset 关联、模型请求和 Tool Runtime 调用不是 SessionEvent，它们各自遵守运行时生命周期。

{% include dsh/diagram.html number="1" title="一个 Session 从关联 Preset 到 Turn 结束" src="/assets/wiki/deepseek-harness/diagrams/13-session-composition-turn.html" description="展开 Session 创建、Preset 运行实例关联以及两个 Step 的完整时序" note="查看共享 Registration、Session Log、Turn 与 Step 如何连接" %}

Overview 到这里结束。Part 2 再解释这些组件怎样取得依赖、加入调用过程，并在卸载时清理自己的 Registration。

<details class="source-note" markdown="1">
<summary>源码依据：Agent 创建、消息派生与 Turn flow</summary>

**Core、Preset、Session 与 Architecture 文档结论：**AgentFactory 在发布 Agent 前准备 Session 并执行 setup；Preset setup 确保 standing generation 已挂载并关联 Agent；`deriveMessages()` 从日志生成模型 Messages。进入 Turn 后，每个 Step 读取当前注册、请求模型、调度 Tool Calls，并把模型可见事实写回 Session Log。
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

[docs/subsystems/core.md：AgentFactory ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/core.md#ctxagents--agentregistry){: data-source-evidence=""}

[docs/subsystems/session.md：deriveMessages() ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md#derived-history-derivemessages-and-deriveeventmessage){: data-source-evidence=""}

[docs/cordis-primer.md：Cordis in five ideas ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-in-five-ideas){: data-source-evidence=""}

[docs/architecture.md：Turn flow ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#turn-flow){: data-source-evidence=""}

[packages/core/agent-loop/src/agent.ts：turn() ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent-loop/src/agent.ts#L245-L329){: data-source-evidence=""}
</details>

<details markdown="1">
<summary>后续 Docs 与源码阅读入口</summary>

下面的入口按问题整理，不需要先从 Package 目录猜实现位置。

| 想查什么 | 文档入口 | 主要内容 |
|---|---|---|
| DSH 全局结构 | [Architecture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md) | Plugin tree、Turn flow、Session Log、Capability Seam，以及新行为应该进入哪里 |
| Cordis 的基本概念 | [Cordis Primer ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md) · [Services Tutorial ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-tutorial/03-services.md) | Context、Service、`inject`、Effect、Event、Waterfall，以及依赖变化时的 Plugin 生命周期 |
| Preset 怎样跨 Session 工作 | [Agent Presets README ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md) | standing mount、scope parent、generation、blank-session recompose 与 child composition |
| Session 与事件日志 | [Session ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md) | SessionEvent vocabulary、模型历史派生和 Turn/Step 边界 |
| Prompt 与模型输入组装 | [System Prompt ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/system-prompt.md) | Prompt Sections、Prompt Context、Tool providers 与 assembly |
| Tool 注册与执行 | [Tools ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/tools.md) · [Execution Pipeline ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/tool-execution-pipeline.md) | Tool Definition、scoped schemas、Approval、hooks 与结果收尾 |
| Shell Capability Seam | [Shell Family ↗](https://github.com/deepseek-ai/deepseek-harness/tree/47f943859bef60e4160492346772ded9b24f765a/packages/shell) · [Shell Subsystem ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/shell.md) | `ctx.shell` Definition、Local/Sandbox Provider、`tool-bash` Consumer 与 Request/Spec 语义 |
| 可替换能力怎样设计 | [Capability Seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/capability-seams.md) | Definition、Provider、Consumer 及其依赖图 |
| 添加新的 Plugin 或 Tool | [Adding a Package ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cookbook/adding-a-package.md) · [Adding a Tool ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cookbook/adding-a-tool.md) | 新 Package 的 Service/Event/Effect 接入，以及 model-facing Tool 的完整路径 |
| 添加新的模型 Adapter | [Adding an LLM Adapter ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cookbook/adding-an-llm-adapter.md) | Provider 注册、stream contract 与模型请求适配 |
| 长期子任务 | [Subagent ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/subagent.md) | Child Session、Activation、Follow-up、Interrupt 与 Resume |
| 历史如何缩短为模型输入 | [Compaction ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/compaction.md) | Compaction Events、Surface replacement 与恢复路径 |

</details>

<!-- talk-route: Part 2 | 15 min | full: 2.1→2.2→2.3→2.4→2.5 | short: 2.1→2.4→2.5 -->
## Part 2｜Everything Is a Plugin：DSH 如何组织这些能力 {#part-composition}

Part 1 看到同一个 DSH 可以为两个 Session 提供不同的 Prompt 与 Tools。Part 2 先分清 TypeScript 声明、Service Definition、运行时 Service 和 Registry 条目，再沿 Shell 这一个例子看依赖、注册、卸载、Provider 替换和声明式组合。

### 2.1 一个 Plugin 挂载时，运行时真正新增了什么 {#section-2-1}

配置选择并挂载的是 Plugin。`Context` 中的 Service 类型声明，以及 `ToolRuntime` 等实现类，在挂载前就已经存在；对于 `ToolRuntime` 这类 Class Provider，只有 Plugin 被构造并执行 `super(ctx, name)` 后，当前 Context 才出现对应的运行时 Service 实例。普通 Plugin 也可以不注册 Service，只向已有 Registry 加入 Registration。
{: .section-lead}

以 `ctx.tools` 为例，四个动作发生在不同阶段：

| 阶段 | 实际发生的事 | 是否改变运行时 |
|---|---|---|
| TypeScript declaration merging | `Context` 接口声明 `tools: ToolRuntime`，让 `ctx.tools` 通过类型检查 | 否；TypeScript 声明不会在运行时注册任何东西 |
| 实现类源码 | `ToolRuntime extends Service` 定义 Tool Registry 的方法和行为 | 否；这里只是可被加载的代码 |
| Provider Plugin 挂载 | Loader 构造 `ToolRuntime`，构造函数调用 `super(ctx, 'tools')` | 是；Cordis 内部通过 `ctx.reflect.provide(...)` 注册这个实例 |
| Consumer Plugin 挂载 | `tool-bash` 调用 `ctx.tools.register(...)` | 是；现有 Tool Registry 多了一条 `bash` Registration |

所以 Service Definition、运行时 Service 实例和 Registry 条目是三个层次。`ToolRuntime` 的类与类型一直在源码中；挂载以后，当前 Context 才能解析到这一个 `ToolRuntime` 实例；再挂载 `tool-bash`，这个实例内部才多出 `bash` Tool。

后文使用四个运行时术语：

| 名称 | 它是什么 | DSH 中的例子 |
|---|---|---|
| `Plugin` | Cordis 安装和卸载的生命周期单元 | `dsh-tools`、`dsh-tool-bash`、`dsh-agent-loop` |
| `Service` | 已注册在当前 Context 中、可通过 `ctx.<name>` 解析的具名能力实例 | `ctx.tools`、`ctx.shell`、`ctx.sessions`、`ctx.agentLoop` |
| `Registry` | 一类负责保存多项 Registration 的 Service；并非所有 Service 都是 Registry | `ctx.tools` 保存 Tool Definition；`ctx.llm` 保存 Adapter |
| `Registration` | 某个 Plugin 插入 Service/Registry 的一条可撤销记录 | `tool-bash` 加入 `bash` Tool 和 `tool:bash` Prompt Section |

这里的 Service 不是单独部署的网络服务，Registry 也不是另一套外部数据库；它们都是当前 DSH 进程中的对象，只是职责不同。

源码目录看不出“哪些文件夹是 Plugin”，因为 Plugin 不是目录类型，而是 Package 入口遵守的挂载协议。DSH 仍按 `shell`、`llm`、`session`、`preset` 等业务领域组织目录。打开一个 Package 的 `src/index.ts`，通常从下面三种形态判断：

| 入口形态 | 源码标志 | 例子 |
|---|---|---|
| Class Plugin | `default export` 一个可构造的 `Service` 子类 | `AgentLoop`、`ToolRuntime`、`LocalBashExecutor` |
| Namespace / function-style Plugin | 命名导出 `name`、`inject`、`Config`、`apply`，没有 `default export` | `tool-bash`、Persona |
| Object Plugin | 导出一个包含 `apply` 的对象 | Cordis 支持的第三种较少见形态 |

不是每个 Package 都是准备给 Composition 直接挂载的。`dsh-shell` 主要提供抽象 `ShellExecutor` Definition，shipped 配置实际挂载的是 Local/Sandbox 等具体 Provider 子类；纯类型、算法和工具函数包也只会被其他 Package import。Architecture 所说的 “Everything Is a Plugin”，指产品中的可替换运行组件共同服从 Plugin 生命周期，不是说仓库里的每个目录都叫 Plugin。

要看某个产品实际挂载了哪些 Plugin，最直接的入口不是扫描目录，而是查看 Profile 的 `--dump-config` 输出或 Preset 的 `agent.cordis.yml`；每个启用的 row 都会给 Loader 一个需要 import 和挂载的 Package。

Tool Registry 可以具体理解为当前 Context 中已经注册的 `ctx.tools` 实例。它的实现类型是 `ToolRuntime`，负责保存当前可见的 Tool Definitions、向模型组装 Tool Schemas，并让 Tool Call 进入统一执行管线。`ToolRuntime` 类在挂载前就存在；`bash`、`read` 等具体工具则是运行时插入这个 Registry 的 Registration。

AgentLoop 声明的五项 `inject` 也都能找到明确提供者：

| `ctx` key | 运行时由哪个 Provider Plugin 注册 | 它负责什么 |
|---|---|---|
| `ctx.agents` | `AgentRegistry` / `dsh-agent` | 保存 live Agent，并提供统一的 `create()` / `resume()` 入口 |
| `ctx.sessions` | `SessionStore` / `dsh-session` | 创建和保存当前进程中的 Session 对象 |
| `ctx.llm` | `LlmRuntime` / `dsh-llm` | 保存模型 Adapter Registration，并提供流式模型调用入口 |
| `ctx.tools` | `ToolRuntime` / `dsh-tools` | 保存 Tool Registration、组装 Schema、执行 Tool Call |
| `ctx.systemPrompt` | `SystemPrompt` / `dsh-system-prompt` | 保存 Prompt Section、Context 和 Tool Schema Provider，并组装模型请求的 Prompt 部分 |

`LlmRuntime` 与 `SystemPrompt` 的类和 `Context` 类型声明在源码中早已存在；`ctx.llm` 和 `ctx.systemPrompt` 的运行时实例都由对应的 Service Provider Plugin 注册。随后 DeepSeek、Pi 等 Adapter Plugin 向 `ctx.llm` 插入 Adapter Registration，Persona、Tool 等 Plugin 再向 `ctx.systemPrompt` 插入 Section 或 Tool Provider Registration。

Agent Factory 则是另一种关系。`AgentRegistry` 暴露 `ctx.agents.create()` 和 `resume()`，但它不固定 Agent 怎样构造；`AgentLoop` 实现 `AgentFactory` 接口，并通过 `ctx.agents.setFactory(this)` 成为当前创建实现：

```text
Host / Client
  → ctx.agents.create(options)
  → AgentRegistry 查找当前 AgentFactory
  → AgentLoop 创建 Session 与 Agent、执行 setup、最后发布
```

这符合工厂模式的核心目的：使用方只调用稳定的创建接口，不需要 `new ReactLoopAgent(...)`，也不依赖具体 AgentLoop 包。更精确地说，它是一个接口式 Factory/Delegate；这里没有必要把它说成负责创建一整族相关对象的 Abstract Factory。

Shell 例子中的关系是：

```text
dsh-tools Plugin
  └── 挂载时注册 ctx.tools：ToolRuntime / Tool Registry 实例

dsh-bash-sandbox Plugin
  └── 挂载时注册 ctx.shell：ShellExecutor 实例

dsh-tool-bash Plugin
  ├── 使用 ctx.tools、ctx.shell、ctx.systemPrompt
  ├── 向 ctx.tools 注册 bash Tool
  └── 向 ctx.systemPrompt 注册 Bash Prompt Section
```

Composition 也不是 `Plugin + Service + Registration` 三张平级清单。配置先描述 Plugin rows 与父子关系；Loader 挂载这些 Plugin 后，部分 Plugin 注册运行时 Service 实例，另一些 Plugin 再插入 Tool、Prompt、Listener 等 Registration。本文把这棵已挂载的 Plugin 图及其运行时连接关系称为 Composition。TypeScript 声明不会由 Composition 创建；Agent、Inbox、SessionEvent 和正在运行的进程则是 Runtime 中的对象或状态。

同一个运行时对象可以承担两项角色。`AgentLoop` 由 Cordis 以 Class Plugin 形式挂载；构造函数中的 `super(ctx, 'agentLoop')` 又把这个实例注册为 `ctx.agentLoop` Service。随后执行的 `ctx.agents.setFactory(this)` 是另一项 Registration：把同一个实例登记成 `ctx.agents.create/resume` 的委托实现。`ToolRuntime` 同理；`tool-bash` 则只作为 Consumer Plugin 运行，不注册新的 Service 实例。

“AgentLoop 也是 Plugin”不表示它没有核心职责。它仍然从 Inbox 认领输入、写入 Turn/Step 边界、组装请求、调用模型并判断是否继续；只是 Plan、Compaction、权限与 Subagent 不必把全部规则硬编码进 AgentLoop。

<details class="source-note" markdown="1">
<summary>源码依据：同一个对象怎样同时是 Plugin 和 Service Provider</summary>

**Cordis、AgentLoop、ToolRuntime 与 tool-bash 源码结论：**`declare module` 只扩展 TypeScript 的 `Context` 类型；Service 子类实例只有在构造函数调用 `super(ctx, name)` 后才注册到当前 Context。AgentLoop 另外向 AgentRegistry 登记 AgentFactory，普通 Plugin 也可以只向既有 Registry 插入 Registration。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
// 编译期：只让 TypeScript 认识 ctx.tools，不产生运行时代码
declare module '@deepseek-ai/cordis' {
  interface Context { tools: ToolRuntime }
}

// 运行时：Loader 挂载 Class Plugin
mount(ToolRuntime)
  → new ToolRuntime(ctx)
  → super(ctx, 'tools')
  → ctx.reflect.provide(...) registers toolRuntimeInstance as "tools"

// 另一项运行时贡献：Consumer Plugin 插入 Registry 条目
mount(toolBash)
  → ctx.tools.register(bashDefinition)
```

[packages/core/agent-loop/src/index.ts：AgentLoop Service 与 Factory Registration ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent-loop/src/index.ts#L295-L351){: data-source-evidence=""}

[packages/core/tools/src/index.ts：ToolRuntime Service ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/tools/src/index.ts#L783-L832){: data-source-evidence=""}

[vendor/cordis/src/service.ts：Service constructor ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/service.ts){: data-source-evidence=""}

[packages/core/agent/src/index.ts：AgentRegistry / AgentFactory / setFactory ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/agent/src/index.ts#L175-L387){: data-source-evidence=""}

[packages/llm/llm/src/index.ts：LlmRuntime Service ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/llm/llm/src/index.ts#L280-L338){: data-source-evidence=""}

[packages/core/system-prompt/src/index.ts：SystemPrompt Service ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/system-prompt/src/index.ts#L337-L390){: data-source-evidence=""}

[packages/shell/tool-bash/src/index.ts：Registration ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/shell/tool-bash/src/index.ts#L190-L242){: data-source-evidence=""}

[vendor/cordis/src/registry.ts：Plugin shapes ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/registry.ts#L215-L319){: data-source-evidence=""}

[Cordis Services Tutorial：compile time vs runtime ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-tutorial/03-services.md#provide-a-service){: data-source-evidence=""}

[docs/architecture.md：Where new behavior goes ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#where-new-behavior-goes){: data-source-evidence=""}
</details>

### 2.2 tool-bash 从 ctx 里拿到了什么 {#section-2-2}

Cordis 执行 `tool-bash.apply(ctx)` 时传入的 `ctx`，是这次 Plugin 挂载所处的 Context。它既用于解析运行时 Service，也让后续 Effect 归属于当前 Fiber；Registry 再从这个 Context 取得 Registration 应写入的 DSH Scope layer。它不是一个装满所有全局单例的普通对象。
{: .section-lead}

实现上 `ctx` 是 Proxy。读取 `ctx.shell` 时，Cordis 才沿当前 Context 的 Service 解析关系寻找名为 `shell` 的实例；`isolate` group 可以让相同 Service 名在不同 Context 中指向不同 Provider 实例。这是 Cordis 的 Service isolation。

`ctx.tools` 的情况还多一层：Standard 中的 `tool-bash` 解析到 Host 上同一个 ToolRuntime 实例，但 `ctx.tools.register()` 会根据调用 Context 的 DSH ScopeKey，把 `bash` Definition 写进 Standard Preset 的 Registry layer。以后某个 Agent 通过 `agent → preset → global` 链读取 Tool。Service 实例的解析与 Registry 条目的可见范围因此不是同一件事。

Plugin 与运行时 Service 的区别可以直接从这里看：`tool-bash` 是 Cordis 管理其加载和卸载的生命周期单元；`ctx.shell`、`ctx.tools` 则是 Provider Plugin 挂载后注册到 Context 的实例。`tool-bash` 自己不注册新 Service，而是消费四个已经存在的实例：

```ts
export const inject = ['tools', 'shell', 'systemPrompt', 'shellEnv']
```

| 必需 Service | `tool-bash` 中的调用 | 为什么需要它 |
|---|---|---|
| `ctx.tools` | `ctx.tools.register(...)` | `tool-bash` 解析 Host 的 ToolRuntime/Tool Registry 实例，再把 `bash` 写入当前 Preset 的 Registry layer。没有它，模型不会得到可调用的 `bash` Tool。 |
| `ctx.systemPrompt` | `ctx.systemPrompt.section(...)` | 注册一段跨调用的固定指导：每次查看 Bash 结果都要检查 exit code。Tool Schema 说明单次参数，Prompt Section 提供持续行为规则，两者用途不同。 |
| `ctx.shell` | `ctx.shell.resolve()`、`run()`、`start()` | 真正解析并执行命令。当前对象可能是 Local Provider，也可能是 Sandbox Provider；`tool-bash` 不直接启动进程。 |
| `ctx.shellEnv` | `ctx.shellEnv.collect(exec)` | 为这一次命令生成可信的 `DSH_*` 环境快照，例如 `DSH_HOME`、`DSH_SHELL=1`、当前 `DSH_SESSION_ID`，以及可用时的 `DSH_SESSION_JSONL`。 |

`shell` 与 `shellEnv` 因此不是一回事：`shell` 决定“命令怎样执行”，`shellEnv` 决定“这次命令应收到哪些 DSH 管理的环境信息”。`shellEnv` 不运行命令，也不直接修改宿主进程的 `process.env`；它只是为每次 Tool Call 生成一个显式 overlay，再交给 `ctx.shell`。

`dsh-shell` 也不是当前正在工作的 Shell 实例。它是 Service Definition Package，导出抽象 `ShellExecutor`、Request/Spec/Result 类型和共同语义。实际挂载的 `bash-local` 或 `bash-sandbox` 才构造具体子类，并通过 `super(ctx, 'shell')` 把这个实例注册为当前 Scope 可解析的 `ctx.shell`。

所以 Context、Service 与 `inject` 的关系是：Provider Plugin 先在某个 Context 中注册运行时 Service 实例；Consumer Plugin 用 `inject` 声明必需的 Service 名；Cordis 等四项依赖都可解析以后才运行 `tool-bash.apply(ctx)`。任何必需 Service 消失时，这次 `tool-bash` Fiber 会卸载；依赖恢复后再重新运行。

在 Cordis 底层，依赖尚未满足的 Fiber 处于 `pending`，不会执行一半的 `apply()`。但 DSH 的正式 Profile Boot 和 Agent Preset mount 会审计仍未激活的配置 row，并把缺失依赖变成带 Plugin 名称的启动错误；不能把 `pending` 理解成产品永远静默忽略错误。

`tool-bash` 还会通过 `ctx.get()` 查询 Jobs、Approval 或 Sandbox Policy。这些是可选或条件依赖：没有 Jobs 时前台 Bash 仍可用，后台调用会明确失败；Approval 只在提权路径需要；Sandbox Policy 只在当前 `ctx.shell` 宣告自己提供隔离时成为必需，缺失会让 `tool-bash` 在加载阶段响亮失败。`inject` 表达无条件依赖，`ctx.get()` 则允许 Plugin 根据当前能力决定某条路径是否成立。

<details class="source-note" markdown="1">
<summary>源码依据：tool-bash 的四项必需 Service 分别在哪里使用</summary>

**Cordis、tool-bash、Shell 与 ShellEnv 源码结论：**TypeScript 声明只负责类型检查。Cordis Context/`isolate` 选择运行时 Service 实例，ToolRuntime 与 SystemPrompt 再用 DSH ScopeKey 决定 Registration layer；`tool-bash` 最后通过 `ctx.shell` 执行命令，并由 `ctx.shellEnv` 生成每次调用的 `DSH_*` snapshot。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
export const inject = ['tools', 'shell', 'systemPrompt', 'shellEnv']

export function apply(ctx: Context): void {
  ctx.systemPrompt.section({ name: 'tool:bash', /* ... */ })

  ctx.tools.register(defineTool({
    name: 'bash',
    async execute(args, exec) {
      const dshEnv = ctx.shellEnv.collect(exec)
      const spec = ctx.shell.resolve({ command: args.command, dshEnv })
      return ctx.shell.run(spec)
    },
  }))
}
```

[packages/shell/tool-bash/src/index.ts：四项调用 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/shell/tool-bash/src/index.ts#L30-L390){: data-source-evidence=""}

[packages/shell/shell/src/index.ts：ShellExecutor Definition ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/shell/shell/src/index.ts#L65-L100){: data-source-evidence=""}

[packages/shell/shell-env/src/index.ts：ShellEnvRegistry ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/shell/shell-env/src/index.ts#L1-L190){: data-source-evidence=""}

[vendor/cordis/src/reflect.ts：Context Service resolution ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/reflect.ts#L135-L163){: data-source-evidence=""}

[Cordis Tutorial：Dependencies are tracked after load ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-tutorial/03-services.md#dependencies-are-tracked-after-load){: data-source-evidence=""}

[Agent Presets README：What a mount rejects ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#what-a-mount-rejects){: data-source-evidence=""}
</details>

### 2.3 tool-bash 从挂载到退出发生了什么 {#section-2-3}

`tool-bash` 不是每次 Tool Call 来了才临时加载。Loader 在配置 row 启用且四项依赖准备好以后挂载它，运行一次 `apply()`；由此注册的 Bash Prompt 和 `bash` Tool 会持续服务后续请求，直到这次挂载结束。
{: .section-lead}

源码给这条生命周期用了三个容易混淆的名字：

| 名称 | 准确含义 |
|---|---|
| `Fiber` | 某个 Plugin 的一次挂载记录和控制句柄。它保存本次挂载的配置、依赖状态和待清理项；不是线程、协程，也不是 Agent。 |
| `Effect` | 由 Fiber 跟踪的一项安装动作。它执行 setup，对外增加 Registration 或资源，并把相应清理方法交给 Fiber。 |
| `Disposer` | Effect 返回的清理函数，通常是 `() => void` 或异步函数。例如从 Tool Registry 删除 `bash`。 |
| `unload / dispose` | 结束这一次 Plugin 挂载并执行所有 Disposer。它不会删除磁盘上的 Package，也不表示 Node 立即卸载模块代码。 |

这里的 Effect 可以理解为“由 Cordis 跟踪、能够撤销的副作用”。Plugin 不需要先写一份 Effect 清单；调用 `ctx.on()`、`ctx.tools.register()`、`ctx.systemPrompt.section()` 或 `ctx.effect()` 时，当前 Fiber 就会记录对应清理动作。只创建外部资源却没有返回 Disposer，才会留下 Cordis 无法自动回收的副作用。

Fiber 的主要状态变化可以直接写成：

```text
pending（等待依赖）
  → loading（执行 apply / 构造 Service）
  → active（Registration 正在生效）
  → unloading（执行 Disposer）
  → disposed（这次挂载结束）

loading 期间抛错 → failed
```

Effect 的最小结构是：

**忠实伪代码（非仓库原文）：**

```ts
ctx.effect(() => {
  registry.add('bash')      // setup：对外增加内容
  return () => {
    registry.delete('bash') // disposer：撤销这次增加
  }
})
```

Tool、Prompt、Listener 等框架 Registration 已经通过 Helper 接入 Effect。Plugin 自己创建的 Timer、文件 Watcher、Socket 或其他外部资源，则需要显式放进 `ctx.effect()`：setup 创建资源，Disposer 关闭资源。否则 Plugin 即使退出，回调或连接仍可能继续存活。

`tool-bash` 没有直接写这段模板，因为 `ctx.systemPrompt.section()` 和 `ctx.tools.register()` 已经把 Registration 封装成 Effect。挂载与退出的真实顺序是：

```text
Loader 挂载 tool-bash
  → 创建这次挂载的 Fiber
  → 执行 apply(ctx)
  → 注册 tool:bash Prompt Section
  → 注册 bash Tool
  → Fiber 进入 active，可处理很多次 Tool Call

Fiber 开始 unload
  → 先开始撤销后注册的 bash Tool
  → 再开始撤销 Prompt Section
  → Fiber 进入 disposed
```

Cordis 会按注册的相反顺序开始调用 Disposer，但多个异步 Disposer 的完成顺序没有串行保证：Fiber 会等待它们全部结束，却可能让不同 Effect 的异步清理重叠运行。真正有先后依赖的清理步骤必须放进同一个 `ctx.effect()` 返回的 Disposer，由这一个函数自己按顺序 `await`。`tool-bash` 的 Tool 与 Prompt Registration 都使用框架 Helper，不需要另外保存清理句柄。

一次挂载通常在下面几类情况退出：

| 触发条件 | 会发生什么 |
|---|---|
| 代码显式调用 `await fiber.dispose()` | 立即结束这次挂载并等待清理完成 |
| 父 Plugin、根 Context 或整个应用关闭 | 子 Fiber 随父级一起清理 |
| 普通 Loader Composition 删除、禁用或热替换这一 row | 原 Fiber 退出；候选配置可再建立新 Fiber |
| `inject` 中的必需 Service 消失或被替换 | 依赖该 Service 的 Fiber 退出；依赖恢复后重新挂载 |

它不会因为一次 Bash 调用结束、一个 Step/Turn 结束或 Agent 进入 idle 就自动卸载。Agent Preset 还有更具体的规则：当前 standing generation 会跨多个 Session 存活；文件更新只让之后的 Session 使用新 generation，旧 generation 当前不会主动回收。因此 Standard 中的 `tool-bash` 也不是“关掉一个 Session 就卸载一次”。

卸载只撤销这次 Plugin 安装的 Registration，不会撤销已经执行过的命令，也不会删除已经写入的 SessionEvent。后台进程等资源由 Subprocess 或 Jobs 的所有者单独清理；Effect 不能替代每个子系统自己的资源所有权。

Effect 回答“这项 Registration 存在多久”；Waterfall 回答“一次调用怎样经过多层处理”，两者也不能混在一起。Waterfall Listener 收到当前参数和 `next()`：调用 `next()` 才把控制权交给下一层，不调用就用自己的 Decision 结束这条链。模型调用 `bash` 时，已经存在的 Registration 被 Tool Runtime 找到，然后调用经过：

```text
tools/pre-execute
  → tools/execute
  → tool-bash execute()
  → ctx.shell.resolve() + ctx.shell.run()
  → tools/post-execute
```

Scope 与 Effect 分别回答两个问题：Scope 决定谁能看见 Registration，Effect 决定它存在到什么时候。Cordis 管理这两类关系，但不负责决定模型下一步做什么；AgentLoop 仍负责推进 Turn 与 Step，Session 记录已经发生的事实，Persistence 再负责把这些 Event 落盘。

<details class="source-note" markdown="1">
<summary>源码依据：Fiber、Effect 和 Disposer 如何清理 bash Registration</summary>

**Cordis、Tool 与 System Prompt 源码结论：**Fiber 是一次 Plugin application 的生命周期实例；Effect 收集 Disposer。Fiber unload 时按逆序开始清理并等待全部任务，但不同 Effect 的异步 Disposer 可以并发；`tools.register()` 与 `systemPrompt.section()` 都会随所属 Fiber 撤销。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
type Disposer = () => void | Promise<void>

class Fiber {
  state: 'pending' | 'loading' | 'active' | 'unloading' | 'disposed'
  effects: Disposer[]

  async dispose() {
    this.state = 'unloading'
    const cleanupTasks = this.effects.reverse().map(dispose => run(dispose))
    await Promise.all(cleanupTasks)
    this.state = 'disposed'
  }
}

function registerTool(definition): Disposer {
  return currentFiber.effect(() => {
    toolLayer.insert(definition.name, definition)
    return () => toolLayer.remove(definition.name)
  })
}
```

[vendor/cordis/src/fiber.ts：Fiber / Effect / Disposable ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/cordis/src/fiber.ts){: data-source-evidence=""}

[packages/core/system-prompt/src/index.ts：section() ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/system-prompt/src/index.ts#L373-L390){: data-source-evidence=""}

[packages/core/tools/src/index.ts：register() ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/tools/src/index.ts#L1031-L1061){: data-source-evidence=""}

[packages/core/tools/tests/scoped.spec.ts：dispose removes registrations ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/core/tools/tests/scoped.spec.ts#L109-L116){: data-source-evidence=""}

[Agent Presets README：generation lifetime ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#known-limitations-and-deferred-work){: data-source-evidence=""}
</details>

### 2.4 依赖倒置怎样形成 Capability Seam {#section-2-4}

Shell 这项能力被拆成三个角色：`dsh-shell` 定义 `ctx.shell`，`bash-local` 或 `bash-sandbox` 提供实现，`tool-bash` 把它变成模型可见的 Tool。三者合在一起，才形成完整的 Capability Seam。
{: .section-lead}

| 角色 | 当前实现中的例子 | 负责什么 |
|---|---|---|
| Service Definition | `dsh-shell` / `ShellExecutor` | `resolve/run/start`、Request/Result 类型和失败语义 |
| Service Provider | `bash-local`、`bash-sandbox` | 命令究竟怎样启动、是否经过 Sandbox、怎样收集输出 |
| Consumer | `tool-bash` | 模型看到的 Tool Schema、Prompt 指引、参数校验和结果呈现 |

依赖倒置说的是源码依赖方向。`tool-bash` 依赖 `ShellExecutor` 的接口与类型，不依赖 `LocalBashExecutor`；Provider 也实现同一份 Definition。只有 Composition 需要知道当前选择了哪个具体 Provider。

```text
tool-bash
   │ 只调用 ctx.shell
   ▼
ShellExecutor Definition
   ▲
   ├── LocalBashExecutor
   └── SandboxBashExecutor
```

Definition 不只是为了让 TypeScript 编译通过，它还决定跨实现必须一致的语义。例如 `run()` 只有在进程根本无法启动等基础设施故障时 reject；非零退出码、Timeout 和被 Signal 终止都返回带完整事实的 `ShellRunResult`。Provider 可以更换，但不能各自发明一套结果含义。

`bash-sandbox` 也没有复制 `tool-bash`。它继承 Local Provider 的进程机制，只在启动前通过 `ctx.sandbox` 包装 argv，并通过 `sandboxMode` 告诉 Consumer 当前支持隔离。`tool-bash` 据此决定是否向模型显示 `sandbox_permissions` 和 `justification`，但仍然不导入 Sandbox Provider。

Shell 下面还有一条 Subprocess Seam。`bash-local` 自己不调用 Node `child_process`，而是注入 `ctx.subprocess`。把 `subprocess-local` 换成 `subprocess-e2b` 后，`tool-bash` 和 `bash-local` 都不需要改，命令已经在远端执行。为了让 Read、Search、LSP 和 Bash 看到同一批文件，Filesystem Provider 也要一起换成 E2B，这两项 Provider 共同组成 Execution World。

这里仍要保留实现边界：当前 E2B 是 ephemeral POC。被替换的是 Filesystem 与 Subprocess Provider；Harness 进程、Cordis 对象、模型调用、Agent/Session 状态、Persistence、Skills 和更高层协议状态仍留在 Host。它没有完整 reconnect、workspace synchronization 或 durable remote handle，因此不能据此声称整个 Harness 已经迁移到远端。

<details class="source-note" markdown="1">
<summary>源码依据：Local 与 Sandbox Provider 怎样复用同一 Shell Definition</summary>

**Shell Provider 源码结论：**`LocalBashExecutor` 实现 `ShellExecutor` 并把进程创建交给 `ctx.subprocess`；`SandboxBashExecutor` 继承同一实现，在启动边界增加 `ctx.sandbox`。两者都发布为 `ctx.shell`，Consumer 不变。
{: .evidence-summary}

**源码批注版（中文注释为后加）：**

```ts
export class LocalBashExecutor extends ShellExecutor {
  // Local Provider 仍然依赖更底层的 Subprocess Seam
  static inject = ['subprocess']

  async run(spec: ShellExecSpec): Promise<ShellRunResult> {
    return this.runArgv(spec, ['bash', '-c', spec.command])
  }

  protected async runArgv(spec: ShellExecSpec, argv: readonly string[]): Promise<ShellRunResult> {
    using d = deadline(spec.signal, spec.timeoutMs, 'BASH_TIMEOUT')
    // 实际进程由当前 ctx.subprocess Provider 创建
    const handle = this.ctx.subprocess.spawn(this.spawnSpec(spec, argv, spec.stdoutMaxBytes, d.signal))
    // ...收集结果
  }
}

export class SandboxBashExecutor extends LocalBashExecutor {
  static override inject = ['subprocess', 'sandbox', 'sandboxPolicy']

  private confine(command: string, policy: SandboxPolicy): ConfinedArgv {
    // Sandbox Provider 只改变启动 argv，复用其余 Local 机制
    return this.ctx.sandbox.confine(['bash', '-c', command], policy)
  }
}
```

[packages/shell/bash-local/src/index.ts ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/shell/bash-local/src/index.ts#L95-L257){: data-source-evidence=""}

[packages/shell/bash-sandbox/src/index.ts ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/shell/bash-sandbox/src/index.ts#L37-L179){: data-source-evidence=""}

[docs/subsystems/shell.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/shell.md){: data-source-evidence=""}

[docs/architecture.md：Capability seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#capability-seams){: data-source-evidence=""}

[packages/e2b/README.md：POC boundary ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/e2b/README.md){: data-source-evidence=""}
</details>

### 2.5 声明式 Composition 怎样连接 Host 与 Agent {#section-2-5}

Base Bundle 在 Host 侧声明 `subprocess-local`、Sandbox Policy 和 `bash-sandbox`；Standard Preset 在 Agent 侧声明 `tool-bash`。Loader 挂载这些行以后，`inject` 把 Consumer 与当前 `ctx.shell` Provider 连接起来，一条完整 Shell 能力才真正存在。
{: .section-lead}

这部分更准确的说法是“声明式组合”，而不是整个系统都采用声明式编程：YAML 声明希望存在的 Plugin、配置和启用条件，Loader 根据依赖图决定何时挂载；Plugin 的 `apply()` 内部仍然使用普通 TypeScript，命令式地注册 Prompt、Tool 与 Listener。

| 名称 | 它处在哪个阶段 | Shell 例子 |
|---|---|---|
| `Bundle` | Host 配置的分发单位：一组 Cordis rows 及其代码，由 Profile 选择和叠加 | Base Bundle 提供 Subprocess、Sandbox、Shell Provider rows |
| `Agent Preset` | Agent 侧的配置输入：一个包含 `agent.cordis.yml` 的目录 | Standard Preset 提供 `tool-bash` row |
| `Composition` | 上述输入被解析并挂载后形成的 Plugin 图，以及随之注册的运行时 Service 实例与 Registry 条目 | `ctx.shell` Provider 实例、`ctx.tools` Registry 实例和 `bash` Registration 已经连通 |
| `Runtime` | Composition 正在运行时，再加上具体 Agent、Session、Inbox、进程和其他状态 | 某个 Session 真正发起并执行 Bash Tool Call |

因此 Bundle 和 Agent Preset 都是 Composition 的输入来源，不是 Composition 本身；Composition 又只是 Runtime 的组件结构，不包含某个 Session 此刻正在执行的具体状态。

| Host Composition 持有 | Standard Preset 贡献或选择 |
|---|---|
| Subprocess、Sandbox、`ctx.shell` Provider | `tool-bash` / `tool-pwsh` Consumer |
| AgentLoop、Agent/Session Registry、Persistence | Persona 与 Prompt Sections |
| Tool、System Prompt、Skill 等 Registry | 向该 Preset 注册的 Tools 与 Skill roots |
| Sandbox、Approval、Credentials、Model Route | 是否向模型提供 Plan、Compaction 与 Delegation |
| Subagent Registry 与具体 Providers | model-facing Subagent Tools 与 Workflow |

Host plane 与 Agent plane 是职责划分，不是两台机器或两个进程。Shell Provider 要同时服务多个 Session，也被 Host 侧配置和执行策略管理，所以留在 Host；`tool-bash` 决定模型是否获得 Bash Tool，因而由 Preset 贡献。同样，Subagent Registry 留在 Host，而 Standard 只选择是否提供 model-facing delegation Tools。

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

这是 `dsh-agent-presets` 明确选择的生命周期：Plugin、Listener、Watcher 和 Registration 按 generation 建立，而不是按 Session 建立。相应代价是共享 Plugin 必须把 Session 状态放进 Session Log、按 identity 建索引，或者使用明确的 per-agent structure，不能只用一个实例字段保存“当前 Session”。

事件监听也沿相同 Parent Chain 过滤。Standing Preset 中注册的 scoped listener 会收到加入这一 Preset 的 Agent Event，却不会接收 Sibling Preset 的 Agent Event。Host 在没有 live Agent 时读取 cold transcript，也可以根据 durable PresetId 取得对应 standing key，用同一套 Prompt 与 Presentation Registration 解释历史。

{% include dsh/diagram.html number="2" title="Host、Preset 与 Agent 的真实关系" src="/assets/wiki/deepseek-harness/diagrams/14-host-preset-agent.html" description="展开 Host 共享能力、Preset standing composition 与两个独立 Session" note="重点查看挂载一次、父级查找和会话数据分离" %}

Preset 文件变化时，下一次新建 Session 可以进入新的 generation；已经运行的 Session 继续绑定原来的 generation。这样不会在一段已有历史中途突然改变 Tool Schema 或 Prompt。代价是旧 generation 仍要存活，直到整个 tree 被释放；当前实现也把 generation 回收列为未完成问题。

<details class="source-note" markdown="1">
<summary>源码依据：Shell Provider 与 Consumer 怎样由两份配置组成</summary>

**Base Bundle、Standard 与 Preset README 结论：**Host 配置声明 Subprocess、Sandbox 和 Shell Provider；Standard 只声明 model-facing Shell Consumer。一个 Standard generation 挂载一次，多个 Agent 通过 parent binding 使用这些 Registration，Session 状态仍按 identity 分开。
{: .evidence-summary}

Base Bundle 中的 Host rows：

**配置摘录：**

```yaml
- id: subprocess
  name: '@deepseek-ai/dsh-subprocess-local'

- id: sandbox
  name: '@deepseek-ai/dsh-sandbox-local'

- id: sandbox-policy
  name: '@deepseek-ai/dsh-sandbox-policy'
  config:
    mode: !!js process.env.DSH_PERMISSION_MODE ?? 'workspace-write'
    workspaceRoot: !!js process.cwd()

- id: bash-sandbox
  name: '@deepseek-ai/dsh-bash-sandbox'
  disabled: !!js process.platform === 'win32'
  config:
    timeoutMs: 60000
```

Standard Preset 中的 Agent row：

**配置摘录：**

```yaml
- id: tool-bash
  name: '@deepseek-ai/dsh-tool-bash'
  disabled: !!js process.platform === 'win32'
```

[Base Bundle Shell rows ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/bundle/base/cordis.patch.yml#L163-L182){: data-source-evidence=""}

[Standard Preset 的 Host / Agent 注释 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}

[Agent Presets README：standing mount ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}
</details>

<!-- talk-route: Part 3 | 20 min | full: 3.1→3.2→3.3→3.4→3.5 | short: 3.1→3.3→3.4→3.5 -->
## Part 3｜Core Designs：会话、模型输入、工具和长期任务 {#part-core-designs}

Composition 解释一个 Agent 拿到哪些组件。接下来沿一次真实执行继续向下：Session 保存什么，模型每次请求收到什么，历史过长后怎样压缩，工具如何执行，以及一次 Turn 不够时任务怎样继续。

### 3.1 Session 如何记录执行过程并支持恢复 {#section-3-1}

DSH 把 Session 定义为按顺序追加、带类型的 SessionEvent log。它记录一段 Agent interaction 中已经发生的事实；模型消息、网页展示和恢复判断都从这份记录重新生成，而不是各自维护另一份历史。
{: .section-lead}

这种组织通常称为 Event Sourcing：系统保存发生过的 Event，再从 Event 计算当前需要的视图。DSH 并不是完全不使用 Messages；它不把 Messages 维护成第二份独立历史，而是在请求模型时通过 `deriveMessages()` 从 Session Log 生成。

Agent 负责当前执行，Session 记录已经发生的事实。Agent 拥有 Inbox、Cancellation 与当前 Status；Session 拥有可重放的 Event Log。释放 Agent 不等于清空 Session Log，但 Event 能否跨进程恢复，还取决于 Persistence 是否完成落盘。Part 2 讨论 Plugin 安装在哪里，这一节讨论运行数据能否跨过进程生命周期，两者不是同一项分类。

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

| 内容 | 与 Persistence 的关系 | 恢复时怎样处理 |
|---|---|---|
| SessionEvent Log | 内存中的唯一事实来源；Persistence 异步复制并按批次落盘 | 从已持久化 Event 重建 Session |
| 模型 Messages | 不单独保存 | `deriveMessages()` 从 Event 重新生成 |
| UI Conversation | 不作为第二真源 | 从同一 Log Projection 得到 |
| live Agent / Inbox / Cancellation | 不持久化为当前执行对象 | 需要时重新创建 |
| Subagent Activation | 不持久化 | 根据 durable child Session 冷恢复 |

Persistence 是独立接口，可以接 JSONL 或 SQLite。Cold Session 从存储加载时，如果日志尾部仍有未闭合 Turn，恢复逻辑会保留已经持久化的中间事件；必要时先为悬空 Tool Call 写入错误结果、关闭未结束的 Step，最后追加 synthetic interrupted `turn/end`。它不会截掉整个 Turn。这个修复只适用于 cold load，仍在内存中执行的 live Session 不会被擅自补结束事件。遇到当前版本无法忠实解释的格式版本或必需 Event 时，DSH 选择明确拒绝；受支持的 legacy 迁移则由专门逻辑处理，不能把两者统称为“旧格式一律失败”。

持久化还有一个时间边界：`session.append()` 先提交内存中的事实并同步发出 `session/event`，Persistence Plugin 再把 Event 放进按 Session 管理的批次。`session/flush` 会取消等待并排空已有批次；调用方如果要在 `whenIdle()` 后立即读取存储，仍要显式等待 Flush。Turn 结束本身不会自动证明 Backend 已完成 durable write。

<details class="source-note" markdown="1">
<summary>源码依据：SessionEvent 如何成为唯一历史来源</summary>

**Session 与 Persistence 文档结论：**Session 是 append-only typed Event log；LLM history 通过 `deriveMessages()` 生成。Persistence 负责 Flush、恢复和 Header；开放 Turn 恢复为 interrupted，无法忠实读取的格式明确失败。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
const events = await persistence.loadCold(sessionId)

if (hasOpenTurn(events)) {
  // 保留已持久化 Event；按需补齐悬空 Tool、Step，再关闭 Turn
  appendMissingToolErrors(events)
  closeOpenStepIfNeeded(events)
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

Plan Mode 是一个更具体的例子。`plan/mode` 作为 Session Event 保存，当前状态由 Log fold 得到；启用后加入 `plan:policy` Prompt Section。`exit_plan_mode` 始终留在 Tool Catalog 中，因此状态切换不会改变 Tool Schemas；变化的是 Plan Policy Section，已提交的切换还可能在对话尾部追加一条 user-role notice。这样既能恢复协作状态，也把“Prompt 变化”和“Tool Catalog 是否变化”分开记录。

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

{% include dsh/diagram.html number="3" title="完整历史如何变成较短的 Messages" src="/assets/wiki/deepseek-harness/diagrams/15-history-to-model-surface.html" description="展开原始 Event、log-only summary、replacement message 与最终 Messages" note="观察历史保留与模型可见对话缩短如何同时成立" %}

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

[docs/subsystems/session.md：SurfaceOp ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md){: data-source-evidence=""}
</details>

### 3.4 一项 Tool Call 如何真正执行 {#section-3-4}

模型看见 Tool Schema 以后，并不是直接调用对应函数。DSH 先把 Tool Call 写入 Session，再经过可见定义解析、参数校验、扩展 Policy、Approval、Guard 和执行 Waterfall，最后把规范化结果写回 Session。Sandbox 只由需要它的 Tool/Provider 在实际执行点使用。
{: .section-lead}

一个 `ToolDefinition` 由 model-facing `ToolSchema`、必需的 canonical `output` 声明、`execute` 函数，以及可选的调度、Finalizer 和 UI Presentation 字段组成。真正发给模型的 `ToolSchema[]` 通过显式 allowlist 生成；`output`、`execute`、`finalizeContent`、`timeoutMs`、`isConcurrencySafe`、`presentCall` 和 `presentResult` 都不会进入模型请求。

```text
assistant Tool Call
  ↓
session tool/call
  ↓
resolve visible executable definition
  ↓
tools/pre-execute
  ↓
approval decision + monotonic guards
  ↓
tools/execute waterfall → tool body
  └─ Shell / FS 等相关 Tool 在自己的执行点解析并强制 Sandbox Policy
  ↓
tools/post-execute → normalize / finalize
  ↓
session tool/result
```

这条 Tool Execution Pipeline 是通用 Tool Policy 的共同入口。可见性过滤决定模型能否看见并命名一个 Tool；执行层仍会重新解析当前 Scope，并应用只能收紧、不能在后续阶段放宽的 Guard。Sandbox 不是每个 Tool 都必经的通用阶段：Shell 与 Filesystem 等能力在自己的 Consumer/Provider 边界解析并强制相应 Policy。Presentation、Visibility 和 Authority 因而是三件相关但不等价的事情。

工具的调度元数据可以决定多个 Call 能否并行。取消、参数解析失败、未知 Tool、Policy 拒绝和执行异常先由 ToolRuntime 的外层归一化转成可记录结果；如果当前 Call 已解析到有效 Definition，它的 `finalizeContent` 再对最终 model-facing content 执行一次同步约束。无论失败发生在哪一层，Session 都需要得到与原 `callId` 配对的终态，避免下一次 `deriveMessages()` 生成悬空 Tool Call。

Code Mode 改变的是模型组织工具调用的方式。Native 模式的一次响应可以包含一批 Tool Calls；这批结果写回以后，若任务仍要继续，就需要新的模型请求来决定下一批动作。Code 模式向模型提供 `run_code` 与生成的 SDK，让一段程序在一次 Runtime 执行中完成多次 subcall、并发读取、分支、筛选和聚合，再把整理后的结果返回模型。

{% include dsh/diagram.html number="4" title="Native Tools 与 Code Mode 的调用差异" src="/assets/wiki/deepseek-harness/diagrams/16-native-vs-code.html" description="比较模型逐次编排与 Runtime 内程序化编排" note="Code Mode 改变调用接口，但不绕过工具权限管线" %}

Code Mode 的 SDK subcall 仍通过同一个 Tool Runtime，受到相同的 Tool Restriction、Approval 和执行 Hook 约束。默认 worker-thread backend 每次使用 fresh worker，并限制 Heap、Output、Compute Timeout 和 Wall Timeout；这些是故障控制与资源限制，不是恶意代码的硬安全边界。

因此不能直接声称 Code Mode 一定更快或一定节省 Token。它减少模型与工具之间的往返时，也会引入 SDK Token、程序生成、Worker 启动和结果整理成本。可以确定的架构变化是：一部分原本由模型逐轮完成的 orchestration，被移动到 Runtime 中执行。

<details class="source-note" markdown="1">
<summary>源码依据：Code subcall 为什么仍经过统一工具管线</summary>

**Tools 与 Code Mode 文档结论：**Native 调用和 Code SDK subcall 最终都由 ToolRuntime 解析并执行；Nested subcall 可以访问当前 Agent 可见的底层工具，但仍经过限制、Approval 和 `tools/*` hooks。Sandbox enforcement 属于相关 Tool/Provider 的执行点；Worker thread 只提供 containment。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
async function dispatch(call, { nested }) {
  const tool = resolveExecution(call.name, agentScope, nested)
  const decision = await preExecuteWaterfall(tool, call)
  if (decision.kind === 'deny') return deniedResult(decision)
  if (decision.kind === 'ask') {
    const grant = await approval.resolve(decision)
    if (grant !== 'allowed-once') return deniedResult(decision)
  }
  await runMonotonicGuards(tool, call)
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

Subagent 不是 AgentLoop builtin。`ctx.subagents` 是 named Provider Registry；spawn-in-process、fork、ACP、Codex、Claude Code 和 DSH SDK 等实现可以共存。每个 `dsh-tool-subagent` 实例在配置中绑定一个 Provider 和一个模型可见 Tool 名称；模型选择的是当前可见的 delegation Tool，不是临时传入任意 Provider id。Control Tools 负责 follow-up、interrupt 和列表查询。这样“由谁执行 child”与“主 Agent 如何委派”可以分别扩展。

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

`includeRuntimeContext: false` 只影响模型侧动态上下文，不会删除 Host 的 Workspace、Session 或 Tool Runtime。Minimal 仍运行在同一 Host，Tool Call 仍经过统一管线，历史仍写入同一套 SessionEvent 机制。

但“工具更少”不能推出“权限更低”。Minimal 的 Editor 明确解析到 Preset 内的 bare `fs-local`，覆盖 Host 的 sandboxed Filesystem Provider；Persistent Bash 的 Terminal Backend 则继续消费 Host 的 Subprocess 与 Sandbox Policy。Minimal 缩小的是 Agent-side composition 与 Model Surface，不是统一收紧所有执行权限。它也没有改变整个进程的 `ctx.fs`：只有这个 Preset group 的 Consumer 解析到更近的实例。

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

Cordis Preset 在 Standard 能力上增加 Cordis Toolset、Composition Authoring Skill 和专门 Persona，使 Agent 能检查当前进程中的 Composition，定义临时 Dynamic Package，并控制它何时运行和停止。
{: .section-lead}

当前 Toolset 先用 `cordis_inspect` 读取状态，再用 `cordis_define`、`cordis_run`、`cordis_stop` 和 `cordis_undefine` 管理一份 Dynamic Package：

| Tool | 实际语义 |
|---|---|
| `cordis_inspect` | 读取当前进程中的 Service、Plugin Fiber、Tool 与本 Session 的 Dynamic Package |
| `cordis_define` | 保存 Host/Browser 两半代码并做语法检查，但不执行 |
| `cordis_run` | 运行已定义 Package：Host half 在受限 VM 中求值，Browser half 发送给打开的页面 |
| `cordis_stop` | 停止当前运行，等待 Host half 清理并撤回 Browser half；Definition 仍保留 |
| `cordis_undefine` | 必要时先停止，再删除这份内存 Definition |

```text
Cordis Preset
= Standard capabilities
+ Cordis inspection tools
+ cordis_define / run / stop / undefine
+ composition-authoring skill
+ dedicated persona
```

Dynamic Package 只存在于当前 DSH 进程内存。它可以跨后续 Turn 保持运行，注册的 Tool、Prompt 或 Listener 甚至可能影响同一进程中的其他 Session；但只有定义它的 Session 能查看和控制这份 Package。`cordis_stop`、`cordis_undefine`、Toolset 卸载或 DSH 重启都会结束这段生命周期。它不会自动创建 Plugin 文件，也不会自动写入 `agent.cordis.yml`。

Runner 为每次运行持有 Fiber。Dynamic Package 的 façade 不暴露任意 `ctx.effect()`；它允许的 `on`、`provide`、`tools.register` 等路径已经接入清理机制，`cordis_stop` 会 dispose 这次运行并等待清理完成。这里不需要让模型自己保存裸 Disposer，长期保存也不能依赖内存中的 Dynamic Package。

这并不表示 DSH 可以安全地让任意低信任输入修改自身。VM 只提供 containment，不是安全边界；Host-realm helper 仍可能让代码触达 Node 与已有 Service。仓库要求把这套 Toolset 按接近 Bash access 的权限处理。

Composition Authoring Skill 处理的是另一条持久路径：复制 shipped Preset 到 User Preset，再编辑用户目录中的文件。Dynamic Package 用于 live experiment，Preset 文件用于后续 Session 仍能使用的 Composition，两者不能混成同一种“挂载”。

Cordis Preset 的价值在于把 Composition 的表达力推到极端：Agent 不只使用一套组合，也可以参与编写组合。但是否允许这种能力，是 Trust Policy，而不是 Composition Framework 自动做出的决定。

<details class="source-note" markdown="1">
<summary>源码依据：Cordis Preset 能做什么以及信任边界</summary>

**Cordis 配置与 Toolset README 结论：**Preset 增加 `dsh-tool-cordis` 与本地 Composition Authoring Skill。当前 Toolset 使用 inspect/define/run/stop/undefine 生命周期；Dynamic Package 只存在于进程内存，由 Runner/Fiber 清理，VM 不是安全边界。
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

[tool-cordis README：Dynamic Package lifecycle ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/extensions/tool-cordis/README.md){: data-source-evidence=""}
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
| 信任边界 | 取决于 Host Sandbox / Approval | Worker 仅 containment，不是安全边界 | Model Surface 小，但 Persistent Shell 与 bare FS 仍需高信任 | Live Runtime 代码，接近 Shell access |

Standard 与 Code 的主要能力范围相近，但模型接口不同；Minimal 是独立定义的小 Composition，不是 Standard 在运行中的临时状态；Cordis 把 Composition Authoring 暴露给模型。Code Preset 通过独立的 `tool-presentation` row 选择 `code`，Plan Mode 又由 Session Event 单独切换，因此 Preset、Tool Presentation 和 Plan Mode 不能合并成一个“模式”概念。

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

<!-- talk-route: Part 5 | 7 min | full: 5.1→5.2→5.3→5.4→5.5 | short: 5.1→5.2→5.5 -->
## Part 5｜Conclusion：这套设计解决了什么，又付出了什么 {#part-comparison}

前四部分出现的机制，最终都在回答几个具体问题：一条消息为什么可能触发多次模型请求，历史为什么不能只存成 Messages，Shell 为什么能整体换到另一套执行环境，新规则怎样加入又怎样退出，以及什么时候只谈 AgentLoop 已经不够了。

### 5.1 一条用户消息一定只调用一次模型吗 {#section-5-1}

不一定。DSH 中与模型请求一一对应的是 Step，不是用户消息，也不是 Turn；一个 Turn 可以没有 Step，也可以连续执行多个 Step。
{: .section-lead}

第一批输入被 Agent 接收后，Loop 先写入 `turn/start`，再经过 `agent/pre-step`。如果这批输入被拒绝，或被改写为空，Turn 会直接以零个 Step 结束。只要进入 `step/start`，这一 Step 就包含一次模型请求，以及这次响应触发的全部 Tool Calls。

模型调用 Tool 后，结果会先以 `tool/result` 写入 Session。若这个结果还需要模型继续处理，Loop 不会新开一个 Turn，而是在同一 Turn 中进入下一个 Step。因此最常见的三种情况是：

| 实际发生的事 | Turn 中的 Step 数 |
|---|---:|
| 首批输入在进入 Step 前被拒绝或清空 | 0 |
| 模型直接给出最终回答 | 1 |
| 模型调用 Tool，读取结果后继续推理 | 2 个或更多 |

所以“用户发了一条消息”“系统执行了一轮工作”“模型发起了一次请求”是三个不同的计数单位。AgentLoop 负责把流程向前推进；真正发起模型请求、执行 Tool，以及在固定节点加入规则，分别通过对应的 Service 和 Event 完成。

<details class="source-note" markdown="1">
<summary>源码依据：Architecture 怎样定义 Turn 与 Step</summary>

**架构文档结论：**一个 Step 是一次模型请求及其 Tool Calls；一个 Turn 包含零个或多个 Step，从领取输入之前开始，到没有待处理工作时结束。
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

[docs/architecture.md：Turn flow ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#turn-flow){: data-source-evidence=""}
</details>

### 5.2 为什么 Session 不直接保存一份 Messages 数组 {#section-5-2}

因为 Messages 只表示模型在某次请求中看到的对话内容，无法完整表示 Turn、Step、原始流式输出、Tool Call、请求配置和 Compaction 等已经发生的事实。
{: .section-lead}

DSH 把一串只追加的、带类型的 `SessionEvent` 作为会话历史。`Session.deriveMessages()` 再从其中生成模型需要的 `Message[]`。这不是把同一份数据换个名字：许多 Event 只记录执行过程，并不会变成模型消息；`assistant/chunk` 用于回放和用量记录，进入模型历史的是组装完成后的 `assistant/message`。

这项区分也解释了 Compaction。压缩发生后，旧 Event 仍留在 Log 中；新的 `user/message` 通过 `surfaceOp.replace` 替换模型以后看到的一段内容。于是系统可以同时回答两个问题：

- 当时实际发生了什么：读取完整 Session Log。
- 下一次模型应该看到什么：读取当前 Model Surface，再生成 Messages。

`request/header` 还会记录最终 System Prompt、调用配置与 Tool Schemas。恢复时重新派生，而不是信任另一份可能已经与日志不一致的 Messages 数组。这里最重要的边界仍然是：Model-visible means logged。

<details class="source-note" markdown="1">
<summary>源码依据：Session Log 怎样派生 Messages 与 Compaction Surface</summary>

**Session 与 Compaction 文档结论：**SessionEvent Log 是交互历史的唯一事实来源；`deriveMessages()` 只投影会进入模型历史的 Event。Compaction 追加新的替换节点并遮蔽旧 Surface 节点，不删除原始 Event。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
SessionEvent log
  ├─ deriveMessages()      → Message[] for the model
  ├─ transcript projection → human-readable transcript
  └─ persistence           → durable replay

compaction
  ├─ append compaction/start | summary | end
  ├─ append user/message with surfaceOp.replace
  └─ keep the replaced events in the original log
```

[docs/subsystems/session.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md){: data-source-evidence=""}

[docs/subsystems/compaction.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/compaction.md){: data-source-evidence=""}
</details>

### 5.3 Bash 从本机换到远端，需要改多少代码 {#section-5-3}

`tool-bash` 不需要改成一份远程版本。它依赖的是 `ctx.shell` 的接口；Shell Executor 再通过 `ctx.subprocess` 启动进程。具体采用本地还是远端实现，由 Composition 选择 Provider。
{: .section-lead}

这就是依赖倒置真正带来的结果：Consumer 依赖 Service Definition，Provider 实现 Definition，只有负责组装系统的配置需要知道当前选中了哪个 Provider。Tool 的 Schema、输出呈现和工作目录语义仍由 `tool-bash` 负责，不会因为进程换了位置就复制一套。

不过只替换 Subprocess Provider 仍然不够。Bash 读取的文件、File Tool 读取的文件、LSP 打开的文件必须属于同一个 Workspace。因此移动到 E2B 时，`ctx.fs` 与 `ctx.subprocess` 的 Provider 要一起替换；Bash、PTY、LSP 与文件工具会沿各自接口进入同一个远端 Execution World。

这个例子证明的是 DSH 的抽象允许 Execution World 与 Host Runtime 解耦，不是已经完成了分布式 Agent Runtime。当前 E2B 仍是 ephemeral POC，没有 durable remote handle、完整 reconnect 或 workspace synchronization。

<details class="source-note" markdown="1">
<summary>源码依据：Provider Swap 怎样移动 Execution World</summary>

**Architecture 与 Portable Execution World 设计记录结论：**Filesystem 和 Subprocess Provider 共同定义执行世界；上层 Consumer 只依赖稳定 Service。远端组合替换这两个 Provider 后，Shell、PTY 与 LSP 不需要各自增加 E2B 分支。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
tool-bash ─────────────→ ctx.shell ─────→ ctx.subprocess
terminal / LSP ─────────────────────────→ ctx.subprocess
file tools ─────────────────────────────→ ctx.fs

local composition:  subprocess-local + fs-local
remote composition: subprocess-e2b   + fs-e2b
```

[docs/architecture.md：Capability seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#capability-seams){: data-source-evidence=""}

[Portable Execution World 设计记录 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/architecture/2026-07-28-portable-execution-world-consumers.md){: data-source-evidence=""}
</details>

### 5.4 不改 AgentLoop，新的规则怎样加入和退出 {#section-5-4}

DSH 不把权限、重试、Tool 和 Prompt 的规则全部写进 AgentLoop：Plugin 把它们注册到已有 Service 或 Event，卸载时再撤销自己创建的 Registration。
{: .section-lead}

不同需求进入不同位置，而不是都塞进 Loop：

| 需求 | 接入位置 |
|---|---|
| 新增模型可见 Tool | `ctx.tools.register()` |
| Tool 执行前的审批或 Policy | `tools/pre-execute` |
| 模型请求失败后的恢复 | `agent/request-error` |
| 修改请求或包装模型调用 | `agent/request` / `llm/stream` |
| 增加 System Prompt 内容 | `ctx.systemPrompt.section()` |

实现上，这些 Registration 会被当前 Fiber 记录为 Effect；Plugin 卸载时，对应的 Disposer 负责撤销注册或关闭资源。

一次 Tool Call 结束、一个 Step 或 Turn 结束、Agent 进入 idle，都不会让 Plugin 自动卸载。卸载发生在这次挂载被显式 dispose、父 Plugin Tree 关闭、Loader 热替换，或者它依赖的必需 Service 消失时。卸载只撤销这次挂载拥有的 Registration 和资源；已经写入 Session 的历史不会被删掉。

这也回答两个容易混在一起的问题。

第一，正常 Session 对话中 Tool 通常不会因为“这一轮用完了”而卸载。如果 Preset 文件在运行中被修改，已有 Session 继续留在原来的 standing generation，新 Session 才加入新 generation。DSH 这样做，是为了避免已经产生的 Tool Calls 突然面对另一套 Tool 定义。

第二，如果某种动态机制真的让一个新 Tool 进入当前 Agent 的有效 Tool Catalog，下一次请求中的 Tool Schemas 就会变化。依赖 exact-prefix 的 KV Cache 无法把变化前的整个请求前缀视为相同；这不等于 DSH 或 Provider 承诺某次请求必然命中或必然不命中缓存，只能确定请求前缀已经改变。Plan Mode 特意让 `exit_plan_mode` 在两种状态下都保持注册，就是为了切换 Mode 时不改变 Tool Catalog；Plan Policy Prompt 会变化，提交切换时还可能追加一条 user-role notice。

<details class="source-note" markdown="1">
<summary>源码依据：Plugin 何时清理 Registration，DSH 怎样控制 Tool Catalog 变化</summary>

**Lifecycle、Preset 与 Plan 文档结论：**Plugin 卸载会撤销其注册并递归清理子 Plugin；普通调用边界不会触发卸载。Preset Generation 对已运行 Agent 保持稳定，而 Plan Mode 通过常驻退出 Tool 避免 Mode 切换改变 Tool Catalog。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
Tool Call / Step / Turn ends
  → plugin remains ACTIVE

plugin unloads
  → run effect disposers
  → remove owned Tool / Prompt / Listener registrations

preset file changes
  → later sessions may join a new generation
  → existing sessions keep their current generation

effective Tool Schema changes
  → request prefix changes
```

[Plugin lifecycle：Automatic cleanup ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/user/develop/framework/index.md#automatic-cleanup){: data-source-evidence=""}

[Agent Presets README：Model Experience ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#model-experience){: data-source-evidence=""}

[docs/subsystems/plan.md：The exit tool ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/plan.md#the-exit-tool-and-the-plan-command){: data-source-evidence=""}
</details>

### 5.5 什么时候只谈 AgentLoop 已经不够了 {#section-5-5}

当系统除了推进一次 Turn，还要同时管理多种 Agent 定义、可恢复历史、模型输入、长期子任务和执行资源时，AgentLoop 仍然重要，但它只描述了 Runtime 的一部分。
{: .section-lead}

三者的边界可以直接写成：

| 名称 | 负责回答什么 |
|---|---|
| AgentLoop | 一个 Turn 怎样进入 Step、请求模型、把 Tool Calls 交给 Tool Runtime，并在没有待处理工作时结束 |
| Composition | 哪些 Plugin 被挂载，哪些运行时 Service 实例与 Registry 条目因此生效，以及它们跟随什么生命周期 |
| Agent Runtime | Composition 生效以后，具体 Agent、Session、Inbox、模型请求、Tool Call、Subagent 与执行资源怎样共同运行 |

因此 Runtime 不是 Composition。Composition 负责组织组件；Runtime 还包含这些组件运行后产生的身份、持久状态和活动资源。AgentLoop 也确实属于 Composition，但不能因此把整个 Runtime 缩成 AgentLoop：某个 Session 的 Event Log、Inbox 里尚未处理的输入、等待审批的 Tool Call、Subagent 的 Child Session 与 Activation，都不只是 Loop 内的一段控制流。

Standard、Code、Minimal 和 Cordis 也不是四个 AgentLoop。它们复用同一套 Host 能力和执行机制，但选择不同的 Plugin、Prompt、Tool Presentation 与信任范围。四个 Preset 说明了 Composition 可以改变 Agent 的能力和模型接口，而不用复制四套主循环。

这套设计没有让复杂度消失。它要求实现者继续处理 Scope、生命周期、Event Schema、Projection、Generation 和资源所有权；当前 superseded Preset Generation 还不会主动回收，E2B 尚无完整恢复语义，Code Runtime 的 worker thread 也不是 hard multi-tenant boundary。对于固定工具、单会话、无需恢复的程序，一个清楚的小 Loop 仍可能更合适。

整场分享可以收在五个边界上：

1. 一项能力不仅要问“有没有”，还要问谁能看到、什么时候撤销。
2. Durable facts ≠ Live execution：Session 可以保留，正在运行的 Agent 可以结束后重建。
3. Execution history ≠ Model Surface：Compaction 可以保留历史，同时改变下次请求看到的内容。
4. Capability ≠ Model Presentation：Code Preset 可以改变模型使用 Tool 的接口，同时复用底层执行管线。
5. Runtime 必须明确 Ownership：Session、Subagent、Process、Sandbox 和 Plugin Effect 都要知道谁负责取消、恢复与释放。

> **A Harness starts as a Loop. At what point does it become a Runtime?**
{: .final-question}

不是代码达到某个行数的时候，而是它开始同时承担能力组合、持久历史、模型输入、长期执行和资源所有权的时候。DSH 的核心选择，是让这些问题分别进入 Composition、Session、Model Surface 与 Capability Seam，而不是继续把所有规则写进 AgentLoop。

<details class="source-note" markdown="1">
<summary>源码依据：AgentLoop、Composition 与 Runtime 的边界来自哪里</summary>

**Architecture 与 Preset 文档结论：**Architecture 把 Turn Flow、Session Log、Capability Seam 和新行为的扩展位置分别定义；Preset 再决定某个 Agent 实际加入哪一份 model-facing Composition。Runtime 是这些机制与具体运行状态的总和，不是源码中的单独 Class。
{: .evidence-summary}

**关系整理（非仓库原文）：**

```text
AgentLoop
  └─ drives Turn / Step

Composition
  ├─ mounted Plugin graph
  ├─ registered Service instances
  └─ scoped Registrations + lifecycle

Agent Runtime
  ├─ effective Composition
  ├─ Agent / Inbox / cancellation
  ├─ durable SessionEvent log
  ├─ model request assembly
  ├─ Tool and Subagent execution
  └─ filesystem / process resources
```

[docs/architecture.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md){: data-source-evidence=""}

[Agent Presets README ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}
</details>
