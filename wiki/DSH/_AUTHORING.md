# DeepSeek Harness Wiki 维护说明

`index.md` 是这篇 Wiki 和分享讲稿的唯一正文来源。Jekyll 会把它渲染成最终 HTML；不要另建或手改 `index.html`，也不要编辑 `_site/`。

## 最常改的内容

- 改叙述：直接编辑普通 Markdown 段落。
- 改目录：编辑 `## Part ...` 或 `### 1.1 ...` 标题。页面目录会从标题自动生成。
- 改表格、引用和伪代码：使用普通 Markdown 表格、`>` 引用和 fenced code block。
- 改辅助图入口：编辑正文里的 `{% include dsh/diagram.html ... %}` 参数。图不是论证的唯一载体，关键结论仍应写在正文。

标题后的显式 id 用于稳定锚点，例如：

```markdown
## Part 1｜为什么不能只用 AgentLoop 理解整个 Harness {#part-introduction}

### 1.1 同一个 Host 中的三个 Session {#section-1-1}
```

正文固定为 5 个 Part、每个 Part 5 个小节。若确实要改变这个结构，需要同步修改 `scripts/check_deepseek_harness_share.py` 中的结构约束。

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

```ts
// 放短原文，或忠实总结逻辑的伪代码
```

[固定版本源码 ↗](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/path/to/file){: data-source-evidence=""}
</details>
````

源码链接必须固定到页面 front matter 中的 `source_revision`。不要只放链接：链接前至少要有一段证据总结，以及短原文、伪代码或结构摘录。

`.section-lead` 只用于每个小节标题后的第一段，共 25 处。它不是固定措辞模板；改稿时应像正常演讲一样重写整段，而不是保留标签句式。

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

## 本地检查

```bash
python3 scripts/check_deepseek_harness_share.py
npm run build
```

构建完成后访问：

```text
http://127.0.0.1:9090/Ryanhu2001/wiki/DSH/
```
