---
title: "Dockerless: Environment-Free Program Verifier for Coding Agents"
public: true
description: "用 agentic verifier 替代昂贵的 per-repo Docker/test execution，为 SWE agent 的 SFT 筛选和 RL reward 提供环境无关信号。"
type: paper-reading
date: 2026-07-06
paper_title: "Dockerless: Environment-Free Program Verifier for Coding Agents"
venue: "arXiv"
year: "2026"
status: "reading"
source_url: "https://arxiv.org/abs/2606.28436"
---

# Dockerless: Environment-Free Program Verifier for Coding Agents

## 一句话判断

这篇论文的真正价值不是“不要 Docker”这个口号，而是把 SWE agent 训练里最贵的 test-execution verifier，替换成一个会主动读仓库、收集证据、再判断 patch 正确性的 agentic verifier；结论值得跟进，但要注意它仍然依赖 execution-labeled 数据来训练 verifier，且在 Rust/C 这类编译信号很重要的语言上还没有完全补上环境缺口。

## 核心内容

- 问题：SWE agent 的 SFT/RL 训练需要判断 rollout/patch 是否真的修好了 issue；传统做法依赖 per-repository Docker、依赖安装、测试选择和 test runner，维护成本高，也很难覆盖私有、遗留、不可复现环境的代码库。
- 贡献：提出 Dockerless，一个 environment-free agentic patch verifier，不执行候选 patch，而是通过仓库探索收集证据后给出 correctness score。
- 方法：输入 issue、reference patch、candidate patch；先生成 2-4 个验证问题，再并行派 sub-agent 用只读 shell 工具探索仓库，最后把问题、证据和 patch 聚合成二分类 verdict，并用 verdict logits 得到连续 reward。
- 证据：Dockerless 在 verifier AUC 上超过所有比较对象；作为 SFT filter 和 RL reward 后，Qwen3.5-9B 的 env-free post-training 能接近 test-execution RL 的结果。

## 论文定位

- 题目：Dockerless: Environment-Free Program Verifier for Coding Agents
- 类型：SWE agent 训练 / verifier / system + method paper
- 机构：Shanghai Jiao Tong University, Douyin Group
- 来源：[Hugging Face Papers](https://huggingface.co/papers/2606.28436), [arXiv:2606.28436](https://arxiv.org/abs/2606.28436)
- 论文一句话 thesis：如果 verifier 能像 agent 一样主动读仓库、围绕 reference patch 生成可验证问题并收集证据，那么 SWE agent post-training 可以少依赖 per-repository Docker/test execution。

## 方法机制

Dockerless 的核心流程分两层：先做 patch verifier，再把 verifier 接入 SFT/RL。

1. 输入是什么
   输入是一个 SWE issue `x`，一个 reference patch `y_ref`，以及一个 candidate patch `y`。目标是输出 `r_phi(x, y) in [0, 1]`，表示候选 patch 是否解决 issue。

2. verifier 怎么判断
   Dockerless 不直接做 patch 文本相似度，也不跑测试。它先根据 issue 和 reference patch 生成若干 verification questions。这些问题大致覆盖：应该改哪里、行为应该是什么、有哪些测试或断言能证明正确性、还有哪些 edge cases。

3. sub-agent 怎么收集证据
   每个问题交给一个并行 sub-agent。sub-agent 只用 read-only shell 工具，例如 `find`、`grep`、`rg`，在仓库里找文件、调用点、测试、配置或文档，最后返回 evidence-backed answer。

4. 最后怎么打分
   verdict model 条件化在 issue、reference patch、candidate patch 和所有 `(Q_k, A_k)` 证据上，输出 0/1 verdict token。论文用两个 token 的 logits 做 softmax，得到连续分数，作为 SFT 过滤分数或 RL reward。

5. 怎么训练 verifier
   训练数据来自 execution-labeled patches。teacher model 先生成 question-answer-judge trajectory；如果最终 verdict 和真实 test outcome 一致，就保留这条 trajectory。论文报告训练语料覆盖 3.7K unique issues，并对负正样本比例做 4:1 cap。

6. 怎么接入 post-training
   SFT 阶段：从 16K env-free rollouts 里，用 Dockerless 选 top 4K 训练。
   RL 阶段：从 SFT model 出发，采样 rollout group，用 Dockerless 对每个 final patch 作为 reward，跑 GRPO。

## 关键图解

### Figure 1：verifier 设计空间

Figure 1 的作用是把三类 verifier 摆在一起：Docker-based tests 准但贵；普通 LLM scorer 便宜但只看表层；Dockerless 试图占中间位置，不跑 per-repo Docker，但仍然通过仓库探索获得 grounding。
这张图是论文动机图，真正要看的不是图形本身，而是它定义了 Dockerless 的 claim：environment-free 不等于 no repo access，而是 no per-repository execution environment。

### Figure 2：Dockerless 架构

Figure 2 是方法图。它展示了两阶段结构：question generation + parallel evidence probing，然后 judgment。
这张图最重要，因为它说明 Dockerless 不是一个单 prompt judge，而是一个小型 agentic verification workflow。论文的实际新意主要在这里：把 verifier 本身做成“会读仓库的 agent”。

### Figure 3 / Figure 4：训练与 post-training pipeline

Figure 3 解释 verifier 如何用 rejection sampling 学到 question-answer-judge trajectory。Figure 4 则展示 Dockerless 如何被接到 SFT filtering 和 RL reward。
这两张图共同支撑论文第二个 claim：Dockerless 不只是 standalone verifier，还能替代 execution signal 参与训练闭环。

### Table 1 / Table 2 / Table 3：证据主干

- Table 1：Dockerless-RL-9B 在 SWE-bench Verified / Multilingual / Pro 上是 62.0 / 50.0 / 35.2，接近 Test-Execution RL 的 62.4 / 51.3 / 35.7。
- Table 2：Dockerless verifier AUC 是 81.0 / 72.1，高于 DeepSWE Verifier 的 66.7 / 62.9，也高于 GPT-5.4 judge 的 75.9 / 59.5。
- Table 3：用 Dockerless 从 16K env-free rollouts 里筛 top 4K，优于 Random 4K 和 All 16K，说明它确实提供了选择信号，而不是单纯靠更多数据。

## 实验与证据

### verifier 本身

论文构造了一个 balanced trajectory-level verifier benchmark：500 个样本来自 SWE-bench Verified，276 个样本来自 Multi-SWE-bench Flash，正负样本在 split 内平衡。指标用 AUC，因为 verifier 需要做排序/打分，用于 SFT 选择和 RL reward。

结果上，Dockerless 在 Verified split 上达到 81.0 AUC，在 Multi-SWE 上达到 72.1。相对最强 open-source verifier DeepSWE Verifier，分别高 14.3 和 9.2 AUC points。这个结果是整篇 paper 最硬的证据。

### SFT filtering

在同一个 Qwen3.5-9B backbone 和 SFT recipe 下比较数据来源：

| 数据 | Verified | Multilingual | Pro |
|---|---:|---:|---:|
| None / base | 59.6 | 41.3 | 32.3 |
| All 16K env-free | 58.8 | 41.3 | 31.9 |
| Random 4K | 58.2 | 44.3 | 32.0 |
| Env-based 4K | 60.0 | 48.3 | 33.9 |
| Dockerless 4K | 60.6 | 47.7 | 35.3 |

这个表说明 raw env-free rollout 不能直接拿来 SFT；关键是要筛。Dockerless 4K 接近 Env-based 4K，支持“env-free rollout + 强 verifier”这条路线。

### RL reward

Dockerless-RL-9B 使用 env-free rollouts + Dockerless reward，达到 62.0 / 50.0 / 35.2；Test-Execution RL 是 62.4 / 51.3 / 35.7。差距很小，但 Dockerless 不需要 per-repo Docker reward。

延迟上，Figure 6/10 说明 rollout 本身耗时占大头，Dockerless reward 虽然比 DeepSWE Verifier 或 Test Execution 多一些 verifier 计算，但在论文设置里只占总 per-rollout 时间的 7.2%，没有成为主要瓶颈。

## 我怎么判断

### 可信之处

- 它不是只报最终 SWE-bench 分数，而是分别评估 verifier AUC、SFT filter、RL reward 三个环节，证据链比较完整。
- Table 3 是一个重要控制实验：All 16K 和 Random 4K 都不如 Dockerless 4K，说明 Dockerless 的价值确实在“筛选质量”，不是训练数据量。
- Figure 7 的 case study 很有说服力：当 candidate patch 和 reference patch 表面形式不同，但行为等价时，普通相似度/浅层 verifier 容易低估；Dockerless 通过仓库证据给出高分。

### 薄弱之处

- verifier 的训练仍然依赖 execution-labeled patches。也就是说 Dockerless 降低的是 post-training 时 per-repo execution 的使用，不是完全摆脱 execution supervision。
- 论文主结果的 agent evaluation 仍按 env-based evaluation protocol 汇报，真正 env-free evaluation 放在 appendix。虽然 appendix 结果方向一致，但主叙事容易让人误解为全流程都在严格 env-free 设置里评测。
- 对 compilation-heavy languages 的 gap 没完全解决。Appendix E 明确指出 Rust 和 C 里 env-based SFT 有 7-13 点优势，原因可能是 compiler diagnostics 只有环境里才有。
- 成本没有完全消失：Dockerless 需要多个 sub-agent 探索仓库，还需要 vLLM serving verifier 和并行工具调用。它是把 Docker/test cost 换成 agentic verification cost。

### 隐含假设

- reference patch 可用且质量足够高。Dockerless 的 question generation 依赖 reference patch 来定义应验证什么。
- 仓库静态信息足以判断大部分 patch 正确性。对需要真实运行、外部服务、复杂构建或动态行为的 issue，这个假设会变弱。
- 训练 benchmark 的 execution labels 足够可靠；如果 held-out tests 本身覆盖不足，verifier 学到的“正确性”边界也会受限。

## 对你的价值

### 值得借鉴的点

- 对我们之前讨论的 agent environment synthesis / world model / verifier 路线来说，这篇提供了一个很重要的中间路线：不模拟整个环境，也不搭 Docker，而是训练一个“会查证据的 verifier”。
- 对 RL for coding agents 来说，它给了一个可操作 pipeline：env-free rollout collection + verifier top-K filtering + verifier reward GRPO。
- 对个人复现而言，最值得先复现的是 verifier benchmark，而不是端到端 RL：给定 issue/reference/candidate，让一个 agentic verifier 生成 questions、查仓库、打分，先看 AUC/排序能力。

### 不必照搬的点

- 不一定要一开始就训练 Qwen3.5-9B verifier。可以先用强模型做 zero-shot / few-shot agentic verifier，验证 question generation + repo evidence 这条链是否在你的任务上有效。
- 不一定要上完整 RL。先做 SFT filtering 或 rejection sampling 数据清洗，收益更容易观察，也更便宜。

### 如果要复现，先做什么

1. 选一个小的 SWE patch verifier 数据集，包含 issue、reference patch、candidate patch、execution label。
2. 实现 Dockerless-style prompt：生成 2-4 个 verification questions。
3. 给每个问题开一个只读 repo explorer，用 `rg/find/sed` 等工具找证据。
4. 让 judge 聚合 evidence 给 0/1 和 score。
5. 先对比文本相似度、普通 LLM judge、agentic judge 的 AUC。
6. 如果 verifier 有明显收益，再接入 SFT trajectory filtering；最后才考虑 RL reward。

## 最大疑点

这篇 paper 最关键的开放问题是：Dockerless 能否处理那些必须靠运行才暴露的问题，比如编译错误、依赖冲突、异步/并发行为、外部服务交互、数值/性能 bug？论文自己在 Rust/C gap 上已经露出这个边界。我的判断是：Dockerless 很适合替代一部分 expensive test execution，但短期内更像“高质量 verifier/filter”，而不是完整 execution oracle。

## 建议动作

值得继续精读，尤其是 Appendix G 的 prompts 和 Appendix C/D 的数据构造。对你的 wiki/paper-reading 来说，这篇应该归到“agent verifier / environment-free RL / SWE agent training”这一类。后续可以和 SWE-World、CLI-Universe、Agent-World 放到同一个主题链里比较：它们都在绕开昂贵环境，但绕开的方式完全不同。
