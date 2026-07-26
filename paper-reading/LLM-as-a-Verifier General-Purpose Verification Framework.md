---
title: "LLM-as-a-Verifier: General-Purpose Verification Framework"
public: true
description: "这篇把 verification 当成 LLM 的新 scaling axis：不再让 judge 吐一个离散分数，而是读 scoring token logits 的完整分布，生成连续 verifier score，再用于 best-of-N、progress tracking 和 RL dense reward。"
type: paper-reading
date: 2026-07-26
created_at: 2026-07-26T21:34:00+08:00
paper_title: "LLM-as-a-Verifier: A General-Purpose Verification Framework"
authors: "Jacky Kwok, Shulu Li, Pranav Atreya, Yuejiang Liu, Yixing Jiang, Chelsea Finn, Marco Pavone, Ion Stoica, Azalia Mirhoseini"
venue: "arXiv preprint"
year: "2026"
status: "digested"
category: "Agent Evaluation"
tags:
  - agent-evaluation
  - verifier
  - llm-as-judge
  - test-time-scaling
  - reward-modeling
  - reinforcement-learning
  - robotics
source_url: "https://arxiv.org/abs/2607.05391"
source_urls:
  - "https://arxiv.org/abs/2607.05391"
  - "https://arxiv.org/pdf/2607.05391"
  - "https://llm-as-a-verifier.com"
  - "https://github.com/llm-as-a-verifier/llm-as-a-verifier"
---

# LLM-as-a-Verifier：verification 是新的 scaling axis，起点是别把分数分布压成一个整数

- **Paper**: [LLM-as-a-Verifier: A General-Purpose Verification Framework](https://arxiv.org/abs/2607.05391)
- **Authors**: Jacky Kwok, Shulu Li, Pranav Atreya, Yuejiang Liu, Yixing Jiang, Chelsea Finn, Marco Pavone, Ion Stoica, Azalia Mirhoseini（Stanford / UC Berkeley / NVIDIA Research）
- **Version**: arXiv v2, 2026-07-07（v1 2026-07-06）
- **Code / project**: [llm-as-a-verifier.com](https://llm-as-a-verifier.com)、[GitHub](https://github.com/llm-as-a-verifier/llm-as-a-verifier)；另附 TurboAgent，一个 Claude Code / OpenAI-compatible client 的 inference-time proxy，实时可视化 verifier 输出
- **类型**: training-free verifier / test-time scaling / reward modeling
- **关键词**: verification scaling, scoring-token logits, continuous reward, Probabilistic Pivot Tournament, Value-Order Correlation, dense RL reward

## 读法：给人和 agent 的路标

不要按"又一个 LLM-as-judge prompt trick"读。这篇的中心论点是：**verification（判断一个 solution 对不对的能力）可以像 pre-training、post-training、test-time compute 一样被 scale**。普通 judge 的病根在于把模型对分数的内部 belief 压成一个离散整数，于是复杂 trajectory 大量同分、比较全是 tie；本文改读 scoring-token logits 的完整分布并取期望，得到连续 reward，然后系统研究三个 scaling 维度（granularity、repetition、criteria decomposition），再配一个省预算的 tournament 排序算法。读完应该带走的是"连续信号 + 可调预算旋钮 + 成本可控的选择器"这一整套机制，而不是某个 benchmark 分数。

给 agent 之后检索，关键词是：`LLM-as-a-Verifier`、`verification scaling`、`scoring-token logits`、`continuous verifier score`、`Probabilistic Pivot Tournament`、`PPT`、`Value-Order Correlation`、`VOC`、`dense verifier reward`、`TurboAgent`。

## 一句话判断

这篇把 agent 评测里的"judge 给一个分数"改成"verifier 输出一个可校准、可重复、可分解、可用于排序和训练的连续信号"，training-free，在 Terminal-Bench V2（**86.5%**）、SWE-Bench Verified（**78.2%**）、RoboRewardBench（**87.4%**）、MedAgentBench（**73.3%**）四个 domain 上同时报 SOTA。

My read is，这篇值得精读，因为它和 Anthropic agent evals、AutomationBench 都指向同一件事：**agent scaling 的下一块短板是 verification**。但边界也清楚：方法依赖 scoring-token logits（很多 frontier API 不开放）；提升来自 best-of-N candidate selection，背后有成倍的推理与验证成本；医疗和机器人结果是 benchmark evidence，不是生产安全证明。

## 图表优先读法

| 先看 | 图 / 表 | 读完应该抓住什么 |
|---|---|---|
| 1 | 自制机制图 | 核心机制：从 score-token distribution 取期望得连续 reward，再转 pairwise preference，最后 PPT 选择 |
| 2 | Fig.2 framework | coding / robotics / medical trajectory 进同一个 verifier，输出 selection、progress、RL reward 三种信号 |
| 3 | Fig.4 scaling axes | granularity 73.1→77.5、repetition 74.7→77.4、criteria 单项→78.3，三个旋钮各管一件事 |
| 4 | Fig.7 judge vs verifier | 同预算下 verifier 全面领先，tie rate 恒为 0；K=1 verifier ≈ K=16 judge |
| 5 | Fig.6 PPT | best-of-N 的验证成本从 O(N^2) 降到 O(Nk)，附录 Table 9 有 budget-accuracy 曲线 |
| 6 | Fig.1 / Table 3 | headline 数字要和 Pass@1、oracle Pass@N 一起读：headroom 只兑现了一部分 |

## 先看我压缩的机制图

![Self-made verifier score pipeline](assets/paper-reading/llm-as-a-verifier/verifier-score-pipeline.svg)

*自制图解：task 和 N 条候选 trajectory 进入 pairwise verifier prompt，在 `<score_A>` / `<score_B>` 位置读 scoring-token logits；对分布取期望（跨 C 个 criteria、K 次重复）得到连续 reward，经 Bradley-Terry 转成软偏好，最后由 PPT 在 O(Nk) 预算内选出 winner。全流程不训练任何模型。*

## 1. 问题设定：generator scaling 之后，短板是 verifier

Agent 系统里模型经常一次任务生成多条 trajectory——coding agent 多跑几个 patch、机器人多条 rollout、医疗 agent 多条检索决策路径。作者在 Terminal-Bench V2 上展示 headroom：把 leaderboard 轨迹 pooling 后，oracle Pass@K 可达 **98.9%**。很多任务不是没人做得出来，而是"做出来了但系统不知道哪条是对的"。所以要区分两种 scaling：

- **Generator scaling**：让模型更可能生成一个好答案。
- **Verifier scaling**：当候选已经存在时，更可靠地找出好答案。

My analysis is that，这篇的价值全在第二点。真实系统会越来越像 sampling + harness + verifier 的组合；verifier 不够细，best-of-N 就只是浪费 token。

## 2. 机制：从离散 judge 到连续 verifier

![LLM-as-a-Verifier official framework](assets/paper-reading/llm-as-a-verifier/official-framework.png)

*原图来自论文：Figure 2 总框架。输入不限于文本——coding trajectory、robot video rollout、medical tool-use trace 都被抽象成待验证的 trajectory；核心信号来自 scoring-token logits 的完整分布；三个 scaling 旋钮（granularity / repetition / decomposition）并列；输出有三种用途：test-time candidate selection、progress tracking、RL dense reward。*

技术 move 只有一个：**不取 argmax score token，而是对分数 token 的数值映射取期望**。给定任务 `x`、trajectory `τ`、criteria 数 `C`、重复次数 `K`、分数 token 集合 `V_score = \lbrace v_1, ..., v_G \rbrace`（Eq. 3.1）：

$$
R\left(x,\tau\right)
=
\frac{1}{CK}
\sum_{c=1}^{C}
\sum_{k=1}^{K}
\sum_{g=1}^{G}
p_{\theta}\left(v_g \mid x,c,\tau\right)\phi\left(v_g\right)
$$

其中 `p_theta(v_g | x,c,tau)` 是 verifier 给 score token 的概率，`phi(v_g)` 把 token 映射为标量。Reward 线性归一化到 `[0,1]` 后，用 Bradley-Terry 转成 pairwise preference（Eq. 3.2）：

$$
P\left(\tau_i \succ \tau_j \mid x\right)
=
\frac{1}{1+\exp\left(-\left(R\left(x,\tau_i\right)-R\left(x,\tau_j\right)\right)\right)}
$$

Verifier prompt 骨架很朴素——关键是不相信最终吐出的整数，而是读 tag 位置的 logprobs：

```text
You are an expert [domain] reviewer.
Evaluation Criteria: [domain specific criteria]
Task: {task prompt}
Trajectory A: {A}    Trajectory B: {B}

Carefully analyze each trajectory, then provide your final scores:
<score_A> INTEGER_1_TO_20 </score_A>
<score_B> INTEGER_1_TO_20 </score_B>

Rating Rules: 1 = incorrect, 10 = borderline, 20 = correct.
```

实现细节：实际用 letter-based scale 代替数字，避免多位数 tokenization 干扰 logprob extraction。

## 3. 三个 verification scaling 旋钮

![Verification scaling axes](assets/paper-reading/llm-as-a-verifier/official-verification-scaling.png)

*原图来自论文：Figure 4，Terminal-Bench V2 上的 controlled analysis。三个旋钮分别解决分辨率（granularity）、方差（repetition）、复合判断偏差（criteria decomposition），应按 latency / cost budget 一起调，而不是笼统地"多问几遍模型"。*

| 旋钮 | 范围 | Pairwise accuracy | 机制解释 |
|---|---|---:|---|
| Score granularity `G` | 1 → 20 | 73.1% → **77.5%** | 更细的投影空间让内部 belief 不被四舍五入；SNR 从 **0.775** 升到 **0.799** |
| Repeated evaluation `K` | 1 → 16 | 74.7% → **77.4%** | Monte Carlo 平均，方差按 O(1/K) 收缩，但 bias 不变 |
| Criteria decomposition `C` | 1 → 3 | 单项 75.2%–76.4% → **78.3%** | specification / output / errors 各管一块，ensemble 收互补信息 |

两个要点：granularity 不给模型新信息，只是给它一个更细的表达空间，这是三个旋钮里增益最大的（+4.4pp）；repetition 收益递减，因为 hard examples 上存在 correlated bias，重复采样平均不掉系统性偏见。Coding domain 的三个 criterion 是 **Specification**（满足任务要求）、**Output**（输出格式符合预期）、**Errors**（日志无失败信号）。

## 4. 直接证据：同预算下 verifier 完胜 judge

![Continuous verifier versus discrete judge](assets/paper-reading/llm-as-a-verifier/official-judge-vs-verifier.png)

*原图来自论文：Figure 7。左：pairwise accuracy，verifier 在每个 K 下都领先；右：离散 judge 的 tie rate 从 26.7% 降到 5.5%，而 verifier 恒为 0。论文原话：single-pass verifier (K=1) already matches a heavily ensembled judge (K=16)——连续 logprob expectation 本身就是更强的信号，不是靠多问。*

| K | Judge accuracy | Verifier accuracy | Judge tie rate | Verifier tie rate |
|---:|---:|---:|---:|---:|
| 1 | 71.8% | **74.7%** | 26.7% | **0.0%** |
| 4 | 74.4% | 77.1% | 11.7% | 0.0% |
| 16 | 74.7% | **77.5%** | 5.5% | 0.0% |

`query-optimize` case study 把机制讲得最透：两条 trajectory 都产出了更快的 SQL query，但正确的那条在 canonical database 上完整跑完并 diff 验证输出，错误的那条另建了新数据库、没验证等价性。100 次重复评估里，离散 judge（G=5）**88 次打成 tie**、只有 12 次排对；连续 verifier（G=20）**77 次排对、0 次 tie**（23 次排错）。

My read is，这个 case 重要在于它就是典型的 agent 失败形态：产物看起来 plausible，但关键验证步骤缺失。连续 verifier 的优势正来自保留模型"不太放心"的那部分概率质量。

## 5. PPT：把 best-of-N 的验证成本从 O(N^2) 压到 O(Nk)

![Probabilistic Pivot Tournament](assets/paper-reading/llm-as-a-verifier/official-pivot-tournament.png)

*原图来自论文：Figure 6。PPT 是控成本的 ranking 算法，不是 verifier 分数本身：ring pass 抵消 position bias，pivot selection 把预算集中到有希望赢的候选，最后按平均胜率选 winner。*

1. **Ring pass**：随机 Hamiltonian cycle 比一圈（N 对），每个 candidate 恰好在 A、B 位置各出现一次，期望上抵消 position bias。
2. **Pivot selection**：按 ring-pass 平均偏好 `w_i / c_i` 选 top-k pivots。
3. **Pivot rounds**：非 pivot 只和 pivots 比，pivots 之间互比。
4. **Selection**：聚合 win mass `w_i` 和 comparison count `c_i`，返回 `w_i / c_i` 最高者。

总比较数 `N + k(N-k) + C(k,2)`，即 **O(Nk)**，`k << N`。附录 Table 9 的 budget-accuracy 曲线：

| Method | Pairs queried | Accuracy |
|---|---:|---:|
| Pass@1 | 0 | 52.64% |
| V1, 1N budget | 1,400 | 64.64% |
| V1, 5N budget | 7,000 | 65.85% |
| PPT k=1 | 2,570 | 65.83% |
| PPT k=5 | 6,609 | 66.27% |
| PPT k=9 | 9,630 | **67.13%** |
| Full round-robin | 13,111 | 67.42% |

My analysis is that，PPT 的贡献比 headline SOTA 更工程：k=9 用 73% 的预算拿到几乎全量 round-robin 的准确率，而同预算的朴素采样（V1, 7N = 9,800 对）只有 65.53%。真实系统里 best-of-N 能不能用，取决的就是这条曲线。

## 6. 四个 domain 的主结果：headroom 兑现了一部分

![Overall performance results](assets/paper-reading/llm-as-a-verifier/official-sota-results.png)

*原图来自论文：Figure 1 / Table 3 的 headline 数字。读法是三点一线：candidate pool 的 Pass@1（下限）、oracle Pass@N（上限）、verifier 选择结果（实际兑现），不能只看红柱子。*

主实验 protocol：`G=20`、`K=8`、三 criterion decomposition（除非另注明），PPT 做 selection。

| Benchmark | Pool Pass@1 | Oracle Pass@N | Verifier 结果 | 超过的 baseline |
|---|---:|---:|---:|---|
| Terminal-Bench V2 | 83.1% | 92.1% (N=5) | **86.5%** | GPT-5.5+NexAU-AHE 84.7%、Opus 4.7 80.2%、Gemini 3.1 Pro 80.2% |
| SWE-Bench Verified | 76.1% | 84.4% (N=3) | **78.2%** | Opus 4.5 76.8%、Gemini 3 Flash 75.8%、MiniMax M2.5 75.8% |
| MedAgentBench | 70.2% | 75.0% (N=5) | **73.3%** | Opus 4.8 70.2%、Gemini 3.5 Flash 66.3%、GPT-5.5 65.1% |
| RoboRewardBench | 70.8%（discrete judge） | — | **87.4%** preference accuracy | RoboReward-8B 81.4%、Robometer-4B 78.8%、TOPReward 74.7% |

设置细节：Terminal-Bench 用 Capy scaffold，GPT-5.5 采 `N=5`，Gemini 2.5 Flash 做 verifier；SWE-Bench 用 mini-swe-agent，heterogeneous pool（Opus 4.5 / Gemini 3 Flash / MiniMax M2.5 各一条）；MedAgentBench 是模拟 EHR 环境，Opus 4.8 采 `N=5`；RoboRewardBench 用 Qwen 3.6 35B VLM verifier 对多帧 video rollout 打分，比的是 preference accuracy 而不是任务成功率。

My read is，真正的问题是 headroom 兑现率：Terminal-Bench 从 83.1 到 86.5，只吃掉 9.0pp headroom 中的 3.4pp；SWE-Bench 从 76.1 到 78.2，也只取回 2.1/8.3。Verifier 有用，但离"把 best-of-N headroom 全部兑现"还远，而且每一分都要付出 N 倍生成 + O(Nk) 验证的成本。

## 7. Progress tracking：verifier score 当任务进度条

![Progress tracking with verifier scores](assets/paper-reading/llm-as-a-verifier/official-progress-signal.png)

*原图来自论文：Figure 8，Terminal-Bench 的 pytorch-model-cli 任务。成功轨迹（读 model.py → 装 g++ → 装 CPU-only torch → 改 hidden_dim → DONE）score 随步骤上升；失败轨迹装了不必要的 torchvision，耗尽 disk space 后 compilation error，score 长期低位。verifier 不只能事后选答案，还能在任务中发现 agent 进入坏状态。*

作者定义 **Value-Order Correlation（VOC）**：trajectory prefix 的 verifier score 与真实时间步顺序的 Spearman 相关。Terminal-Bench V2 上 500 对轨迹：

| Trajectory outcome | Spearman VOC |
|---|---:|
| Successful | **0.848 ± 0.012** |
| Failed | 0.769 ± 0.016 |

机器人上更强（500 条 RoboRewardBench 轨迹）：

| Method | Spearman VOC |
|---|---:|
| LLM-as-a-Verifier（Qwen 3.6 35B, K=5, G=20） | **0.966** |
| RoboReward-8B | 0.877 |
| Robometer-4B | 0.780 |
| TOPReward | 0.565 |

TOPReward 的问题是几乎立刻饱和在 P(True)=1.0，而连续 verifier 保持了平滑、按时间对齐的信号。配套的 **TurboAgent** 是一个 Claude Code / OpenAI-compatible 客户端的 inference-time proxy，不改 harness 就能实时可视化 verifier 输出。

My analysis is that，这是全文对 agent 产品最有启发的部分：verifier 从"任务结束后打分"变成"任务过程中预警"——长任务 agent 可以在 score plateau 或下跌时触发暂停、回滚、换策略，而不是等坏状态写进磁盘才知道失败。

## 8. Dense reward for RL：proof of concept

verifier score 还能当 RL 的 dense reward，缓解 sparse reward 下的 credit assignment：

- **LIBERO + DSRL-SAC**：fine-tune `π0` policy 做 ketchup task，每次 rollout 后 VLM verifier 从 `N_f=10` 抽帧生成 progress `ρ_t = R(x, τ_{1:t})`，shaping 为 `r_t = r_t^env + λρ_t`（λ=1、K=3、5 seeds、1.5M environment steps）。约 **1.8x** sample efficiency，final success rate **0.76 vs 0.69**。
- **MATH + GRPO（Qwen3-8B）**：group 内全错时 correctness reward 无梯度；verifier 对 reasoning trace 加偏好项 `r_i = r_correct + r_format + β·r_reasoning`（β=0.1、group size 16、64 groups/step、LR 2e-5）。约 **1.1x** sample efficiency，即达到 matched accuracy 少约 10% optimizer steps。

My read is，这部分是 proof of concept：机器人只有单个 LIBERO 任务，MATH 提升也不大，且实验限于 single-turn。但它说明连续 score 的形态天然适合 dense feedback，比 0/1 outcome reward 更能给中间步骤记功。

## 9. 附录里别漏的两点

### 9.1 PRM / ORM：verifier 可以插在两个位置

附录把同一个 verifier 分别当 process reward model（每步 action 选择）和 outcome reward model（最终候选选择）用：

| 用法 | Benchmark | 设置 | 结果 |
|---|---|---|---|
| PRM | TauBench | 每步采样 actions k=1→9 | Pass@1 **48.7% → 55.7%** |
| PRM | Terminal-Bench | 每步采样 actions k=1→9 | Pass@1 **49.8% → 54.3%** |
| ORM | SWE-Bench Lite | best-of-N + verifier | **23.5% → 33.0%** |
| ORM | AIME | best-of-N + verifier | **71.5% → 90.0%** |
| ORM | HMMT | best-of-N + verifier | **52.0% → 73.3%** |

启发比数字重要：verifier 不必只做最后裁判，也可以在每步 action branching 时做轻量筛选——对应到 pipeline 设计，就是"每段生成后即时校验"而不是"整篇写完再总评"。

### 9.2 没有 logprobs 的 closed model 怎么办

方法依赖 scoring-token logits，很多 closed frontier API 不开放。附录给了两阶段 workaround：closed model（GPT-5.5）先输出 reasoning + 离散分，再把 task、两条 trajectory 和这份 reasoning 转给开放 logprob 的 Gemini 2.5 Flash，在其 `<score_A>` / `<score_B>` 位置读分布（Table 12）：

| K | GPT-5.5 discrete acc | Discrete tie | 两阶段 continuous acc | Continuous tie |
|---:|---:|---:|---:|---:|
| 1 | 74.9% | 10.9% | **80.1%** | 0.0% |
| 4 | 77.6% | 7.0% | 81.0% | 0.0% |
| 16 | 79.1% | 5.0% | **81.2%** | 0.0% |

My analysis is that，workaround 实用但暴露系统依赖：最强 verifier 若不开放 logprobs，你就需要一个开放 logprob 的 scoring backend 来"读分布"，部署复杂度、延迟、模型间一致性都变成工程问题。

## 我怎么判断

### 可信之处

- **机制证据链完整**：不只报 SOTA，还有 tie-rate 分析、SNR 表、三轴 controlled scaling 曲线和 query-optimize 逐 case 解剖，连续 scoring 的因果链是闭合的。
- **training-free 且跨模态**：同一框架覆盖 text / code / EHR tool-use / video rollout 四个 domain，不需要训练任何 reward model。
- **成本被当一等公民**：PPT 有完整 budget-accuracy ablation（Table 9），不是只报最贵配置的分数。
- **limitation 自己写清楚了**：logprob 依赖、scaling axes 不穷尽（criteria 仍手写）、RL 限于 single-turn，且给了 closed-model workaround 及其数据。

### 需要警惕

- **logprob access 是硬门槛**：两阶段 workaround 能救急，但引入第二个模型和额外延迟，不是同一件事。
- **成本叠乘**：N 条候选 × K 次重复 × C 个 criteria × pairwise 比较，PPT 降低但没消除；oracle headroom 高也可能是"高成本幻觉"——候选池里有答案不等于产品上值得为它付 N 倍推理费。
- **verifier 可能继承 generator 的盲区**：若两者来自相近模型家族，可能共同自信地选错；论文对 hard examples 上的 correlated bias 也只是承认而未解决。
- **benchmark SOTA ≠ 生产安全**：MedAgentBench 是模拟 EHR，机器人是 rollout preference，离真实部署的风险语境很远。
- **headroom 没吃满**：86.5 vs oracle 92.1、78.2 vs 84.4，说明连续 verifier 也远非 oracle，收益/成本比要逐场景算。

## 对我的价值

沉淀成 verifier 设计 checklist：

1. **保留分布，别压成整数**：judge 输出改为读 score-token logprobs 取期望；没有 logprob 就用两阶段（closed model 出 reasoning、open model 出分布）。
2. **监控 tie rate**：大量候选同分说明 rubric 或 scoring 太粗——这是最便宜的健康指标。
3. **拆 criteria 各自打分**：对 paper-note 类任务即 source fidelity / 关键数字 / 图像证据 / build / 可读性分项保分，ensemble 而不是一个总分。
4. **多候选要 budget 策略**：先 ring pass 粗筛、再对强候选精排，把验证预算花在"有希望赢"的候选上。
5. **verifier 信号进过程而不只进终点**：长任务里 score 连续不涨即触发暂停 / 回滚 / 换策略，对应 PRM 用法。

## 一句话收束

当 generator 已经偶尔能做对时，下一步提升来自 verifier——而让 verifier 变得可 scale 的那个动作小得惊人：**读分布、取期望，别把模型的犹豫压成一个整数**。
