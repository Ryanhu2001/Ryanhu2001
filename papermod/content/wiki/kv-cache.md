---
title: "KV Cache: What Inference Remembers"
summary: "Why an autoregressive model keeps past keys and values, what caching saves, and why longer conversations still consume more memory."
type: concept
date: 2026-09-04
url: "/wiki/kv-cache/"
---

A key-value cache stores intermediate attention results so that an autoregressive model does not have to rebuild its entire history for every new token.

## What is stored

Each attention layer maintains its own keys and values. In a causal model, adding a future token does not change the representations of earlier tokens, so their keys and values can be reused.

The current query is different: it asks what information is useful **now**. A normal decoding cache therefore retains past keys and values, not every past query.

## A decoding step

At each step, the model projects the new token into a query, key, and value. The key and value join the cache; the query attends over the accumulated entries.

Schematically, for one attention head:

```python
K = append(K, k_t)
V = append(V, v_t)
weights = softmax(q_t @ K.T / sqrt(head_dim))
output = weights @ V
```

Caching avoids repeated computation. It does not eliminate reading the retained history. See the [Transformers caching guide](https://huggingface.co/docs/transformers/main/en/cache_explanation) for the implementation details.

## The memory trade-off

For equal-sized key and value tensors, the payload size follows directly from their dimensions:

```text
bytes = 2 × layers × batch × tokens × kv_heads × head_dim × bytes_per_element
```

For example, 32 layers, one sequence, 8,192 tokens, 8 KV heads, 128 dimensions per head, and two-byte elements require 1 GiB for the cached tensors alone. This calculation excludes model weights, temporary buffers, and allocation overhead.

The cache is useful precisely because it keeps information around. Its memory cost is the other side of that reuse.
