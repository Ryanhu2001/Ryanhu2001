# Ryan Hu

Personal notes, paper reading, and wiki pages.

The public site is generated from Markdown notes in `wiki/` and published from `docs/`.

## Write

Add a note under `wiki/`:

```yaml
---
title: Note title
public: true
description: Short summary.
---
```

Images and attachments live in `assets/`.

## Build

```sh
node scripts/build-wiki.mjs
```

GitHub Actions rebuilds the public site after notes are pushed.
