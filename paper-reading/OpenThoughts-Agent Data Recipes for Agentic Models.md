---
title: "OpenThoughts-Agent: Data Recipes for Agentic Models"
public: true
description: "把 agentic SFT 数据配方拆成六个可消融阶段、跑了 100+ 控制实验的公开 cookbook：任务源选择能拉开 30pp，最强模型不是最佳 teacher，RL 数据源会改变策略性格。"
type: paper-reading
date: 2026-07-26
created_at: 2026-07-26T21:06:00+08:00
paper_title: "OpenThoughts-Agent: Data Recipes for Agentic Models"
authors: "Negin Raoof, Richard Zhuang, Marianna Nezhurina, Etash Guha, et al."
venue: "arXiv preprint"
year: "2026"
status: "digested"
category: "Agent Training"
tags:
  - agent-training
  - sft
  - rl
  - data-curation
  - swe-bench
  - terminal-bench
source_url: "https://arxiv.org/abs/2606.24855"
source_urls:
  - "https://arxiv.org/abs/2606.24855"
  - "https://www.openthoughts.ai/"
---

# OpenThoughts-Agent：agent 后训练的主菜是数据配方，不是 RL

- **Paper**: [OpenThoughts-Agent: Data Recipes for Agentic Models](https://arxiv.org/abs/2606.24855)
- **Version**: arXiv v1, 2026-06-23
- **Project**: [openthoughts.ai](https://www.openthoughts.ai/)（数据、pipeline、实验记录、模型全部公开）
- **类型**: agentic post-training / SFT data curation / RL data ablation
- **关键词**: six-stage SFT pipeline, task source ablation, teacher model selection, minimum-turn filter, synthetic task augmentation, pymethods2test, reward collapse

## 读法：给人和 agent 的路标

不要按"又一个 SWE-Bench 模型"读。这篇的真正价值是**方法论**：把 agentic SFT 数据的生产过程拆成六个独立阶段，每个阶段做控制实验（全文 100+ ablations），再把 SFT 和 RL 放进同一条后训练链路里比较。读完应该带走的不是某个分数，而是一张"哪些旋钮值得拧、哪些拧了没用"的地图。

给 agent 之后检索，关键词是：`OpenThoughts-Agent`、`six-stage SFT pipeline`、`95 task generation strategies`、`task source ablation 30pp`、`teacher model GLM-4.7-AWQ`、`minimum-turn filter`、`synthetic task augmentation`、`pymethods2test`、`reward collapse`。

## 一句话判断

OpenThoughts-Agent 的核心结论是：**agent 后训练的上限主要由任务来源、轨迹过滤和规模化方式决定**——任务源选择单项就能在 SWE-Bench Verified-100 上拉开约 30pp，而多种看起来合理的干预（任务改写增强）全部无效。它用这套配方产出 100K 公开轨迹，把 Qwen3-32B 训到 7 个 agent benchmark 平均 **44.8%**，超过用 264K 数据的 Nemotron-Terminal-32B（**40.9%**）。

## 图表优先读法

| 先看 | 图/表 | 读完应该抓住什么 |
|---|---|---|
| 1 | Figure 2：SFT pipeline | 六个阶段各自是一个可消融的旋钮 |
| 2 | Table 1 | 100K 精配方 > 264K 粗规模 |
| 3 | Scaling 图组 | upsampling 会 plateau，合成任务增强才能继续涨 |
| 4 | RL reward 曲线两张 | 数据源决定策略性格：探索型会 collapse，压缩型平滑上升 |
| 5 | Table 11 | RL 要接在"中等强度 SFT"后面，裸 base 上 RL 几乎无效 |

## 先看我整理的配方地图

![OpenThoughts-Agent data recipe map](assets/paper-reading/openthoughts-agent/data-recipe-map.svg)

这张自制图把论文从"训了个模型"拉回"配方对象化"：任务源、混合、增强、过滤、teacher、轨迹过滤是六个 SFT 旋钮，RL 数据源是第七个旋钮且会改变行为风格。后面每一节对应图里一个节点。

## 六阶段 SFT pipeline：每个阶段的实验结论

![OpenThoughts-Agent SFT pipeline](assets/paper-reading/openthoughts-agent/sft-pipeline.png)

*原文 Figure 2：六个阶段串成一条生产线,每一段都做了控制实验。*

| 阶段 | 问题 | 论文发现 |
|---|---|---|
| 1. Task sourcing | 任务从哪来 | 测了 **95 种**任务生成策略，影响最大：可拉开约 **30pp**（SWE-Bench Verified-100） |
| 2. Source mixing | 多来源怎么混 | **Top-4 / Top-8 混合最优**，胜过单一最强来源；Top-16 反而回落 |
| 3. Task augmentation | 要不要改写任务描述 | **全部无效**——澄清、加难度等 LLM 干预都不如保持原样 |
| 4. Task filtering | 要不要筛任务 | LLM 质量过滤器是最有效的筛法，平均 **+3pp** |
| 5. Teacher selection | 谁生成轨迹 | 最强模型 ≠ 最佳 teacher：GPT-5.3-Codex 自己做题最强，当 teacher 却输给 GLM-4.7-AWQ |
| 6. Rollout filtering | 保留哪些轨迹 | **过滤掉少于 5 轮的短轨迹**收益最大，且在 compute-controlled 对照下依然成立 |

最终 100K 数据集（v2）用的是 Top-4 任务源：swe-smith、StackExchange SuperUser、StackExchange Tezos、issue-tasks——其中 Tezos 只有 997 个原始任务，靠合成改写扩到 21K 个表面形式。这个细节直接呼应了下面的 scaling 结论。

## 32B 主结果：100K 精配方赢 264K 粗规模

| Model | Train size | Avg (7 benchmarks) | SWE-Bench Verified | Terminal-Bench 2.0 | BFCL-Parity |
|---|---:|---:|---:|---:|---:|
| OpenThinkerAgent-32B | 100K | **44.8** | **54.0** | **26.2** | **85.9** |
| Nemotron-Terminal-32B | 264K | 40.9 | 41.9 | 25.1 | 69.1 |
| SWE-Lego-Qwen3-32B | 18K | 34.7 | 51.0 | 16.1 | 81.0 |
| Qwen3-32B base | — | 22.8 | 29.1 | 7.5 | 68.3 |

两个读表要点：**跨 benchmark 同时涨**（很多 agent 数据集只顶得动一个榜），以及 **2.6 倍的数据量劣势被配方质量翻盘**。评估还包括 pipeline 定稿后才引入的 OOD 基准（Aider Polyglot、GAIA-127、MedAgentBench、FinanceAgent-Terminal），降低了"配方过拟合评估集"的嫌疑。

## Scaling：upsampling 会撞墙，多样性才是瓶颈

![OpenThoughts-Agent scaling methods](assets/paper-reading/openthoughts-agent/scaling-methods.png)

*原文 scaling 对比图：同一个 10K 基座往上扩，只有合成任务增强能越过 upsampling 的平台期。*

从 10K 往 100K 扩，作者比了四条路：同任务多 rollout（upsampling）、从原始来源挖更多任务（受来源规模限制）、合成任务改写、扩大来源数。结论清晰——**upsampling 从 31.6K 到 100K 只有 +3pp 并出现平台期**，而合成改写在同一基座上继续上涨；扩到 Top-8/16 来源没有可靠收益。32B 最终轨迹：31.6K 时 SWE-Bench V-100 48.0% / TB2.0 21.2%，100K 时 **55.7% / 26.2%**。

这是数据飞轮的经典陷阱：重复采样高分来源会把模型带进窄分布。**规模化要扩的是语义多样性，不是样本计数。**

![OpenThoughts-Agent 8B scaling](assets/paper-reading/openthoughts-agent/ot-agent-8b-scaling.png)

*原文 8B 尺度对照：同样的配方在 8B 上复现同样的趋势（100K 时 SWE-Bench V-100 39.7%），且在每个匹配数据量上都超过 Nemotron-Corpus 和 SERA。*

## 三个反直觉细节

**1. 最强模型不是最佳 teacher。** GPT-5.3-Codex 解题能力最强，但生成的轨迹训出来的学生不如 GLM-4.7-AWQ 的（Terminal-Bench 2.0 差约 5pp）。teacher 的职责不是"把题做对"，而是产出**适合学生学习**的轨迹——格式、工具风格、思考长度、错误恢复方式都影响可蒸馏性。

**2. 长轨迹不是噪声，是行为信号。** 在 token 预算对齐的严格对照下，保留 ≥5 轮的轨迹仍比随机子集强（SWE-Bench V-100 +5.4pp）。短轨迹往往只是浅层工具调用；搜索、试错、恢复、验证这些真正的 agent 行为都长在长轨迹里。

**3. RL 数据源会改变策略性格。** 8B 上系统比较了 8 个 RL 数据源，源间差距 7.6pp，远大于 2.0pp 的复跑方差。最强的 `pymethods2test` 把策略推向强探索：post-RL 思考 token 翻倍、工具调用 +31%、在 30 对同题轨迹上 LLM judge 以 **25/30（83.3%）** 偏好 post-RL 版本。

## RL 的两种命运：一张 collapse，一张平滑

![OpenThoughts-Agent RL reward collapse](assets/paper-reading/openthoughts-agent/rl-hero-reward-collapse.png)

*原文 hero run 曲线：`pymethods2test` 源上 reward 先升到约 0.51，随后崩落到约 0.13——探索被推过了头。*

![OpenThoughts-Agent baseline RL monotone reward](assets/paper-reading/openthoughts-agent/rl-baseline-reward-monotone.png)

*原文 baseline 曲线：`llm-verifier-freelancer` 源上 reward 单调平滑上升——更像行为压缩而非探索。*

两张曲线必须对照看：探索型数据源带来真实的泛化收益（held-out SWE-Bench 上 18 个 fail→pass 翻转，judge 分析确认不是 reward gaming），但训练动态不稳定，可能 collapse；压缩型数据源稳定却保守。**只看最终 benchmark 分数会同时漏掉这两种风险。**

组合上，Table 11 的结论很实用：RL 要接在**中等强度 SFT** 之后——ColdSFT+RL 达到 21.7 平均分，而在裸 Qwen3-8B 上直接 RL 只有 3.6，几乎无效。SFT 的角色是给 RL 准备可探索的起点：太弱没有 coverage，太强则行为分布已经锁死。

## 我怎么判断

### 可信之处

- **控制变量的密度罕见**：100+ ablations、compute-controlled 对照、复跑方差都报了，不是单次 hero run。
- **OOD 基准是定稿后加的**：配方不是对着全部评估集调出来的。
- **有行为分析**：RL 那章不只报分数，还报轨迹长度、工具调用、judge 对比和失败翻转。
- **全量公开**：数据、pipeline、实验记录、模型都放出，可复现性有实际保障。

### 需要警惕

- **base model 单一**：全部从 Qwen3 family 出发，配方对其他底座的迁移性未做隔离。
- **RL 只在 8B 系统研究**：作者明说 32B 是否复用同一 RL recipe 是开放问题。
- **100K 是上限**：多百万轨迹量级下这些趋势是否外推，未测。
- **域偏软件工程与终端**：配方结论对 browser/GUI/research agent 是否成立，论文没有回答。

## 对我的价值

沉淀成一张 agent training checklist：

1. **先做 task-source ablation**，它的杠杆（30pp）远大于任何下游优化。
2. **teacher 按学生的学习效果选**，不看 teacher 自己的榜单名次。
3. **轨迹过滤看结构不看结果**：≥5 轮过滤比 pass/fail 过滤更有信息量。
4. **扩数据优先扩语义多样性**，upsampling 的平台期来得很快。
5. **RL 监控行为指标 + reward 曲线**，只盯最终分数会把 collapse 当成"训到一半的正常波动"。

## 一句话收束

这篇把"agent 后训练靠感觉调数据"变成了一组可讨论、可复用、可失败的公开实验——它教的不是某个配方，而是**配方应该怎么被实验出来**。
