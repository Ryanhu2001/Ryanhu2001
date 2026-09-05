---
title: "Rotary Position Embeddings"
summary: "How rotating query and key vectors brings relative position into attention, and why that alone does not guarantee long-context performance."
type: concept
date: 2026-09-04
url: "/wiki/rotary-position-embeddings/"
---

Rotary Position Embeddings, or RoPE, encode position by rotating query and key vectors rather than adding a position vector to the token representation.

## Rotate pairs, preserve length

Coordinates are grouped into pairs. Each pair forms a two-dimensional plane, with a rotation angle determined by position and a pair-specific frequency.

Rotation changes direction without changing length. Position therefore affects how queries and keys align while preserving their norms.

## Relative position in the dot product

Let `q` and `k` be unrotated column vectors. If `R(p)` applies the paired rotations at position `p`, then:

```text
q_m = R(m) q
k_n = R(n) k

q_mᵀ k_n = qᵀ R(m)ᵀ R(n) k
           = qᵀ R(n - m) k
```

The positional term depends on the relative offset, `n - m`. This identity is central to [RoFormer](https://arxiv.org/abs/2104.09864).

Holding the unrotated vectors fixed, positions 10 and 7 give the same result as 110 and 107. This illustrates the algebra, not a claim that contextual representations remain unchanged when a real sequence moves.

## A mechanism, not a guarantee

Computing a rotation at an unseen position is possible. Using that position reliably is a separate question about a trained model.

RoPE supplies a positional mechanism; long-context quality still needs evaluation.
