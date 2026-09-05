---
title: "Linear Attention"
public: true
summary: "A short note on recurrent memory: replacing a growing token history with a fixed-size state."
type: concept
status: growing
topics:
  - sequence-model
  - attention
  - recurrent-memory
date: 2026-08-28
url: "/wiki/Linear Attention.html"
---

Recurrent linear attention compresses a token history into a fixed-size state that can be updated one step at a time.

## Why it matters

Standard autoregressive attention retains the keys and values of earlier tokens. As the sequence grows, so does the amount of history that must be stored and read.

The useful distinction is not just which tokens a model attends to, but **how it stores the past**:

- Standard attention keeps a growing collection of keys and values.
- Recurrent linear attention writes history into a fixed-size state, \(S_t\).

## An intuition

Instead of keeping a separate entry for every past token, the recurrent form updates one memory state. In RetNet, the previous state decays, the current token adds a key-value update, and a query reads from the resulting state.

## A minimal RetNet model

[RetNet](https://arxiv.org/abs/2307.08621) replaces standard self-attention with retention, which supports parallel, recurrent, and chunkwise recurrent computation.

For a single head, omitting positional phase terms, normalization, and gating, the recurrent core can be written as follows. Here, \(q_t\), \(k_t\), and \(v_t\) are row vectors.

\[
\begin{aligned}
S_t &= \gamma S_{t-1} + k_t^{\top} v_t, \\
y_t &= q_t S_t.
\end{aligned}
\]

The same update in pseudocode:

```python
def retention_step(q_t, k_t, v_t, state, gamma):
    state = gamma * state + outer(k_t, v_t)
    y_t = q_t @ state
    return y_t, state
```

Here, \(\gamma\) controls decay, \(k_t^{\top} v_t\) writes the current information, and \(q_t S_t\) reads from the compressed history. This is the recurrent core, not a complete RetNet block.

## How I think about it

Linear attention is useful to think of as a **memory architecture**, not merely a lower-complexity attention mechanism.

The recurrent form trades a growing history for a fixed-size representation. That makes compression the central question: information from different tokens can interfere when written into the same state.

## Hybrid attention in practice

Linear and token-to-token attention need not be mutually exclusive. Both [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) and [Kimi K3](https://huggingface.co/moonshotai/Kimi-K3) interleave three linear-attention layers with one token-to-token attention layer.

{{< figure src="assets/wiki/linear-attention/hybrid-attention.svg" alt="Qwen3.8-Flash-Next repeats three Gated DeltaNet layers and one QSA layer twelve times. Kimi K3 repeats three KDA layers and one Gated MLA layer twenty-three times, then adds a final Gated MLA layer." caption="Hybrid attention schedules. Blue blocks use recurrent linear attention; teal blocks use sparse or global token-to-token attention. Arrows run from input to output, bottom to top." >}}

Qwen pairs Gated DeltaNet with **Qwen Sparse Attention (QSA)**. Kimi pairs **Kimi Delta Attention (KDA)** with Gated Multi-head Latent Attention. Its extra final Gated MLA layer brings the backbone to 93 layers, compared with Qwen's 48.

The diagram groups attention with its following feed-forward network. In Kimi, **FFN*** denotes Stable LatentMoE except for the first, dense FFN. The repeated four-layer attention group is not an Attention Residuals block boundary.

They also differ across depth: Qwen uses four-stream Gated Residual reads and writes, while Kimi's Block Attention Residuals retrieve from the embedding and block history. Those internal residual paths are summarized here, not expanded in the figure. Vision, sublayer normalization, Qwen's Layer-2 n-gram embedding, and the auxiliary MTP branch are omitted from this backbone view. See the [Qwen architecture report](https://arxiv.org/html/2608.30320v1) and [Kimi architecture report](https://arxiv.org/html/2607.24653v1#S2) for the complete structures.

## Open questions

- How should we measure interference when the state has insufficient capacity?
- How do RetNet's parallel and recurrent forms correspond exactly?
- What different problems are addressed by GLA's gates, DeltaNet's delta rule, and KDA's state update?

## Related directions

- RetNet
- GLA
- DeltaNet
- KDA
