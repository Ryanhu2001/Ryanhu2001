---
layout: dsh_runtime_wiki
title: "DeepSeek Harness：从 Agent Loop 到 Composable Agent Runtime"
public: true
description: "从多 Session、可恢复历史、模型请求和远程执行出发，分析 DeepSeek Harness 如何从 Agent Loop 发展为 Agent Runtime。"
lead: "从同一个后台同时运行多个 Session 开始，说明 DSH 如何组织 Agent、保存历史、构造模型请求，并管理远程执行和长期任务。"
duration: "技术分享讲稿 · 约 58 分钟正文 + Q&A"
source_revision: "47f943859bef60e4160492346772ded9b24f765a"
type: agent-harness
date: 2026-08-17
permalink: /wiki/DSH/
---

<!--
维护说明：
1. 本文件是正文唯一来源，最终 HTML 由 Jekyll 直接渲染，不要手改 _site。
2. ## 是五个 Part；### 是 25 个小节。保留显式 id，目录会自动生成。
3. 图通过 dsh/diagram.html include 声明。
4. 源码说明放在 <details class="source-note" markdown="1"> 中。
-->

最简单的 Harness 只有一个循环：把用户的话发给模型，执行模型要求的工具，再把工具结果交回模型。只做一个 Demo 时，这个理解完全够用。

但产品很快会多出第二个会话、第三个工作目录、不同的工具和提示词。会话要能关闭后恢复；子 Agent 要能继续工作；浏览器可以退出，但后台任务不能跟着消失；文件与命令还可能在远端沙箱中执行。此时难点已经不是循环本身，而是循环周围的那套管理系统。

这场分享关注的就是这部分：当一个 Harness 同时管理多个会话、工具、历史和执行环境时，这些内容分别由谁维护，怎样隔离，什么时候持久化，又怎样进入模型请求。沿着这些问题往下看，DSH 的组件组织、Session 记录和执行接口才会有具体含义。

| 章节 | 建议时长 | 要回答的问题 |
|---|---:|---|
| Part 1 · 为什么需要 Runtime | 8 min | 从三个会话和一次普通请求开始 |
| Part 2 · Agent 怎样组装 | 15 min | 谁看得到什么，东西何时出现和消失 |
| Part 3 · 五个核心设计 | 20 min | 历史、模型输入、长任务和工具执行 |
| Part 4 · 四个 Agent Preset | 8 min | Standard、Code、Minimal、Cordis 有何不同 |
| Part 5 · 比较与结论 | 7 min | 哪些设计值得学，代价是什么 |

所有实现判断都固定到页面顶部标出的 DSH 版本。每个小节末尾都保留了源码总结、短原文或伪代码；五张辅助图只用来展开少数不适合线性阅读的关系。

## Part 1｜为什么不能只用 AgentLoop 理解整个 Harness {#part-introduction}

先从三个实际问题开始：同一个后台怎样同时运行多个会话，会话关闭以后怎样继续，以及文件和命令怎样改到远端执行。

### 1.1 同一个 Host 中的三个 Session {#section-1-1}

这里的 Host 指真正运行 DSH 的后台程序，Session 指一段可以持久化和恢复的会话。一个 Host 可以同时运行多个 Session；它们共享 Host 级基础设施，但工作目录、可用工具、提示词和历史必须彼此隔离。
{: .section-lead}

直接看一个常见情况。A 在修改 repo-A，B 在分析 repo-B，C 只做一次轻量的文本编辑。A 需要完整的文件、终端和搜索工具；B 希望模型通过 Code Mode 批量调用工具；C 只需要两个简单工具。三个窗口虽然连到同一个后台进程，却不能互相看见对方的文件、工具或对话。

```text
                         DSH Host
                            │
             ┌──────────────┼──────────────┐
             │              │              │
         Session A      Session B      Session C
          repo-A         repo-B         repo-A
             │              │              │
       tools / skills   tools / skills   tools / skills
       MCP / standard   MCP / code       minimal
       history A        history B        history C
```

最容易出错的是“后来加进来的东西”。例如 repo-A 配了一个数据库 MCP 工具：它应当只出现在 A；把它改成用户级配置以后，新建的 B 是否能看到；MCP 再发来工具列表变化时，已经跑了几十轮的 A 是否立刻更新——这些都不能只靠一个全局工具数组决定。

| 需要隔离的东西 | A 的情况 | B 的情况 | 出错会怎样 |
|---|---|---|---|
| 工作目录 | repo-A | repo-B | 读错或改错仓库 |
| 可用工具 | 完整原生工具 | Code Mode 接口 | 模型调用了不该有的能力 |
| 对话历史 | history A | history B | 上下文串线 |
| 关闭与恢复 | 仍在运行 | 暂时关闭 | 关闭 B 时误删 A 的注册 |

因此，工具注册不能只回答“Host 里有没有”，还要回答“它对哪些会话有效”。Part 2 再回到源码，说明 DSH 怎样表达这种作用范围。

<details class="source-note" markdown="1">
<summary>源码依据：Preset 如何隔离不同 Agent</summary>

**文档结论：**Preset 只挂载一次；会话通过一条父级查找链加入它。最近一层覆盖更远一层，同级的另一个 Preset 不会收到这边的注册。
{: .evidence-summary}

```ts
// 来自 Preset README 的核心关系，改写为伪代码
effectiveValue(agent, key) = firstDefined(
  agent.scope[key],
  agent.preset.scope[key],
  global.scope[key]
)

// 文档原句中的查找顺序
agent → preset → global  // nearest shadowing farthest
```

[packages/preset/agent-presets/README.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}
</details>

### 1.2 Session 的身份不属于某个浏览器页面 {#section-1-2}

浏览器页面只持有会话标识，不拥有会话本身。页面关闭以后，Session 的身份和历史仍保存在 Host；下次继续时，Host 再根据这个标识找到正在运行的 Agent，或者从持久化记录恢复一个新的执行对象。
{: .section-lead}

如果把会话等同于页面里的 JavaScript 对象，刷新页面就会丢失身份，换一个客户端也无法接管，更谈不上进程重启后的恢复。DSH 因此让客户端只持有 `SessionId` 或 `AgentId` 这样的编号，真正的执行对象留在 Host。

```text
Browser / TUI / Client
         │
         │ 只传 AgentId / SessionId
         ▼
      DSH Host
         │
   查找正在运行的 Agent
         │
   已在运行，或从会话恢复
```

Host 收到请求后，先看这个会话是否已经有正在运行的 Agent。如果有就直接复用；如果只有保存下来的会话，就执行恢复；如果两个客户端同时要求恢复同一个会话，只做一次恢复并让两边等待同一个结果。

这样一来，Session 的标识和历史可以跨进程保留，Agent 则只在需要执行时存在。源码把“Session 还在，但对应 Agent 已不在内存，需要重新创建”的路径叫作 cold resume。

这并不代表 DSH 已经是完整的分布式系统。它只说明身份边界已经拆开：客户端负责“我要操作哪个会话”，Host 负责“这个会话此刻要不要恢复成一个 Agent”。

所以页面、Session 和 Agent 不是同一个对象：页面只是客户端，Session 保存身份与历史，Agent 负责当前这次执行。

<details class="source-note" markdown="1">
<summary>源码依据：Host 怎样根据 id 找回 Agent</summary>

**文档结论：**Remote API 传 id，不传 Host 对象；解析时优先复用 live Agent，普通冷会话可以自动恢复，并发恢复使用同一项进行中的工作。
{: .evidence-summary}

```ts
async function resolveAgent(sessionId) {
  if (agents.has(sessionId)) return agents.get(sessionId)
  if (!sessions.canResume(sessionId)) throw unknownSession
  return resumeSingleFlight(sessionId) // 同一个 id 只恢复一次
}
```

[docs/api-gateway.md：Host resolution ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/api-gateway.md#host-resolution){: data-source-evidence=""}

[packages/api/remotes/README.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/api/remotes/README.md){: data-source-evidence=""}
</details>

### 1.3 本地执行与远程执行如何共用上层工具 {#section-1-3}

只要读文件和运行命令都通过统一接口，上层的 Bash、PTY 和 LSP 就不需要区分文件究竟位于本机还是远端。替换这两个接口的实现，就可以把文件与进程一起切换到另一套执行环境。
{: .section-lead}

如果 Agent 要在 E2B 沙箱里改代码，可以分别实现一套 E2B 版 Bash、文件工具、PTY 和 LSP。DSH 没有在每个上层工具里重复这项适配，而是让它们统一使用“文件系统”和“子进程”两个接口；本地运行时接本地实现，远端运行时一起接到同一个沙箱。

```text
本地：ctx.fs + ctx.subprocess → 本机文件与进程
                               ↑
                  Bash / PTY / LSP / 文件工具
                               ↓
远端：ctx.fs + ctx.subprocess → 同一个 E2B Sandbox
```

这里有一个不能破坏的条件：文件系统和进程必须属于同一套执行环境。不能让文件工具写到远端，却让 Bash 在本地执行，否则 Bash 看不到刚写入的文件。PTY 和 LSP 也必须使用相同的路径与进程命名空间。

DSH 文档把这类可替换的接口称为 `Capability Seam`。这里对应的是 `ctx.fs` 和 `ctx.subprocess`。切换到 E2B 时，AgentLoop、Session、提示词和模型请求仍留在 Host，远端只负责文件和进程。本地实现、E2B 实现和上层工具的对应关系留到折叠区再展开。

**边界：当前 E2B 是 POC。**沙箱状态是临时的；没有断线重连、持久 remote handle、工作区同步或完整远程恢复。准确说法是“抽象允许 Execution World 与 Host 分开”，不是“DSH 已经实现完整分布式 Agent Runtime”。

<details class="source-note" markdown="1">
<summary>源码依据：本地与 E2B 共用哪些接口</summary>

**文档结论：**上层 consumer 只依赖 filesystem 与 subprocess；E2B 同时替换两者。设计文档也明确把当前实现标成 ephemeral POC。
{: .evidence-summary}

```ts
// 上层工具不判断 local / E2B
async function runCodingTool(ctx, input) {
  const file = await ctx.fs.read(input.path)
  return ctx.subprocess.run(input.command, { cwd: file.workspace })
}

// 组合时二选一，并且必须成对
provide({ fs: localFs, subprocess: localProcess })
provide({ fs: e2bFs,   subprocess: e2bProcess })
```

[Portable execution world Agent Note ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/architecture/2026-07-28-portable-execution-world-consumers.md){: data-source-evidence=""}

[Filesystem subsystem ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/filesystem.md){: data-source-evidence=""}

[Subprocess subsystem ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/subprocess.md){: data-source-evidence=""}
</details>

### 1.4 远程执行不等于多租户安全 {#section-1-4}

能够在远端执行，只说明文件和进程的位置可以改变。多租户安全还要求容器、凭据、文件、进程和网络都有明确隔离；当前 DSH 不能据此宣称已经解决多租户安全。
{: .section-lead}

这里需要明确边界。E2B 证明文件和命令可以移到远端；Code Mode 的 worker thread 能限制内存、输出和执行时间。但这些能力分别解决“在哪里执行”和“失控时怎样终止”，并不自动组成可信的租户边界。

| 看到的能力 | 它真正解决什么 | 不能据此推出 |
|---|---|---|
| 不同会话看到不同工具 | 可见性隔离 | 工具执行时权限也安全 |
| worker thread + 预算 | 故障控制与资源限制 | 恶意代码无法越界 |
| E2B 沙箱 | 执行位置可远程化 | 会话可断线重连和持久恢复 |
| Session 可恢复 | 对话身份与历史可保留 | 凭据和网络已经按租户治理 |

Code Runtime 的默认实现每次创建新的 worker，并限制内存、输出、计算时间和总运行时间。设计文档把它定义为故障限制手段，同时明确说明 worker thread 不是多租户安全边界；真正的云端多租户仍需要容器级隔离。

因此本文后面讲“隔离”时会明确区分四件事：谁看得见、谁有权执行、失败能否被终止、恶意代码能否越界。把它们都叫 sandbox，会让判断失真。

这些接口为后续接入更强的隔离方案留出了位置，但当前实现能够保证什么，仍要按文件、进程、凭据和网络逐项确认。

<details class="source-note" markdown="1">
<summary>源码依据：Code Runtime 怎样描述安全边界</summary>

**设计结论：**worker-thread backend 是 containment，不是 hard security boundary；模型生成的代码应按接近 Shell 的信任级别对待。
{: .evidence-summary}

```ts
// 现有 backend 能做
freshWorker({ heapLimit, outputLimit, computeTimeout, wallTimeout })

// 现有 backend 不能保证
workerThread !== multiTenantSecurityBoundary

// 真正多租户仍需要
container + credentialIsolation + filesystemIsolation + networkIsolation
```

[Code Mode Agent Note：Trust posture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-06-15-code-mode.md#trust-posture){: data-source-evidence=""}
</details>

### 1.5 一次用户请求内部发生了什么 {#section-1-5}

一次用户请求可能包含多次模型调用。DSH 将整次请求的处理过程记为一个 Turn；其中每一次模型请求，以及这次请求产生的工具执行，记为一个 Step。因此一个 Turn 可以包含零个、一个或多个 Step。
{: .section-lead}

例如用户说“修复这个 bug”。模型第一次搜索，第二次读文件，第三次修改，第四次给最终答案：这是一个 Turn、四个 Step。相反，如果请求在真正调用模型前就被取消，它仍然可以有一个 Turn，但没有 Step。

```text
User → Agent Inbox → turn/start
  → agent/pre-step → step/start
  → user/message
  → 组装 Prompt + Tools + History
  → 请求模型
  → assistant/message
  → tool/call → 执行工具 → tool/result
  → step/end → 需要继续？ → turn/end
```

上面的长箭头可以先压缩成五步：取出用户输入；准备本轮提示词和工具；请求模型；执行模型要求的工具；判断要不要再请求一次模型。AgentLoop 主要负责保证这个顺序，而不是亲自实现每个功能。

{% include dsh/diagram.html number="1" title="一次请求中的多次模型调用" src="/assets/wiki/deepseek-harness/diagrams/13-one-turn-through-dsh.html" description="展开一次用户请求的完整执行顺序" note="区分会写进历史的事件、当前执行控制与工具执行" %}

到这里可以看到，AgentLoop 主要负责执行顺序。接下来的问题是：每次进入这条路径时，当前会话为什么会拿到这组提示词、工具和策略？Part 2 继续看一个 Agent 是怎样确定下来的。

<details class="source-note" markdown="1">
<summary>源码依据：Turn 与 Step 的边界</summary>

**架构文档结论：**Turn 包含零个或多个 Step；Step 包含一次 Model Request 和该请求产生的 Tool Executions。Loop 在固定位置发出事件，让其他模块参与。
{: .evidence-summary}

```ts
append('turn/start')
while (shouldContinue) {
  await hooks.run('agent/pre-step')
  append('step/start')
  const response = await model(request)
  await executeRequestedTools(response)
  append('step/end')
}
append('turn/end')
```

[docs/architecture.md：Turn flow ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#turn-flow){: data-source-evidence=""}
</details>

## Part 2｜同一个 Host 为什么能运行不同的 Agent {#part-composition}

同一个 Host 可以运行 Standard、Code 或 Minimal 等不同 Agent。差异并不来自多套 AgentLoop，而来自每个 Agent 参与了哪些组件，以及这些组件的作用范围和生命周期。

### 2.1 一个 Agent 由哪些部分共同决定 {#section-2-1}

在 DSH 中，一个 Agent 的行为由模型路由、提示词、工具、Skills、Plan、Compaction、Subagent 等组件共同决定，而不是由一个固定的 `Agent` 类完整写死。
{: .section-lead}

这不只是给同一个对象换几个参数。组件是否存在、依赖哪些服务、注册结果对谁生效，以及卸载时撤销哪些注册，都属于 Agent 的组成方式。

```text
Agent A
= 模型选择 + 人设 + 系统提示词
+ Bash + 文件工具 + Skills
+ Plan + 压缩 + 子 Agent + Workflow
+ 原生工具接口

Agent B
= 不同人设 + 不同 Skills
+ 相似的底层工具
+ Code Mode 接口
```

Agent B 可以拥有相似的底层工具，却让模型通过 `run_code` 使用它们；也可以使用不同的人设和 Skills。两者仍然复用同一套 AgentLoop 执行流程。

DSH 使用 `Composition` 表示参与某个 Agent 的组件，以及它们之间的依赖、作用范围和生命周期。`Preset` 是仓库里已经写好并命名的一组 Agent 组合；Plan Mode 则表示某个 Session 当前是否处在规划阶段，两者不是同一个概念。
{: .term-note}

Preset 的入口文件是 `agent.cordis.yml`。它明确列出需要加载的插件和插件组；这些插件再提供或注册工具、提示词片段、监听器与其他服务。

因此，看一份 Preset 文件时需要确认四件事：加载哪些组件、它们依赖什么、注册结果对谁生效，以及这些结果何时被撤销。

<details class="source-note" markdown="1">
<summary>源码依据：Standard 具体加载了哪些组件</summary>

**源码结论：**Standard 不是一个 `fullAgent: true` 开关，而是明确列出 persona、文件工具、Skills、Plan、压缩和委派等组件。
{: .evidence-summary}

```yaml
# apps/cli/config/agent-presets/standard/agent.cordis.yml（节选）
- id: persona
  name: '@deepseek-ai/dsh-persona'
- id: tool-bash
  name: '@deepseek-ai/dsh-tool-bash'
- id: tool-fs
  name: '@deepseek-ai/dsh-tool-fs'
- id: planning
  name: cordis:group
- id: compaction
  name: cordis:group
- id: delegation
  name: cordis:group
```

[standard/agent.cordis.yml ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}
</details>

### 2.2 一项能力对谁生效，又在什么时候撤销 {#section-2-2}

每增加一项能力，都要确定它对哪些 Agent 生效，以及它从何时开始生效、何时彻底撤销。这两个问题分别对应作用范围和生命周期。
{: .section-lead}

先看“谁看得见”。Agent A 可以使用 GitHub 工具，Agent B 不可以；但 GitHub 工具仍可使用 Host 提供的凭据服务和公共工具注册表。也就是说，依赖可以来自上层公共设施，最终注册却只落到 A 的可见范围。

再看“什么时候消失”。一个插件加载时可能同时添加工具、提示词、事件监听器和计时器。卸载插件时，这些东西都要一起撤销。只从数组里删掉工具名字，却留下监听器，仍然会在以后污染别的请求。

```text
加载插件：注册工具、提示词、监听器和临时资源
卸载插件：撤销同一批注册，并释放临时资源
```

很多跨会话 Bug 都是只答对其中一个问题：东西只对 A 可见，但 A 关闭后计时器还在；或者插件能干净卸载，却一开始把服务注册成全进程唯一，导致 B 也拿到了它。

Cordis 的论文把这两部分分别称为 spatial composability 和 temporal composability。正文后面仍使用“作用范围”和“生命周期”，避免把论文术语和源码名混在一起。

{% include dsh/diagram.html number="2" title="能力的作用范围与生命周期" src="/assets/wiki/deepseek-harness/diagrams/14-space-time-composition.html" description="展开一项能力对谁生效、何时撤销" note="只保留 Agent A / B 与加载 / 卸载两组关系" %}

作用范围保证 A 的注册不会进入 B；生命周期保证组件卸载以后，它创建的工具、提示词、监听器和临时资源一并消失。

<details class="source-note" markdown="1">
<summary>源码依据：注册为什么必须可撤销</summary>

**Cordis Primer 原意：**工具、提示词、provider 和 listener 都应通过可逆 effect 安装；每个 registration 都应拥有 disposer，让 reload 与 teardown 能预测地撤销它。
{: .evidence-summary}

```ts
// Cordis 希望满足：A + Plugin - Plugin ≈ A
ctx.effect(() => {
  const removeTool = ctx.tools.register(tool)
  const removePrompt = ctx.systemPrompt.register(section)

  return () => {
    removePrompt()
    removeTool()
  }
})
```

[docs/cordis-primer.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md){: data-source-evidence=""}
</details>

### 2.3 Cordis 在 DSH 中具体负责什么 {#section-2-3}

Cordis 不负责决定模型下一步做什么，也不执行 AgentLoop。它在 DSH 中负责组件之间的三类关系：组件何时可以启动，注册结果对谁有效，以及组件退出时要撤销什么。
{: .section-lead}

仍以 GitHub 工具插件为例。它只有在凭据服务和工具注册表都可用以后才能启动；注册出来的工具只应进入指定 Agent 的工具列表；插件被卸载时，这项工具注册和相关监听器都要撤销。模型调用这个工具以后，执行仍要经过 Host 的权限检查和工具管线。

这三类关系原本可以分别由依赖注入、事件系统和手工清理代码实现。Cordis 的作用是让 DSH 中的插件都遵守同一套启动、可见和退出规则。这样新增工具、提示词或压缩模块时，不需要各自再定义一套生命周期。

正文只保留三个高层问题：依赖是否已满足，注册对谁有效，退出时能否完整撤销。源码里的对应名称和调用方式放在下面的源码依据中。

<details class="source-note" markdown="1">
<summary>源码依据：依赖声明和请求拦截怎样工作</summary>

**文档结论：**依赖满足后插件才进入生命周期；Waterfall listener 接收 `next`，调用它表示继续，不调用表示在这一层结束。
{: .evidence-summary}

```ts
plugin.inject = ['tools', 'credentials']

plugin.apply = (ctx) => {
  // 运行到这里时，两项依赖都已存在
}

ctx.on('tools/execute', async (call, next) => {
  if (!allowed(call)) return denied
  return next(call) // 交给下一层
})
```

[Cordis in five ideas ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-in-five-ideas){: data-source-evidence=""}

[Waterfall semantics ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/cordis-primer.md#cordis-waterfall-semantics){: data-source-evidence=""}
</details>

### 2.4 Host 与 Preset 分别负责什么 {#section-2-4}

DSH 将跨 Session 共享的基础设施放在 Host，将某类 Agent 是否启用某项功能、向模型暴露哪些内容放在 Preset。两者的职责不同，但 Preset 中的组件可以使用 Host 提供的服务。
{: .section-lead}

| Host：公共设施 | Preset / Agent：这次选择 |
|---|---|
| AgentLoop、会话存储、持久化 | 人设与提示词片段 |
| 工具和模型注册表 | 向这个 Agent 开放哪些工具与 Skills |
| 沙箱、审批、凭据 | 是否启用 Plan、压缩、委派 |
| 子 Agent 实现的注册表 | 是否给模型委派与工作流工具 |
| 共享 API 与读取历史的能力 | 工具以原生调用还是 Code Mode 呈现 |

同一 Preset 下的每个会话不会重新加载全部插件。Standard Preset 在进程中挂载一次，选择 Standard 的会话都使用这次挂载；真正属于单个会话的数据，仍由插件按 Session id 分开保存。

```text
                Global / Host
                      ↑
               standard preset
                 挂载一次
                 ↑      ↑
             Agent A  Agent B

查找顺序：Agent 自己 → Preset → 全局默认
```

共享挂载不等于共享会话数据。Plan 是否开启、压缩是否正在进行等内容，必须按 Session id 分别记录，否则 A 和 B 会互相覆盖。

Preset 文件更新以后，新会话使用新版本；已经运行的会话继续使用原来的版本，直到它们结束。这样可以避免会话运行到一半时，工具或提示词突然换成另一套定义。

<details class="source-note" markdown="1">
<summary>源码依据：挂载一次、分层查找与 isolate</summary>

**Preset README 结论：**一个 Preset 每进程挂载一次；Agent 的查找链是 `agent → preset → global`。这里的 Realm 只涉及 Service 实例放在哪个隔离容器：Preset 自己拥有的 Service 不应发布到 root realm，否则会与其他 Preset 的同名 Service 冲突。
{: .evidence-summary}

```yaml
# standard/agent.cordis.yml（Plan 服务节选）
- id: planning
  name: cordis:group
  group: true
  isolate:
    planMode: true   # 这套 Preset 私有的 Service 实例
  config:
    - id: plan-mode
      name: '@deepseek-ai/dsh-plan-mode'
```

[Agent Presets README ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}

[Standard preset 的 Host / Agent 注释 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}
</details>

### 2.5 AgentLoop 负责什么，不负责什么 {#section-2-5}

在 DSH 中，AgentLoop 维护 Turn 与 Step 的执行顺序。Compaction、Plan、权限和 Subagent 在固定位置参与执行，但各自的规则不写进 AgentLoop。把 AgentLoop 本身也做成 Plugin 只是代码组织形式，职责边界才是这里要讨论的内容。
{: .section-lead}

```text
不是：
AgentLoop
├── if planMode
├── if needCompact
├── if subagent
└── if codeMode

而是：
Plan / 压缩 / 权限 / 工具 / 子 Agent
                ↓
        在固定插入点参与
                ↓
        AgentLoop 只保证主顺序
```

例如压缩模块在下一次模型请求前检查上下文是否过长；模型服务返回超长错误时，它也能处理错误并重试。Plan 模块负责是否启用 Plan 及对应提示词。工具权限进入统一执行管线。这些功能都会影响执行过程，但不由 Loop 独占。

这也解释了 Part 1 的远程执行：文件系统先定义稳定接口，本地和 E2B 分别提供实现，Bash 和 LSP 只消费接口。Loop 不需要知道实际文件在哪。

因此，新增一项功能时，首先要判断它应该进入哪个已有接口或执行节点，而不是默认去修改 AgentLoop。

<details class="source-note" markdown="1">
<summary>源码依据：新行为应该放在哪里</summary>

**架构文档结论：**跨重载保留的事实进入 Session event；请求与工具策略进入对应事件或 waterfall；可替换底层实现应有完整的 definition、provider 和 consumer 边界。
{: .evidence-summary}

```ts
await ctx.waterfall('agent/pre-step', step)
const response = await ctx.waterfall('agent/request', request)
await ctx.waterfall('tools/execute', toolCall)
await ctx.waterfall('agent/turn-stopping', turn)

// 其他 package 在这些稳定节点注册自己的规则
```

[Architecture：Cordis ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#cordis){: data-source-evidence=""}

[Architecture：Capability seams ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md#capability-seams){: data-source-evidence=""}
</details>

## Part 3｜Session、模型输入与执行 {#part-core-designs}

前面解释了 Agent 怎样组装。现在看 DSH 如何保存历史、缩短模型输入、组织长任务，以及让同一批工具以两种方式被模型使用。

### 3.1 哪些内容需要持久化 {#section-3-1}

DSH 分别处理已经发生的事实和当前进程中的执行对象。用户消息、模型输出、工具结果和模型请求内容要进入 Session 历史；正在运行的 Agent、取消信号和内存队列可以在进程结束后释放，并在恢复时重新创建。
{: .section-lead}

只保存聊天消息不够。假设一次恢复后模型行为变了，我们还想知道：当时用的是哪个模型、系统提示词是什么、模型拿到了哪些工具定义、某次工具调用是否真的返回。DSH 因此把会话保存成一串按顺序追加的事件，而不是只存一个 messages 数组。

```text
Durable SessionEvent log
├── 一轮何时开始 / 结束
├── 每次模型请求何时开始 / 结束
├── 用户与助手消息
├── 工具调用与结果
├── 当时的系统提示词和工具定义
└── 当时的模型与上下文容量
          │
          └── deriveMessages() → 重新生成本轮模型要看的消息
```

模型消息是从 SessionEvent 记录中生成的一种视图。网页可以从同一份记录还原流式输出；调试工具可以读取工具调用；恢复逻辑可以判断上一轮是否在中途崩溃。这样不需要为这些用途分别维护一份历史。

| 类型 | 例子 | 进程退出以后 | 为什么 |
|---|---|---|---|
| 持久事实 | SessionEvent | 保留 | 恢复、Fork、回放和审计都需要 |
| 派生视图 | 模型 messages、网页展示 | 可以重建 | 它不是第二份真源 |
| 当前执行 | Agent、Inbox、Cancellation | 释放后重建 | 它只负责“现在怎么跑” |

这三类内容的寿命不同。系统重启以后，事件记录需要重新加载，模型消息和页面内容可以重新生成，当前执行对象则按需要重新创建。

<details class="source-note" markdown="1">
<summary>源码依据：历史怎样生成 messages，崩溃怎样恢复</summary>

**Session 文档结论：**Session 是 typed append-only SessionEvent log。`request/header` 记录最终提示词与工具 schemas，`request/context` 记录 provider、model 和 context window；`deriveMessages()` 再从事件日志生成模型历史。崩溃留下的开放 Turn 不会被截断，而会补一个 interrupted 结束事件。
{: .evidence-summary}

```ts
events = persistence.load(sessionId)

if (hasOpenTurn(events)) {
  events.append({
    type: 'turn/end',
    reason: { kind: 'interrupted' }
  })
}

messages = deriveMessages(events)
```

[docs/subsystems/session.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md){: data-source-evidence=""}

[docs/subsystems/persistence.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/persistence.md){: data-source-evidence=""}
</details>

### 3.2 为什么压缩上下文不需要删除历史 {#section-3-2}

压缩上下文不等于删除历史。DSH 保留原始 SessionEvent，再单独计算下一次模型请求需要包含哪些内容。旧内容可以在模型输入中被摘要替代，但审计和恢复仍能访问原始事件。
{: .section-lead}

假设历史中已有 A 到 G 七段内容，模型上下文即将用满。直接删除 A 到 E 会丢失原始记录。DSH 在事件日志中追加压缩过程和摘要，同时在下一次模型输入中用摘要替代 A 到 E。

```text
压缩前：
Durable Log   A B C D E F G
模型本轮看到  A B C D E F G

压缩后：
Durable Log   A B C D E F G + 压缩过程 + 摘要
模型本轮看到  [A-E 的摘要] F G
```

这样做把两个问题分开了：历史回答“发生过什么”，模型输入回答“为了下一步推理，现在应该给模型看什么”。网页也可以选择展示完整历史，而模型只接收短版本。

DSH 会从完整事件记录重新计算本轮模型输入。本文把计算出来、真正发送给模型的这部分内容称为 **Model Surface**。它不是另一份独立历史。
{: .term-note}

{% include dsh/diagram.html number="3" title="完整历史如何变成本轮模型输入" src="/assets/wiki/deepseek-harness/diagrams/15-history-to-model-surface.html" description="展开压缩前后的历史与模型输入" note="只保留原始记录、替换范围、摘要和最终结果" %}

DSH 还会先处理特别长的工具结果：保留开头和结尾，中间用明确标记省略。若这样已经解除压力，就不必额外调用模型做摘要。正常情况下，压缩在下一次请求前检查；如果模型服务已经返回上下文超长错误，也有一条恢复路径。

历史只追加，模型输入则可以用一条新消息替换一段旧内容。这两个约束并不冲突。

<details class="source-note" markdown="1">
<summary>源码依据：摘要如何替换模型输入，而不删除原历史</summary>

**Compaction 文档结论：**从事件记录生成模型输入的过程称为 projection。压缩过程本身记录为 log-only events；真正进入模型的是一个带 `SurfaceOp.replace(start, end)` 的新消息。`compaction/start` 与 `compaction/end` 记录过程边界，原始 events 不会被删除。
{: .evidence-summary}

```ts
append({ type: 'compaction/start', ... })

append({
  type: 'user/message',
  content: summary,
  surfaceOp: SurfaceOp.replace(start, end)
})

append({ type: 'compaction/end', ... })

// deriveMessages(log) 得到：summary + recent messages
```

[docs/subsystems/compaction.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/compaction.md){: data-source-evidence=""}

[Session Surface types ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/session.md#surface-types){: data-source-evidence=""}
</details>

### 3.3 一次模型请求由哪些内容组成 {#section-3-3}

模型收到的不只是聊天记录。系统提示词、工具定义、当前目录、Skills、压缩后的历史、Plan 指令和 Code Mode SDK 都可能进入请求。判断一项改动是否影响模型，需要检查最终请求，而不只是后台注册表。
{: .section-lead}

例如 Host 注册了二十个工具，不代表某个 Agent 会把二十个工具都发给模型。Preset 可能只暴露其中五个，也可能把这五个工具转换成一个 `run_code` 接口。真正决定模型行为和 token 成本的是最终组装出的请求。

```text
Model Surface
= 系统提示词
+ 工具定义
+ 当前运行信息
+ Skills 内容
+ 压缩后对话
+ Plan 等模式说明
+ Code Mode SDK
```

为什么这里要谈 KV Cache？很多模型服务会复用请求开头完全相同的部分。若每轮都在靠前位置改变工具定义或系统提示词，后续请求就可能无法复用缓存，增加首 token 延迟和成本。所以“一个功能放在请求的什么位置、多久变化一次”也是架构问题。

KV Cache 或 Prompt Cache 在这里指模型服务对相同请求前缀的复用。是否命中取决于具体服务，但请求前缀发生变化时通常无法继续复用原来的缓存。

DSH 用 Plan Mode 展示了一个很具体的取舍：进入 Plan 后，增加一段“只规划、不执行”的提示词，但不从工具列表中删除写工具。这样工具目录保持稳定，缓存变化更小。真正禁止危险操作仍靠审批和沙箱，而不是仅靠提示词。

| 需要分开的三件事 | Plan Mode 怎样做 | 含义 |
|---|---|---|
| 行为引导 | 增加 Plan 提示词 | 告诉模型应该怎样做 |
| 实际权限 | 由 Sandbox / Approval 独立执行 | 模型想做也未必被允许 |
| 缓存稳定性 | 模式切换不改变工具目录 | 仍会改变提示词，但少改一大块 schema |

这三件事不能混在一起。提示词是行为指导，不是权限边界；保持工具列表不变有利于缓存，但并不意味着整次请求完全相同。

因此遇到动态 MCP、Skills 或 Mode 变化时，要按三步检查：后台注册表变了吗；当前 Agent 的可见集合变了吗；最终请求真的变了吗。只有第三步直接改变模型输入。

<details class="source-note" markdown="1">
<summary>源码依据：Plan 为什么不删除写工具</summary>

**文档结论：**DSH 的 Model Experience 合同要求 model-facing package 说明模型看到什么、token 影响和 KV Cache 影响。Plan Mode 中，`exit_plan_mode` 在非 Plan 状态也保持注册；进入或离开 Plan 只改变提示词片段，不改变工具目录。
{: .evidence-summary}

```ts
normal.tools = [read, write, bash, exit_plan_mode, ...]
plan.tools   = [read, write, bash, exit_plan_mode, ...]

plan.systemPrompt += planPolicy

// 写操作是否真正允许，由独立执行层判断
allowed = sandbox.check(call) && approval.check(call)
```

[Package Model Experience contract ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/process/2026-07-12-package-model-experience-contract.md){: data-source-evidence=""}

[System Prompt Assembly ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/system-prompt.md){: data-source-evidence=""}

[Plan Mode ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/plan.md){: data-source-evidence=""}
</details>

### 3.4 Goal、Subagent 与 Workflow 的区别 {#section-3-4}

Goal、Subagent 和 Workflow 都可以支持较长任务，但它们管理的对象不同：Goal 记录当前 Session 要继续完成的目标；Subagent 创建独立的 child Session；Workflow 组织多个执行步骤或执行者。
{: .section-lead}

最容易混淆的是 Goal 与 Subagent。Goal 仍属于当前 Session；Subagent 会创建一个新的 child Session，并拥有独立历史、模型选择和父子关系。

| 机制 | 是否新建 Session | 持久化身份 | 主要用途 |
|---|---|---|---|
| Goal | 否 | 当前 Session | 同一 Session 分多轮继续一个目标 |
| Subagent | 是 | Child Session | 委派、并行或使用其他子 Agent 实现 |
| Workflow / Ralph | 取决于步骤 | Workflow 运行及其执行单元 | 组织多个步骤或执行者 |

DSH 的 Subagent 不是 AgentLoop 里写死的一条分支。系统维护一张按名字查找的实现表，可以同时接入进程内 spawn、fork、ACP、Codex、Claude Code 或 DSH SDK。上层委派工具只选择使用哪一种实现，不必知道它的具体启动方式。

DSH 将 child Session 与当前进程中的运行对象分开。Child Session 可以持久存在；对应的 Agent 只在需要工作时驻留内存。Subagent 文档把 Session 在当前进程中的一次运行记录称为 **Activation**。

```text
Child Session（可持久化）
        │
        └── 当前运行实例（Activation，可有可无）
                  ├── 当前 Agent
                  ├── 等待处理的消息队列
                  └── 它拥有的子任务

新消息：正在跑 → 放进同一个队列
        正等待 → 唤醒它
        不在内存 → 从子会话恢复后再投递
```

Activation 不是另一种 Session，只是源码对“这个 Session 当前是否有 Agent 在运行”的记录。进程退出后它可以消失，child Session 的身份和历史仍然保留。

{% include dsh/diagram.html number="4" title="子会话与当前运行实例" src="/assets/wiki/deepseek-harness/diagrams/17-session-activation.html" description="展开子会话正在运行、等待和恢复的三条路径" note="图中保留源码术语 Activation，并给出中文解释" %}

Interrupt 也只停止当前执行，不删除子会话。它保留尚未处理的 inbox 消息；以后再发消息时仍可唤醒或恢复。这样“暂停正在做的事”和“永久销毁这个子 Agent”不会被一个 cancel 混在一起。

所以长任务的核心不是“循环跑久一点”，而是身份、驻留、父子所有权、取消和恢复都要有明确含义。

<details class="source-note" markdown="1">
<summary>源码依据：新消息如何投递给长期子 Agent</summary>

**Subagent 文档结论：**一个 child Session 最多有一个 live Activation。Followup 优先复用它；没有 Activation 时，从持久化 Session cold resume。Interrupt 会保留 inbox，释放顺序是 child first，控制权限由 direct-parent identity 或 live ancestry 判断。
{: .evidence-summary}

```ts
async function followup(parent, childSessionId, message) {
  assertDirectParent(parent.session.id, childSessionId)

  const activation = activations.get(childSessionId)
  if (activation?.running) return activation.agent.followup(message)
  if (activation?.waiting) return activation.agent.wake(message)

  const child = await agents.resume(childSessionId)
  return child.followup(message)
}
```

[docs/subsystems/subagent.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/subagent.md){: data-source-evidence=""}

[docs/subsystems/goal.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/goal.md){: data-source-evidence=""}

[packages/workflow/README.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/workflow/README.md){: data-source-evidence=""}
</details>

### 3.5 工具怎样执行，Code Mode 改了什么 {#section-3-5}

DSH 分开处理工具注册、模型看到的工具接口和工具执行管线。Code Mode 改变的是模型使用工具的接口；底层工具仍然经过相同的校验、审批、执行和记录流程。
{: .section-lead}

先看普通工具调用。模型返回工具名和参数后，DSH 不会直接调用函数。它先记录请求，检查参数和策略，处理审批，再执行工具，整理结果并写回会话。所有工具都走同一条 **Tool Execution Pipeline**。

```text
assistant tool call
  → 记录 tool/call
  → 校验参数与策略
  → 审批
  → 执行工具函数
  → 整理输出
  → 记录 tool/result
```

Native 模式把每个工具分别告诉模型。模型要“搜索十个文件、过滤结果、再读其中三个”时，通常要多轮往返。Code Mode 则给模型一个生成的 TypeScript SDK 和 `run_code`；模型写一小段程序，由普通 Runtime 完成循环、分支和聚合，再把筛选后的结果交回模型。

```text
Native：模型 → search → 模型 → read → 模型 → read → 模型

Code：  模型 → 一段程序 → run_code
                           ├── search
                           ├── read × N
                           ├── filter
                           └── return 精简结果
             → 模型
```

因此 Code Mode 的变化不是“突然多了一批能力”，而是把一部分控制流从模型轮次移到了确定性的程序执行。底层仍然是同一批工具。

DSH 文档将系统已经注册的工具能力与模型看到的接口分开。Native、Code 和 Both 是三种工具呈现方式，不是三套工具实现。

{% include dsh/diagram.html number="5" title="Native Tool Calling 与 Code Mode" src="/assets/wiki/deepseek-harness/diagrams/16-native-vs-code.html" description="展开两种工具调用方式的执行顺序" note="比较模型往返次数和 Runtime 内部调用" %}

内部子调用不会绕过权限。`run_code` 中的 search、read 等调用仍回到统一 pipeline；需要独占的工具不会和其他调用并发，允许并发的调用也受数量上限控制。

**边界：**不能预先声称 Code Mode 一定省 token 或更快。SDK 自身占 token，简单单工具任务可能更差。它更可能在大量工具调用、分支、过滤和中间结果很大的任务上获益，必须用真实 workload 测量。

因此，这里能够确认的是控制流从多次模型往返移到了一次程序执行；token、延迟和结果质量是否更好，要由具体任务的实验回答。

<details class="source-note" markdown="1">
<summary>源码依据：Code Mode 的子调用是否绕过权限</summary>

**设计结论：**`ToolDefinition` 区分模型可见 schema 与 Host 内部执行信息。外层 `run_code` 和内部每个工具 subcall 都经过统一 Tool Execution Pipeline；调度器复用工具的并发分类与上限。Code Runtime 有资源限制，但不是多租户安全边界。
{: .evidence-summary}

```ts
async function codeSubcall(name, args) {
  // 不是直接 tools[name].execute(args)
  return toolPipeline.dispatch({
    parentCall: 'run_code',
    name,
    args
  })
}

toolPipeline = validate
  → policy / approval
  → execute
  → normalize
  → durable result
```

[docs/subsystems/tools.md ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/tools.md){: data-source-evidence=""}

[Tool Execution Pipeline ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/tool-execution-pipeline.md){: data-source-evidence=""}

[Code Mode Agent Note ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-06-15-code-mode.md){: data-source-evidence=""}

[Per-agent tool presentation ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-08-05-per-agent-tool-presentation.md){: data-source-evidence=""}
</details>

## Part 4｜四个 Agent Preset {#part-presets}

Standard、Code、Minimal、Cordis 是四个完整的 Agent Preset。Plan Mode 是 Session 内部的协作状态；Native、Code、Both 是工具呈现方式。这三个维度不能混称为 Mode。

### 4.1 Standard：完整的日常 Coding Agent {#section-4-1}

Standard 是面向日常 Coding Agent 的完整 Preset。终端、文件、Skills、Plan、Compaction、Goal、Subagent、Workflow、Todo 和 Web 都在这个 Preset 中启用。
{: .section-lead}

Standard 的文件可以直接看到这种组织方式：AgentLoop 没有实现所有功能，Preset 明确选择参与的组件。Host 继续提供工具注册表、模型路由、持久化、沙箱和审批；Standard 决定这个 Agent 是否使用并向模型暴露相应能力。

```text
Standard
├── Persona / Agent Instructions
├── Bash / Pwsh / Filesystem / Search
├── Skills / Goals / Plan
├── Compaction + Tool Result Pruner
├── Subagent / Fork
├── Workflow / Ralph
└── Ask User / Todo / Web
```

Standard 并不拥有所有底层服务。例如子 Agent 的实现和 Goal 管理都由 Host 注册；Standard 只选择是否把对应工具暴露给模型。这与 2.4 的 Host / Preset 分工一致。

YAML 按身份、Shell、文件系统、Skills、Goal、Plan、Compaction、委派和其他工具分区，可以直接看出 Standard 启用了哪些组件。

<details class="source-note" markdown="1">
<summary>源码依据：Standard 由哪些区域组成</summary>

**源码结论：**Standard 文件用注释明确分出 identity、shell、filesystem、skills、goals、plan mode、compaction、delegation and workflows、remaining tools 等区域。提供 Plan、Compaction 和 Workflow Service 的 group 使用独立 isolate；只向 Host registry 贡献工具的组件则复用 Host service。
{: .evidence-summary}

```yaml
# 只保留结构，不展开每个包
- id: persona
- id: tool-bash
- id: tool-fs
- id: skill-filesystem
- id: tool-goal
- id: planning
- id: compaction
- id: delegation
- id: tool-ask-user
- id: tool-todo
- id: tool-web
```

[Standard Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/standard/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.2 Code：工具大体相同，模型使用方式变了 {#section-4-2}

Code Preset 基本保留 Standard 的组件，只增加一项配置，将工具以 Code Mode 呈现给模型。它没有另行实现一套文件、搜索或审批工具。
{: .section-lead}

文件工具仍是原来的文件工具，搜索、审批和执行管线也不变。变化的是模型看到 `run_code` 和生成的 SDK，而不是一组原生 function schemas。

```text
Standard = 完整能力 + native 工具接口
Code     = 完整能力 + code 工具接口
```

这不表示两个文件存在自动继承关系。Code 文件当前复制 Standard 的内容，再增加工具呈现配置；Standard 后续增加组件时，Code 也需要同步。这是一项明确的维护成本。

Code 更适合多工具、分支和聚合任务；是否作为默认 Preset，仍取决于模型写程序的稳定性、SDK token、审批体验和真实 workload。

<details class="source-note" markdown="1">
<summary>源码依据：Code Preset 实际多了哪一项配置</summary>

**源码原文结论：**文件头写着 “Everything in standard is here unchanged”，主要新增的是 `tool-presentation` 行，配置值为 `code`。该组件依赖 Host 提供的 `codeRuntime`，缺少 TypeScript runtime 时会在挂载阶段失败。
{: .evidence-summary}

```yaml
- id: tool-presentation
  name: '@deepseek-ai/dsh-agent-tool-presentation'
  config:
    mode: code
```

[Code Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/code/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.3 Minimal：一套独立的精简配置 {#section-4-3}

Minimal 只启用固定 persona、持久 Bash 和 `str_replace_editor`，没有加入 Standard 中的 Skills、Plan、Compaction、Subagent 和 Workflow。这说明 Preset 不必从 Standard 开始删减，也可以独立选择一组更小的组件。
{: .section-lead}

Minimal 也不自动拼接运行时上下文。与 Standard 相比，它的模型输入和可用工具都更少。

```text
Minimal
├── complete persona
│   └── includeRuntimeContext: false
├── persistent bash
├── str_replace_editor
└── no compaction / plan / subagent / workflow
```

Minimal 还在自己的 Preset 范围内提供 local filesystem。Host 默认 filesystem 没有被删除，但 Minimal Agent 查找 `ctx.fs` 时会优先使用 Preset 内的实现。具体的覆盖规则放在下面的源码依据中。

Minimal 的价值不是“功能更少所以一定更好”，而是说明向模型暴露的提示词和工具可以被主动缩小，不必以越来越大的默认 Agent 为唯一基础。

<details class="source-note" markdown="1">
<summary>源码依据：Minimal 怎样缩小提示词和工具</summary>

**源码结论：**persona 被标成 complete，并关闭 runtime context；Preset 只加载 persistent shell 与 editor，且没有 compaction 行。`filesystem` group 使用 `isolate: { fs: true }`，因此替换只发生在 Minimal Preset 内；Cordis 将较近定义优先的规则称为 shadow。
{: .evidence-summary}

```yaml
- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: You are a helpful software engineer assistant.
    complete: true
    includeRuntimeContext: false

- id: persistent-bash
  name: '@deepseek-ai/dsh-tool-bash-persistent'

- id: str-replace-editor
  name: '@deepseek-ai/dsh-tool-str-replace-editor'
```

[Minimal Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/minimal/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.4 Cordis：允许 Agent 修改运行时组合 {#section-4-4}

Cordis Preset 在 Standard 之上增加读取当前运行环境、编写 Agent 配置、临时挂载和卸载插件的能力。它允许 Agent 修改构成自己或其他 Agent 的组件。
{: .section-lead}

这个 Preset 带有 Cordis 工具、用于编写组合配置的 Skill，以及说明 Host 与 Agent 组件边界的 persona。用户可以让它创建或修改另一种 Agent 配置。

```text
Cordis Preset
= Standard
+ 查看当前 Runtime
+ 编写 agent.cordis.yml
+ mount / unmount 临时插件
+ composition-authoring skill
```

`cordis_mount` 会在当前运行的 Host 中执行模型生成的 JavaScript，因此这一能力应按接近 Shell access 的权限处理。这里所说的修改只涉及组件和 Agent 配置，不涉及模型权重。

因此 Cordis Preset 适合可信的架构实验和 Agent authoring，不适合作为普通低信任会话的默认入口。

<details class="source-note" markdown="1">
<summary>源码依据：Cordis Preset 怎样说明权限风险</summary>

**文件头结论：**`cordis_mount` evaluates model-written JavaScript against the live runtime；文档要求把这个 Preset 当作 shell access。Authoring Skill 还要求不要直接修改 shipped presets，而应复制到用户 Preset 目录后再编辑。
{: .evidence-summary}

```yaml
# 读取并修改 live runtime
- id: tool-cordis
  name: '@deepseek-ai/dsh-tool-cordis'

# 随 Preset 提供 composition authoring skill
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - skills/
```

[Cordis Preset ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/apps/cli/config/agent-presets/cordis/agent.cordis.yml){: data-source-evidence=""}
</details>

### 4.5 四个 Preset 的完整对照 {#section-4-5}

Standard、Code、Minimal、Cordis 复用同一套 Runtime 和 AgentLoop，但选择不同组件、工具呈现方式和信任边界。它们也不是四种互斥的运行状态。
{: .section-lead}

| 能力或选择 | Standard | Code | Minimal | Cordis |
|---|---|---|---|---|
| 主要定位 | 完整日常版 | 程序化调用工具 | 独立精简版 | 编写运行时配置 |
| 文件与 Shell | 完整 | 完整 | 特殊的两工具组合 | 完整 |
| Skills | 有 | 有 | 无 | 有，另加 authoring skill |
| Plan / Compaction | 有 | 有 | 无 | 有 |
| Subagent / Workflow | 有 | 有 | 无 | 有 |
| 工具呈现 | native | code | 简单原生工具 | native |
| 修改运行中的组件 | 无 | 无 | 无 | 有 |
| 权限风险 | 常规 | 需信任代码执行 | 较小 | 很高，接近 Shell |

表中需要重点区分“工具呈现”。Standard 与 Code 的底层能力大体相近，但模型接口不同；Minimal 是独立定义的较小 Preset；Cordis 则把 Composition 本身暴露为模型可操作对象。

Preset 决定参与 Agent 的组件；Plan Mode 表示某个 Session 当前的协作状态；Tool Presentation 决定工具以 native、code 或 both 哪种接口出现。它们是三个独立维度。

这四个 Preset 复用同一个 Host 和 AgentLoop，却可以得到不同的提示词、工具接口和功能范围，不需要为每一种 Agent 复制一套执行循环。

<details class="source-note" markdown="1">
<summary>源码依据：四个 Preset 的文件位置与切换限制</summary>

**Preset README 结论：**每个 Preset 是一个包含 `agent.cordis.yml` 的目录；会话创建时记录所选 Preset。已经产生历史的 Session 不能重新组合到另一个 Preset，只有空白 Session 允许切换。
{: .evidence-summary}

```text
apps/cli/config/agent-presets/
├── standard/agent.cordis.yml
├── code/agent.cordis.yml
├── minimal/agent.cordis.yml
└── cordis/agent.cordis.yml

recompose(session, nextPreset)
  → allowed only when session is blank
```

[Agent Presets README ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md){: data-source-evidence=""}
</details>

## Part 5｜怎样比较，以及应该带走什么 {#part-comparison}

最后不做功能勾选表。Claude Code、Codex、Kimi 和 DSH 都在处理现代 Harness 的共同问题；真正值得比较的是它们分别选择了什么语义，以及这些选择适合什么场景。

### 5.1 比较架构问题，而不是功能数量 {#section-5-1}

两个产品都提供 Plan、Subagent 或 Compaction，不代表它们采用了相同架构。比较时需要确认这些功能由谁维护、是否持久化、怎样取消和恢复，而不是只比较是否存在同名入口。
{: .section-lead}

例如两个产品都叫 Subagent：一个可能只是执行一次外部命令并返回文本；另一个可能创建可恢复的 child Session。两者在功能表里都能打勾，但长期任务、取消、父子权限和进程重启后的含义完全不同。

| 应该问的问题 | 真正要查的语义 |
|---|---|
| 一个 Agent 怎样定义？ | 固定应用、普通配置，还是运行时组装 |
| 能力对谁生效？ | 用户、项目、会话、Agent 和全局分别能看到什么 |
| 运行中变化怎样传播？ | 立即更新、新会话生效，还是必须重启 |
| 历史的唯一来源是什么？ | messages、events，还是其他模型 |
| 模型最终看到什么？ | prompt、tools、skills、压缩视图如何组装 |
| Subagent 是什么？ | 一次调用、child loop、持久 child Session，还是外部产品 |
| 取消和恢复由谁负责？ | 身份、所有者、控制权限和清理规则 |
| 工具变化怎样影响缓存？ | schema、顺序与前缀是否稳定 |

比较时还要限定版本和证据。产品文档没有公开内部实现，就写“未知”；不要自动用一个最简单的实现替它补空白。某个 UI 都叫 Plan，也不能推断它们都使用持久事件、稳定工具目录或相同权限模型。

功能勾选表适合快速确认产品能力，但不能说明恢复、并发和失败时的行为。架构比较还需要记录产品版本、公开证据、未知项和边界条件；例如应当确认“已有 Session 是否接收 MCP tool update”，而不是只写“支持动态工具”。

DSH 的价值不需要建立在“别人没有”上。Claude Code 也有 User / Project / Local 等配置范围和动态 MCP 工具；Codex 也公开讨论工具顺序和 prompt cache。共同问题真实存在，才更值得比较不同答案。

<details class="source-note" markdown="1">
<summary>源码依据：比较结论怎样保持可核对</summary>

**比较方法：**每个答案同时记录版本、来源、已确认语义和仍未知的部分。这样以后产品更新时，可以修改一格证据，而不必推翻整段叙事。
{: .evidence-summary}

```ts
comparison = {
  question: '已有 Session 是否接收动态工具变化？',
  product: 'Claude Code',
  versionOrDate: '2026-08',
  confirmed: 'MCP supports list_changed',
  unknown: '所有内部传播与缓存细节未公开',
  source: 'official docs'
}
```

[Claude Code MCP docs ↗](https://code.claude.com/docs/en/mcp){: data-source-evidence=""}

[OpenAI：Unrolling the Codex agent loop ↗](https://openai.com/index/unrolling-the-codex-agent-loop/){: data-source-evidence=""}
</details>

### 5.2 工具变化为什么会影响缓存 {#section-5-2}

很多模型缓存要求请求前缀完全相同。工具定义通常位于请求前部；增删工具、改变顺序或修改 schema，都可能让后续请求失去缓存复用。因此，动态工具既改变功能集合，也可能改变延迟和成本。
{: .section-lead}

假设上一轮模型看到 Tool A、B、C，下一轮 MCP 新增 Tool D。即使对话完全相同，请求前部的工具块也变了。若工具顺序还不稳定，同一集合仅仅换个顺序也可能造成 cache miss。

不同 Harness 可以用四类思路处理：始终发送完整目录；只发送当前可用目录；先提供工具搜索，按需加载完整 schema；或者像 Code Mode 一样，用一个程序接口和 SDK 表达一批能力。没有一种对所有任务都最好。

| 策略 | 好处 | 代价 |
|---|---|---|
| 固定完整目录 | 前缀相对稳定 | 首轮 schema token 大 |
| 动态目录 | 当前集合最直接 | 增删和排序会改变前缀 |
| 延迟发现 | 完整 schema 按需进入 | 多一次发现步骤，语义更复杂 |
| Code 模式工具接口 | Runtime 承担循环与聚合 | SDK token、worker 和安全成本 |

要评估真实效果，不能只比较一轮 token。至少要记录首轮与后续轮输入、cache read/write、首 token 时间、额外发现轮次、工具变化次数、总模型调用和任务是否成功。正确语义仍然优先：权限或工作区真的变化时，不能为了缓存假装它没变。

DSH 的几个具体选择是：工具按作用范围解析；每个 Agent 可以选择工具呈现方式；Plan 切换保持工具目录不变；直接影响模型输入的 package 必须说明 KV Cache 影响；`request/header` 记录最终提示词和工具 schemas。它们不能保证缓存命中，但能明确请求在哪些位置发生了变化。

<details class="source-note" markdown="1">
<summary>源码依据：为什么工具顺序也重要</summary>

**公开资料结论：**Codex 团队把 prompt caching 描述为 exact prefix match，并记录过 MCP 工具顺序不稳定导致 cache miss；Claude Code 文档也把工具定义变化纳入缓存设计。
{: .evidence-summary}

```text
上一轮前缀：system + [Tool A, Tool B, Tool C] + history
下一轮前缀：system + [Tool B, Tool A, Tool C] + history
                         ↑ 集合相同，字节前缀已不同

工程目标：
stable ordering + stable serialization + explicit surface version
```

[Claude Code prompt caching docs ↗](https://code.claude.com/docs/en/prompt-caching){: data-source-evidence=""}

[Codex agent loop：prompt caching ↗](https://openai.com/index/unrolling-the-codex-agent-loop/){: data-source-evidence=""}
</details>

### 5.3 DSH 的主要设计特点 {#section-5-3}

DSH 的主要特点不是某一个独有功能，而是多个功能尽量复用同一套组件生命周期、Session 记录、模型输入生成和底层接口替换规则。
{: .section-lead}

Plan、压缩、子 Agent、Code Mode 在其他现代 Harness 中都可能出现。DSH 更值得研究的是，这些功能尽量复用相同的依赖、作用范围、清理、事件和 Session 规则，而不是各自在 Loop 中增加一套局部逻辑。

| 统一处理的内容 | DSH 的做法 | 带来的结果 |
|---|---|---|
| 组件的加入与退出 | 每个组件说明依赖、可见范围与清理方式 | 新功能不必都修改 AgentLoop |
| 会话中已经发生的事实 | 统一写入 SessionEvent 记录 | 恢复、Fork、UI 和调试共享来源 |
| 完整历史与本轮模型输入 | 分开保存和生成 | 压缩不必删除原始历史 |
| 模型看到的内容 | 明确记录提示词、工具和缓存影响 | 模型输入可以单独评审 |
| 文件与进程的具体实现 | 上层只依赖统一接口 | 本地与远端实现可以替换 |

这套设计语言让评审顺序变得稳定：新组件依赖什么；它注册了什么；对谁可见；谁负责撤销；是否改变模型输入；进程崩溃后哪些事实还在。问题本身比框架名字更值得借鉴。

这套统一规则仍需要测试证明。框架名称本身不能替代崩溃恢复、并发恢复、卸载是否彻底，以及不同会话是否发生注册冲突等具体行为测试。

<details class="source-note" markdown="1">
<summary>源码依据：Architecture 文档怎样安排职责</summary>

**架构结论：**文档分别列出 Cordis、Events、Turn flow、Session log、Capability seams 和 Where new behavior goes，说明新增行为应进入哪一层，而不是默认修改 AgentLoop。
{: .evidence-summary}

```text
需要保存事实      → SessionEvent
需要观察流程      → emit / parallel / serial event
需要包裹或拒绝    → waterfall
需要替换底层实现  → definition + provider + consumer
只影响某个 Agent  → scoped contribution
跨会话公共设施    → Host service
```

[DeepSeek Harness Architecture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md){: data-source-evidence=""}

[Repository invariants ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/AGENTS.md){: data-source-evidence=""}
</details>

### 5.4 复杂度与尚未解决的问题 {#section-5-4}

DSH 没有消除复杂度。它把原本集中在控制流程中的复杂度，分散到作用范围、生命周期、事件格式、所有权和恢复规则中。这有利于局部替换和测试，也增加了理解与实现成本。
{: .section-lead}

作用范围、共享服务的归属、组件清理、Preset 版本和模型输入生成分别对应不同的代码规则，不能互相替代。统一框架只规定这些规则应该放在哪里，不能自动保证每个插件都实现正确。

| 得到的能力 | 同时承担的成本 |
|---|---|
| 多 Session 的组件组织与隔离 | 要理解可见范围、共享服务归属与清理 |
| 事件日志与恢复 | 要维护事件 schema、兼容性和崩溃语义 |
| 可替换的模型输入视图 | 要证明摘要替换和工具调用配对始终正确 |
| Preset 热更新 | 要同时管理新旧 Preset 实例的生命周期 |
| 远程执行环境 | reconnect、同步和持久 handle 尚未解决 |
| Code Runtime | SDK token、worker 预算和非安全边界 |

Preset 更新尤其能说明取舍：磁盘文件变化后，新会话进入新版本，正在运行的会话继续使用旧版本。这样不会在历史中途换工具和提示词，但 Host 需要同时保留两个版本，直到没有会话再使用旧版本。

远程执行的限制也不能藏在脚注里。当前 E2B 是临时性的 POC，没有完整的断线重连、工作区同步或持久远程句柄；Code worker thread 也不是多租户安全边界。架构允许未来接入，不等于当前已经完成。

常驻的 Preset 组件和当前 Agent 都会占用资源。即使插件只挂载一次，每个被访问过的 Session 仍可能保留消息队列、索引和子 Agent 实现持有的资源；如果没有空闲回收机制，可恢复并不意味着常驻成本很低。持久化层遇到无法忠实读取的新版本格式时，DSH 选择明确报错，而不是猜测性回放。

判断这套设计是否值得，最终要看团队是否真的需要多会话、动态能力、恢复、长期子 Agent 和多种模型输入；如果都不需要，一个清楚的小 Loop 可能更好。

<details class="source-note" markdown="1">
<summary>源码依据：热更新和远程执行的明确边界</summary>

**文档结论：**默认 Preset 的变化只影响之后创建的会话，运行中会话继续使用原组合；E2B note 明确列出 ephemeral state、无 reconnect、无 workspace sync 等限制；Persistence 文档要求遇到无法忠实读取的新格式时明确失败。
{: .evidence-summary}

```ts
onPresetFileChanged(nextGeneration) {
  presetForNewSessions = nextGeneration
  // runningSessions 继续引用各自原来的 generation
}

e2bPoc = {
  ephemeral: true,
  reconnect: false,
  durableRemoteHandle: false,
  workspaceSync: false
}
```

[Preset generation lifecycle ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/packages/preset/agent-presets/README.md#where-to-call-mount){: data-source-evidence=""}

[E2B POC boundary ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/architecture/2026-07-28-portable-execution-world-consumers.md#e2b-poc-boundary){: data-source-evidence=""}

[Code Runtime trust posture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/.agents/notes/implemented/feature/2026-06-15-code-mode.md#trust-posture){: data-source-evidence=""}

[Persistence compatibility ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems/persistence.md){: data-source-evidence=""}
</details>

### 5.5 五个结论 {#section-5-5}

最后回到贯穿全文的五个边界。
{: .section-lead}

**第一，能力既有可见范围，也有生命周期。**不要只问“有没有这个工具”，还要问谁看得到、谁拥有、何时加载、何时撤销。

**第二，已经发生的事实，不等于当前正在运行的对象。**Session 可以持久；Agent、Inbox 和 Cancellation 可以被释放后重建。

**第三，完整历史，不等于模型这轮需要看到的内容。**Compaction 可以保留原始事件，只替换模型视图。

**第四，系统拥有的能力，不等于模型使用能力的接口。**Code Mode 没有复制工具，而是改变模型与 Runtime 的计算分工。

**第五，Runtime 需要明确资源由谁负责。**Tool、Session、Subagent、Process、Sandbox 和模型输入分别由谁维护；取消、恢复、清理与失败时发生什么，都应该可以明确回答。

```text
一个 Host 上的多个 Session
  → 每个 Agent 怎样拿到自己的能力？
  → 谁看见，何时生效？
  → 哪些事实要保存？
  → 模型最终看见什么？
  → 长任务怎样恢复和取消？
  → 执行环境能否替换？
  → Loop 逐渐需要一套 Runtime
```

所以 DSH 最有意思的已经不是有没有 Plan、Compaction、Subagent 或 Code Mode。更重要的是：当这些功能同时存在时，它们能否共享一套清楚的身份、历史、可见范围、执行和清理规则，而不是最终都回到 AgentLoop 里增加一个 `if`。

> **A Harness starts as a Loop. At what point does it become a Runtime?**
{: .final-question}

答案不是“代码超过多少行”，而是系统是否已经不得不显式管理多身份、可恢复历史、动态能力、资源所有权和模型输入。简单场景里，小 Loop 仍然可能是更好的设计；问题复杂到这些边界无法回避时，Runtime 才成为真正的需求。

<details class="source-note" markdown="1">
<summary>源码依据：建议继续阅读的顺序</summary>

**建议顺序：**先读 architecture 的 Turn flow 与 capability seams，再按兴趣进入 Session、Compaction、Plan、Subagent、Tools；最后再读 Preset YAML。不要从包目录或 Cordis 类型定义开始，否则很容易再次掉进术语里。
{: .evidence-summary}

```text
docs/architecture.md
  → docs/subsystems/session.md
  → docs/subsystems/compaction.md
  → docs/subsystems/system-prompt.md
  → docs/subsystems/plan.md
  → docs/subsystems/subagent.md
  → docs/subsystems/tools.md
  → apps/cli/config/agent-presets/*/agent.cordis.yml
```

[DeepSeek Harness Architecture ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/docs/architecture.md){: data-source-evidence=""}

[Subsystem references ↗](https://github.com/deepseek-ai/deepseek-harness/tree/47f943859bef60e4160492346772ded9b24f765a/docs/subsystems){: data-source-evidence=""}
</details>
