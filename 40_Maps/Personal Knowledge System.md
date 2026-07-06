---
title: Personal Knowledge System
public: true
description: The operating map for this vault.
---

# Personal Knowledge System

This vault is organized as a working pipeline rather than a perfect taxonomy.

## Folders

- `00_Inbox/`: raw captures and temporary material
- `10_Notes/`: digested notes with judgment
- `20_Projects/`: active research, code, and writing projects
- `30_Blog/`: drafts and published essays
- `40_Maps/`: topic maps and navigation pages
- `50_Templates/`: reusable note templates
- `90_Archive/`: old material kept for reference

## Note Standard

Each durable note should answer:

- What is the idea?
- Where did it come from?
- What do I think about it?
- Where can it be reused?

## Weekly Maintenance

1. Empty or prune `00_Inbox/`.
2. Promote 3 to 5 items into `10_Notes/`.
3. Add links to existing maps.
4. Move one note toward a blog post, project memo, or decision.

## Publishing Rule

Only notes with this frontmatter are published:

```yaml
public: true
```

Private notes stay local even if the repo is public, as long as they do not include `public: true` and the build script remains the publishing path.

