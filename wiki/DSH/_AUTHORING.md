# DeepSeek Harness Wiki 维护说明

`index.md` 是这篇 Wiki 和分享讲稿的唯一正文来源。Jekyll 会把它渲染成最终 HTML；不要另建或手改 `index.html`，也不要编辑 `_site/`。

## 最常改的内容

- 改叙述：直接编辑普通 Markdown 段落。
- 改目录：编辑 `## Part ...` 或 `### 1.1 ...` 标题。页面目录会从标题自动生成。
- 改表格、引用和伪代码：使用普通 Markdown 表格、`>` 引用和 fenced code block。
- 改辅助图入口：编辑正文里的 `{% include dsh/diagram.html ... %}` 参数。图不是论证的唯一载体，关键结论仍应写在正文。

标题后的显式 id 用于稳定锚点，例如：

```markdown
## Part 1｜Overview：AgentLoop 之外还要管理什么 {#part-introduction}

### 1.1 两个 Session，为什么会拿到不同的能力 {#section-1-1}
```

正文固定为 5 个 Part：Part 1 有 2 个小节，Part 2–5 各有 5 个。若确实要改变这个结构，需要同步修改 `scripts/check_deepseek_harness_share.py` 中的结构约束。

每个 Part 标题前保留一行不会显示在页面中的演讲路线：

```markdown
<!-- talk-route: Part 1 | 6 min | full: 1.1→1.2 | short: 1.1→1.2 -->
```

`full` 对应页面标出的完整分享时长；`short` 是现场时间不足时仍能保持主线的章节顺序。它只记录取舍，不复制正文，也不要求在页面里增加“必讲”或“备用”标签。调整小节职责或时间后，应在相邻的 `talk-route` 中同步更新。

## Overview 词表与文档入口

Part 1 标题后只保留一张短词表，收录读懂 Overview 场景和时序所必需的运行时对象。当前是 `Host`、`Agent`、`Inbox`、`Session`、`SessionEvent`、`AgentLoop`、`Turn`、`Step`。不要把 Cordis、Composition、Subagent 或 Model Surface 的完整术语体系重新塞回开头；这些概念在第一次真正使用它们的小节中解释。

Overview 图优先使用“Agent 创建流程”“从日志生成 Messages”等读者动作；`AgentFactory`、`deriveMessages()` 这类源码标识只在正文紧邻处解释，并保留到源码依据中，不直接作为图的前置知识。Preset 必须画成“确保 standing generation 已挂载，再关联 Agent”；不能画成每创建一个 Session 都重新挂载 Plugin 和注册 Tools。

固定版本的关键文档入口放在 Overview 结束后的折叠区。每行只回答“这份文档适合查什么”，保持一两句话并链接到固定 revision。普通文档段落由正文用中文概括，不把英文 README 或设计说明整段复制到页面。

## Part 2 的 Shell 主案例

Part 2 的 2.2–2.5 统一沿 `packages/shell` 展开：`ShellExecutor` Definition、Local/Sandbox Provider、`tool-bash` Consumer、Prompt/Tool Registration、Effect/Disposer，以及 Base Bundle 与 Standard Preset 的声明式组合。不要在这一段重新切换成 Filesystem、Persona 等另一套主案例；其他 Seam 只用于说明 Execution World 等 Shell 本身无法单独证明的边界。

2.2 必须从 `tool-bash.apply(ctx)` 的真实使用出发，逐项解释 `tools`、`systemPrompt`、`shell`、`shellEnv`；其中 `shell` 是执行能力，`shellEnv` 是每次命令的可信 `DSH_*` snapshot，不能合并成一句“Shell 依赖”。Context 要说明成当前 Plugin 的 Service 解析与 Effect 归属入口，而不是普通全局容器。必须分开 Cordis Service isolation 与 DSH Registry ScopeKey：前者决定 `ctx.shell` 解析哪个 Provider 实例，后者决定 `bash` Registration 对哪些 Agent 可见。另补充 Proxy 属性解析，以及 Cordis `pending` 与 DSH Boot/Preset mount 响亮审计之间的区别。

2.3 必须先讲 mount → active → unload 的实际时间线，再命名 Fiber、Effect、Disposer。Fiber 要明确不是线程/协程，Disposer 是清理函数，unload 是结束本次挂载而不是删除 Package。列出显式 dispose、父树关闭、Loader row 更新、inject 依赖变化四类触发，同时明确 Tool Call、Turn 结束和 Agent idle 不会触发卸载；standing Preset generation 的特殊寿命也要保留。Effect 除了 Registry 条目，还要说明 Timer、Watcher、Socket 等自管资源必须显式返回清理函数。Cordis 只保证按逆序开始调用 Fiber 的 Effect Disposer，并等待全部结束；不同 Effect 的异步清理可以并发，存在顺序依赖的步骤必须放进同一个 Disposer 自行串行等待。

这一章先固定编译期与运行时的边界：`declare module` 只扩展 TypeScript 类型，Service Definition/实现类也在挂载前存在；Service Provider Plugin 只有在构造时调用 `super(ctx, name)`，才把实例注册到当前 Context。运行时再区分：Plugin 是挂载生命周期单元；Service 是当前 Context 可解析的具名实例；Registry 是保存多项 Registration 的 Service；Registration 是 Plugin 插入 Registry/Service 的可撤销条目。Composition 指已挂载 Plugin 图及其运行时连接关系。Bundle 与 Agent Preset 是配置输入，Runtime 还包含 Agent、Session、Inbox 和进程等运行状态。

Plugin 是入口协议而不是目录分类。源码识别以 `src/index.ts` 为准：Service Class 的 default export，或 namespace/function-style 的 `name`/`inject`/`Config`/`apply`，以及较少见的 `{ apply }` object。不要把 Service Definition、类型包或任意 `packages/` 子目录都称为 Plugin；实际挂载集合以 `--dump-config` 和 Preset rows 为准。

AgentLoop 构造中的 `super(ctx, 'agentLoop')` 与 `ctx.agents.setFactory(this)` 必须分开说明：前者把这个运行时实例注册为 `ctx.agentLoop`，后者把同一实例登记为 `ctx.agents.create/resume` 的接口式 Factory/Delegate。`llm`、`systemPrompt`、`tools`、`sessions` 和 `agents` 都要指明“类型声明在哪里、运行时 Provider Plugin 是谁”，不能只把 inject key 当作不言自明的全局对象。

Part 4 的 Cordis Toolset 以 `packages/extensions/tool-cordis/README.md` 的当前五个 Tool 为准：`cordis_inspect`、`cordis_define`、`cordis_run`、`cordis_stop`、`cordis_undefine`。不要继续使用旧的 mount/unmount 名称，也不要要求模型自己持有裸 Disposer；Dynamic Package 的运行 Fiber 与清理由 Host Runner 管理。

## Part 5 的问题回收

Part 5 不再另起一套横向比较框架，而是用五个问题检查前四部分是否真正连起来：一条消息与模型请求的关系、为什么保存 SessionEvent Log、Shell Provider 怎样替换、新规则怎样加入和退出、什么时候 AgentLoop 已经不足以描述系统。第四问同时回答普通 Session 中 Tool 是否会卸载，以及有效 Tool Catalog 变化为什么会改变请求前缀；第五问保留 Runtime 的最终定义、设计代价和五条边界总结。

## 一个小节怎样对应到页面

````markdown
### 2.1 标题 {#section-2-1}

用一段自然的正文承接标题，直接说明这一节讨论的关系。页面只会把字号稍微放大，不会添加“结论”标签或卡片。
{: .section-lead}

继续使用普通 Markdown 段落、表格或短代码块展开。正文先写产品和架构层的关系；只有确实需要对应源码时，才介绍源码名称，并在第一次出现时说明准确含义。

不要为了帮助理解而自造比喻。优先使用真实场景、明确的对象关系和源码能够证明的行为。`Realm`、`Effect`、`SurfaceOp` 等只影响实现核对的名字放进下面的折叠区。

<details class="source-note" markdown="1">
<summary>源码依据：这一段证据回答什么</summary>

**文档结论：**概括这段文档或源码能够证明什么。
{: .evidence-summary}

**忠实伪代码（非仓库原文）：**

```ts
// 放短原文，或忠实总结逻辑的伪代码
```

[固定版本源码 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/path/to/file){: data-source-evidence=""}
</details>
````

源码链接必须固定到页面 front matter 中的 `source_revision`。不要只放链接：链接前至少要有一段证据总结，以及短原文、伪代码或结构摘录。

每个代码块前必须明确标注其来源，只允许以下六种标签：

- `源码摘录`：逐字来自链接中的源码；可以截取连续片段，但不能改写符号或函数名。
- `源码批注版（中文注释为后加）`：保留源码语句和调用顺序，在代码块内部加入中文 `//` 说明；必须明确声明注释不是仓库原文，并链接原始源码。
- `配置摘录`：逐字来自链接中的配置文件。
- `流程图摘录`：逐字来自链接中文档已有的结构化流程图，而不是普通说明段落。
- `忠实伪代码（非仓库原文）`：为了缩短控制流而重新组织，必须明确告诉读者不是仓库原文。
- `关系整理（非仓库原文）`：根据多个来源整理的表格、树或映射，不应伪装成原始文档。

普通文档段落一律在证据总结中用中文重述，不整段粘贴英文。只有源码、配置和结构化流程图可以逐字摘录；不要把自行命名的函数或变量放在无来源标签的代码块里。

`.section-lead` 只用于每个小节标题后的第一段，共 22 处。它不是固定措辞模板；改稿时应像正常演讲一样重写整段，而不是保留标签句式。

## 辅助图组件

```liquid
{% include dsh/diagram.html
   number="1"
   title="弹窗标题"
   src="/assets/wiki/deepseek-harness/diagrams/example.html"
   description="正文里的按钮说明"
   note="这张图只帮助理解什么" %}
```

图由 `_includes/dsh/diagram.html` 生成按钮，点击后才加载 HTML。正文应保证不打开图也能读懂。

五张图与正文使用同一组边界：

- Overview 图只表示“确保 Preset 运行实例存在并关联 Agent”，不能画成每个 Session 重复注册 Prompt/Tools。
- Compaction 图必须分开 log-only `compaction/summary` 与 model-visible replacement `user/message`，并明确它改变的是后续派生 Messages，不是只影响当前一轮。
- Native Tool 图以一个模型响应中的 Tool Call batch 为单位，不能假设一次响应只有一个 Call。
- Activation 图只有在 SessionEvent 已持久化后才能写“跨进程恢复”；进程内 Session 对象本身不是耐久存储。
- 每次修改 Spec 后都重新用 Archify `validate`、`deliver` 和 `visual-check`，不要手改生成 HTML。

## 本地检查

```bash
python3 scripts/check_deepseek_harness_share.py
npm run build
```

构建完成后访问：

```text
http://127.0.0.1:9090/Ryanhu2001/wiki/DSH/
```
